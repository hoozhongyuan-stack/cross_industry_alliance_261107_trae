"""业务单号生成与请求体哈希。"""

import hashlib
import json
import secrets

from django.utils import timezone


def generate_no(prefix: str, random_digits: int = 6) -> str:
    stamp = timezone.localtime().strftime("%Y%m%d%H%M%S")
    rand = "".join(str(secrets.randbelow(10)) for _ in range(random_digits))
    return f"{prefix}{stamp}{rand}"


def payload_hash(payload) -> str:
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
