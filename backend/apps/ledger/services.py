"""记账服务：唯一写入口，负责校验借贷平衡、幂等与余额快照。"""

from datetime import timedelta
from typing import Iterable, Optional

from django.db import transaction
from django.db.models import Sum

from apps.ledger.constants import (
    DEBIT_NORMAL_ACCOUNTS,
    MERCHANT_BALANCE_FIELD,
    NON_NEGATIVE_FIELDS,
    AccountType,
    Direction,
)
from apps.ledger.models import LedgerEntry, LedgerTransaction, MerchantAccount, SettlementItem


class LedgerError(Exception):
    """记账业务错误。"""


class InvalidEntry(LedgerError):
    pass


class UnbalancedTransaction(LedgerError):
    pass


class NegativeBalance(LedgerError):
    pass


def ensure_account(merchant_id: int) -> MerchantAccount:
    account, _ = MerchantAccount.objects.get_or_create(merchant_id=merchant_id)
    return account


def _validate(entries: Iterable[dict]) -> int:
    total_debit = 0
    total_credit = 0
    valid_types = set(AccountType.values)
    for entry in entries:
        account_type = entry.get("account_type")
        direction = entry.get("direction")
        amount = entry.get("amount")
        account_id = entry.get("account_id", 0)
        if account_type not in valid_types:
            raise InvalidEntry(f"未知科目：{account_type}")
        if direction not in (Direction.DEBIT, Direction.CREDIT):
            raise InvalidEntry(f"未知借贷方向：{direction}")
        if not isinstance(amount, int) or amount <= 0:
            raise InvalidEntry("分录金额必须为正整数（分）")
        if not isinstance(account_id, int) or account_id < 0:
            raise InvalidEntry("账户 ID 非法")
        if direction == Direction.DEBIT:
            total_debit += amount
        else:
            total_credit += amount
    if total_debit != total_credit:
        raise UnbalancedTransaction(f"借贷不平：借方 {total_debit} / 贷方 {total_credit}")
    return total_debit


def _signed_delta(account_type: str, direction: str, amount: int) -> int:
    debit_normal = account_type in DEBIT_NORMAL_ACCOUNTS
    if (debit_normal and direction == Direction.DEBIT) or (not debit_normal and direction == Direction.CREDIT):
        return amount
    return -amount


def _platform_balance(account_type: str, account_id: int) -> int:
    filters = {"account_type": account_type, "account_id": account_id}
    debit = LedgerEntry.objects.filter(**filters, direction=Direction.DEBIT).aggregate(v=Sum("amount"))["v"] or 0
    credit = LedgerEntry.objects.filter(**filters, direction=Direction.CREDIT).aggregate(v=Sum("amount"))["v"] or 0
    return debit - credit if account_type in DEBIT_NORMAL_ACCOUNTS else credit - debit


def _post_entry(txn: LedgerTransaction, entry: dict) -> None:
    account_type = entry["account_type"]
    account_id = entry.get("account_id", 0)
    direction = entry["direction"]
    amount = entry["amount"]
    balance_field = MERCHANT_BALANCE_FIELD.get(account_type)

    if balance_field:
        ensure_account(account_id)
        account = MerchantAccount.objects.select_for_update().get(merchant_id=account_id)
        delta = _signed_delta(account_type, direction, amount)
        new_balance = getattr(account, balance_field) + delta
        if balance_field in NON_NEGATIVE_FIELDS and new_balance < 0:
            raise NegativeBalance(f"{account_type} 余额不足：当前 {getattr(account, balance_field)}，变动 {delta}")
        setattr(account, balance_field, new_balance)
        account.version += 1
        account.save(update_fields=[balance_field, "version", "updated_at"])
        balance_after = new_balance
    else:
        delta = _signed_delta(account_type, direction, amount)
        balance_after = _platform_balance(account_type, account_id) + delta

    LedgerEntry.objects.create(
        txn=txn,
        account_type=account_type,
        account_id=account_id,
        direction=direction,
        amount=amount,
        balance_after=balance_after,
        remark=entry.get("remark", ""),
    )


def post_transaction(
    *,
    biz_type: str,
    event_type: str,
    idempotency_key: str,
    entries: Iterable[dict],
    biz_id: Optional[int] = None,
    total_amount: Optional[int] = None,
    remark: str = "",
) -> LedgerTransaction:
    """写一笔平衡的记账事务。

    entries 元素：{"account_type", "account_id", "direction", "amount", "remark"}。
    幂等键重复时直接返回原事务，不重复记账、不改余额。
    """
    payload = list(entries)
    debit_total = _validate(payload)
    amount_for_txn = total_amount if total_amount is not None else debit_total
    if amount_for_txn != debit_total:
        raise UnbalancedTransaction("total_amount 必须等于借方合计")

    with transaction.atomic():
        txn, created = LedgerTransaction.objects.get_or_create(
            idempotency_key=idempotency_key,
            defaults={
                "biz_type": biz_type,
                "biz_id": biz_id,
                "event_type": event_type,
                "total_amount": amount_for_txn,
                "remark": remark,
            },
        )
        if not created:
            return txn
        for entry in payload:
            _post_entry(txn, entry)
    return txn


def create_settlement_item(order) -> SettlementItem:
    """订单完成时生成结算项：due_at = completed_at + 商户结算周期 N 天。"""
    from apps.orders.models import Order

    if order.status != Order.Status.COMPLETED or order.completed_at is None:
        raise LedgerError("只有已完成订单才能生成结算项")

    cycle_days = order.merchant.settlement_cycle_days
    net_amount = order.product_amount + order.delivery_fee - order.commission_amount - order.refunded_amount
    item, created = SettlementItem.objects.get_or_create(
        order=order,
        defaults={
            "merchant": order.merchant,
            "order_completed_at": order.completed_at,
            "due_at": order.completed_at + timedelta(days=cycle_days),
            "product_amount": order.product_amount,
            "delivery_fee": order.delivery_fee,
            "commission_rate": order.commission_rate,
            "commission_amount": order.commission_amount,
            "refund_amount": order.refunded_amount,
            "net_amount": net_amount,
        },
    )
    return item
