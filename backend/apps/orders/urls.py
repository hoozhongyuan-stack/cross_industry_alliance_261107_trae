from rest_framework.routers import DefaultRouter

from .views import MyOrderViewSet

router = DefaultRouter()
router.register("orders", MyOrderViewSet, basename="my-order")

urlpatterns = router.urls
