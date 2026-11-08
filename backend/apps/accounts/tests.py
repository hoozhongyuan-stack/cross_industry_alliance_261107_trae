"""接口冒烟测试：健康检查与 JWT 登录。"""

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import AppUser


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
