"""下单、取消与支付成功后的履约准备。"""

import secrets
from collections import defaultdict
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Product, ProductSku, ServiceSlot
from apps.common.api import ApiError
from apps.fulfillment.models import Appointment, OrderDelivery, VerifyCode
from apps.merchants.models import Merchant
from apps.merchants.services import resolve_commission_rate

from .models import Order, OrderItem
from .services import transit_order


def _validate_products(merchant_id, order_type, items):
    product_ids = [item["product_id"] for item in items]
    products = {
        product.id: product for product in Product.objects.select_related("merchant").filter(pk__in=product_ids)
    }
    contexts = []
    for item in items:
        product = products.get(item["product_id"])
        if product is None or product.status != Product.Status.ON_SALE:
            raise ApiError("PRODUCT_NOT_AVAILABLE", "商品不存在或已下架", 409)
        if product.merchant_id != merchant_id:
            raise ApiError("MERCHANT_MISMATCH", "商品不属于该商户", 409)
        if order_type == Order.Type.SERVICE and product.type != Product.Type.SERVICE:
            raise ApiError("DELIVERY_TYPE_NOT_SUPPORTED", "服务订单包含实物商品", 409)
        if order_type != Order.Type.SERVICE and product.type != Product.Type.PHYSICAL:
            raise ApiError("DELIVERY_TYPE_NOT_SUPPORTED", "实物订单包含服务商品", 409)
        contexts.append({"item": item, "product": product, "sku": None})
    return contexts


def _attach_skus(contexts):
    sku_ids = [ctx["item"].get("sku_id") for ctx in contexts if ctx["item"].get("sku_id")]
    skus = {sku.id: sku for sku in ProductSku.objects.select_for_update().filter(pk__in=sku_ids)}
    for ctx in contexts:
        sku_id = ctx["item"].get("sku_id")
        if not sku_id:
            continue
        sku = skus.get(sku_id)
        if sku is None or sku.product_id != ctx["product"].id:
            raise ApiError("SKU_NOT_FOUND", "规格不存在或不属于该商品", 409)
        ctx["sku"] = sku


def _check_stock(contexts):
    need = defaultdict(int)
    for ctx in contexts:
        if ctx["sku"] is not None:
            need[ctx["sku"].id] += ctx["item"]["quantity"]
    for sku_id, quantity in need.items():
        sku = next(ctx["sku"] for ctx in contexts if ctx["sku"] and ctx["sku"].id == sku_id)
        if sku.available_stock < quantity:
            raise ApiError(
                "STOCK_NOT_ENOUGH",
                f"库存不足，当前可售 {sku.available_stock}",
                409,
                {"available_stock": sku.available_stock},
            )
    return need


def _reserve_slot(contexts, appointment):
    if not appointment:
        return None
    service_products = [ctx["product"] for ctx in contexts if ctx["product"].type == Product.Type.SERVICE]
    if not service_products:
        raise ApiError("SLOT_NOT_AVAILABLE", "该订单不支持预约", 409)
    slot = ServiceSlot.objects.select_for_update().filter(pk=appointment["slot_id"]).first()
    if slot is None or slot.product_id not in [product.id for product in service_products]:
        raise ApiError("SLOT_NOT_AVAILABLE", "预约时段不存在或不属于该商品", 409)
    if slot.slot_date < timezone.localdate() or slot.status == ServiceSlot.Status.CLOSED:
        raise ApiError("SLOT_NOT_AVAILABLE", "预约时段不可用", 409)
    if slot.remaining < 1:
        raise ApiError("SLOT_FULL", "预约时段已满", 409)
    slot.reserved_count += 1
    if slot.reserved_count >= slot.capacity:
        slot.status = ServiceSlot.Status.FULL
    slot.save(update_fields=["reserved_count", "status", "updated_at"])
    return slot


