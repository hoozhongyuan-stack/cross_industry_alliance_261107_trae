"""为每个请求生成 trace_id，并写入响应头。"""

import uuid


class RequestIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.trace_id = request.headers.get("X-Trace-Id") or uuid.uuid4().hex
        response = self.get_response(request)
        response["X-Trace-Id"] = request.trace_id
        return response
