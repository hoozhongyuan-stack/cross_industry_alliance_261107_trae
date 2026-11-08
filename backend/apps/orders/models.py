"""订单主表、商品行、状态日志、履约信息、核销码、预约与评价。

状态机见技术方案 4.x：PENDING_PAYMENT → PENDING_ACCEPT → PENDING_FULFILL →
FULFILLING → COMPLETED，异常分支 AFTER_SALE / REFUNDING / REFUNDED / CLOSED。
"""

from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel
from apps.common.utils import generate_no


def default_order_no() -> str:
    return generate_no("O")


class Order(TimeStampedModel):
    class Type(models.TextChoices):
        EXPRESS = "EXPRESS", "快递配送"
        PICKUP = "PICKUP", "到店自提"
        SERVICE = "SERVICE", "到店服务"

    class Status(models.TextChoices):
        PENDING_PAYMENT = "PENDING_PAYMENT", "待支付"
        PENDING_ACCEPT = "PENDING_ACCEPT", "待接单"
        PENDING_FULFILL = "PENDING_FULFILL", "待履约"
        FULFILLING = "FULFILLING", "履约中"
        COMPLETED = "COMPLETED", "已完成"
        AFTER_SALE = "AFTER_SALE", "售后中"
        REFUNDING = "REFUNDING", "退款中"
        REFUNDED = "REFUNDED", "已退款"
        CLOSED = "CLOSED", "已关闭"

    class FulfillmentStatus(models.TextChoices):
        NOT_STARTED = "NOT_STARTED", "未开始"
        APPOINTMENT_CONFIRMED = "APPOINTMENT_CONFIRMED", "预约已确认"
        SHIPPED = "SHIPPED", "已发货"
        PICKUP_READY = "PICKUP_READY", "待自提"
        VERIFY_READY = "VERIFY_READY", "待核销"
        DONE = "DONE", "已履约"

    order_no = models.CharField("订单号", max_length=32, unique=True, default=default_order_no)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders", verbose_name="用户"
    )
    merchant = models.ForeignKey(
        "merchants.Merchant", on_delete=models.PROTECT, related_name="orders", verbose_name="商户"
    )
    order_type = models.CharField("订单类型", max_length=16, choices=Type.choices)
    status = models.CharField(
        "主状态", max_length=24, choices=Status.choices, default=Status.PENDING_PAYMENT, db_index=True
    )
    fulfillment_status = models.CharField(
        "履约状态",
        max_length=24,
        choices=FulfillmentStatus.choices,
        default=FulfillmentStatus.NOT_STARTED,
        db_index=True,
    )
    product_amount = models.BigIntegerField("商品金额（分）", default=0)
    delivery_fee = models.BigIntegerField("配送费（分）", default=0)
    payable_amount = models.BigIntegerField("应付金额（分）", default=0)
    paid_amount = models.BigIntegerField("实付金额（分）", default=0)
    refunded_amount = models.BigIntegerField("累计退款（分）", default=0)
    commission_rate = models.DecimalField("佣金率快照", max_digits=5, decimal_places=4, default=0)
    commission_amount = models.BigIntegerField("佣金（分）", default=0)
    contact_json = models.JSONField("联系人快照", default=dict, blank=True)
    remark = models.CharField("用户备注", max_length=200, blank=True, default="")
    cancel_reason = models.CharField("取消原因", max_length=200, blank=True, default="")
    idempotency_key = models.CharField("创建幂等键", max_length=64, unique=True, null=True, blank=True)
    idempotency_hash = models.CharField("请求体哈希", max_length=64, blank=True, default="")
    expire_at = models.DateTimeField("支付超时时间", null=True, blank=True)
    paid_at = models.DateTimeField("支付时间", null=True, blank=True)
    accepted_at = models.DateTimeField("接单时间", null=True, blank=True)
    completed_at = models.DateTimeField("完成时间（结算起点）", null=True, blank=True, db_index=True)
    closed_at = models.DateTimeField("关闭时间", null=True, blank=True)
    version = models.PositiveIntegerField("乐观锁版本", default=0)

    class Meta:
        verbose_name = "订单"
        verbose_name_plural = "订单"
        db_table = "order"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["user", "created_at"], name="ix_order_user_created"),
            models.Index(fields=["merchant", "status"], name="ix_order_merchant_status"),
            models.Index(fields=["status", "expire_at"], name="ix_order_status_expire"),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(refunded_amount__lte=models.F("paid_amount")),
                name="ck_order_refund_lte_paid",
            ),
            models.CheckConstraint(check=models.Q(product_amount__gte=0), name="ck_order_amount_nonnegative"),
        ]

    def __str__(self):
        return self.order_no


