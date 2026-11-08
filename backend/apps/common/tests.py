"""字段加密测试：加解密往返、随机 nonce、数据库中不落明文。"""

from django.db import connection
from django.test import TestCase

from apps.accounts.models import AppUser, UserAddress
from apps.merchants.models import Merchant
from apps.payments.models import PlatformPaymentConfig

from .crypto import decrypt_text, encrypt_text


class CryptoTests(TestCase):
    def test_roundtrip_uses_random_nonce(self):
        first = encrypt_text("张三 13800138000")
        second = encrypt_text("张三 13800138000")
        self.assertTrue(first.startswith("enc:v1:"))
        self.assertNotEqual(first, second)
        self.assertEqual(decrypt_text(first), "张三 13800138000")

    def test_legacy_plaintext_passthrough(self):
        self.assertEqual(decrypt_text("legacy-plaintext"), "legacy-plaintext")


class EncryptionAtRestTests(TestCase):
    def setUp(self):
        self.user = AppUser.objects.create_user(phone="13500000001", password="pass12345")

    def _raw(self, sql, params):
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchone()

    def test_user_address_is_encrypted_at_rest(self):
        address = UserAddress.objects.create(
            user=self.user,
            receiver_name="张三",
            phone="13800138000",
            city="上海",
            detail="静安区南京西路 100 号",
        )
        self.assertEqual(UserAddress.objects.get(pk=address.pk).receiver_name, "张三")
        raw_name, raw_phone, raw_detail = self._raw(
            "SELECT receiver_name, phone, detail FROM user_address WHERE id = %s", [address.pk]
        )
        for value in (raw_name, raw_phone, raw_detail):
            self.assertTrue(value.startswith("enc:v1:"))
        self.assertNotIn("张三", raw_name)
        self.assertNotIn("13800138000", raw_phone)

    def test_merchant_bank_info_is_encrypted_at_rest(self):
        merchant = Merchant.objects.create(
            merchant_no="M300",
            name="加密测试商户",
            bank_info={"bank": "招商银行", "card_no": "6225888888888888"},
        )
        self.assertEqual(Merchant.objects.get(pk=merchant.pk).bank_info["card_no"], "6225888888888888")
        (raw_bank,) = self._raw("SELECT bank_info FROM merchant WHERE id = %s", [merchant.pk])
        self.assertTrue(raw_bank.startswith("enc:v1:"))
        self.assertNotIn("6225888888888888", raw_bank)

    def test_payment_config_secrets_are_encrypted_at_rest(self):
        config = PlatformPaymentConfig.objects.create(
            channel=PlatformPaymentConfig._meta.get_field("channel").choices[0][0],
            merchant_no="1900000109",
            api_v3_key="api-v3-key-plain",
            private_key="-----BEGIN PRIVATE KEY-----",
            platform_cert="-----BEGIN CERTIFICATE-----",
        )
        self.assertEqual(PlatformPaymentConfig.objects.get(pk=config.pk).api_v3_key, "api-v3-key-plain")
        raw_key, raw_private, raw_cert = self._raw(
            "SELECT api_v3_key, private_key, platform_cert FROM platform_payment_config WHERE id = %s",
            [config.pk],
        )
        for value in (raw_key, raw_private, raw_cert):
            self.assertTrue(value.startswith("enc:v1:"))
        self.assertNotIn("api-v3-key-plain", raw_key)
