from django.contrib import admin

from apps.common.admin import BaseAdmin

from .models import PaymentOrder, RefundOrder


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