class OrderItem(TimeStampedModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items", verbose_name="订单")
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="商品"
    )
    sku = models.ForeignKey("catalog.ProductSku", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="规格")
    snapshot_json = models.JSONField("商品快照", default=dict, blank=True)
    title = models.CharField("商品标题快照", max_length=120)
    price = models.BigIntegerField("成交单价（分）")
    quantity = models.PositiveIntegerField("数量", default=1)
    amount = models.BigIntegerField("行金额（分）")
    refund_amount = models.BigIntegerField("行退款（分）", default=0)

    class Meta:
        verbose_name = "订单商品行"
        verbose_name_plural = "订单商品行"
        db_table = "order_item"
        ordering = ("id",)
        indexes = [models.Index(fields=["order", "product"], name="ix_order_item_order_product")]

    def __str__(self):
        return f"{self.order_id}-{self.title}"


class OrderStatusLog(TimeStampedModel):
    class OperatorType(models.TextChoices):
        USER = "USER", "用户"
        MERCHANT = "MERCHANT", "商户"
        PLATFORM = "PLATFORM", "平台"
        SYSTEM = "SYSTEM", "系统"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="status_logs", verbose_name="订单")
    from_status = models.CharField("原状态", max_length=24)
    to_status = models.CharField("新状态", max_length=24)
    event = models.CharField("事件", max_length=40)
    operator_type = models.CharField("操作方", max_length=16, choices=OperatorType.choices, default=OperatorType.SYSTEM)
    operator_id = models.BigIntegerField("操作人 ID", null=True, blank=True)
    operator_name = models.CharField("操作人", max_length=60, blank=True, default="")
    reason = models.CharField("原因", max_length=200, blank=True, default="")

    class Meta:
        verbose_name = "订单状态日志"
        verbose_name_plural = "订单状态日志"
        db_table = "order_status_log"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["order", "created_at"], name="ix_order_statuslog_created")]

    def __str__(self):
        return f"{self.order_id}: {self.from_status}→{self.to_status}"


class OrderReview(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "待审核"
        VISIBLE = "VISIBLE", "已展示"
        HIDDEN = "HIDDEN", "已隐藏"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="reviews", verbose_name="订单")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews", verbose_name="用户"
    )
    merchant = models.ForeignKey(
        "merchants.Merchant", on_delete=models.CASCADE, related_name="reviews", verbose_name="商户"
    )
    score = models.PositiveSmallIntegerField("评分（1-5）")
    content = models.CharField("内容", max_length=500, blank=True, default="")
    images = models.JSONField("图片", default=list, blank=True)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.VISIBLE, db_index=True)
    reply = models.CharField("商户回复", max_length=500, blank=True, default="")
    replied_at = models.DateTimeField("回复时间", null=True, blank=True)

    class Meta:
        verbose_name = "订单评价"
        verbose_name_plural = "订单评价"
        db_table = "order_review"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(fields=["order", "user"], name="uq_order_review_order_user"),
            models.CheckConstraint(check=models.Q(score__gte=1) & models.Q(score__lte=5), name="ck_review_score_range"),
        ]
        indexes = [models.Index(fields=["merchant", "status"], name="ix_review_merchant_status")]

    def __str__(self):
        return f"{self.order_id}-{self.score}"


class CartItem(TimeStampedModel):
    """P0 单店购物车：服务端持久化，跨小程序/H5 共享。不做跨店合并。"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cart_items", verbose_name="用户"
    )
    merchant = models.ForeignKey(
        "merchants.Merchant", on_delete=models.CASCADE, related_name="cart_items", verbose_name="商户"
    )
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.CASCADE, related_name="cart_items", verbose_name="商品"
    )
    sku = models.ForeignKey(
        "catalog.ProductSku",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cart_items",
        verbose_name="规格",
    )
    quantity = models.PositiveIntegerField("数量", default=1)
    selected = models.BooleanField("已选中", default=True)

    class Meta:
        verbose_name = "购物车项"
        verbose_name_plural = "购物车项"
        db_table = "cart_item"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(fields=["user", "product", "sku"], name="uq_cart_user_product_sku"),
            models.CheckConstraint(check=models.Q(quantity__gt=0), name="ck_cart_quantity_positive"),
        ]
        indexes = [models.Index(fields=["user", "merchant"], name="ix_cart_user_merchant")]

    def __str__(self):
        return f"{self.user_id}-{self.product_id}x{self.quantity}"
