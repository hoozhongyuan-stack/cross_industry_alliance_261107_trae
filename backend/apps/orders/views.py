from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common.api import (
    ApiError,
    EnvelopeAPIView,
    EnvelopeExceptionMixin,
    EnvelopeResponse,
    ok,
)
from apps.common.utils import payload_hash
from apps.payments.services import create_payment

from .cart_services import add_cart_item, delete_cart_item, serialize_cart, update_cart_item
from .models import Order
from .order_services import cancel_order, create_order
from .serializers import (
    CancelInputSerializer,
    CartItemInputSerializer,
    CartItemPatchSerializer,
    CartSerializer,
    OrderContractSerializer,
    OrderCreateInputSerializer,
    OrderDetailSerializer,
    OrderListSerializer,
    PayInputSerializer,
)


class MyOrderViewSet(EnvelopeExceptionMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """当前登录用户的订单（列表 / 创建 / 详情）。商户端与平台端后续按角色扩展。"""

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

    @extend_schema(tags=["order"], request=OrderCreateInputSerializer, responses=EnvelopeResponse)
    def create(self, request):
        idempotency_key = request.headers.get("Idempotency-Key", "").strip()
        if not idempotency_key:
            raise ApiError("VALIDATION_ERROR", "缺少 Idempotency-Key", 422)
        serializer = OrderCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = dict(serializer.validated_data)
        order, created = create_order(
            request.user,
            idempotency_key=idempotency_key,
            request_hash=payload_hash(payload),
            **payload,
        )
        return ok(
            request,
            OrderContractSerializer(order).data,
            status_code=201 if created else 200,
        )


@extend_schema(tags=["order"], responses=EnvelopeResponse)
class OrderPayView(EnvelopeAPIView):
    """发起支付（Mock 微信统一下单）。"""

    permission_classes = [IsAuthenticated]
    serializer_class = PayInputSerializer

    def post(self, request, pk):
        idempotency_key = request.headers.get("Idempotency-Key", "").strip()
        if not idempotency_key:
            raise ApiError("VALIDATION_ERROR", "缺少 Idempotency-Key", 422)
        serializer = PayInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment, pay_params = create_payment(request.user, pk, serializer.validated_data["channel"], idempotency_key)
        return ok(
            request,
            {
                "payment_no": payment.payment_no,
                "prepay_id": payment.prepay_id,
                "pay_params": pay_params,
                "expire_at": payment.expire_at.isoformat() if payment.expire_at else None,
            },
        )


@extend_schema(tags=["order"], responses=EnvelopeResponse)
class OrderCancelView(EnvelopeAPIView):
    """取消待支付订单，释放库存与预约时段。"""

    permission_classes = [IsAuthenticated]
    serializer_class = CancelInputSerializer

    def post(self, request, pk):
        serializer = CancelInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = cancel_order(request.user, pk, serializer.validated_data.get("reason", ""))
        return ok(request, OrderContractSerializer(order).data)


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
