from rest_framework import serializers

from .models import AppUser, UserAddress, UserIdentity


class UserIdentitySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserIdentity
        fields = ("channel", "open_id", "union_id")


class AppUserSerializer(serializers.ModelSerializer):
    identities = UserIdentitySerializer(many=True, read_only=True)

    class Meta:
        model = AppUser
        fields = ("id", "phone", "nickname", "avatar_url", "gender", "status", "identities", "created_at")
        read_only_fields = fields


class MerchantRoleSerializer(serializers.Serializer):
    merchant_id = serializers.IntegerField()
    merchant_name = serializers.CharField()
    role = serializers.CharField()


class MeSerializer(AppUserSerializer):
    merchant_roles = MerchantRoleSerializer(many=True, read_only=True)
    is_staff = serializers.BooleanField()

    class Meta(AppUserSerializer.Meta):
        fields = AppUserSerializer.Meta.fields + ("merchant_roles", "is_staff")
        read_only_fields = fields


class WechatLoginSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=64)
    channel = serializers.ChoiceField(choices=["WECHAT_MINI", "WECHAT_H5"], default="WECHAT_MINI")


class SmsSendSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    scene = serializers.ChoiceField(choices=["LOGIN", "ORDER_NOTICE"], default="LOGIN")


class SmsLoginSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    sms_code = serializers.CharField(min_length=4, max_length=8)
    union_id = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")


class AddressInputSerializer(serializers.Serializer):
    receiver_name = serializers.CharField(max_length=40)
    phone = serializers.CharField(max_length=20)
    province = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    city = serializers.CharField(max_length=32)
    district = serializers.CharField(max_length=32)
    detail = serializers.CharField(max_length=120)
    lng = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)
    lat = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)
    tag = serializers.ChoiceField(choices=["HOME", "COMPANY", "OTHER"], default="OTHER")
    is_default = serializers.BooleanField(default=False)


class AddressSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(read_only=True, format=None)

    class Meta:
        model = UserAddress
        fields = (
            "id",
            "receiver_name",
            "phone",
            "province",
            "city",
            "district",
            "detail",
            "lng",
            "lat",
            "tag",
            "is_default",
            "created_at",
        )
        read_only_fields = fields
