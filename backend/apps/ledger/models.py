"""虚拟账户、复式记账流水、结算与提现。

约束：
- ledger_entry 只追加，不修改不删除；
- 同一 idempotency_key 只产生一个 ledger_transaction；
- 业务状态与记账在同一数据库事务内提交。
"""

from django.db import models

from apps.common.models import TimeStampedModel
from apps.common.utils import generate_no

from .constants import AccountType, Direction


def default_txn_no() -> str:
    return generate_no("L")


def default_batch_no() -> str:
    return generate_no("B")


def default_withdrawal_no() -> str:
    return generate_no("W")


class MerchantAccount(TimeStampedModel):
    """余额快照：与 ledger_entry 在同一事务内更新，等价于物化视图。"""

    merchant = models.OneToOneField(
        "merchants.Merchant", on_delete=models.CASCADE, related_name="account", verbose_name="商户"
    )
    pending_balance = models.BigIntegerField("待结算（分）", default=0)
    frozen_balance = models.BigIntegerField("冻结（分）", default=0)
    available_balance = models.BigIntegerField("可提现（分）", default=0)
    withdrawing_balance = models.BigIntegerField("提现中（分）", default=0)
    version = models.PositiveIntegerField("乐观锁版本", default=0)

    class Meta:
        verbose_name = "商户虚拟账户"
        verbose_name_plural = "商户虚拟账户"
        db_table = "merchant_account"
        constraints = [
            models.CheckConstraint(check=models.Q(pending_balance__gte=0), name="ck_account_pending_nonnegative"),
            models.CheckConstraint(check=models.Q(frozen_balance__gte=0), name="ck_account_frozen_nonnegative"),
            models.CheckConstraint(
                check=models.Q(withdrawing_balance__gte=0), name="ck_account_withdrawing_nonnegative"
            ),
        ]

    def __str__(self):
        return f"商户账户-{self.merchant_id}"


class LedgerTransaction(TimeStampedModel):
    class BizType(models.TextChoices):
        PAYMENT = "PAYMENT", "支付"
        REFUND = "REFUND", "退款"
        SETTLEMENT = "SETTLEMENT", "结算"
        WITHDRAWAL = "WITHDRAWAL", "提现"
        FREEZE = "FREEZE", "冻结/解冻"
        ADJUSTMENT = "ADJUSTMENT", "人工调整"

    txn_no = models.CharField("记账事务号", max_length=32, unique=True, default=default_txn_no)
    biz_type = models.CharField("业务类型", max_length=24, choices=BizType.choices, db_index=True)
    biz_id = models.BigIntegerField("业务单据 ID", null=True, blank=True)
    event_type = models.CharField("业务事件", max_length=32, db_index=True)
    idempotency_key = models.CharField("幂等键", max_length=64, unique=True)
    total_amount = models.BigIntegerField("事务总金额（分）", default=0)
    remark = models.CharField("备注", max_length=200, blank=True, default="")

    class Meta:
        verbose_name = "记账事务"
        verbose_name_plural = "记账事务"
        db_table = "ledger_transaction"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["biz_type", "biz_id"], name="ix_ledger_txn_biz")]

    def __str__(self):
        return self.txn_no


class LedgerEntry(TimeStampedModel):
    txn = models.ForeignKey(
        LedgerTransaction, on_delete=models.PROTECT, related_name="entries", verbose_name="记账事务"
    )
    account_type = models.CharField("科目", max_length=32, choices=AccountType.choices, db_index=True)
    account_id = models.BigIntegerField("账户 ID（平台为 0）", default=0)
    direction = models.CharField("借贷方向", max_length=1, choices=Direction.choices)
    amount = models.BigIntegerField("金额（分）")
    balance_after = models.BigIntegerField("记账后余额（分）")
    remark = models.CharField("备注", max_length=200, blank=True, default="")

    class Meta:
        verbose_name = "记账分录"
        verbose_name_plural = "记账分录"
        db_table = "ledger_entry"
        ordering = ("id",)
        indexes = [models.Index(fields=["account_type", "account_id", "created_at"], name="ix_ledger_entry_account")]
        constraints = [
            models.CheckConstraint(check=models.Q(amount__gt=0), name="ck_ledger_entry_amount_positive"),
            models.CheckConstraint(
                check=models.Q(direction__in=[Direction.DEBIT, Direction.CREDIT]), name="ck_ledger_entry_direction"
            ),
        ]

    def __str__(self):
        return f"{self.txn_id}-{self.account_type}-{self.direction}{self.amount}"


class SettlementBatch(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "待发布"
        PUBLISHED = "PUBLISHED", "已发布"
        CLOSED = "CLOSED", "已关闭"

    batch_no = models.CharField("批次号", max_length=32, unique=True, default=default_batch_no)
    period_start = models.DateField("周期开始")
    period_end = models.DateField("周期结束")
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    total_amount = models.BigIntegerField("结算总额（分）", default=0)
    commission_amount = models.BigIntegerField("佣金总额（分）", default=0)
    net_amount = models.BigIntegerField("应打款总额（分）", default=0)
    published_at = models.DateTimeField("发布时间", null=True, blank=True)
    published_by_id = models.BigIntegerField("发布人 ID", null=True, blank=True)
    published_by_name = models.CharField("发布人", max_length=60, blank=True, default="")
    remark = models.CharField("备注", max_length=200, blank=True, default="")

    class Meta:
        verbose_name = "结算批次"
        verbose_name_plural = "结算批次"
        db_table = "settlement_batch"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["status", "created_at"], name="ix_settle_batch_sts_created")]

    def __str__(self):
        return self.batch_no


