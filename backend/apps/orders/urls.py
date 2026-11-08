from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import CartItemCreateView, CartItemDetailView, CartView, MyOrderViewSet

router = DefaultRouter()
router.register("orders", MyOrderViewSet, basename="my-order")

urlpatterns = router.urls + [
    path("cart/", CartView.as_view(), name="cart"),
    path("cart/items/", CartItemCreateView.as_view(), name="cart-item-create"),
    path("cart/items/<int:pk>/", CartItemDetailView.as_view(), name="cart-item-detail"),
]
