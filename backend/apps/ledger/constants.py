"""复式记账科目定义与余额方向。

借贷必平；资产类（借方余额）与负债/收入类（贷方余额）方向相反。
平台账户使用 account_id=0，商户账户使用 merchant_id。
"""

from django.db import models


class AccountType(models.TextChoices):
    PLATFORM_CASH = "PLATFORM_CASH", "平台现金"
    MERCHANT_PENDING = "MERCHANT_PENDING", "商户待结算"
    MERCHANT_FROZEN = "MERCHANT_FROZEN", "商户冻结"
    MERCHANT_AVAILABLE = "MERCHANT_AVAILABLE", "商户可提现"
    MERCHANT_WITHDRAWING = "MERCHANT_WITHDRAWING", "商户提现中"
    PLATFORM_COMMISSION_REVENUE = "PLATFORM_COMMISSION_REVENUE", "平台佣金收入"


class Direction(models.TextChoices):
    DEBIT = "D", "借"
    CREDIT = "C", "贷"


# 借方为正的科目（资产）；其余为贷方为正（负债 / 收入）
DEBIT_NORMAL_ACCOUNTS = {AccountType.PLATFORM_CASH}

# 需要维护 merchant_account 余额快照的科目
MERCHANT_BALANCE_FIELD = {
    AccountType.MERCHANT_PENDING: "pending_balance",
    AccountType.MERCHANT_FROZEN: "frozen_balance",
    AccountType.MERCHANT_AVAILABLE: "available_balance",
    AccountType.MERCHANT_WITHDRAWING: "withdrawing_balance",
}

# 不允许为负的余额科目；available 允许负数表示商户欠款
NON_NEGATIVE_FIELDS = {"pending_balance", "frozen_balance", "withdrawing_balance"}

PLATFORM_ACCOUNT_ID = 0
