from django.contrib import admin

from apps.common.admin import BaseAdmin

from .models import Notification, OutboxEvent


@admin.register(Notification)
class NotificationAdmin(BaseAdmin):
    list_display = ("id", "recipient_type", "recipient_id", "channel", "title", "status", "sent_at")
    list_filter = ("recipient_type", "channel", "status")
    search_fields = ("recipient_id", "title")


@admin.register(OutboxEvent)
class OutboxEventAdmin(BaseAdmin):
    list_display = (
        "id",
        "aggregate_type",
        "aggregate_id",
        "event_type",
        "status",
        "retry_count",
        "next_retry_at",
        "published_at",
    )
    list_filter = ("status", "event_type")
    search_fields = ("aggregate_type", "aggregate_id", "event_type")
