"""支付单、退款单与平台支付配置。

微信商户号、APIv3 密钥与证书由平台 PC 后台维护，密钥字段加密存储（T2）；
P0 只做内部记账，不做真实渠道联调。
"""

from django.conf import settings
from django.db import models

from apps.common.fields import EncryptedTextField
from apps.common.models import TimeStampedModel
from apps.common.utils import generate_no


def default_payment_no() -> str:
    return generate_no("P")


def default_refund_no() -> str:
    return generate_no("R")


class PaymentOrder(TimeStampedModel):
    class Channel(models.TextChoices):
        WECHAT_MINI = "WECHAT_MINI", "微信小程序"
        WECHAT_H5 = "WECHAT_H5", "微信 H5"

    class Status(models.TextChoices):
        CREATED = "CREATED", "已创建"
        PAYING = "PAYING", "支付中"
        PAID = "PAID", "已支付"
        REFUNDING = "REFUNDING", "退款中"
        PARTIAL_REFUNDED = "PARTIAL_REFUNDED", "部分退款"
        REFUNDED = "REFUNDED", "已全额退款"
        CLOSED = "CLOSED", "已关闭"

    payment_no = models.CharField("支付单号", max_length=32, unique=True, default=default_payment_no)
    order = models.ForeignKey("orders.Order", on_delete=models.PROTECT, related_name="payments", verbose_name="订单")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payments", verbose_name="用户"
    )
    channel = models.CharField("支付渠道", max_length=16, choices=Channel.choices)
    amount = models.BigIntegerField("支付金额（分）")
    status = models.CharField("状态", max_length=20, choices=Status.choices, default=Status.CREATED, db_index=True)
    prepay_id = models.CharField("预支付 ID", max_length=64, blank=True, default="")
    transaction_id = models.CharField("微信交易号", max_length=64, unique=True, null=True, blank=True)
    idempotency_key = models.CharField("幂等键", max_length=64, unique=True)
    paid_at = models.DateTimeField("支付成功时间", null=True, blank=True)
    expire_at = models.DateTimeField("支付超时时间", null=True, blank=True)
    raw_callback = models.JSONField("回调原文（脱敏）", default=dict, blank=True)

    class Meta:
        verbose_name = "支付单"
        verbose_name_plural = "支付单"
        db_table = "payment_order"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["order", "status"], name="ix_payment_order_order_status"),
            models.Index(fields=["status", "created_at"], name="ix_payment_status_created"),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(amount__gt=0), name="ck_payment_amount_positive"),
        ]

    def __str__(self):
        return self.payment_no


class RefundOrder(TimeStampedModel):
    class Status(models.TextChoices):
        REQUESTED = "REQUESTED", "已申请"
        PROCESSING = "PROCESSING", "退款中"
        SUCCESS = "SUCCESS", "退款成功"
        FAILED = "FAILED", "退款失败"

    refund_no = models.CharField("退款单号", max_length=32, unique=True, default=default_refund_no)
    order = models.ForeignKey("orders.Order", on_delete=models.PROTECT, related_name="refunds", verbose_name="订单")
    payment = models.ForeignKey(PaymentOrder, on_delete=models.PROTECT, related_name="refunds", verbose_name="支付单")
    after_sale = models.ForeignKey(
        "aftersales.AfterSale",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="refunds",
        verbose_name="售后单",
    )
    amount = models.BigIntegerField("退款金额（分）")
    reason = models.CharField("退款原因", max_length=200, blank=True, default="")
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.REQUESTED, db_index=True)
    transaction_id = models.CharField("微信退款单号", max_length=64, unique=True, null=True, blank=True)
    refunded_at = models.DateTimeField("退款成功时间", null=True, blank=True)
    fail_reason = models.CharField("失败原因", max_length=200, blank=True, default="")
    raw_callback = models.JSONField("回调原文（脱敏）", default=dict, blank=True)

    class Meta:
        verbose_name = "退款单"
        verbose_name_plural = "退款单"
        db_table = "refund_order"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["order", "status"], name="ix_refund_order_order_status"),
            models.Index(fields=["status", "created_at"], name="ix_refund_status_created"),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(amount__gt=0), name="ck_refund_amount_positive"),
        ]

    def __str__(self):
        return self.refund_no


class PlatformPaymentConfig(TimeStampedModel):
    """平台支付渠道配置：由 PC 后台维护，密钥与证书加密存储（T2）。

    每个渠道仅一条启用配置；历史变更通过 operation_log 审计。
    """

    channel = models.CharField("支付渠道", max_length=16, choices=PaymentOrder.Channel.choices, unique=True)
    merchant_no = models.CharField("商户号", max_length=32)
    app_id = models.CharField("应用 ID", max_length=32, blank=True, default="")
    api_v3_key = EncryptedTextField("APIv3 密钥")
    cert_serial_no = models.CharField("证书序列号", max_length=64, blank=True, default="")
    private_key = EncryptedTextField("商户私钥 PEM")
    platform_cert = EncryptedTextField("平台证书 PEM")
    notify_url = models.URLField("支付回调地址", blank=True, default="")
    enabled = models.BooleanField("启用", default=False)
    updated_by_id = models.BigIntegerField("最后修改人 ID", null=True, blank=True)
    updated_by_name = models.CharField("最后修改人", max_length=60, blank=True, default="")

    class Meta:
        verbose_name = "平台支付配置"
        verbose_name_plural = "平台支付配置"
        db_table = "platform_payment_config"
        ordering = ("channel",)

    def __str__(self):
        return f"{self.get_channel_display()}({self.merchant_no})"
