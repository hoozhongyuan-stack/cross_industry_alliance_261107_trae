"""健康检查：不依赖鉴权，用于部署探针。"""

from django.db import connections
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.serializers import CharField, Serializer
from rest_framework.views import APIView


class HealthSerializer(Serializer):
    status = CharField()
    service = CharField()
    time = CharField()
    db = CharField()


class HealthView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = HealthSerializer

    def get(self, request):
        payload = {
            "status": "ok",
            "service": "alliance-mall-api",
            "time": timezone.localtime().isoformat(),
        }
        try:
            connections["default"].cursor()
        except Exception as exc:  # pragma: no cover - 仅在数据库不可用时触发
            payload["status"] = "degraded"
            payload["db"] = "error"
            payload["detail"] = str(exc)
            return Response(payload, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        payload["db"] = "ok"
        return Response(payload)
