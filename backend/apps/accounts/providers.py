"""微信登录与短信适配层。

M1 只提供 Mock 实现，真实渠道联调放到 M5；调用方不感知实现切换。
"""

import hashlib
import logging

from django.conf import settings

from apps.common.api import ApiError

logger = logging.getLogger(__name__)


class MockWechatProvider:
    def exchange_code(self, code, channel):
        digest = hashlib.sha256(f"{channel}:{code}".encode()).hexdigest()[:24]
        return {"open_id": f"mock_{digest}", "union_id": f"union_{digest}"}


class MockSmsProvider:
    def send(self, phone, code):
        logger.info("mock sms to %s, code=%s", phone, code)


def get_wechat_provider():
    if settings.WECHAT_MOCK_MODE:
        return MockWechatProvider()
    raise ApiError("WECHAT_NOT_CONFIGURED", "真实微信登录未接入（M5）", 503)


def get_sms_provider():
    if settings.SMS_MOCK_MODE:
        return MockSmsProvider()
    raise ApiError("SMS_NOT_CONFIGURED", "短信服务商未确定（T6）", 503)
