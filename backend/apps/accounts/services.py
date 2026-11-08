"""登录与会话服务：微信 Mock 登录、短信验证码、JWT 签发。"""

import secrets

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.api import ApiError

from .models import AppUser, UserIdentity
from .providers import get_sms_provider, get_wechat_provider


def issue_tokens(user) -> dict:
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "expires_in": int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds()),
    }


def _ensure_active(user) -> None:
    if not user.is_active or user.status == AppUser.Status.DISABLED:
        raise ApiError("ACCOUNT_DISABLED", "账号已被禁用", 403)


def login_with_wechat(code: str, channel: str) -> AppUser:
    profile = get_wechat_provider().exchange_code(code, channel)
    open_id = profile["open_id"]
    union_id = profile["union_id"]

    with transaction.atomic():
        identity = (
            UserIdentity.objects.select_for_update()
            .filter(channel=channel, open_id=open_id)
            .select_related("user")
            .first()
        )
        if identity:
            user = identity.user
        else:
            user = AppUser.objects.filter(union_id=union_id).first()
            if user is None:
                user = AppUser(union_id=union_id, nickname="微信用户")
                user.set_unusable_password()
                user.save()
            UserIdentity.objects.get_or_create(
                channel=channel,
                open_id=open_id,
                defaults={"user": user, "union_id": union_id},
            )
    _ensure_active(user)
    return user


def send_sms_code(phone: str, scene: str) -> dict:
    throttle_key = f"sms:throttle:{phone}"
    if not cache.add(throttle_key, 1, settings.SMS_SEND_INTERVAL_SECONDS):
        raise ApiError("RATE_LIMITED", "验证码发送过于频繁，请稍后再试", 429)

    code = f"{secrets.randbelow(10**6):06d}"
    cache.set(f"sms:code:{phone}", code, settings.SMS_CODE_TTL_SECONDS)
    get_sms_provider().send(phone, code)
    return {
        "expires_in": settings.SMS_CODE_TTL_SECONDS,
        "debug_code": code if settings.SMS_MOCK_MODE else None,
    }


def login_with_sms(phone: str, sms_code: str, union_id: str = "") -> AppUser:
    stored = cache.get(f"sms:code:{phone}")
    if not stored or not secrets.compare_digest(str(stored), sms_code):
        raise ApiError("SMS_CODE_INVALID", "验证码错误或已过期", 422)

    cache.delete(f"sms:code:{phone}")
    user = AppUser.objects.filter(phone=phone).first()
    if user is None:
        user = AppUser.objects.create_user(phone=phone, nickname="手机用户")

    if union_id:
        if user.union_id and user.union_id != union_id:
            raise ApiError("ACCOUNT_UNION_CONFLICT", "该账号已绑定其他微信身份", 409)
        if not user.union_id:
            user.union_id = union_id
            user.save(update_fields=["union_id", "updated_at"])

    _ensure_active(user)
    return user
