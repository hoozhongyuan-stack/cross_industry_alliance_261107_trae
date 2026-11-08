from rest_framework import serializers

from .models import AppUser, UserIdentity


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