class SettlementItem(TimeStampedModel):
    """订单与资金的连接点：一张订单最多一个结算项（unique order）。"""

    class Status(models.TextChoices):
        PENDING = "PENDING", "待结算"
        FROZEN = "FROZEN", "已冻结"
        SETTLED = "SETTLED", "已结算"
        CANCELLED = "CANCELLED", "已取消"

    order = models.OneToOneField(
        "orders.Order", on_delete=models.PROTECT, related_name="settlement_item", verbose_name="订单"
    )
    merchant = models.ForeignKey(
        "merchants.Merchant", on_delete=models.PROTECT, related_name="settlement_items", verbose_name="商户"
    )
    batch = models.ForeignKey(
        SettlementBatch, on_delete=models.SET_NULL, null=True, blank=True, related_name="items", verbose_name="批次"
    )
    order_completed_at = models.DateTimeField("订单完成时间")
    due_at = models.DateTimeField("可结算时间 = 完成 + N 天", db_index=True)
    product_amount = models.BigIntegerField("商品金额（分）", default=0)
    delivery_fee = models.BigIntegerField("配送费（分）", default=0)
    commission_rate = models.DecimalField("佣金率快照", max_digits=5, decimal_places=4, default=0)
    commission_amount = models.BigIntegerField("佣金（分）", default=0)
    refund_amount = models.BigIntegerField("结算前退款（分）", default=0)
    net_amount = models.BigIntegerField("应结金额（分）", default=0)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    settled_at = models.DateTimeField("结算时间", null=True, blank=True)

    class Meta:
        verbose_name = "结算项"
        verbose_name_plural = "结算项"
        db_table = "settlement_item"
        ordering = ("due_at", "id")
        indexes = [
            models.Index(fields=["merchant", "status", "due_at"], name="ix_settle_item_mch_due"),
            models.Index(fields=["status", "due_at"], name="ix_settlement_item_status_due"),
        ]

    def __str__(self):
        return f"{self.order_id}-{self.status}"


class WithdrawalOrder(TimeStampedModel):
    class Status(models.TextChoices):
        REQUESTED = "REQUESTED", "已申请"
        APPROVED = "APPROVED", "已审批"
        PAYING = "PAYING", "打款中"
        PAID = "PAID", "已打款"
        REJECTED = "REJECTED", "已驳回"
        FAILED = "FAILED", "打款失败"

    withdrawal_no = models.CharField("提现单号", max_length=32, unique=True, default=default_withdrawal_no)
    merchant = models.ForeignKey(
        "merchants.Merchant", on_delete=models.PROTECT, related_name="withdrawals", verbose_name="商户"
    )
    account = models.ForeignKey(
        MerchantAccount, on_delete=models.PROTECT, related_name="withdrawals", verbose_name="虚拟账户"
    )
    amount = models.BigIntegerField("申请金额（分）")
    fee = models.BigIntegerField("手续费（分）", default=0)
    net_amount = models.BigIntegerField("实付金额（分）")
    bank_snapshot_json = models.JSONField("收款银行快照（脱敏）", default=dict, blank=True)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.REQUESTED, db_index=True)
    requested_at = models.DateTimeField("申请时间", null=True, blank=True)
    reviewed_by_id = models.BigIntegerField("审核人 ID", null=True, blank=True)
    reviewed_by_name = models.CharField("审核人", max_length=60, blank=True, default="")
    reviewed_at = models.DateTimeField("审核时间", null=True, blank=True)
    paid_at = models.DateTimeField("打款时间", null=True, blank=True)
    voucher_url = models.URLField("打款回单", blank=True, default="")
    voucher_no = models.CharField("银行回单号", max_length=64, blank=True, default="")
    fail_reason = models.CharField("驳回/失败原因", max_length=200, blank=True, default="")

    class Meta:
        verbose_name = "提现单"
        verbose_name_plural = "提现单"
        db_table = "withdrawal_order"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["merchant", "status"], name="ix_withdrawal_merchant_status"),
            models.Index(fields=["status", "created_at"], name="ix_withdrawal_status_created"),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(amount__gt=0), name="ck_withdrawal_amount_positive"),
        ]

    def __str__(self):
        return self.withdrawal_no


class AccountAdjustment(TimeStampedModel):
    """结算后的人工调整：必须关联调整分录，不允许直接改余额。"""

    class Type(models.TextChoices):
        RECONCILIATION = "RECONCILIATION", "对账差异"
        COMPLAINT = "COMPLAINT", "客诉补偿"
        OFFLINE = "OFFLINE", "线下补款"
        OTHER = "OTHER", "其他"

    merchant = models.ForeignKey(
        "merchants.Merchant", on_delete=models.PROTECT, related_name="adjustments", verbose_name="商户"
    )
    type = models.CharField("类型", max_length=20, choices=Type.choices)
    amount = models.BigIntegerField("调整金额（分，正负均可）")
    reason = models.CharField("原因", max_length=200)
    related_type = models.CharField("关联单据类型", max_length=24, blank=True, default="")
    related_id = models.BigIntegerField("关联单据 ID", null=True, blank=True)
    ledger_txn = models.ForeignKey(
        LedgerTransaction,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="adjustments",
        verbose_name="调整分录",
    )
    created_by_id = models.BigIntegerField("操作人 ID", null=True, blank=True)
    created_by_name = models.CharField("操作人", max_length=60, blank=True, default="")

    class Meta:
        verbose_name = "账户调整"
        verbose_name_plural = "账户调整"
        db_table = "account_adjustment"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["merchant", "created_at"], name="ix_adjustment_merchant_created")]

    def __str__(self):
        return f"{self.merchant_id}-{self.amount}"
