"""微信支付适配层：M1 仅 Mock，真实 V3 联调在 M5。"""

from django.conf import settings

from apps.common.api import ApiError


def create_prepay(payment) -> dict:
    if settings.WECHAT_MOCK_MODE:
        return {
            "prepay_id": f"mock_{payment.payment_no}",
            "pay_params": {"mock": True},
        }
    raise ApiError("WECHAT_PAY_NOT_CONFIGURED", "真实微信支付未接入（M5）", 503)
