"""订单状态机与购物车约束测试。"""

from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient

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


class CartAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = AppUser.objects.create_user(phone="13900000003", password="pass12345")
        self.client.force_authenticate(self.user)
        self.merchant = Merchant.objects.create(merchant_no="M102", name="购物车 API 商户")
        self.other_merchant = Merchant.objects.create(merchant_no="M103", name="另一家商户")
        self.product = Product.objects.create(
            merchant=self.merchant,
            type=Product.Type.PHYSICAL,
            title="API 商品",
            price=1000,
            status=Product.Status.ON_SALE,
        )
        self.sku = ProductSku.objects.create(product=self.product, sku_code="API-SKU", price=1000, stock=10)
        self.other_product = Product.objects.create(
            merchant=self.other_merchant,
            type=Product.Type.PHYSICAL,
            title="其他商户商品",
            price=2000,
            status=Product.Status.ON_SALE,
        )
        self.other_sku = ProductSku.objects.create(
            product=self.other_product, sku_code="OTHER-SKU", price=2000, stock=10
        )

    def _add(self, product_id=None, sku_id=None, quantity=1):
        return self.client.post(
            "/api/v1/cart/items/",
            {"product_id": product_id or self.product.id, "sku_id": sku_id or self.sku.id, "quantity": quantity},
            format="json",
        )

    def test_add_item_and_increment_same_sku(self):
        first = self._add()
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(first.data["data"]["total_amount"], 1000)
        second = self._add()
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data["data"]["items"][0]["quantity"], 2)
        self.assertEqual(second.data["data"]["total_amount"], 2000)

    def test_cross_store_cart_is_rejected(self):
        self._add()
        response = self._add(product_id=self.other_product.id, sku_id=self.other_sku.id)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "CROSS_STORE_CART")

    def test_stock_not_enough(self):
        response = self._add(quantity=11)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "STOCK_NOT_ENOUGH")

    def test_update_quantity_and_selected(self):
        created = self._add()
        item_id = created.data["data"]["items"][0]["id"]
        patched = self.client.patch(f"/api/v1/cart/items/{item_id}/", {"quantity": 3}, format="json")
        self.assertEqual(patched.status_code, 200)
        self.assertEqual(patched.data["data"]["total_amount"], 3000)
        unselected = self.client.patch(f"/api/v1/cart/items/{item_id}/", {"selected": False}, format="json")
        self.assertEqual(unselected.status_code, 200)
        self.assertEqual(unselected.data["data"]["total_amount"], 0)

    def test_delete_item(self):
        created = self._add()
        item_id = created.data["data"]["items"][0]["id"]
        deleted = self.client.delete(f"/api/v1/cart/items/{item_id}/")
        self.assertEqual(deleted.status_code, 204)
        listing = self.client.get("/api/v1/cart/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.data["data"]["items"], [])

    def test_cart_requires_authentication(self):
        response = APIClient().get("/api/v1/cart/")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["code"], "AUTH_REQUIRED")
