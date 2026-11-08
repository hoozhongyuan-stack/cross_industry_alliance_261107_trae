from django.contrib import admin

from apps.common.admin import BaseAdmin

from .models import Merchant, MerchantQualification, MerchantStaff


class MerchantStaffInline(admin.TabularInline):
    model = MerchantStaff
    extra = 0
    fields = ("user", "role", "status", "joined_at")
    raw_id_fields = ("user",)


class MerchantQualificationInline(admin.TabularInline):
    model = MerchantQualification
    extra = 0
    fields = ("type", "file_url", "expire_at", "audit_status", "reject_reason")


@admin.register(Merchant)
class MerchantAdmin(BaseAdmin):
    list_display = (
        "id",
        "merchant_no",
        "name",
        "category",
        "city",
        "status",
        "commission_rate",
        "settlement_cycle_days",
    )
    list_filter = ("status", "category", "city")
    search_fields = ("merchant_no", "name", "contact_phone")
    inlines = (MerchantStaffInline, MerchantQualificationInline)


@admin.register(MerchantStaff)
class MerchantStaffAdmin(BaseAdmin):
    list_display = ("id", "merchant", "user", "role", "status", "joined_at")
    list_filter = ("role", "status")
    raw_id_fields = ("merchant", "user")


@admin.register(MerchantQualification)
class MerchantQualificationAdmin(BaseAdmin):
    list_display = ("id", "merchant", "type", "expire_at", "audit_status")
    list_filter = ("type", "audit_status")
    raw_id_fields = ("merchant",)
