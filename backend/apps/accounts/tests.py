"""接口测试：健康检查、JWT、M1 认证适配层与地址簿。"""

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import AppUser, UserAddress, UserIdentity


class HealthTests(TestCase):
    def test_health_endpoint_ok(self):
        response = APIClient().get("/api/v1/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ok")
        self.assertEqual(response.data["db"], "ok")


class AuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = AppUser.objects.create_user(phone="13700000001", password="pass12345", nickname="测试用户")

    def test_jwt_login_and_me(self):
        response = self.client.post(
            "/api/v1/accounts/auth/token/", {"phone": "13700000001", "password": "pass12345"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        token = response.data["access"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        me = self.client.get("/api/v1/accounts/me/")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.data["phone"], "13700000001")

    def test_me_requires_authentication(self):
        response = APIClient().get("/api/v1/accounts/me/")
        self.assertEqual(response.status_code, 401)

    def test_product_list_is_public(self):
        response = APIClient().get("/api/v1/products/")
        self.assertEqual(response.status_code, 200)


class WechatLoginTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_login_creates_user_and_returns_tokens(self):
        response = self.client.post("/api/v1/auth/wechat/login/", {"code": "dev-code"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["code"], "OK")
        self.assertIn("access", response.data["data"])
        self.assertEqual(AppUser.objects.count(), 1)
        self.assertEqual(UserIdentity.objects.count(), 1)

    def test_same_code_returns_same_user(self):
        self.client.post("/api/v1/auth/wechat/login/", {"code": "dev-code"}, format="json")
        self.client.post("/api/v1/auth/wechat/login/", {"code": "dev-code"}, format="json")
        self.assertEqual(AppUser.objects.count(), 1)
        self.assertEqual(UserIdentity.objects.count(), 1)


class SmsLoginTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.phone = "13800138001"

    def _send(self):
        response = self.client.post("/api/v1/auth/sms/send/", {"phone": self.phone, "scene": "LOGIN"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        return cache.get(f"sms:code:{self.phone}")

    def test_sms_send_and_login(self):
        code = self._send()
        response = self.client.post("/api/v1/auth/h5/sms/", {"phone": self.phone, "sms_code": code}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("access", response.data["data"])
        self.assertTrue(AppUser.objects.filter(phone=self.phone).exists())

    def test_send_is_rate_limited(self):
        self._send()
        second = self.client.post("/api/v1/auth/sms/send/", {"phone": self.phone, "scene": "LOGIN"}, format="json")
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.data["code"], "RATE_LIMITED")

    def test_wrong_code_is_rejected(self):
        self._send()
        response = self.client.post("/api/v1/auth/h5/sms/", {"phone": self.phone, "sms_code": "000000"}, format="json")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.data["code"], "SMS_CODE_INVALID")


class AddressAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = AppUser.objects.create_user(phone="13700000002", password="pass12345")
        self.client.force_authenticate(self.user)

    def _create(self, **overrides):
        payload = {
            "receiver_name": "张三",
            "phone": "13800138000",
            "city": "上海",
            "district": "静安区",
            "detail": "南京西路 100 号",
        }
        payload.update(overrides)
        return self.client.post("/api/v1/addresses/", payload, format="json")

    def test_create_list_and_default(self):
        first = self._create(is_default=True)
        self.assertEqual(first.status_code, 201, first.data)
        second = self._create(receiver_name="李四", is_default=True)
        self.assertEqual(second.status_code, 201)
        self.assertFalse(UserAddress.objects.get(pk=first.data["data"]["id"]).is_default)
        self.assertTrue(UserAddress.objects.get(pk=second.data["data"]["id"]).is_default)

        listing = self.client.get("/api/v1/addresses/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(len(listing.data["data"]), 2)
        self.assertEqual(listing.data["trace_id"], listing["X-Trace-Id"])

    def test_update_and_delete(self):
        created = self._create()
        address_id = created.data["data"]["id"]
        patched = self.client.patch(f"/api/v1/addresses/{address_id}/", {"detail": "新地址"}, format="json")
        self.assertEqual(patched.status_code, 200)
        self.assertEqual(patched.data["data"]["detail"], "新地址")
        deleted = self.client.delete(f"/api/v1/addresses/{address_id}/")
        self.assertEqual(deleted.status_code, 204)
        self.assertFalse(UserAddress.objects.filter(pk=address_id).exists())

    def test_cannot_access_other_users_address(self):
        created = self._create()
        address_id = created.data["data"]["id"]
        other = AppUser.objects.create_user(phone="13700000003", password="pass12345")
        self.client.force_authenticate(other)
        response = self.client.patch(f"/api/v1/addresses/{address_id}/", {"detail": "越权"}, format="json")
        self.assertEqual(response.status_code, 404)

    def test_requires_authentication(self):
        response = APIClient().get("/api/v1/addresses/")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["code"], "AUTH_REQUIRED")
