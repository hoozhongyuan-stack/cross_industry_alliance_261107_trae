"""订单状态迁移：唯一入口，保证状态日志与时间戳同步落库。"""

from typing import Optional

from django.db import transaction
from django.utils import timezone

from .models import Order, OrderStatusLog


class InvalidTransition(Exception):
    """当前状态不接受该事件。"""


ORDER_TRANSITIONS = {
    (Order.Status.PENDING_PAYMENT, "PAY_SUCCESS"): Order.Status.PENDING_ACCEPT,
    (Order.Status.PENDING_PAYMENT, "CANCEL"): Order.Status.CLOSED,
    (Order.Status.PENDING_PAYMENT, "TIMEOUT"): Order.Status.CLOSED,
    (Order.Status.PENDING_ACCEPT, "MERCHANT_ACCEPT"): Order.Status.PENDING_FULFILL,
    (Order.Status.PENDING_ACCEPT, "MERCHANT_REJECT"): Order.Status.REFUNDING,
    (Order.Status.PENDING_ACCEPT, "TIMEOUT"): Order.Status.REFUNDING,
    (Order.Status.PENDING_FULFILL, "SHIP"): Order.Status.FULFILLING,
    (Order.Status.PENDING_FULFILL, "PICKUP_READY"): Order.Status.FULFILLING,
    (Order.Status.PENDING_FULFILL, "APPOINTMENT_CONFIRM"): Order.Status.FULFILLING,
    (Order.Status.PENDING_FULFILL, "USER_CANCEL"): Order.Status.REFUNDING,
    (Order.Status.PENDING_FULFILL, "SERVICE_VERIFY"): Order.Status.COMPLETED,
    (Order.Status.FULFILLING, "CONFIRM_RECEIVE"): Order.Status.COMPLETED,
    (Order.Status.FULFILLING, "PICKUP_VERIFY"): Order.Status.COMPLETED,
    (Order.Status.FULFILLING, "SERVICE_VERIFY"): Order.Status.COMPLETED,
    (Order.Status.COMPLETED, "APPLY_AFTER_SALE"): Order.Status.AFTER_SALE,
    (Order.Status.AFTER_SALE, "REFUND_APPROVED"): Order.Status.REFUNDING,
    (Order.Status.AFTER_SALE, "ARBITRATION_REFUND"): Order.Status.REFUNDING,
    (Order.Status.REFUNDING, "REFUND_SUCCESS_FULL"): Order.Status.REFUNDED,
    (Order.Status.REFUNDING, "REFUND_SUCCESS_PARTIAL"): Order.Status.COMPLETED,
}

FULFILLMENT_BY_EVENT = {
    "PAY_SUCCESS": Order.FulfillmentStatus.NOT_STARTED,
    "SHIP": Order.FulfillmentStatus.SHIPPED,
    "PICKUP_READY": Order.FulfillmentStatus.PICKUP_READY,
    "APPOINTMENT_CONFIRM": Order.FulfillmentStatus.APPOINTMENT_CONFIRMED,
    "SERVICE_VERIFY": Order.FulfillmentStatus.DONE,
    "CONFIRM_RECEIVE": Order.FulfillmentStatus.DONE,
    "PICKUP_VERIFY": Order.FulfillmentStatus.DONE,
}

TIMESTAMP_BY_STATUS = {
    Order.Status.PENDING_ACCEPT: "paid_at",
    Order.Status.PENDING_FULFILL: "accepted_at",
    Order.Status.COMPLETED: "completed_at",
    Order.Status.CLOSED: "closed_at",
}


def transit_order(
    order_id: int,
    event: str,
    *,
    operator_type: str = OrderStatusLog.OperatorType.SYSTEM,
    operator_id: Optional[int] = None,
    operator_name: str = "",
    reason: str = "",
) -> Order:
    """按事件迁移订单状态；非法迁移抛出 InvalidTransition，调用方转 409。"""
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_id)
        target = ORDER_TRANSITIONS.get((order.status, event))
        if target is None:
            raise InvalidTransition(f"订单 {order.order_no} 处于 {order.status}，不接受事件 {event}")

        from_status = order.status
        order.status = target
        update_fields = ["status", "fulfillment_status", "version", "updated_at"]

        if target == Order.Status.FULFILLING and event in FULFILLMENT_BY_EVENT:
            order.fulfillment_status = FULFILLMENT_BY_EVENT[event]
        elif event == "SERVICE_VERIFY" or event in ("CONFIRM_RECEIVE", "PICKUP_VERIFY"):
            order.fulfillment_status = Order.FulfillmentStatus.DONE

        stamp_field = TIMESTAMP_BY_STATUS.get(target)
        if stamp_field:
            setattr(order, stamp_field, timezone.now())
            update_fields.append(stamp_field)

        if target == Order.Status.CLOSED and reason:
            order.cancel_reason = reason
            update_fields.append("cancel_reason")

        order.version += 1
        order.save(update_fields=update_fields)

        OrderStatusLog.objects.create(
            order=order,
            from_status=from_status,
            to_status=target,
            event=event,
            operator_type=operator_type,
            operator_id=operator_id,
            operator_name=operator_name,
            reason=reason,
        )
    return order
