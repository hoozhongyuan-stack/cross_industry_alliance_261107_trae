from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.api import EnvelopeAPIView, EnvelopeResponse, ok

from .models import AppUser, UserAddress
from .serializers import (
    AddressInputSerializer,
    AddressSerializer,
    AppUserSerializer,
    MeSerializer,
    SmsLoginSerializer,
    SmsSendSerializer,
    WechatLoginSerializer,
)
from .services import issue_tokens, login_with_sms, login_with_wechat, send_sms_code


class MeView(APIView):
    """当前登录用户与所属商户身份。"""

    permission_classes = [IsAuthenticated]
    serializer_class = MeSerializer

    def get(self, request):
        user = request.user
        staff_roles = list(
            user.merchant_staff_roles.filter(status="ACTIVE")
            .annotate(merchant_name=F("merchant__name"))
            .values("merchant_id", "merchant_name", "role")
        )
        data = MeSerializer(user).data
        data["merchant_roles"] = staff_roles
        data["is_staff"] = user.is_staff
        return Response(data)


class StaffListView(APIView):
    """仅平台后台可用：用户列表（按手机号 / 昵称检索）。"""

    permission_classes = [IsAuthenticated]
    serializer_class = AppUserSerializer

    def get(self, request):
        if not request.user.is_staff:
            return Response({"detail": "需要平台后台权限"}, status=403)
        keyword = request.query_params.get("keyword", "").strip()
        qs = AppUser.objects.all().order_by("-created_at")
        if keyword:
            qs = qs.filter(phone__contains=keyword) | qs.filter(nickname__contains=keyword)
        return Response(AppUserSerializer(qs[:50], many=True).data)


@extend_schema(tags=["auth"], responses=EnvelopeResponse)
class WechatLoginView(EnvelopeAPIView):
    """小程序登录：Mock 阶段 code 换 openid/unionid。"""

    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = WechatLoginSerializer

    def post(self, request):
        serializer = WechatLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = login_with_wechat(**serializer.validated_data)
        return ok(request, issue_tokens(user))


@extend_schema(tags=["auth"], responses=EnvelopeResponse)
class SmsSendView(EnvelopeAPIView):
    """发送短信验证码；Mock 模式返回 debug_code。"""

    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = SmsSendSerializer

    def post(self, request):
        serializer = SmsSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = send_sms_code(**serializer.validated_data)
        return ok(request, data)


@extend_schema(tags=["auth"], responses=EnvelopeResponse)
class SmsLoginView(EnvelopeAPIView):
    """H5 手机号验证码登录。"""

    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = SmsLoginSerializer

    def post(self, request):
        serializer = SmsLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = login_with_sms(**serializer.validated_data)
        return ok(request, issue_tokens(user))


@extend_schema(tags=["consumer"], responses=EnvelopeResponse)
class AddressListCreateView(EnvelopeAPIView):
    """收货地址列表与新增。"""

    permission_classes = [IsAuthenticated]
    serializer_class = AddressSerializer

    def get(self, request):
        addresses = UserAddress.objects.filter(user=request.user)
        return ok(request, AddressSerializer(addresses, many=True).data)

    @transaction.atomic
    def post(self, request):
        serializer = AddressInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        if payload.get("is_default"):
            UserAddress.objects.filter(user=request.user).update(is_default=False)
        address = UserAddress.objects.create(user=request.user, **payload)
        return ok(request, AddressSerializer(address).data, status_code=201)


@extend_schema(tags=["consumer"], responses=EnvelopeResponse)
class AddressDetailView(EnvelopeAPIView):
    """收货地址修改与删除。"""

    permission_classes = [IsAuthenticated]
    serializer_class = AddressSerializer

    def _get_address(self, request, pk):
        return get_object_or_404(UserAddress, pk=pk, user=request.user)

    @transaction.atomic
    def patch(self, request, pk):
        address = self._get_address(request, pk)
        serializer = AddressInputSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        if payload.get("is_default"):
            UserAddress.objects.filter(user=request.user).exclude(pk=address.pk).update(is_default=False)
        for field, value in payload.items():
            setattr(address, field, value)
        address.save()
        return ok(request, AddressSerializer(address).data)

    @extend_schema(responses={204: None})
    def delete(self, request, pk):
        address = self._get_address(request, pk)
        address.delete()
        return Response(status=204)
