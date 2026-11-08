"""统一响应包裹与异常处理，供新增（目标契约）接口使用。"""

import uuid

from django.http import Http404
from rest_framework import serializers
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied,
    Throttled,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import APIView


class EnvelopeResponse(serializers.Serializer):
    """仅用于 OpenAPI 快照描述统一响应结构。"""

    code = serializers.CharField()
    message = serializers.CharField()
    trace_id = serializers.CharField()
    data = serializers.JSONField(required=False, allow_null=True)


class ApiError(Exception):
    """业务错误：由 view 抛出，统一转换为错误包裹。"""

    def __init__(self, code: str, message: str, status_code: int = 409, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


def trace_id(request) -> str:
    return getattr(request, "trace_id", uuid.uuid4().hex)


def ok(request, data=None, status_code: int = 200, message: str = "success") -> Response:
    return Response(
        {"code": "OK", "message": message, "trace_id": trace_id(request), "data": data},
        status=status_code,
    )


def error(request, code: str, message: str, status_code: int, details=None) -> Response:
    payload = {"code": code, "message": message, "trace_id": trace_id(request)}
    if details is not None:
        payload["details"] = details
    return Response(payload, status=status_code)


class EnvelopeExceptionMixin:
    """把 DRF 异常转换为 {code, message, trace_id, details}。"""

    def handle_exception(self, exc):
        request = self.request
        if isinstance(exc, ApiError):
            return error(request, exc.code, exc.message, exc.status_code, exc.details)
        if isinstance(exc, ValidationError):
            return error(request, "VALIDATION_ERROR", "参数校验失败", 422, exc.detail)
        if isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
            return error(request, "AUTH_REQUIRED", "未登录或 Token 失效", 401)
        if isinstance(exc, PermissionDenied):
            return error(request, "PERMISSION_DENIED", "无权限或跨商户访问", 403)
        if isinstance(exc, Http404):
            return error(request, "NOT_FOUND", "资源不存在", 404)
        if isinstance(exc, Throttled):
            return error(request, "RATE_LIMITED", "请求过于频繁", 429)
        if isinstance(exc, APIException):
            return error(request, exc.default_code.upper(), str(exc.detail), exc.status_code)
        return super().handle_exception(exc)


class EnvelopeAPIView(EnvelopeExceptionMixin, APIView):
    """使用统一响应包裹的 APIView。"""
