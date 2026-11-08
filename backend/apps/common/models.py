"""跨领域复用的抽象模型。金额统一使用 BIGINT 存储「分」。"""

from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField("创建时间", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        abstract = True
        ordering = ("-created_at",)
