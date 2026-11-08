from django.contrib import admin

from apps.common.admin import BaseAdmin

from .models import (
    AccountAdjustment,
    LedgerEntry,
    LedgerTransaction,
    MerchantAccount,
    SettlementBatch,
    SettlementItem,
    WithdrawalOrder,
)


class LedgerEntryInline(admin.TabularInline):
    model = LedgerEntry
    extra = 0
    can_delete = False
    fields = ("account_type", "account_id", "direction", "amount", "balance_after", "created_at")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(MerchantAccount)
class MerchantAccountAdmin(BaseAdmin):
    list_display = (
        "id",
        "merchant",
        "pending_balance",
        "frozen_balance",
        "available_balance",
        "withdrawing_balance",
        "version",
        "updated_at",
    )
    search_fields = ("merchant__name", "merchant__merchant_no")
    raw_id_fields = ("merchant",)
    readonly_fields = ("pending_balance", "frozen_balance", "available_balance", "withdrawing_balance", "version")

    def has_add_permission(self, request):
        return False


@admin.register(LedgerTransaction)
class LedgerTransactionAdmin(BaseAdmin):
    list_display = ("id", "txn_no", "biz_type", "event_type", "biz_id", "total_amount", "idempotency_key", "created_at")
    list_filter = ("biz_type", "event_type")
    search_fields = ("txn_no", "idempotency_key", "biz_id")
    inlines = (LedgerEntryInline,)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(LedgerEntry)
class LedgerEntryAdmin(BaseAdmin):
    list_display = ("id", "txn", "account_type", "account_id", "direction", "amount", "balance_after", "created_at")
    list_filter = ("account_type", "direction")
    search_fields = ("txn__txn_no",)
    raw_id_fields = ("txn",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(SettlementBatch)
class SettlementBatchAdmin(BaseAdmin):
    list_display = (
        "id",
        "batch_no",
        "period_start",
        "period_end",
        "status",
        "total_amount",
        "commission_amount",
        "net_amount",
        "published_at",
    )
    list_filter = ("status",)
    search_fields = ("batch_no",)


@admin.register(SettlementItem)
class SettlementItemAdmin(BaseAdmin):
    list_display = ("id", "order", "merchant", "due_at", "net_amount", "status", "batch", "settled_at")
    list_filter = ("status", "merchant")
    search_fields = ("order__order_no", "merchant__name")
    raw_id_fields = ("order", "merchant", "batch")


@admin.register(WithdrawalOrder)
class WithdrawalOrderAdmin(BaseAdmin):
    list_display = (
        "id",
        "withdrawal_no",
        "merchant",
        "amount",
        "fee",
        "net_amount",
        "status",
        "requested_at",
        "paid_at",
        "voucher_no",
    )
    list_filter = ("status", "merchant")
    search_fields = ("withdrawal_no", "voucher_no", "merchant__name")
    raw_id_fields = ("merchant", "account")


@admin.register(AccountAdjustment)
class AccountAdjustmentAdmin(BaseAdmin):
    list_display = ("id", "merchant", "type", "amount", "reason", "created_by_name", "created_at")
    list_filter = ("type",)
    search_fields = ("merchant__name", "reason")
    raw_id_fields = ("merchant", "ledger_txn")
