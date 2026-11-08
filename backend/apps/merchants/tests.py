"""佣金解析测试：商户覆盖优先，类目默认兜底。"""

from decimal import Decimal

from django.test import TestCase

from apps.catalog.models import Category

from .models import Merchant
from .services import resolve_commission_rate


class CommissionResolutionTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="餐饮", commission_rate=Decimal("0.0500"))
        self.merchant = Merchant.objects.create(merchant_no="M200", name="测试餐厅", category=self.category)

    def test_uses_category_default_when_no_override(self):
        self.assertIsNone(self.merchant.commission_rate)
        self.assertEqual(resolve_commission_rate(self.merchant), Decimal("0.0500"))

    def test_merchant_override_wins(self):
        self.merchant.commission_rate = Decimal("0.0300")
        self.merchant.save(update_fields=["commission_rate"])
        self.assertEqual(resolve_commission_rate(self.merchant), Decimal("0.0300"))

    def test_zero_override_is_respected(self):
        self.merchant.commission_rate = Decimal("0")
        self.merchant.save(update_fields=["commission_rate"])
        self.assertEqual(resolve_commission_rate(self.merchant), Decimal("0"))

    def test_no_category_falls_back_to_zero(self):
        merchant = Merchant.objects.create(merchant_no="M201", name="无类目商户")
        self.assertEqual(resolve_commission_rate(merchant), Decimal("0"))
