"""消费者端公开路由：认证与地址簿（挂载在 /api/v1/ 下）。"""

from django.urls import path

from .views import AddressDetailView, AddressListCreateView, SmsLoginView, SmsSendView, WechatLoginView

urlpatterns = [
    path("auth/wechat/login/", WechatLoginView.as_view(), name="wechat-login"),
    path("auth/h5/sms/", SmsLoginView.as_view(), name="sms-login"),
    path("auth/sms/send/", SmsSendView.as_view(), name="sms-send"),
    path("addresses/", AddressListCreateView.as_view(), name="address-list"),
    path("addresses/<int:pk>/", AddressDetailView.as_view(), name="address-detail"),
]
