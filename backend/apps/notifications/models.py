"""通知记录与 Outbox 可靠事件。

业务事务内只写 outbox_event；发送器按 next_retry_at 拉取，成功后置 PUBLISHED。
"""

from django.db import models

from apps.common.models import TimeStampedModel


class Notification(TimeStampedModel):
    class RecipientType(models.TextChoices):
        USER = "USER", "用户"
        MERCHANT = "MERCHANT", "商户"
        STAFF = "STAFF", "平台员工"

    class Channel(models.TextChoices):
        WECHAT = "WECHAT", "微信订阅消息"
        SMS = "SMS", "短信"
        IN_APP = "IN_APP", "站内信"

    class Status(models.TextChoices):
        PENDING = "PENDING", "待发送"
        SENT = "SENT", "已发送"
        FAILED = "FAILED", "发送失败"
        READ = "READ", "已读"

    recipient_type = models.CharField("接收方类型", max_length=16, choices=RecipientType.choices)
    recipient_id = models.BigIntegerField("接收方 ID", db_index=True)
    channel = models.CharField("渠道", max_length=16, choices=Channel.choices)
    template_id = models.CharField("模板 ID", max_length=64, blank=True, default="")
    title = models.CharField("标题", max_length=80, blank=True, default="")
    payload = models.JSONField("参数", default=dict, blank=True)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    sent_at = models.DateTimeField("发送时间", null=True, blank=True)
    read_at = models.DateTimeField("阅读时间", null=True, blank=True)
    fail_reason = models.CharField("失败原因", max_length=200, blank=True, default="")

    class Meta:
        verbose_name = "通知"
        verbose_name_plural = "通知"
        db_table = "notification"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["recipient_type", "recipient_id", "created_at"], name="ix_notification_recipient")
        ]

    def __str__(self):
        return f"{self.recipient_type}-{self.recipient_id}-{self.title}"


class OutboxEvent(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "待发送"
        PROCESSING = "PROCESSING", "发送中"
        PUBLISHED = "PUBLISHED", "已发送"
        FAILED = "FAILED", "失败待重试"
        DEAD = "DEAD", "已放弃"

    aggregate_type = models.CharField("聚合类型", max_length=24, db_index=True)
    aggregate_id = models.BigIntegerField("聚合 ID", db_index=True)
    event_type = models.CharField("事件类型", max_length=40, db_index=True)
    payload = models.JSONField("事件载荷", default=dict, blank=True)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    retry_count = models.PositiveSmallIntegerField("重试次数", default=0)
    next_retry_at = models.DateTimeField("下次重试时间", null=True, blank=True, db_index=True)
    last_error = models.CharField("最近错误", max_length=200, blank=True, default="")
    published_at = models.DateTimeField("发送成功时间", null=True, blank=True)

    class Meta:
        verbose_name = "Outbox 事件"
        verbose_name_plural = "Outbox 事件"
        db_table = "outbox_event"
        ordering = ("created_at",)
        indexes = [models.Index(fields=["status", "next_retry_at"], name="ix_outbox_status_retry")]

    def __str__(self):
        return f"{self.aggregate_type}-{self.aggregate_id}-{self.event_type}"
