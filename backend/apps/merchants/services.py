"""佣金解析：商户覆盖值优先，其次类目默认值。"""

from decimal import Decimal

from .models import Merchant


def resolve_commission_rate(merchant: Merchant) -> Decimal:
    """返回下单时应快照的佣金率；两者都未配置时为 0。"""
    if merchant.commission_rate is not None:
        return merchant.commission_rate
    if merchant.category_id:
        return merchant.category.commission_rate
    return Decimal("0")
