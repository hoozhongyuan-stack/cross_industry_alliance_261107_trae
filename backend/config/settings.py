"""Django 配置：开发默认 SQLite，生产通过环境变量切换 MySQL。"""

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(key: str, default: bool = False) -> bool:
    return os.getenv(key, str(default)).lower() in {"1", "true", "yes", "on"}


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-insecure-key-change-me-in-production-0123456789")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = [h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "apps.common",
    "apps.accounts",
    "apps.merchants",
    "apps.catalog",
    "apps.orders",
    "apps.payments",
    "apps.fulfillment",
    "apps.aftersales",
    "apps.ledger",
    "apps.governance",
    "apps.notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.common.middleware.RequestIdMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

if os.getenv("DB_ENGINE", "sqlite").lower() == "mysql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.getenv("DB_NAME", "alliance"),
            "USER": os.getenv("DB_USER", "root"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "127.0.0.1"),
            "PORT": os.getenv("DB_PORT", "3306"),
            "OPTIONS": {"charset": "utf8mb4", "init_command": "SET sql_mode='STRICT_TRANS_TABLES'"},
            "CONN_MAX_AGE": 60,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "accounts.AppUser"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DATETIME_FORMAT": "%Y-%m-%d %H:%M:%S",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "异业联盟商城 API",
    "DESCRIPTION": "消费者 / 商户 / 平台三端共用领域服务。金额单位为「分」，时间为 Asia/Shanghai。",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SORT_OPERATIONS": False,
    "ENUM_NAME_OVERRIDES": {
        "AppUserStatusEnum": "apps.accounts.models.AppUser.Status",
        "MerchantStatusEnum": "apps.merchants.models.Merchant.Status",
        "ProductStatusEnum": "apps.catalog.models.Product.Status",
        "ProductTypeEnum": "apps.catalog.models.Product.Type",
        "OrderStatusEnum": "apps.orders.models.Order.Status",
        "OrderTypeEnum": "apps.orders.models.Order.Type",
        "PaymentStatusEnum": "apps.payments.models.PaymentOrder.Status",
        "PaymentChannelEnum": "apps.payments.models.PaymentOrder.Channel",
        "UserChannelEnum": "apps.accounts.models.UserIdentity.Channel",
        "RefundStatusEnum": "apps.payments.models.RefundOrder.Status",
        "AfterSaleStatusEnum": "apps.aftersales.models.AfterSale.Status",
        "WithdrawalStatusEnum": "apps.ledger.models.WithdrawalOrder.Status",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=2),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
}

# 业务默认值（可在 .env 覆盖；未确认项保持 TBD，不写死规则）
DEFAULT_SETTLEMENT_CYCLE_DAYS = int(os.getenv("DEFAULT_SETTLEMENT_CYCLE_DAYS", "7"))

# 第三方渠道：M1 先走 Mock，真实联调留到 M5
WECHAT_MOCK_MODE = env_bool("WECHAT_MOCK_MODE", DEBUG)
SMS_MOCK_MODE = env_bool("SMS_MOCK_MODE", DEBUG)
SMS_CODE_TTL_SECONDS = int(os.getenv("SMS_CODE_TTL_SECONDS", "300"))
SMS_SEND_INTERVAL_SECONDS = int(os.getenv("SMS_SEND_INTERVAL_SECONDS", "60"))
ORDER_PAYMENT_TIMEOUT_MINUTES = int(os.getenv("ORDER_PAYMENT_TIMEOUT_MINUTES", "15"))
