from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    CartItemCreateView,
    CartItemDetailView,
    CartView,
    MyOrderViewSet,
    OrderCancelView,
    OrderPayView,
)

router = DefaultRouter()
router.register("orders", MyOrderViewSet, basename="my-order")

urlpatterns = router.urls + [
    path("orders/<int:pk>/pay/", OrderPayView.as_view(), name="order-pay"),
    path("orders/<int:pk>/cancel/", OrderCancelView.as_view(), name="order-cancel"),
    path("cart/", CartView.as_view(), name="cart"),
    path("cart/items/", CartItemCreateView.as_view(), name="cart-item-create"),
    path("cart/items/<int:pk>/", CartItemDetailView.as_view(), name="cart-item-detail"),
]
