"""履约：配送/自提信息、核销码、服务预约。核销是服务订单完成的唯一凭证。"""

from django.db import models

from apps.common.models import TimeStampedModel


class OrderDelivery(TimeStampedModel):
    class Type(models.TextChoices):
        EXPRESS = "EXPRESS", "快递"
        PICKUP = "PICKUP", "自提"

    order = models.OneToOneField("orders.Order", on_delete=models.CASCADE, related_name="delivery", verbose_name="订单")
    type = models.CharField("配送方式", max_length=16, choices=Type.choices)
    address_snapshot = models.JSONField("地址快照", default=dict, blank=True)
    receiver_name = models.CharField("收货人", max_length=40, blank=True, default="")
    receiver_phone = models.CharField("收货电话", max_length=20, blank=True, default="")
    logistics_company = models.CharField("物流公司", max_length=40, blank=True, default="")
    logistics_no = models.CharField("物流单号", max_length=64, blank=True, default="")
    pickup_code = models.CharField("提货码", max_length=12, blank=True, default="")
    shipped_at = models.DateTimeField("发货时间", null=True, blank=True)
    received_at = models.DateTimeField("签收时间", null=True, blank=True)

    class Meta:
        verbose_name = "订单配送信息"
        verbose_name_plural = "订单配送信息"
        db_table = "order_delivery"

    def __str__(self):
        return f"{self.order_id}-{self.type}"


class VerifyCode(TimeStampedModel):
    class Type(models.TextChoices):
        VERIFY = "VERIFY", "核销码"
        PICKUP = "PICKUP", "提货码"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "有效"
        USED = "USED", "已核销"
        EXPIRED = "EXPIRED", "已过期"
        INVALID = "INVALID", "已作废"

    order = models.ForeignKey(
        "orders.Order", on_delete=models.CASCADE, related_name="verify_codes", verbose_name="订单"
    )
    merchant = models.ForeignKey(
        "merchants.Merchant", on_delete=models.PROTECT, related_name="verify_codes", verbose_name="商户"
    )
    code = models.CharField("核销码", max_length=20, unique=True)
    type = models.CharField("类型", max_length=16, choices=Type.choices, default=Type.VERIFY)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    valid_from = models.DateTimeField("生效时间", null=True, blank=True)
    valid_to = models.DateTimeField("失效时间", null=True, blank=True)
    used_at = models.DateTimeField("核销时间", null=True, blank=True)
    used_by_id = models.BigIntegerField("核销人 ID", null=True, blank=True)
    used_by_name = models.CharField("核销人", max_length=60, blank=True, default="")

    class Meta:
        verbose_name = "核销码"
        verbose_name_plural = "核销码"
        db_table = "verify_code"
        indexes = [
            models.Index(fields=["order", "status"], name="ix_verify_code_order_status"),
            models.Index(fields=["merchant", "status"], name="ix_verify_code_merchant_status"),
        ]

    def __str__(self):
        return f"{self.code}({self.status})"


class Appointment(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING_CONFIRM = "PENDING_CONFIRM", "待确认"
        CONFIRMED = "CONFIRMED", "已确认"
        COMPLETED = "COMPLETED", "已完成"
        CANCELLED = "CANCELLED", "已取消"
        NO_SHOW = "NO_SHOW", "爽约"

    order = models.OneToOneField(
        "orders.Order", on_delete=models.CASCADE, related_name="appointment", verbose_name="订单"
    )
    slot = models.ForeignKey(
        "catalog.ServiceSlot", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="时段"
    )
    slot_date = models.DateField("预约日期")
    start_time = models.TimeField("开始时间")
    end_time = models.TimeField("结束时间")
    status = models.CharField(
        "状态", max_length=20, choices=Status.choices, default=Status.PENDING_CONFIRM, db_index=True
    )
    confirmed_at = models.DateTimeField("确认时间", null=True, blank=True)
    canceled_at = models.DateTimeField("取消时间", null=True, blank=True)
    remark = models.CharField("备注", max_length=120, blank=True, default="")

    class Meta:
        verbose_name = "预约"
        verbose_name_plural = "预约"
        db_table = "appointment"
        indexes = [models.Index(fields=["slot_date", "status"], name="ix_appointment_date_status")]

    def __str__(self):
        return f"{self.order_id}-{self.slot_date}"
