from django.db.models import F
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AppUser
from .serializers import AppUserSerializer, MeSerializer


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
