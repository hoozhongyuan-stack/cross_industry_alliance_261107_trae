"""规则版本、审核任务、操作日志与内容位。

规则版本用于给订单/售后/结算提供不可变快照；操作日志只追加。
"""

from django.db import models

from apps.common.models import TimeStampedModel


class RuleVersion(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "草稿"
        ACTIVE = "ACTIVE", "生效中"
        RETIRED = "RETIRED", "已失效"

    version_no = models.CharField("版本号", max_length=32, unique=True)
    snapshot_json = models.JSONField("规则快照", default=dict)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True)
    effective_at = models.DateTimeField("生效时间", null=True, blank=True)
    created_by_id = models.BigIntegerField("创建人 ID", null=True, blank=True)
    created_by_name = models.CharField("创建人", max_length=60, blank=True, default="")
    remark = models.CharField("说明", max_length=200, blank=True, default="")

    class Meta:
        verbose_name = "规则版本"
        verbose_name_plural = "规则版本"
        db_table = "rule_version"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["status", "effective_at"], name="ix_rule_status_effective")]

    def __str__(self):
        return self.version_no


class AuditTask(TimeStampedModel):
    class BizType(models.TextChoices):
        MERCHANT = "MERCHANT", "商户入驻"
        PRODUCT = "PRODUCT", "商品上架"
        REVIEW = "REVIEW", "评价内容"
        QUALIFICATION = "QUALIFICATION", "资质材料"

    class Status(models.TextChoices):
        PENDING = "PENDING", "待审核"
        PROCESSING = "PROCESSING", "审核中"
        APPROVED = "APPROVED", "已通过"
        REJECTED = "REJECTED", "已驳回"
        CANCELLED = "CANCELLED", "已取消"

    biz_type = models.CharField("业务类型", max_length=20, choices=BizType.choices, db_index=True)
    biz_id = models.BigIntegerField("业务单据 ID")
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    decision = models.CharField("审核结论", max_length=16, blank=True, default="")
    reason = models.CharField("审核意见", max_length=200, blank=True, default="")
    assigned_to_id = models.BigIntegerField("审核人 ID", null=True, blank=True)
    assigned_to_name = models.CharField("审核人", max_length=60, blank=True, default="")
    handled_at = models.DateTimeField("处理时间", null=True, blank=True)

    class Meta:
        verbose_name = "审核任务"
        verbose_name_plural = "审核任务"
        db_table = "audit_task"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["biz_type", "status", "created_at"], name="ix_audit_biz_status_created"),
            models.Index(fields=["assigned_to_id", "status"], name="ix_audit_assignee_status"),
        ]

    def __str__(self):
        return f"{self.biz_type}-{self.biz_id}-{self.status}"


class OperationLog(TimeStampedModel):
    operator_id = models.BigIntegerField("操作人 ID", null=True, blank=True)
    operator_name = models.CharField("操作人", max_length=60, blank=True, default="")
    action = models.CharField("动作", max_length=40, db_index=True)
    biz_type = models.CharField("业务类型", max_length=24, blank=True, default="")
    biz_id = models.BigIntegerField("业务单据 ID", null=True, blank=True)
    before_json = models.JSONField("变更前", default=dict, blank=True)
    after_json = models.JSONField("变更后", default=dict, blank=True)
    ip = models.GenericIPAddressField("IP", null=True, blank=True)
    user_agent = models.CharField("UA", max_length=200, blank=True, default="")

    class Meta:
        verbose_name = "操作日志"
        verbose_name_plural = "操作日志"
        db_table = "operation_log"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["biz_type", "biz_id", "created_at"], name="ix_oplog_biz_created")]

    def __str__(self):
        return f"{self.operator_name}-{self.action}"


class ContentItem(TimeStampedModel):
    class SlotCode(models.TextChoices):
        HOME_BANNER = "HOME_BANNER", "首页 Banner"
        HOME_RECOMMEND = "HOME_RECOMMEND", "首页推荐位"
        CATEGORY_ENTRY = "CATEGORY_ENTRY", "类目入口"
        MERCHANT_FEATURE = "MERCHANT_FEATURE", "商户精选"

    class Status(models.TextChoices):
        ENABLED = "ENABLED", "展示中"
        DISABLED = "DISABLED", "已下线"

    slot_code = models.CharField("内容位", max_length=24, choices=SlotCode.choices, db_index=True)
    title = models.CharField("标题", max_length=80, blank=True, default="")
    image_url = models.URLField("图片", blank=True, default="")
    link_url = models.CharField("跳转链接", max_length=200, blank=True, default="")
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.ENABLED, db_index=True)
    sort = models.IntegerField("排序", default=0)
    start_at = models.DateTimeField("开始展示", null=True, blank=True)
    end_at = models.DateTimeField("结束展示", null=True, blank=True)

    class Meta:
        verbose_name = "内容位"
        verbose_name_plural = "内容位"
        db_table = "content_item"
        ordering = ("slot_code", "sort", "id")
        indexes = [models.Index(fields=["slot_code", "status", "sort"], name="ix_content_slot_status_sort")]

    def __str__(self):
        return f"{self.slot_code}-{self.title}"
