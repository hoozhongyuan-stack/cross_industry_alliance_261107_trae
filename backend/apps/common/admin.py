"""后台管理公用基类：统一只读审计字段与检索能力。"""

from django.contrib import admin


class BaseAdmin(admin.ModelAdmin):
    list_per_page = 30
    show_full_result_count = False
    empty_value_display = "-"

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        field_names = {f.name for f in self.model._meta.fields}
        for name in ("created_at", "updated_at"):
            if name in field_names and name not in readonly:
                readonly.append(name)
        return tuple(readonly)
