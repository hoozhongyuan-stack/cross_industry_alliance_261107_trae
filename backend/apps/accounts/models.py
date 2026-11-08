"""用户主档与多端身份。

AppUser 同时是 Django 的 AUTH_USER_MODEL：平台后台用手机号 + 密码登录，
消费者端后续接入微信 open_id / union_id（P0 先落库，不做微信登录联调）。
"""

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models

from apps.common.models import TimeStampedModel


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, phone, password=None, **extra_fields):
        if not phone:
            raise ValueError("手机号不能为空")
        user = self.model(phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("status", AppUser.Status.ACTIVE)
        if not extra_fields["is_staff"] or not extra_fields["is_superuser"]:
            raise ValueError("超级用户必须 is_staff=True 且 is_superuser=True")
        return self.create_user(phone, password, **extra_fields)


class AppUser(AbstractBaseUser, PermissionsMixin):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "正常"
        DISABLED = "DISABLED", "禁用"

    class Gender(models.TextChoices):
        UNKNOWN = "U", "未知"
        MALE = "M", "男"
        FEMALE = "F", "女"

    union_id = models.CharField("微信 union_id", max_length=64, unique=True, null=True, blank=True)
    phone = models.CharField("手机号", max_length=20, unique=True, null=True, blank=True, db_index=True)
    nickname = models.CharField("昵称", max_length=64, blank=True, default="")
    avatar_url = models.URLField("头像", blank=True, default="")
    gender = models.CharField("性别", max_length=1, choices=Gender.choices, default=Gender.UNKNOWN)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    is_staff = models.BooleanField("可登录后台", default=False)
    is_active = models.BooleanField("账号有效", default=True)
    last_login_ip = models.GenericIPAddressField("最近登录 IP", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "用户"
        verbose_name_plural = "用户"
        db_table = "app_user"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.nickname or '匿名'}（{self.phone or self.union_id or self.pk}）"


class UserIdentity(TimeStampedModel):
    """同一用户在不同渠道（小程序 / H5 / APP）的身份映射。"""

    class Channel(models.TextChoices):
        WECHAT_MINI = "WECHAT_MINI", "微信小程序"
        WECHAT_H5 = "WECHAT_H5", "微信 H5"
        APP = "APP", "APP"

    user = models.ForeignKey(AppUser, on_delete=models.CASCADE, related_name="identities", verbose_name="用户")
    channel = models.CharField("渠道", max_length=20, choices=Channel.choices)
    open_id = models.CharField("open_id", max_length=64)
    union_id = models.CharField("union_id", max_length=64, blank=True, default="")

    class Meta:
        verbose_name = "用户渠道身份"
        verbose_name_plural = "用户渠道身份"
        db_table = "user_identity"
        constraints = [models.UniqueConstraint(fields=["channel", "open_id"], name="uq_user_identity_channel_openid")]
        indexes = [models.Index(fields=["user", "channel"], name="ix_user_identity_user_channel")]

    def __str__(self):
        return f"{self.user_id}@{self.channel}"
