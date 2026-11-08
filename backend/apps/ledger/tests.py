"""记账核心测试：借贷平衡、幂等、负余额守卫与结算项生成。"""

from datetime import timedelta

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from apps.ledger.constants import AccountType, Direction
from apps.ledger.models import LedgerEntry, LedgerTransaction, MerchantAccount, SettlementItem
from apps.ledger.services import (
    NegativeBalance,
    UnbalancedTransaction,
    create_settlement_item,
    ensure_account,
    post_transaction,
)
from apps.merchants.models import Merchant


def make_merchant(no="M001", cycle=7):
    return Merchant.objects.create(merchant_no=no, name=f"测试商户{no}", settlement_cycle_days=cycle)


class LedgerPostingTests(TestCase):
    def setUp(self):
        self.merchant = make_merchant()

    def pay(self, key="pay:1", amount=8800):
        return post_transaction(
            biz_type="PAYMENT",
            event_type="PAY_SUCCESS",
            idempotency_key=key,
            biz_id=1,
            entries=[
                {
                    "account_type": AccountType.PLATFORM_CASH,
                    "account_id": 0,
                    "direction": Direction.DEBIT,
                    "amount": amount,
                },
                {
                    "account_type": AccountType.MERCHANT_PENDING,
                    "account_id": self.merchant.id,
                    "direction": Direction.CREDIT,
                    "amount": amount,
                },
            ],
        )

    def test_payment_creates_balanced_entries(self):
        txn = self.pay()
        self.assertEqual(txn.entries.count(), 2)
        debit = sum(e.amount for e in txn.entries.all() if e.direction == Direction.DEBIT)
        credit = sum(e.amount for e in txn.entries.all() if e.direction == Direction.CREDIT)
        self.assertEqual(debit, credit)

        account = MerchantAccount.objects.get(merchant=self.merchant)
        self.assertEqual(account.pending_balance, 8800)
        self.assertEqual(account.available_balance, 0)

        cash_entry = txn.entries.get(account_type=AccountType.PLATFORM_CASH)
        self.assertEqual(cash_entry.balance_after, 8800)

    def test_idempotent_repeat_does_not_double_book(self):
        first = self.pay()
        second = self.pay()
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(LedgerEntry.objects.count(), 2)
        self.assertEqual(MerchantAccount.objects.get(merchant=self.merchant).pending_balance, 8800)

    def test_unbalanced_transaction_rejected(self):
        with self.assertRaises(UnbalancedTransaction):
            post_transaction(
                biz_type="PAYMENT",
                event_type="PAY_SUCCESS",
                idempotency_key="pay:bad",
                entries=[
                    {
                        "account_type": AccountType.PLATFORM_CASH,
                        "account_id": 0,
                        "direction": Direction.DEBIT,
                        "amount": 8800,
                    },
                    {
                        "account_type": AccountType.MERCHANT_PENDING,
                        "account_id": self.merchant.id,
                        "direction": Direction.CREDIT,
                        "amount": 8700,
                    },
                ],
            )
        self.assertEqual(LedgerEntry.objects.count(), 0)
        self.assertFalse(MerchantAccount.objects.filter(merchant=self.merchant).exists())

    def test_pending_balance_cannot_go_negative(self):
        ensure_account(self.merchant.id)
        with self.assertRaises(NegativeBalance):
            post_transaction(
                biz_type="REFUND",
                event_type="REFUND_SUCCESS",
                idempotency_key="refund:1",
                entries=[
                    {
                        "account_type": AccountType.MERCHANT_PENDING,
                        "account_id": self.merchant.id,
                        "direction": Direction.DEBIT,
                        "amount": 8800,
                    },
                    {
                        "account_type": AccountType.PLATFORM_CASH,
                        "account_id": 0,
                        "direction": Direction.CREDIT,
                        "amount": 8800,
                    },
                ],
            )
        account = MerchantAccount.objects.get(merchant=self.merchant)
        self.assertEqual(account.pending_balance, 0)
        self.assertEqual(LedgerEntry.objects.count(), 0)

    def test_settlement_splits_commission_and_available(self):
        self.pay(amount=8800)
        post_transaction(
            biz_type="SETTLEMENT",
            event_type="SETTLEMENT_PUBLISHED",
            idempotency_key="settle:1",
            biz_id=1,
            entries=[
                {
                    "account_type": AccountType.MERCHANT_PENDING,
                    "account_id": self.merchant.id,
                    "direction": Direction.DEBIT,
                    "amount": 8800,
                },
                {
                    "account_type": AccountType.MERCHANT_AVAILABLE,
                    "account_id": self.merchant.id,
                    "direction": Direction.CREDIT,
                    "amount": 8360,
                },
                {
                    "account_type": AccountType.PLATFORM_COMMISSION_REVENUE,
                    "account_id": 0,
                    "direction": Direction.CREDIT,
                    "amount": 440,
                },
            ],
        )
        account = MerchantAccount.objects.get(merchant=self.merchant)
        self.assertEqual(account.pending_balance, 0)
        self.assertEqual(account.available_balance, 8360)

    def test_withdrawal_moves_available_to_withdrawing(self):
        post_transaction(
            biz_type="SETTLEMENT",
            event_type="SETTLEMENT_PUBLISHED",
            idempotency_key="settle:2",
            entries=[
                {
                    "account_type": AccountType.PLATFORM_CASH,
                    "account_id": 0,
                    "direction": Direction.DEBIT,
                    "amount": 8360,
                },
                {
                    "account_type": AccountType.MERCHANT_AVAILABLE,
                    "account_id": self.merchant.id,
                    "direction": Direction.CREDIT,
                    "amount": 8360,
                },
            ],
        )
        post_transaction(
            biz_type="WITHDRAWAL",
            event_type="WITHDRAWAL_REQUESTED",
            idempotency_key="withdraw:1",
            entries=[
                {
                    "account_type": AccountType.MERCHANT_AVAILABLE,
                    "account_id": self.merchant.id,
                    "direction": Direction.DEBIT,
                    "amount": 8360,
                },
                {
                    "account_type": AccountType.MERCHANT_WITHDRAWING,
                    "account_id": self.merchant.id,
                    "direction": Direction.CREDIT,
                    "amount": 8360,
                },
            ],
        )
        account = MerchantAccount.objects.get(merchant=self.merchant)
        self.assertEqual(account.available_balance, 0)
        self.assertEqual(account.withdrawing_balance, 8360)


