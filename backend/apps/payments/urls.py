from django.urls import path

from .views import WechatPayCallbackView

urlpatterns = [
    path("pay/", WechatPayCallbackView.as_view(), name="wechat-pay-callback"),
]
