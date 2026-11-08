"""订单状态机测试。"""

from django.test import TestCase

from apps.accounts.models import AppUser
from apps.merchants.models import Merchant

from .models import Order, OrderStatusLog
from .services import InvalidTransition, transit_order


class OrderTransitionTests(TestCase):
    def setUp(self):
        self.user = AppUser.objects.create_user(phone="13900000001", password="pass12345")
        self.merchant = Merchant.objects.create(merchant_no="M100", name="状态机商户")
        self.order = Order.objects.create(
            user=self.user,
            merchant=self.merchant,
            order_type=Order.Type.SERVICE,
            payable_amount=8800,
        )

    def test_pay_success_moves_to_pending_accept(self):
        order = transit_order(self.order.id, "PAY_SUCCESS")
        self.assertEqual(order.status, Order.Status.PENDING_ACCEPT)
        self.assertIsNotNone(order.paid_at)
        self.assertEqual(OrderStatusLog.objects.filter(order=order).count(), 1)

    def test_accept_sets_accepted_at(self):
        transit_order(self.order.id, "PAY_SUCCESS")
        order = transit_order(self.order.id, "MERCHANT_ACCEPT")
        self.assertEqual(order.status, Order.Status.PENDING_FULFILL)
        self.assertIsNotNone(order.accepted_at)

    def test_invalid_event_raises(self):
        with self.assertRaises(InvalidTransition):
            transit_order(self.order.id, "MERCHANT_ACCEPT")

    def test_version_increments(self):
        self.assertEqual(self.order.version, 0)
        order = transit_order(self.order.id, "PAY_SUCCESS")
        self.assertEqual(order.version, 1)

    def test_close_records_reason(self):
        order = transit_order(self.order.id, "CANCEL", reason="用户取消")
        self.assertEqual(order.status, Order.Status.CLOSED)
        self.assertEqual(order.cancel_reason, "用户取消")
        self.assertIsNotNone(order.closed_at)
