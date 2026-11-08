"""类目、商品/服务、SKU 库存与预约时段。价格单位为分。"""

from django.db import models

from apps.common.models import TimeStampedModel


class Category(TimeStampedModel):
    class Status(models.TextChoices):
        ENABLED = "ENABLED", "启用"
        DISABLED = "DISABLED", "停用"

    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="children", verbose_name="上级类目"
    )
    name = models.CharField("类目名", max_length=40)
    icon_url = models.URLField("图标", blank=True, default="")
    level = models.PositiveSmallIntegerField("层级", default=1)
    sort = models.IntegerField("排序", default=0)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.ENABLED, db_index=True)
    commission_rate = models.DecimalField("默认佣金率", max_digits=5, decimal_places=4, default=0)

    class Meta:
        verbose_name = "类目"
        verbose_name_plural = "类目"
        db_table = "category"
        ordering = ("sort", "id")
        indexes = [models.Index(fields=["parent", "sort"], name="ix_category_parent_sort")]

    def __str__(self):
        return self.name


class Product(TimeStampedModel):
    class Type(models.TextChoices):
        PHYSICAL = "PHYSICAL", "实物商品"
        SERVICE = "SERVICE", "到店服务"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "草稿"
        PENDING = "PENDING", "待审核"
        ON_SALE = "ON_SALE", "在售"
        OFF_SALE = "OFF_SALE", "已下架"
        REJECTED = "REJECTED", "审核驳回"

    class DeliveryType(models.TextChoices):
        EXPRESS = "EXPRESS", "快递配送"
        PICKUP = "PICKUP", "到店自提"
        VERIFY = "VERIFY", "到店核销"
        APPOINTMENT = "APPOINTMENT", "预约服务"

    merchant = models.ForeignKey(
        "merchants.Merchant", on_delete=models.CASCADE, related_name="products", verbose_name="商户"
    )
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="products", verbose_name="类目"
    )
    type = models.CharField("商品类型", max_length=16, choices=Type.choices)
    title = models.CharField("标题", max_length=120)
    subtitle = models.CharField("副标题", max_length=200, blank=True, default="")
    cover_url = models.URLField("封面", blank=True, default="")
    images = models.JSONField("图片列表", default=list, blank=True)
    description = models.TextField("详情", blank=True, default="")
    price = models.BigIntegerField("展示价（分）", default=0)
    original_price = models.BigIntegerField("划线价（分）", default=0)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True)
    verify_days = models.PositiveSmallIntegerField("核销有效期（天）", default=30)
    appointment_required = models.BooleanField("需预约", default=False)
    delivery_types = models.JSONField("履约方式", default=list, blank=True)
    sold_count = models.PositiveIntegerField("已售件数", default=0)
    sort = models.IntegerField("排序", default=0)

    class Meta:
        verbose_name = "商品/服务"
        verbose_name_plural = "商品/服务"
        db_table = "product"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["merchant", "status"], name="ix_product_merchant_status"),
            models.Index(fields=["category", "status"], name="ix_product_category_status"),
        ]

    def __str__(self):
        return self.title


class ProductSku(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="skus", verbose_name="商品")
    sku_code = models.CharField("规格编码", max_length=40)
    spec_json = models.JSONField("规格快照", default=dict, blank=True)
    price = models.BigIntegerField("售价（分）")
    stock = models.IntegerField("总库存", default=0)
    locked_stock = models.IntegerField("下单锁定", default=0)
    sold_stock = models.IntegerField("已售", default=0)
    version = models.PositiveIntegerField("乐观锁版本", default=0)

    class Meta:
        verbose_name = "商品规格"
        verbose_name_plural = "商品规格"
        db_table = "product_sku"
        constraints = [models.UniqueConstraint(fields=["product", "sku_code"], name="uq_product_sku_code")]
        indexes = [models.Index(fields=["product", "price"], name="ix_sku_product_price")]

    def __str__(self):
        return f"{self.product_id}-{self.sku_code}"

    @property
    def available_stock(self) -> int:
        return max(self.stock - self.locked_stock - self.sold_stock, 0)


class ServiceSlotTemplate(TimeStampedModel):
    """按周重复的营业时段模板，定时任务据此生成具体日期的 ServiceSlot。"""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="slot_templates", verbose_name="商品")
    weekday = models.PositiveSmallIntegerField("星期（0=周一）")
    start_time = models.TimeField("开始时间")
    end_time = models.TimeField("结束时间")
    capacity = models.PositiveIntegerField("可预约人数", default=1)
    enabled = models.BooleanField("启用", default=True)

    class Meta:
        verbose_name = "时段模板"
        verbose_name_plural = "时段模板"
        db_table = "service_slot_template"
        constraints = [
            models.UniqueConstraint(
                fields=["product", "weekday", "start_time"], name="uq_slot_template_product_weekday_start"
            )
        ]
        indexes = [models.Index(fields=["product", "weekday"], name="ix_slot_tpl_prod_weekday")]

    def __str__(self):
        return f"{self.product_id}-{self.weekday}-{self.start_time}"


class ServiceSlot(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "OPEN", "开放"
        FULL = "FULL", "已约满"
        CLOSED = "CLOSED", "关闭"

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="slots", verbose_name="商品")
    slot_date = models.DateField("日期")
    start_time = models.TimeField("开始时间")
    end_time = models.TimeField("结束时间")
    capacity = models.PositiveIntegerField("可预约人数", default=1)
    reserved_count = models.PositiveIntegerField("已预约人数", default=0)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.OPEN, db_index=True)

    class Meta:
        verbose_name = "预约时段"
        verbose_name_plural = "预约时段"
        db_table = "service_slot"
        constraints = [
            models.UniqueConstraint(fields=["product", "slot_date", "start_time"], name="uq_slot_product_date_start")
        ]
        indexes = [models.Index(fields=["product", "slot_date", "status"], name="ix_slot_product_date_status")]

    def __str__(self):
        return f"{self.product_id}-{self.slot_date}-{self.start_time}"

    @property
    def remaining(self) -> int:
        return max(self.capacity - self.reserved_count, 0)
