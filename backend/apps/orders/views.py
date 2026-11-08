from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Order
from .serializers import OrderDetailSerializer, OrderListSerializer


class MyOrderViewSet(viewsets.ReadOnlyModelViewSet):
    """当前登录用户的订单（列表 / 详情）。商户端与平台端后续按角色扩展。"""

    permission_classes = [IsAuthenticated]
    queryset = Order.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Order.objects.none()
        return (
            Order.objects.filter(user=self.request.user)
            .select_related("merchant")
            .prefetch_related("items", "verify_codes", "status_logs")
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        if self.action == "list":
            return OrderListSerializer
        return OrderDetailSerializer

    filterset_fields = ("status", "merchant", "order_type")
    search_fields = ("order_no",)
