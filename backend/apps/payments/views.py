"""微信支付回调入口（M1 Mock）。"""

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.api import ApiError

from .serializers import CallbackAckSerializer, CallbackPayloadSerializer
from .services import process_payment_success


@extend_schema(request=CallbackPayloadSerializer, responses={200: CallbackAckSerializer})
class WechatPayCallbackView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = CallbackAckSerializer

    def post(self, request):
        if not settings.WECHAT_MOCK_MODE:
            return Response({"code": "FAIL", "message": "真实微信回调未接入（M5）"}, status=503)
        try:
            payment_no = str(request.data.get("payment_no", ""))[:32]
            transaction_id = str(request.data.get("transaction_id", ""))[:64]
            amount = int(request.data.get("amount", 0))
            if request.data.get("trade_state") != "SUCCESS":
                raise ApiError("PAYMENT_NOT_SUCCESS", "支付未成功", 400)
            if not payment_no or not transaction_id:
                raise ApiError("VALIDATION_ERROR", "缺少支付单号或交易号", 400)
            process_payment_success(payment_no, transaction_id, amount)
        except ApiError as exc:
            return Response({"code": "FAIL", "message": exc.message}, status=exc.status_code)
        except (TypeError, ValueError):
            return Response({"code": "FAIL", "message": "回调参数格式错误"}, status=400)
        return Response({"code": "SUCCESS", "message": "ok"})
