from django.contrib import admin

from apps.common.admin import BaseAdmin

from .models import AuditTask, ContentItem, OperationLog, RuleVersion


@admin.register(RuleVersion)
class RuleVersionAdmin(BaseAdmin):
    list_display = ("id", "version_no", "status", "effective_at", "created_by_name", "created_at")
    list_filter = ("status",)
    search_fields = ("version_no",)


@admin.register(AuditTask)
class AuditTaskAdmin(BaseAdmin):
    list_display = ("id", "biz_type", "biz_id", "status", "decision", "assigned_to_name", "created_at", "handled_at")
    list_filter = ("biz_type", "status")
    search_fields = ("biz_id", "assigned_to_name")


@admin.register(OperationLog)
class OperationLogAdmin(BaseAdmin):
    list_display = ("id", "operator_name", "action", "biz_type", "biz_id", "ip", "created_at")
    list_filter = ("action", "biz_type")
    search_fields = ("operator_name", "action")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ContentItem)
class ContentItemAdmin(BaseAdmin):
    list_display = ("id", "slot_code", "title", "status", "sort", "start_at", "end_at")
    list_filter = ("slot_code", "status")
    list_editable = ("sort", "status")
