"""订单状态机与购物车约束测试。"""

from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.models import AppUser
from apps.catalog.models import Product, ProductSku
from apps.merchants.models import Merchant

from .models import CartItem, Order, OrderStatusLog
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


class CartItemTests(TestCase):
    def setUp(self):
        self.user = AppUser.objects.create_user(phone="13900000002", password="pass12345")
        self.merchant = Merchant.objects.create(merchant_no="M101", name="购物车商户")
        self.product = Product.objects.create(
            merchant=self.merchant, type=Product.Type.PHYSICAL, title="测试商品", price=1000
        )
        self.sku = ProductSku.objects.create(product=self.product, sku_code="SKU-1", price=1000, stock=10)

    def _add(self, quantity=1):
        return CartItem.objects.create(
            user=self.user, merchant=self.merchant, product=self.product, sku=self.sku, quantity=quantity
        )

    def test_cannot_add_same_sku_twice(self):
        self._add()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._add()

    def test_quantity_must_be_positive(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._add(quantity=0)
