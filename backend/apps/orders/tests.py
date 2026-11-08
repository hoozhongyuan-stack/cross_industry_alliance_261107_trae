"""订单状态机、购物车、下单支付闭环测试。"""

from datetime import timedelta
from uuid import uuid4

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AppUser
from apps.catalog.models import Category, Product, ProductSku, ServiceSlot
from apps.fulfillment.models import Appointment, VerifyCode
from apps.ledger.models import LedgerTransaction, MerchantAccount
from apps.merchants.models import Merchant
from apps.payments.models import PaymentOrder

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


class OrderFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = AppUser.objects.create_user(phone="13900000004", password="pass12345")
        self.client.force_authenticate(self.user)
        self.category = Category.objects.create(name="测试类目", commission_rate="0.0500")
        self.merchant = Merchant.objects.create(
            merchant_no="M104", name="交易闭环商户", category=self.category, status=Merchant.Status.ACTIVE
        )
        self.product = Product.objects.create(
            merchant=self.merchant,
            category=self.category,
            type=Product.Type.PHYSICAL,
            title="实物商品",
            price=1000,
            status=Product.Status.ON_SALE,
        )
        self.sku = ProductSku.objects.create(product=self.product, sku_code="FLOW-SKU", price=1000, stock=10)
        self.service = Product.objects.create(
            merchant=self.merchant,
            category=self.category,
            type=Product.Type.SERVICE,
            title="到店服务",
            price=3000,
            status=Product.Status.ON_SALE,
            appointment_required=True,
        )
        self.service_sku = ProductSku.objects.create(product=self.service, sku_code="SERVICE-SKU", price=3000, stock=5)
        self.slot = ServiceSlot.objects.create(
            product=self.service,
            slot_date=timezone.localdate() + timedelta(days=1),
            start_time="10:00",
            end_time="10:30",
            capacity=2,
        )

    def _payload(self, **overrides):
        payload = {
            "merchant_id": self.merchant.id,
            "order_type": "EXPRESS",
            "items": [{"product_id": self.product.id, "sku_id": self.sku.id, "quantity": 2}],
            "contact": {"name": "张三", "phone": "13800138000", "address_detail": "南京西路 100 号"},
            "remark": "",
        }
        payload.update(overrides)
        return payload

    def _create(self, key=None, **overrides):
        return self.client.post(
            "/api/v1/orders/",
            self._payload(**overrides),
            format="json",
            HTTP_IDEMPOTENCY_KEY=key or uuid4().hex,
        )

    def _service_payload(self):
        return {
            "merchant_id": self.merchant.id,
            "order_type": "SERVICE",
            "items": [{"product_id": self.service.id, "sku_id": self.service_sku.id, "quantity": 1}],
            "contact": {"name": "李四", "phone": "13800138001"},
            "appointment": {"slot_id": self.slot.id, "remark": "下午到店"},
        }

    def test_create_order_snapshots_amounts_and_locks_stock(self):
        response = self._create()
        self.assertEqual(response.status_code, 201, response.data)
        data = response.data["data"]
        self.assertEqual(data["status"], "PENDING_PAYMENT")
        self.assertEqual(data["product_amount"], 2000)
        self.assertEqual(data["payable_amount"], 2000)
        self.assertEqual(float(data["commission_rate"]), 0.05)
        self.assertEqual(data["commission_amount"], 100)
        self.assertEqual(Order.objects.count(), 1)
        self.sku.refresh_from_db()
        self.assertEqual(self.sku.locked_stock, 2)

    def test_create_is_idempotent(self):
        key = uuid4().hex
        first = self._create(key=key)
        second = self._create(key=key)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data["data"]["id"], second.data["data"]["id"])
        self.assertEqual(Order.objects.count(), 1)
        self.sku.refresh_from_db()
        self.assertEqual(self.sku.locked_stock, 2)

    def test_idempotency_conflict_on_different_payload(self):
        key = uuid4().hex
        self._create(key=key)
        response = self._create(
            key=key,
            items=[{"product_id": self.product.id, "sku_id": self.sku.id, "quantity": 1}],
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "IDEMPOTENCY_CONFLICT")

    def test_stock_not_enough(self):
        response = self._create(items=[{"product_id": self.product.id, "sku_id": self.sku.id, "quantity": 11}])
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "STOCK_NOT_ENOUGH")
        self.assertEqual(Order.objects.count(), 0)

    def test_service_order_reserves_slot_and_requires_appointment(self):
        response = self.client.post(
            "/api/v1/orders/",
            self._service_payload(),
            format="json",
            HTTP_IDEMPOTENCY_KEY=uuid4().hex,
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Appointment.objects.count(), 1)
        self.slot.refresh_from_db()
        self.assertEqual(self.slot.reserved_count, 1)

        missing = self.client.post(
            "/api/v1/orders/",
            {**self._service_payload(), "appointment": None},
            format="json",
            HTTP_IDEMPOTENCY_KEY=uuid4().hex,
        )
        self.assertEqual(missing.status_code, 409)
        self.assertEqual(missing.data["code"], "APPOINTMENT_REQUIRED")

    def test_slot_full_is_rejected(self):
        self.slot.capacity = 1
        self.slot.save(update_fields=["capacity"])
        first = self.client.post(
            "/api/v1/orders/", self._service_payload(), format="json", HTTP_IDEMPOTENCY_KEY=uuid4().hex
        )
        self.assertEqual(first.status_code, 201, first.data)
        second = self.client.post(
            "/api/v1/orders/", self._service_payload(), format="json", HTTP_IDEMPOTENCY_KEY=uuid4().hex
        )
        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.data["code"], "SLOT_FULL")

    def test_pay_and_callback_close_the_loop(self):
        created = self._create(order_type="PICKUP")
        order_id = created.data["data"]["id"]

        paid = self.client.post(
            f"/api/v1/orders/{order_id}/pay/",
            {"channel": "WECHAT_MINI"},
            format="json",
            HTTP_IDEMPOTENCY_KEY=uuid4().hex,
        )
        self.assertEqual(paid.status_code, 200, paid.data)
        payment = PaymentOrder.objects.get(order_id=order_id)
        self.assertEqual(payment.status, PaymentOrder.Status.PAYING)
        self.assertTrue(payment.prepay_id.startswith("mock_"))

        callback = self.client.post(
            "/api/v1/callback/wechat/pay/",
            {
                "payment_no": payment.payment_no,
                "transaction_id": "wx-txn-001",
                "amount": payment.amount,
                "trade_state": "SUCCESS",
            },
            format="json",
        )
        self.assertEqual(callback.status_code, 200, callback.data)
        self.assertEqual(callback.data["code"], "SUCCESS")

        order = Order.objects.get(pk=order_id)
        self.assertEqual(order.status, Order.Status.PENDING_ACCEPT)
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentOrder.Status.PAID)
        self.assertEqual(MerchantAccount.objects.get(merchant=self.merchant).pending_balance, 2000)
        self.assertEqual(LedgerTransaction.objects.count(), 1)
        self.assertEqual(VerifyCode.objects.filter(order=order).count(), 1)
        self.sku.refresh_from_db()
        self.assertEqual(self.sku.locked_stock, 0)
        self.assertEqual(self.sku.sold_stock, 2)

        replay = self.client.post(
            "/api/v1/callback/wechat/pay/",
            {
                "payment_no": payment.payment_no,
                "transaction_id": "wx-txn-001",
                "amount": payment.amount,
                "trade_state": "SUCCESS",
            },
            format="json",
        )
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(LedgerTransaction.objects.count(), 1)
        self.assertEqual(MerchantAccount.objects.get(merchant=self.merchant).pending_balance, 2000)

    def test_callback_amount_mismatch(self):
        created = self._create()
        order_id = created.data["data"]["id"]
        self.client.post(
            f"/api/v1/orders/{order_id}/pay/",
            {},
            format="json",
            HTTP_IDEMPOTENCY_KEY=uuid4().hex,
        )
        payment = PaymentOrder.objects.get(order_id=order_id)
        response = self.client.post(
            "/api/v1/callback/wechat/pay/",
            {
                "payment_no": payment.payment_no,
                "transaction_id": "wx-txn-002",
                "amount": payment.amount - 1,
                "trade_state": "SUCCESS",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "FAIL")

    def test_cancel_releases_stock_and_closes_payment(self):
        created = self._create()
        order_id = created.data["data"]["id"]
        self.client.post(f"/api/v1/orders/{order_id}/pay/", {}, format="json", HTTP_IDEMPOTENCY_KEY=uuid4().hex)
        response = self.client.post(
            f"/api/v1/orders/{order_id}/cancel/",
            {"reason": "用户取消"},
            format="json",
            HTTP_IDEMPOTENCY_KEY=uuid4().hex,
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["status"], "CLOSED")
        self.sku.refresh_from_db()
        self.assertEqual(self.sku.locked_stock, 0)
        payment = PaymentOrder.objects.get(order_id=order_id)
        self.assertEqual(payment.status, PaymentOrder.Status.CLOSED)

    def test_cancel_service_order_releases_slot(self):
        created = self.client.post(
            "/api/v1/orders/", self._service_payload(), format="json", HTTP_IDEMPOTENCY_KEY=uuid4().hex
        )
        order_id = created.data["data"]["id"]
        response = self.client.post(
            f"/api/v1/orders/{order_id}/cancel/", {}, format="json", HTTP_IDEMPOTENCY_KEY=uuid4().hex
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.slot.refresh_from_db()
        self.assertEqual(self.slot.reserved_count, 0)

    def test_cannot_pay_other_users_order(self):
        created = self._create()
        other = AppUser.objects.create_user(phone="13900000005", password="pass12345")
        self.client.force_authenticate(other)
        response = self.client.post(
            f"/api/v1/orders/{created.data['data']['id']}/pay/",
            {},
            format="json",
            HTTP_IDEMPOTENCY_KEY=uuid4().hex,
        )
        self.assertEqual(response.status_code, 404)
