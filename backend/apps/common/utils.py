"""业务单号生成：前缀 + 时间 + 随机位，长度 <= 32，满足 VARCHAR(32)。"""

import secrets

from django.utils import timezone


def generate_no(prefix: str, random_digits: int = 6) -> str:
    stamp = timezone.localtime().strftime("%Y%m%d%H%M%S")
    rand = "".join(str(secrets.randbelow(10)) for _ in range(random_digits))
    return f"{prefix}{stamp}{rand}"
