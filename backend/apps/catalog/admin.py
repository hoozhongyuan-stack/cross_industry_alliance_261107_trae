from django.contrib import admin

from apps.common.admin import BaseAdmin

from .models import Category, Product, ProductSku, ServiceSlot, ServiceSlotTemplate


@admin.register(Category)
class CategoryAdmin(BaseAdmin):
    list_display = ("id", "name", "parent", "level", "sort", "status", "commission_rate")
    list_filter = ("status", "level")
    search_fields = ("name",)
    list_editable = ("sort", "status")


class ProductSkuInline(admin.TabularInline):
    model = ProductSku
    extra = 1
    fields = ("sku_code", "price", "stock", "locked_stock", "sold_stock", "spec_json", "version")


class ServiceSlotInline(admin.TabularInline):
    model = ServiceSlot
    extra = 0
    fields = ("slot_date", "start_time", "end_time", "capacity", "reserved_count", "status")


@admin.register(Product)
class ProductAdmin(BaseAdmin):
    list_display = ("id", "title", "merchant", "category", "type", "price", "status", "sold_count")
    list_filter = ("status", "type", "merchant")
    search_fields = ("title", "merchant__name")
    autocomplete_fields = ("merchant",)
    inlines = (ProductSkuInline, ServiceSlotInline)


@admin.register(ProductSku)
class ProductSkuAdmin(BaseAdmin):
    list_display = ("id", "product", "sku_code", "price", "stock", "locked_stock", "sold_stock")
    search_fields = ("sku_code", "product__title")
    raw_id_fields = ("product",)


@admin.register(ServiceSlotTemplate)
class ServiceSlotTemplateAdmin(BaseAdmin):
    list_display = ("id", "product", "weekday", "start_time", "end_time", "capacity", "enabled")
    list_filter = ("weekday", "enabled")
    raw_id_fields = ("product",)


@admin.register(ServiceSlot)
class ServiceSlotAdmin(BaseAdmin):
    list_display = ("id", "product", "slot_date", "start_time", "end_time", "capacity", "reserved_count", "status")
    list_filter = ("status", "slot_date")
    raw_id_fields = ("product",)
