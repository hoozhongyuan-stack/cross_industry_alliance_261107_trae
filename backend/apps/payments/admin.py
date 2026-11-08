from django.contrib import admin

from apps.common.admin import BaseAdmin

from .models import PaymentOrder, PlatformPaymentConfig, RefundOrder


@admin.register(PaymentOrder)
class PaymentOrderAdmin(BaseAdmin):
    list_display = ("id", "payment_no", "order", "channel", "amount", "status", "transaction_id", "paid_at")
    list_filter = ("status", "channel")
    search_fields = ("payment_no", "transaction_id", "order__order_no")
    raw_id_fields = ("order", "user")


@admin.register(RefundOrder)
class RefundOrderAdmin(BaseAdmin):
    list_display = ("id", "refund_no", "order", "payment", "amount", "status", "refunded_at", "fail_reason")
    list_filter = ("status",)
    search_fields = ("refund_no", "transaction_id", "order__order_no")
    raw_id_fields = ("order", "payment", "after_sale")


@admin.register(PlatformPaymentConfig)
class PlatformPaymentConfigAdmin(BaseAdmin):
    """密钥与证书字段在数据库内加密；后台仅授权角色可访问。"""

    list_display = ("id", "channel", "merchant_no", "app_id", "enabled", "updated_by_name", "updated_at")
    list_filter = ("channel", "enabled")
    search_fields = ("merchant_no", "app_id")
    readonly_fields = ("created_at", "updated_at", "updated_by_id", "updated_by_name")
