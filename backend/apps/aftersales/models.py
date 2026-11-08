"""售后单、仲裁案与举证材料。

与退款单的关系通过 RefundOrder.after_sale 外键建立（单向），避免跨 app 循环依赖；
AfterSale 侧可用 related_name="refunds" 反查。
"""

from django.db import models

from apps.common.models import TimeStampedModel
from apps.common.utils import generate_no


def default_after_sale_no() -> str:
    return generate_no("AS")


def default_case_no() -> str:
    return generate_no("AC")


class AfterSale(TimeStampedModel):
    class Type(models.TextChoices):
        REFUND_ONLY = "REFUND_ONLY", "仅退款"
        RETURN_REFUND = "RETURN_REFUND", "退货退款"
        SERVICE_ISSUE = "SERVICE_ISSUE", "服务问题"

    class Status(models.TextChoices):
        APPLIED = "APPLIED", "已申请"
        MERCHANT_PROCESSING = "MERCHANT_PROCESSING", "商户处理中"
        MERCHANT_AGREED = "MERCHANT_AGREED", "商户同意"
        MERCHANT_REJECTED = "MERCHANT_REJECTED", "商户拒绝"
        ARBITRATING = "ARBITRATING", "仲裁中"
        RESOLVED = "RESOLVED", "已裁定"
        REFUNDING = "REFUNDING", "退款中"
        COMPLETED = "COMPLETED", "已完成"
        CANCELLED = "CANCELLED", "已取消"

    class MerchantDecision(models.TextChoices):
        PENDING = "PENDING", "待处理"
        AGREED = "AGREED", "同意"
        REJECTED = "REJECTED", "拒绝"

    after_sale_no = models.CharField("售后单号", max_length=32, unique=True, default=default_after_sale_no)
    order = models.ForeignKey("orders.Order", on_delete=models.PROTECT, related_name="after_sales", verbose_name="订单")
    order_item = models.ForeignKey(
        "orders.OrderItem", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="订单行"
    )
    user = models.ForeignKey(
        "accounts.AppUser", on_delete=models.PROTECT, related_name="after_sales", verbose_name="用户"
    )
    merchant = models.ForeignKey(
        "merchants.Merchant", on_delete=models.PROTECT, related_name="after_sales", verbose_name="商户"
    )
    type = models.CharField("售后类型", max_length=24, choices=Type.choices)
    reason_code = models.CharField("原因码", max_length=32, blank=True, default="")
    description = models.TextField("问题描述", blank=True, default="")
    evidence_json = models.JSONField("凭证", default=list, blank=True)
    request_amount = models.BigIntegerField("申请金额（分）")
    approved_amount = models.BigIntegerField("批准金额（分）", default=0)
    status = models.CharField("状态", max_length=24, choices=Status.choices, default=Status.APPLIED, db_index=True)
    merchant_decision = models.CharField(
        "商户处理结果", max_length=16, choices=MerchantDecision.choices, default=MerchantDecision.PENDING
    )
    merchant_reason = models.TextField("商户处理说明", blank=True, default="")
    deadline_at = models.DateTimeField("商户处理截止时间", null=True, blank=True, db_index=True)
    arbitration_case = models.ForeignKey(
        "ArbitrationCase",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="after_sales",
        verbose_name="仲裁案",
    )
    closed_at = models.DateTimeField("结案时间", null=True, blank=True)

    class Meta:
        verbose_name = "售后单"
        verbose_name_plural = "售后单"
        db_table = "after_sale"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["merchant", "status", "deadline_at"], name="ix_aftersale_mch_sts_due"),
            models.Index(fields=["user", "created_at"], name="ix_after_sale_user_created"),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(request_amount__gt=0), name="ck_after_sale_request_positive"),
            models.CheckConstraint(check=models.Q(approved_amount__gte=0), name="ck_after_sale_approved_nonnegative"),
        ]

    def __str__(self):
        return self.after_sale_no


class ArbitrationCase(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "待受理"
        EVIDENCE = "EVIDENCE", "举证中"
        PROCESSING = "PROCESSING", "裁定中"
        DECIDED = "DECIDED", "已裁定"
        CLOSED = "CLOSED", "已结案"

    class Liability(models.TextChoices):
        MERCHANT = "MERCHANT", "商户责任"
        USER = "USER", "用户责任"
        PLATFORM = "PLATFORM", "平台责任"
        SHARED = "SHARED", "双方共担"
        UNDECIDED = "UNDECIDED", "未定"

    case_no = models.CharField("仲裁案号", max_length=32, unique=True, default=default_case_no)
    after_sale = models.OneToOneField(
        AfterSale, on_delete=models.CASCADE, related_name="arbitration", verbose_name="售后单"
    )
    amount = models.BigIntegerField("争议金额（分）")
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    ruling = models.TextField("裁定说明", blank=True, default="")
    liability = models.CharField("责任归属", max_length=16, choices=Liability.choices, default=Liability.UNDECIDED)
    deadline_at = models.DateTimeField("裁定截止时间", null=True, blank=True)
    decided_at = models.DateTimeField("裁定时间", null=True, blank=True)
    decided_by_id = models.BigIntegerField("裁定人 ID", null=True, blank=True)
    decided_by_name = models.CharField("裁定人", max_length=60, blank=True, default="")

    class Meta:
        verbose_name = "仲裁案"
        verbose_name_plural = "仲裁案"
        db_table = "arbitration_case"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["status", "deadline_at"], name="ix_arbitration_status_deadline")]

    def __str__(self):
        return self.case_no


class ArbitrationEvidence(TimeStampedModel):
    class Party(models.TextChoices):
        USER = "USER", "用户"
        MERCHANT = "MERCHANT", "商户"
        PLATFORM = "PLATFORM", "平台"

    case = models.ForeignKey(ArbitrationCase, on_delete=models.CASCADE, related_name="evidences", verbose_name="仲裁案")
    party = models.CharField("提交方", max_length=16, choices=Party.choices)
    file_url = models.URLField("材料地址")
    note = models.CharField("说明", max_length=200, blank=True, default="")

    class Meta:
        verbose_name = "仲裁举证"
        verbose_name_plural = "仲裁举证"
        db_table = "arbitration_evidence"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["case", "party"], name="ix_arb_evid_case_party")]

    def __str__(self):
        return f"{self.case_id}-{self.party}"
