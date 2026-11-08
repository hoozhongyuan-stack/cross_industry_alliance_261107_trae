"""字段级加密：AES-256-GCM。

密钥来源：
- 生产/预发：环境变量 FIELD_ENCRYPTION_KEY（32 字节 base64）。
- 开发/测试：未配置时由 SECRET_KEY 派生，禁止用于生产。
密文格式：enc:v1:<urlsafe_base64(nonce + ciphertext + tag)>。
"""

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

PREFIX = "enc:v1:"


def _key() -> bytes:
    raw = os.getenv("FIELD_ENCRYPTION_KEY", "").strip()
    if raw:
        padding = "=" * (-len(raw) % 4)
        key = base64.urlsafe_b64decode(raw + padding)
        if len(key) != 32:
            raise ImproperlyConfigured("FIELD_ENCRYPTION_KEY 必须是 32 字节 base64")
        return key
    return hashlib.sha256(f"{settings.SECRET_KEY}:field-encryption".encode()).digest()


def is_encrypted(value: str) -> bool:
    return isinstance(value, str) and value.startswith(PREFIX)


def encrypt_text(value: str) -> str:
    nonce = os.urandom(12)
    ciphertext = AESGCM(_key()).encrypt(nonce, value.encode("utf-8"), None)
    return PREFIX + base64.urlsafe_b64encode(nonce + ciphertext).decode()


def decrypt_text(value: str) -> str:
    if not is_encrypted(value):
        return value
    payload = base64.urlsafe_b64decode(value[len(PREFIX) :].encode())
    nonce, ciphertext = payload[:12], payload[12:]
    return AESGCM(_key()).decrypt(nonce, ciphertext, None).decode("utf-8")
