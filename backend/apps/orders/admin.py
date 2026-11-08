from django.contrib import admin

from apps.common.admin import BaseAdmin

from .models import CartItem, Order, OrderItem, OrderReview, OrderStatusLog


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = ("product", "sku", "title", "price", "quantity", "amount", "refund_amount")
    readonly_fields = ("price", "amount", "refund_amount")


class OrderStatusLogInline(admin.TabularInline):
    model = OrderStatusLog
    extra = 0
    can_delete = False
    fields = ("from_status", "to_status", "event", "operator_type", "operator_name", "reason", "created_at")
    readonly_fields = fields


@admin.register(Order)
class OrderAdmin(BaseAdmin):
    list_display = (
        "id",
        "order_no",
        "user",
        "merchant",
        "order_type",
        "status",
        "payable_amount",
        "paid_amount",
        "created_at",
    )
    list_filter = ("status", "order_type", "merchant")
    search_fields = ("order_no", "user__phone", "merchant__name")
    raw_id_fields = ("user", "merchant")
    inlines = (OrderItemInline, OrderStatusLogInline)
    readonly_fields = ("order_no", "version")


@admin.register(OrderItem)
class OrderItemAdmin(BaseAdmin):
    list_display = ("id", "order", "title", "price", "quantity", "amount", "refund_amount")
    search_fields = ("order__order_no", "title")
    raw_id_fields = ("order", "product", "sku")


@admin.register(OrderStatusLog)
class OrderStatusLogAdmin(BaseAdmin):
    list_display = ("id", "order", "from_status", "to_status", "event", "operator_type", "created_at")
    list_filter = ("operator_type", "to_status")
    search_fields = ("order__order_no",)
    raw_id_fields = ("order",)


@admin.register(OrderReview)
class OrderReviewAdmin(BaseAdmin):
    list_display = ("id", "order", "user", "merchant", "score", "status", "created_at")
    list_filter = ("status", "score")
    raw_id_fields = ("order", "user", "merchant")


@admin.register(CartItem)
class CartItemAdmin(BaseAdmin):
    list_display = ("id", "user", "merchant", "product", "sku", "quantity", "selected", "created_at")
    list_filter = ("selected", "merchant")
    search_fields = ("user__phone", "product__title")
    raw_id_fields = ("user", "merchant", "product", "sku")
