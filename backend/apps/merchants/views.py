from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from .models import Merchant
from .serializers import MerchantSerializer


class MerchantViewSet(viewsets.ReadOnlyModelViewSet):
    """消费者端门店浏览：只暴露营业中的商户。"""

    queryset = Merchant.objects.filter(status=Merchant.Status.ACTIVE).select_related("category").order_by("-created_at")
    serializer_class = MerchantSerializer
    authentication_classes = []
    permission_classes = [AllowAny]
    filterset_fields = ("category", "city", "district")
    search_fields = ("name", "short_name")