class SettlementItemTests(TestCase):
    def setUp(self):
        self.merchant = make_merchant(no="M002", cycle=3)
        self.user = self._create_user()

    def _create_user(self):
        from apps.accounts.models import AppUser

        return AppUser.objects.create_user(phone="13800000001", password="pass12345")

    def test_due_at_uses_merchant_cycle(self):
        from apps.orders.models import Order

        completed_at = timezone.now()
        order = Order.objects.create(
            user=self.user,
            merchant=self.merchant,
            order_type=Order.Type.SERVICE,
            status=Order.Status.COMPLETED,
            product_amount=8800,
            payable_amount=8800,
            paid_amount=8800,
            commission_amount=440,
            commission_rate="0.0500",
            completed_at=completed_at,
        )
        item = create_settlement_item(order)
        self.assertEqual(item.due_at, completed_at + timedelta(days=3))
        self.assertEqual(item.net_amount, 8800 - 440)
        self.assertEqual(SettlementItem.objects.count(), 1)


class AuditLedgerCommandTests(TestCase):
    def setUp(self):
        self.merchant = make_merchant(no="M003")

    def _post_payment(self):
        return post_transaction(
            biz_type="PAYMENT",
            event_type="PAY_SUCCESS",
            idempotency_key="audit:pay:1",
            entries=[
                {
                    "account_type": AccountType.PLATFORM_CASH,
                    "account_id": 0,
                    "direction": Direction.DEBIT,
                    "amount": 8800,
                },
                {
                    "account_type": AccountType.MERCHANT_PENDING,
                    "account_id": self.merchant.id,
                    "direction": Direction.CREDIT,
                    "amount": 8800,
                },
            ],
        )

    def test_balanced_books_pass(self):
        self._post_payment()
        call_command("audit_ledger")

    def test_snapshot_drift_is_detected(self):
        self._post_payment()
        MerchantAccount.objects.filter(merchant=self.merchant).update(pending_balance=1)
        with self.assertRaises(CommandError):
            call_command("audit_ledger")

    def test_unbalanced_transaction_is_detected(self):
        self._post_payment()
        txn = LedgerTransaction.objects.create(
            biz_type=LedgerTransaction.BizType.ADJUSTMENT,
            event_type="MANUAL_BAD",
            idempotency_key="audit:bad",
            total_amount=100,
        )
        LedgerEntry.objects.create(
            txn=txn,
            account_type=AccountType.PLATFORM_CASH,
            account_id=0,
            direction=Direction.DEBIT,
            amount=100,
            balance_after=100,
        )
        with self.assertRaises(CommandError):
            call_command("audit_ledger")
