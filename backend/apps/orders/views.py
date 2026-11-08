from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common.api import EnvelopeAPIView, EnvelopeResponse, ok

from .cart_services import add_cart_item, delete_cart_item, serialize_cart, update_cart_item
from .models import Order
from .serializers import (
    CartItemInputSerializer,
    CartItemPatchSerializer,
    CartSerializer,
    OrderDetailSerializer,
    OrderListSerializer,
)


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


@extend_schema(tags=["cart"], responses=EnvelopeResponse)
class CartView(EnvelopeAPIView):
    """当前用户购物车（单店）。"""

    permission_classes = [IsAuthenticated]
    serializer_class = CartSerializer

    def get(self, request):
        return ok(request, serialize_cart(request.user))


@extend_schema(tags=["cart"], responses=EnvelopeResponse)
class CartItemCreateView(EnvelopeAPIView):
    """加入购物车；同商品同规格累加。"""

    permission_classes = [IsAuthenticated]
    serializer_class = CartItemInputSerializer

    def post(self, request):
        serializer = CartItemInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        add_cart_item(request.user, **serializer.validated_data)
        return ok(request, serialize_cart(request.user))


@extend_schema(tags=["cart"], responses=EnvelopeResponse)
class CartItemDetailView(EnvelopeAPIView):
    """修改数量/选中状态或移出购物车。"""

    permission_classes = [IsAuthenticated]
    serializer_class = CartItemPatchSerializer

    def patch(self, request, pk):
        serializer = CartItemPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        update_cart_item(request.user, pk, **serializer.validated_data)
        return ok(request, serialize_cart(request.user))

    @extend_schema(responses={204: None})
    def delete(self, request, pk):
        delete_cart_item(request.user, pk)
        return Response(status=204)
