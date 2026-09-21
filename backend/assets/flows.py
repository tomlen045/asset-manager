"""P2-1 资产流程：领用/归还/调拨/报废 申请-审批模型 + P2-2 盘点任务"""
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model


class AssetFlow(models.Model):
    """资产流程单：assign(领用)/return(归还)/transfer(调拨)/scrap(报废)
    状态：pending(待审批) → approved(已批准，自动执行) / rejected(已驳回)"""
    TYPES = [
        ('assign', '领用'), ('return', '归还'), ('transfer', '调拨'), ('scrap', '报废'),
    ]
    STATUS = [('pending', '待审批'), ('approved', '已批准'), ('rejected', '已驳回')]

    flow_no = models.CharField('流程单号', max_length=32, unique=True)
    flow_type = models.CharField('类型', max_length=12, choices=TYPES)
    asset = models.ForeignKey('assets.Asset', on_delete=models.CASCADE,
                              related_name='flows', verbose_name='资产')
    # 领用/调拨目标
    to_user = models.ForeignKey(get_user_model(), null=True, blank=True,
                                on_delete=models.SET_NULL, related_name='flows_to',
                                verbose_name='目标使用人')
    to_department = models.ForeignKey('assets.Department', null=True, blank=True,
                                      on_delete=models.SET_NULL,
                                      verbose_name='目标部门')
    to_location = models.ForeignKey('assets.Location', null=True, blank=True,
                                    on_delete=models.SET_NULL,
                                    verbose_name='目标位置')
    reason = models.TextField('事由')
    status = models.CharField('状态', max_length=10, choices=STATUS, default='pending')
    applicant = models.ForeignKey(get_user_model(), on_delete=models.CASCADE,
                                  related_name='flows_applied', verbose_name='申请人')
    approver = models.ForeignKey(get_user_model(), null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name='flows_approved',
                                 verbose_name='审批人')
    approve_remark = models.CharField('审批意见', max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.flow_no} {self.get_flow_type_display()} {self.status}'

    def approve(self, approver, remark=''):
        """批准并执行资产状态变更（含留痕）"""
        self.status = 'approved'
        self.approver = approver
        self.approve_remark = remark or '同意'
        self.finished_at = timezone.now()
        a = self.asset
        detail = {}

        if self.flow_type == 'assign':
            a.status = 'in_use'
            a.custodian = self.to_user
            a.department = self.to_department or a.department
            detail = {'to_user': self.to_user.username if self.to_user else ''}
            action = 'assign'
        elif self.flow_type == 'return':
            a.status = 'in_stock'
            a.custodian = None
            detail = {'from_user': a.custodian.username if a.custodian else ''}
            action = 'return'
        elif self.flow_type == 'transfer':
            if self.to_department:
                a.department = self.to_department
            if self.to_location:
                a.location = self.to_location
            detail = {'to_dept': self.to_department.name if self.to_department else '',
                      'to_loc': self.to_location.name if self.to_location else ''}
            action = 'transfer'
        elif self.flow_type == 'scrap':
            a.status = 'scrapped'
            detail = {'reason': self.reason[:100]}
            action = 'scrap'

        a.save()
        self.save()
        a.lifecycle.create(action=action, detail=detail, operator=approver)

    def reject(self, approver, remark):
        self.status = 'rejected'
        self.approver = approver
        self.approve_remark = remark or '驳回'
        self.finished_at = timezone.now()
        self.save()


class Stocktake(models.Model):
    """盘点任务：圈定范围（类别/部门/位置/自定义标签）→ 逐台扫码确认 → 差异报表"""
    name = models.CharField('任务名称', max_length=100)
    # 范围：空=全部
    category = models.ForeignKey('assets.AssetCategory', null=True, blank=True,
                                 on_delete=models.SET_NULL, verbose_name='限定类别')
    department = models.ForeignKey('assets.Department', null=True, blank=True,
                                   on_delete=models.SET_NULL, verbose_name='限定部门')
    custom_filter = models.JSONField('自定义标签过滤', null=True, blank=True,
                                     help_text='如 {"terminal_type": "生产类终端"}')
    STATUS = [('ongoing', '进行中'), ('finished', '已完成')]
    status = models.CharField('状态', max_length=10, choices=STATUS, default='ongoing')
    created_by = models.ForeignKey(get_user_model(), on_delete=models.CASCADE,
                                   verbose_name='创建人')
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def scope_queryset(self):
        from assets.models import Asset
        qs = Asset.objects.exclude(status='scrapped')
        if self.category:
            qs = qs.filter(category=self.category)
        if self.department:
            qs = qs.filter(department=self.department)
        if self.custom_filter:
            for k, v in self.custom_filter.items():
                qs = qs.filter(**{f'custom__{k}': v})
        return qs

    def stats(self):
        items = self.items.all()
        total = self.scope_queryset().count() or items.count()
        found = items.filter(found=True).count()
        unexpected = items.filter(unexpected=True).count()
        return {
            'total': total, 'found': found,
            'missing': max(total - found - unexpected, 0),
            'unexpected': unexpected,
            'progress': round(found / total * 100, 1) if total else 0,
        }


class StocktakeItem(models.Model):
    """盘点明细：found=已扫码确认；unexpected=账外资产（扫到但不在任务范围）"""
    stocktake = models.ForeignKey(Stocktake, on_delete=models.CASCADE,
                                  related_name='items', verbose_name='任务')
    asset = models.ForeignKey('assets.Asset', on_delete=models.CASCADE,
                              verbose_name='资产')
    found = models.BooleanField('已确认', default=False)
    found_at = models.DateTimeField(null=True, blank=True)
    found_location = models.CharField('实盘位置', max_length=100, blank=True)
    unexpected = models.BooleanField('账外', default=False)
    note = models.CharField('备注', max_length=200, blank=True)

    class Meta:
        unique_together = [('stocktake', 'asset')]
