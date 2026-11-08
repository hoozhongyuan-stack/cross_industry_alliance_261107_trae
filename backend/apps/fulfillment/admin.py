from django.contrib import admin

from apps.common.admin import BaseAdmin

from .models import Appointment, OrderDelivery, VerifyCode


@admin.register(OrderDelivery)
class OrderDeliveryAdmin(BaseAdmin):
    list_display = ("id", "order", "type", "logistics_company", "logistics_no", "shipped_at", "received_at")
    list_filter = ("type",)
    raw_id_fields = ("order",)


@admin.register(VerifyCode)
class VerifyCodeAdmin(BaseAdmin):
    list_display = ("id", "code", "order", "merchant", "type", "status", "valid_to", "used_at")
    list_filter = ("status", "type", "merchant")
    search_fields = ("code", "order__order_no")
    raw_id_fields = ("order", "merchant")


@admin.register(Appointment)
class AppointmentAdmin(BaseAdmin):
    list_display = ("id", "order", "slot_date", "start_time", "status", "confirmed_at")
    list_filter = ("status", "slot_date")
    raw_id_fields = ("order", "slot")