def create_order(
    user,
    *,
    merchant_id,
    order_type,
    items,
    contact,
    appointment=None,
    remark="",
    idempotency_key,
    request_hash,
):
    with transaction.atomic():
        existing = Order.objects.filter(idempotency_key=idempotency_key).first()
        if existing is not None:
            if existing.user_id != user.id or existing.idempotency_hash != request_hash:
                raise ApiError("IDEMPOTENCY_CONFLICT", "幂等键已用于不同请求", 409)
            return existing, False

        merchant = Merchant.objects.filter(pk=merchant_id, status=Merchant.Status.ACTIVE).first()
        if merchant is None:
            raise ApiError("MERCHANT_NOT_AVAILABLE", "商户不存在或未营业", 409)

        contexts = _validate_products(merchant_id, order_type, items)
        _attach_skus(contexts)
        if appointment is None and any(ctx["product"].appointment_required for ctx in contexts):
            raise ApiError("APPOINTMENT_REQUIRED", "该服务需要选择预约时段", 409)
        slot = _reserve_slot(contexts, appointment)
        sku_need = _check_stock(contexts)

        product_amount = sum(
            (ctx["sku"].price if ctx["sku"] else ctx["product"].price) * ctx["item"]["quantity"] for ctx in contexts
        )
        rate = resolve_commission_rate(merchant)
        commission_amount = int((Decimal(product_amount) * rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        now = timezone.now()
        order = Order.objects.create(
            user=user,
            merchant=merchant,
            order_type=order_type,
            status=Order.Status.PENDING_PAYMENT,
            product_amount=product_amount,
            delivery_fee=0,
            payable_amount=product_amount,
            commission_rate=rate,
            commission_amount=commission_amount,
            contact_json=contact,
            remark=remark,
            expire_at=now + timedelta(minutes=settings.ORDER_PAYMENT_TIMEOUT_MINUTES),
            idempotency_key=idempotency_key,
            idempotency_hash=request_hash,
        )

        for ctx in contexts:
            product = ctx["product"]
            sku = ctx["sku"]
            price = sku.price if sku else product.price
            quantity = ctx["item"]["quantity"]
            OrderItem.objects.create(
                order=order,
                product=product,
                sku=sku,
                snapshot_json={
                    "title": product.title,
                    "cover_url": product.cover_url,
                    "spec": sku.spec_json if sku else {},
                    "type": product.type,
                    "verify_days": product.verify_days,
                },
                title=product.title,
                price=price,
                quantity=quantity,
                amount=price * quantity,
            )

        for sku_id, quantity in sku_need.items():
            sku = next(ctx["sku"] for ctx in contexts if ctx["sku"] and ctx["sku"].id == sku_id)
            sku.locked_stock += quantity
            sku.version += 1
            sku.save(update_fields=["locked_stock", "version", "updated_at"])

        if order_type in (Order.Type.EXPRESS, Order.Type.PICKUP):
            OrderDelivery.objects.create(
                order=order,
                type=order_type,
                address_snapshot=contact,
                receiver_name=contact.get("name", ""),
                receiver_phone=contact.get("phone", ""),
            )

        if slot is not None:
            Appointment.objects.create(
                order=order,
                slot=slot,
                slot_date=slot.slot_date,
                start_time=slot.start_time,
                end_time=slot.end_time,
                status=Appointment.Status.PENDING_CONFIRM,
                remark=appointment.get("remark", ""),
            )

    return order, True


def _release_stock(order):
    need = defaultdict(int)
    for item in order.items.all():
        if item.sku_id:
            need[item.sku_id] += item.quantity
    if not need:
        return
    skus = {sku.id: sku for sku in ProductSku.objects.select_for_update().filter(pk__in=need)}
    for sku_id, quantity in need.items():
        sku = skus.get(sku_id)
        if sku is None:
            continue
        sku.locked_stock = max(sku.locked_stock - quantity, 0)
        sku.version += 1
        sku.save(update_fields=["locked_stock", "version", "updated_at"])


def _release_slot(order):
    appointment = Appointment.objects.select_for_update().filter(order=order).select_related("slot").first()
    if appointment is None or appointment.status == Appointment.Status.CANCELLED:
        return
    appointment.status = Appointment.Status.CANCELLED
    appointment.canceled_at = timezone.now()
    appointment.save(update_fields=["status", "canceled_at", "updated_at"])
    if appointment.slot_id:
        slot = appointment.slot
        slot.reserved_count = max(slot.reserved_count - 1, 0)
        if slot.status == ServiceSlot.Status.FULL and slot.remaining > 0:
            slot.status = ServiceSlot.Status.OPEN
        slot.save(update_fields=["reserved_count", "status", "updated_at"])


def cancel_order(user, order_id, reason=""):
    from apps.payments.models import PaymentOrder

    with transaction.atomic():
        order = Order.objects.select_for_update().filter(pk=order_id, user=user).first()
        if order is None:
            raise ApiError("NOT_FOUND", "订单不存在", 404)
        if order.status == Order.Status.CLOSED:
            return order
        if order.status != Order.Status.PENDING_PAYMENT:
            raise ApiError("ORDER_STATE_CONFLICT", "当前状态不允许取消", 409)

        transit_order(
            order.id,
            "CANCEL",
            operator_type="USER",
            operator_id=user.id,
            reason=reason,
        )
        _release_stock(order)
        _release_slot(order)
        PaymentOrder.objects.filter(
            order=order, status__in=[PaymentOrder.Status.CREATED, PaymentOrder.Status.PAYING]
        ).update(status=PaymentOrder.Status.CLOSED)
    order.refresh_from_db()
    return order


def mark_order_paid(order):
    """支付成功后：锁定库存转已售，生成核销码/提货码。"""
    need = defaultdict(int)
    max_verify_days = 0
    for item in order.items.all():
        if item.sku_id:
            need[item.sku_id] += item.quantity
        max_verify_days = max(max_verify_days, int(item.snapshot_json.get("verify_days", 0)))

    if need:
        skus = {sku.id: sku for sku in ProductSku.objects.select_for_update().filter(pk__in=need)}
        for sku_id, quantity in need.items():
            sku = skus.get(sku_id)
            if sku is None:
                continue
            sku.locked_stock = max(sku.locked_stock - quantity, 0)
            sku.sold_stock += quantity
            sku.version += 1
            sku.save(update_fields=["locked_stock", "sold_stock", "version", "updated_at"])

    if order.order_type not in (Order.Type.PICKUP, Order.Type.SERVICE):
        return
    if VerifyCode.objects.filter(order=order).exists():
        return

    code_type = VerifyCode.Type.PICKUP if order.order_type == Order.Type.PICKUP else VerifyCode.Type.VERIFY
    code = _generate_verify_code()
    verify_code = VerifyCode.objects.create(
        order=order,
        merchant=order.merchant,
        code=code,
        type=code_type,
        status=VerifyCode.Status.ACTIVE,
        valid_from=timezone.now(),
        valid_to=timezone.now() + timedelta(days=max(max_verify_days, 1)),
    )
    if order.order_type == Order.Type.PICKUP:
        OrderDelivery.objects.filter(order=order).update(pickup_code=verify_code.code)


def _generate_verify_code() -> str:
    for _ in range(6):
        code = f"{secrets.randbelow(10**8):08d}"
        if not VerifyCode.objects.filter(code=code).exists():
            return code
    raise ApiError("VERIFY_CODE_GENERATE_FAILED", "核销码生成失败，请重试", 500)
