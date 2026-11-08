from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from apps.common.admin import BaseAdmin

from .models import AppUser, UserIdentity


class AppUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = AppUser
        fields = ("phone",)


class AppUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = AppUser
        fields = "__all__"


@admin.register(AppUser)
class AppUserAdmin(DjangoUserAdmin, BaseAdmin):
    list_display = ("id", "phone", "nickname", "status", "is_staff", "created_at")
    list_filter = ("status", "is_staff", "is_active")
    search_fields = ("phone", "nickname", "union_id")
    ordering = ("-created_at",)
    fieldsets = (
        (None, {"fields": ("phone", "password")}),
        ("资料", {"fields": ("nickname", "avatar_url", "gender", "union_id")}),
        ("权限", {"fields": ("status", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("审计", {"fields": ("last_login", "last_login_ip", "created_at", "updated_at")}),
    )
    readonly_fields = ("last_login", "created_at", "updated_at")
    form = AppUserChangeForm
    add_form = AppUserCreationForm
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("phone", "password1", "password2", "is_staff")}),)


@admin.register(UserIdentity)
class UserIdentityAdmin(BaseAdmin):
    list_display = ("id", "user", "channel", "open_id", "union_id", "created_at")
    list_filter = ("channel",)
    search_fields = ("open_id", "union_id", "user__phone")
    raw_id_fields = ("user",)
