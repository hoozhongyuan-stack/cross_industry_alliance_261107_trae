"""支付回调请求与响应结构（仅用于契约描述）。"""

from rest_framework import serializers


class CallbackPayloadSerializer(serializers.Serializer):
    payment_no = serializers.CharField()
    transaction_id = serializers.CharField()
    amount = serializers.IntegerField()
    trade_state = serializers.CharField()


class CallbackAckSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
