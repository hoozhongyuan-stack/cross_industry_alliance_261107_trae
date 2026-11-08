from rest_framework import serializers

from .models import Category, Product, ProductSku, ServiceSlot


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "parent", "name", "icon_url", "level", "sort")


class ProductSkuSerializer(serializers.ModelSerializer):
    available_stock = serializers.IntegerField(read_only=True)

    class Meta:
        model = ProductSku
        fields = ("id", "sku_code", "spec_json", "price", "available_stock")


class ServiceSlotSerializer(serializers.ModelSerializer):
    remaining = serializers.IntegerField(read_only=True)

    class Meta:
        model = ServiceSlot
        fields = ("id", "slot_date", "start_time", "end_time", "capacity", "remaining", "status")


class ProductSerializer(serializers.ModelSerializer):
    merchant_name = serializers.CharField(source="merchant.name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True, default="")
    type_label = serializers.CharField(source="get_type_display", read_only=True)
    skus = ProductSkuSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "merchant_id",
            "merchant_name",
            "category_id",
            "category_name",
            "type",
            "type_label",
            "title",
            "subtitle",
            "cover_url",
            "images",
            "description",
            "price",
            "original_price",
            "status",
            "verify_days",
            "appointment_required",
            "delivery_types",
            "sold_count",
            "skus",
        )


class ProductListSerializer(serializers.ModelSerializer):
    merchant_name = serializers.CharField(source="merchant.name", read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "merchant_id",
            "merchant_name",
            "type",
            "title",
            "subtitle",
            "cover_url",
            "price",
            "original_price",
            "sold_count",
            "delivery_types",
        )
