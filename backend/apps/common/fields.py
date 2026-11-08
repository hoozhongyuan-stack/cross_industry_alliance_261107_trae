"""加密字段：写入自动加密，读取自动解密。

注意：随机 nonce 决定同一明文每次密文不同，因此加密字段不支持等值查询；
需要检索的字段（如登录手机号）应额外保存盲索引，不能直接套用本字段。
"""

import json

from django.db import models

from .crypto import decrypt_text, encrypt_text, is_encrypted


class EncryptedTextField(models.TextField):
    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value is None:
            return None
        return encrypt_text(str(value))

    def from_db_value(self, value, expression, connection):
        if value is None:
            return None
        return decrypt_text(value)


class EncryptedJSONField(models.TextField):
    def get_prep_value(self, value):
        if value is None:
            return None
        if isinstance(value, str):
            value = json.loads(value)
        return encrypt_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")))

    def from_db_value(self, value, expression, connection):
        if value is None:
            return None
        if not is_encrypted(value):
            return json.loads(value)
        return json.loads(decrypt_text(value))
