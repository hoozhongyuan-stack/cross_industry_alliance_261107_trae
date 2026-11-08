"""支付下单与回调处理。"""

from django.db import transaction
from django.utils import timezone

from apps.common.api import ApiError
from apps.ledger.constants import AccountType, Direction
from apps.ledger.services import post_transaction
from apps.orders.models import Order
from apps.orders.order_services import mark_order_paid
from apps.orders.services import transit_order

from .models import PaymentOrder
from .providers import create_prepay


def create_payment(user, order_id, channel, idempotency_key):
    with transaction.atomic():
        existing = PaymentOrder.objects.filter(idempotency_key=idempotency_key).first()
        if existing is not None:
            if existing.order_id != order_id or existing.user_id != user.id:
                raise ApiError("IDEMPOTENCY_CONFLICT", "幂等键已用于其他支付请求", 409)
            return existing, {"mock": True} if existing.prepay_id else {}

        order = Order.objects.select_for_update().filter(pk=order_id, user=user).first()
        if order is None:
            raise ApiError("NOT_FOUND", "订单不存在", 404)
        if order.status != Order.Status.PENDING_PAYMENT:
            raise ApiError("ORDER_STATE_CONFLICT", "当前订单状态不允许支付", 409)
        if order.expire_at and timezone.now() > order.expire_at:
            raise ApiError("ORDER_EXPIRED", "订单已超时关闭", 409)

        payment = PaymentOrder.objects.filter(
            order=order, status__in=[PaymentOrder.Status.CREATED, PaymentOrder.Status.PAYING]
        ).first()
        if payment is None:
            if PaymentOrder.objects.filter(order=order, status=PaymentOrder.Status.PAID).exists():
                raise ApiError("ORDER_STATE_CONFLICT", "订单已支付", 409)
            payment = PaymentOrder.objects.create(
                order=order,
                user=user,
                channel=channel,
                amount=order.payable_amount,
                status=PaymentOrder.Status.CREATED,
                idempotency_key=idempotency_key,
                expire_at=order.expire_at,
            )

        prepay = create_prepay(payment)
        payment.prepay_id = prepay["prepay_id"]
        payment.status = PaymentOrder.Status.PAYING
        payment.save(update_fields=["prepay_id", "status", "updated_at"])
        return payment, prepay["pay_params"]


def process_payment_success(payment_no: str, transaction_id: str, amount: int) -> PaymentOrder:
    with transaction.atomic():
        payment = PaymentOrder.objects.select_for_update().filter(payment_no=payment_no).first()
        if payment is None:
            raise ApiError("PAYMENT_NOT_FOUND", "支付单不存在", 404)
        if amount != payment.amount:
            raise ApiError(
                "PAY_AMOUNT_MISMATCH",
                "回调金额与支付单不一致",
                409,
                {"expected_amount": payment.amount, "actual_amount": amount},
            )
        if payment.status == PaymentOrder.Status.PAID:
            if payment.transaction_id != transaction_id:
                raise ApiError("PAYMENT_TRANSACTION_CONFLICT", "交易号与已支付记录不一致", 409)
            return payment
        if payment.status in (PaymentOrder.Status.CLOSED, PaymentOrder.Status.REFUNDED):
            raise ApiError("ORDER_STATE_CONFLICT", "支付单已关闭或已退款", 409)

        order = Order.objects.filter(pk=payment.order_id).first()
        if order is None or order.status != Order.Status.PENDING_PAYMENT:
            raise ApiError("ORDER_STATE_CONFLICT", "订单状态不允许支付成功", 409)

        payment.status = PaymentOrder.Status.PAID
        payment.transaction_id = transaction_id
        payment.paid_at = timezone.now()
        payment.save(update_fields=["status", "transaction_id", "paid_at", "updated_at"])

        transit_order(order.id, "PAY_SUCCESS", operator_type="SYSTEM")
        post_transaction(
            biz_type="PAYMENT",
            biz_id=payment.id,
            event_type="PAY_SUCCESS",
            idempotency_key=f"payment:{payment.payment_no}",
            entries=[
                {
                    "account_type": AccountType.PLATFORM_CASH,
                    "account_id": 0,
                    "direction": Direction.DEBIT,
                    "amount": payment.amount,
                },
                {
                    "account_type": AccountType.MERCHANT_PENDING,
                    "account_id": order.merchant_id,
                    "direction": Direction.CREDIT,
                    "amount": payment.amount,
                },
            ],
        )
        mark_order_paid(order)
    return payment
