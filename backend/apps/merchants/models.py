"""商户（门店）、员工与资质。

结算周期 N 天按商户配置，默认取 settings.DEFAULT_SETTLEMENT_CYCLE_DAYS；
具体值与佣金率属于商务条款，未经确认的商户不写默认规则。
"""

from django.conf import settings
from django.db import models

from apps.common.fields import EncryptedJSONField
from apps.common.models import TimeStampedModel


class Merchant(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "待审核"
        ACTIVE = "ACTIVE", "营业中"
        REJECTED = "REJECTED", "审核驳回"
        SUSPENDED = "SUSPENDED", "已冻结"
        CLOSED = "CLOSED", "已关店"

    merchant_no = models.CharField("商户编号", max_length=32, unique=True)
    name = models.CharField("商户名称", max_length=80)
    short_name = models.CharField("简称", max_length=40, blank=True, default="")
    category = models.ForeignKey(
        "catalog.Category",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="merchants",
        verbose_name="主营类目",
    )
    logo_url = models.URLField("Logo", blank=True, default="")
    description = models.TextField("简介", blank=True, default="")
    contact_phone = models.CharField("联系电话", max_length=20, blank=True, default="")
    province = models.CharField("省", max_length=32, blank=True, default="")
    city = models.CharField("市", max_length=32, blank=True, default="")
    district = models.CharField("区县", max_length=32, blank=True, default="")
    address = models.CharField("详细地址", max_length=200, blank=True, default="")
    lng = models.DecimalField("经度", max_digits=9, decimal_places=6, null=True, blank=True)
    lat = models.DecimalField("纬度", max_digits=9, decimal_places=6, null=True, blank=True)
    business_hours = models.JSONField("营业时间", default=dict, blank=True)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    commission_rate = models.DecimalField(
        "佣金率覆盖（空则继承类目）", max_digits=5, decimal_places=4, null=True, blank=True
    )
    settlement_cycle_days = models.PositiveSmallIntegerField(
        "结算周期（天）", default=settings.DEFAULT_SETTLEMENT_CYCLE_DAYS
    )
    bank_info = EncryptedJSONField("收款银行信息（加密存储，T9）", default=dict, blank=True)
    opened_at = models.DateTimeField("开店时间", null=True, blank=True)

    class Meta:
        verbose_name = "商户"
        verbose_name_plural = "商户"
        db_table = "merchant"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["category", "status"], name="ix_merchant_category_status"),
            models.Index(fields=["status", "city"], name="ix_merchant_status_city"),
        ]

    def __str__(self):
        return f"{self.name}（{self.merchant_no}）"


class MerchantStaff(TimeStampedModel):
    class Role(models.TextChoices):
        OWNER = "OWNER", "老板"
        MANAGER = "MANAGER", "店长"
        CLERK = "CLERK", "店员"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "在职"
        DISABLED = "DISABLED", "已停用"

    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="staff", verbose_name="商户")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="merchant_staff_roles",
        verbose_name="员工账号",
    )
    role = models.CharField("角色", max_length=16, choices=Role.choices, default=Role.CLERK)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    joined_at = models.DateTimeField("加入时间", null=True, blank=True)

    class Meta:
        verbose_name = "商户员工"
        verbose_name_plural = "商户员工"
        db_table = "merchant_staff"
        constraints = [models.UniqueConstraint(fields=["merchant", "user"], name="uq_merchant_staff")]
        indexes = [models.Index(fields=["merchant", "status"], name="ix_merchant_staff_status")]

    def __str__(self):
        return f"{self.merchant_id}-{self.user_id}({self.role})"


class MerchantQualification(TimeStampedModel):
    class Type(models.TextChoices):
        BUSINESS_LICENSE = "BUSINESS_LICENSE", "营业执照"
        FOOD_PERMIT = "FOOD_PERMIT", "食品经营许可"
        HEALTH_PERMIT = "HEALTH_PERMIT", "卫生许可"
        OTHER = "OTHER", "其他"

    class AuditStatus(models.TextChoices):
        PENDING = "PENDING", "待审核"
        APPROVED = "APPROVED", "已通过"
        REJECTED = "REJECTED", "已驳回"
        EXPIRED = "EXPIRED", "已过期"

    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="qualifications", verbose_name="商户")
    type = models.CharField("资质类型", max_length=24, choices=Type.choices)
    file_url = models.URLField("材料地址")
    expire_at = models.DateField("有效期至", null=True, blank=True)
    audit_status = models.CharField(
        "审核状态", max_length=16, choices=AuditStatus.choices, default=AuditStatus.PENDING, db_index=True
    )
    reject_reason = models.CharField("驳回原因", max_length=200, blank=True, default="")

    class Meta:
        verbose_name = "商户资质"
        verbose_name_plural = "商户资质"
        db_table = "merchant_qualification"
        indexes = [models.Index(fields=["merchant", "type"], name="ix_merchant_qual_type")]

    def __str__(self):
        return f"{self.merchant_id}-{self.get_type_display()}"
