"""对账命令：校验借贷平衡，以及流水汇总与商户账户快照是否一致。

差异只报告、不自动修复；修复必须走反向分录 + AccountAdjustment。
"""

from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.db.models import F, Q, Sum, Value
from django.db.models.functions import Coalesce

from apps.ledger.constants import DEBIT_NORMAL_ACCOUNTS, MERCHANT_BALANCE_FIELD, Direction
from apps.ledger.models import LedgerEntry, LedgerTransaction, MerchantAccount


class Command(BaseCommand):
    help = "对账：全部记账事务借贷必平，所有商户账户快照必须等于流水汇总。"

    def handle(self, *args, **options):
        errors = self._check_transactions_balanced()
        errors.extend(self._check_account_snapshots())

        if errors:
            detail = "\n".join(errors[:50])
            raise CommandError(f"对账失败，共 {len(errors)} 项差异：\n{detail}")
        self.stdout.write(
            self.style.SUCCESS(
                f"对账通过：{LedgerTransaction.objects.count()} 个记账事务、"
                f"{MerchantAccount.objects.count()} 个商户账户"
            )
        )

    def _check_transactions_balanced(self) -> list:
        errors = []
        rows = (
            LedgerTransaction.objects.annotate(
                debit=Coalesce(Sum("entries__amount", filter=Q(entries__direction=Direction.DEBIT)), Value(0)),
                credit=Coalesce(Sum("entries__amount", filter=Q(entries__direction=Direction.CREDIT)), Value(0)),
            )
            .exclude(debit=F("credit"))
            .values_list("txn_no", "debit", "credit")
        )
        for txn_no, debit, credit in rows:
            errors.append(f"借贷不平：{txn_no} 借 {debit} / 贷 {credit}")
        return errors

    def _check_account_snapshots(self) -> list:
        errors = []
        totals = defaultdict(int)
        rows = (
            LedgerEntry.objects.filter(account_type__in=MERCHANT_BALANCE_FIELD, account_id__gt=0)
            .values("account_type", "account_id", "direction")
            .annotate(total=Sum("amount"))
        )
        for row in rows:
            account_type = row["account_type"]
            direction = row["direction"]
            amount = row["total"] or 0
            is_increase = (
                direction == Direction.DEBIT if account_type in DEBIT_NORMAL_ACCOUNTS else direction == Direction.CREDIT
            )
            totals[(account_type, row["account_id"])] += amount if is_increase else -amount

        accounts = list(MerchantAccount.objects.all())
        known_ids = {account.merchant_id for account in accounts}
        for account_type, account_id in totals:
            if account_id not in known_ids:
                errors.append(f"流水指向不存在的商户账户：{account_type} / merchant_id={account_id}")

        for account in accounts:
            for account_type, field in MERCHANT_BALANCE_FIELD.items():
                expected = totals.get((account_type, account.merchant_id), 0)
                actual = getattr(account, field)
                if expected != actual:
                    errors.append(
                        f"余额不一致：merchant_id={account.merchant_id} {account_type} "
                        f"快照 {actual} / 流水 {expected}"
                    )
        return errors
