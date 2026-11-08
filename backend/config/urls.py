"""URL 总表：/api/v1 为业务接口，/api/schema 为契约，/admin 为平台运营后台。"""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/v1/", include("apps.common.urls")),
    path("api/v1/", include("apps.catalog.urls")),
    path("api/v1/", include("apps.merchants.urls")),
    path("api/v1/", include("apps.orders.urls")),
    path("api/v1/", include("apps.accounts.consumer_urls")),
    path("api/v1/accounts/", include("apps.accounts.urls")),
]
