from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from .models import Category, Product
from .serializers import CategorySerializer, ProductListSerializer, ProductSerializer


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.filter(status=Category.Status.ENABLED).order_by("sort", "id")
    serializer_class = CategorySerializer
    authentication_classes = []
    permission_classes = [AllowAny]
    pagination_class = None


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """消费者端商品浏览：只暴露在售商品。"""

    queryset = (
        Product.objects.filter(status=Product.Status.ON_SALE)
        .select_related("merchant", "category")
        .prefetch_related("skus")
        .order_by("-sort", "-created_at")
    )
    authentication_classes = []
    permission_classes = [AllowAny]
    filterset_fields = ("merchant", "category", "type")
    search_fields = ("title", "subtitle")
    ordering_fields = ("price", "sold_count", "created_at")

    def get_serializer_class(self):
        if self.action == "list":
            return ProductListSerializer
        return ProductSerializer
