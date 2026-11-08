from django.contrib import admin

from apps.common.admin import BaseAdmin

from .models import AfterSale, ArbitrationCase, ArbitrationEvidence


class ArbitrationEvidenceInline(admin.TabularInline):
    model = ArbitrationEvidence
    extra = 0
    fields = ("party", "file_url", "note")


@admin.register(AfterSale)
class AfterSaleAdmin(BaseAdmin):
    list_display = (
        "id",
        "after_sale_no",
        "order",
        "merchant",
        "type",
        "request_amount",
        "approved_amount",
        "status",
        "deadline_at",
    )
    list_filter = ("status", "type", "merchant")
    search_fields = ("after_sale_no", "order__order_no", "user__phone")
    raw_id_fields = ("order", "order_item", "user", "merchant", "arbitration_case")


@admin.register(ArbitrationCase)
class ArbitrationCaseAdmin(BaseAdmin):
    list_display = ("id", "case_no", "after_sale", "amount", "status", "liability", "deadline_at")
    list_filter = ("status", "liability")
    search_fields = ("case_no", "after_sale__after_sale_no")
    raw_id_fields = ("after_sale",)
    inlines = (ArbitrationEvidenceInline,)


@admin.register(ArbitrationEvidence)
class ArbitrationEvidenceAdmin(BaseAdmin):
    list_display = ("id", "case", "party", "file_url", "created_at")
    list_filter = ("party",)
    raw_id_fields = ("case",)
