from rest_framework import serializers

from .models import Merchant


class MerchantSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True, default="")

    class Meta:
        model = Merchant
        fields = (
            "id",
            "merchant_no",
            "name",
            "short_name",
            "category_id",
            "category_name",
            "logo_url",
            "description",
            "contact_phone",
            "city",
            "district",
            "address",
            "lng",
            "lat",
            "business_hours",
            "status",
            "opened_at",
        )
