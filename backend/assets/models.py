"""
资产台账核心模型：
- AssetCategory 资产类别（含自定义字段schema、默认折旧参数）
- Asset 资产台账（财务字段固化 + custom JSON 扩展）
- RepairOrder 维修工单（AI经济寿命分析的数据燃料）
- LifecycleLog 全生命周期留痕（不可删改）
"""
from django.db import models
from django.utils import timezone
from decimal import Decimal
import math


class Department(models.Model):
    name = models.CharField('部门名称', max_length=64, unique=True)
    code = models.CharField('部门编码', max_length=20, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Location(models.Model):
    """存放地点：车间/仓库/机房（支持树形）"""
    name = models.CharField('位置名称', max_length=64)
    parent = models.ForeignKey('self', null=True, blank=True,
                               on_delete=models.SET_NULL, related_name='children',
                               verbose_name='上级位置')
    department = models.ForeignKey(Department, null=True, blank=True,
                                   on_delete=models.SET_NULL, verbose_name='管理部门')

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class AssetCategory(models.Model):
    """资产类别：终端/平板/扫描枪/打印头/一体机/显示器…"""
    name = models.CharField('类别名称', max_length=50, unique=True)
    code = models.CharField('类别编码', max_length=20, unique=True)
    default_life = models.IntegerField('默认报废年限(年)', default=8)
    default_salvage_rate = models.FloatField('默认残值率', default=0.05)
    # 自定义字段引擎：零改表扩展
    # [{"key":"print_life","label":"打印寿命(万张)","type":"number","required":false,"options":[]}]
    field_schema = models.JSONField('自定义字段定义', default=list, blank=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f'{self.name}({self.code})'


class AssetQuerySet(models.QuerySet):
    def active(self):
        return self.exclude(status='scrapped')

    def in_scope(self):
        """统计口径过滤：只统计 settings.STATS_CATEGORY_CODES 里的类别。
        所有统计面板/列表统一走这个入口；配置为 None 时不过滤（全量）。
        数据不做任何删除——这只是查询口径。"""
        from django.conf import settings
        codes = getattr(settings, 'STATS_CATEGORY_CODES', None)
        if codes:
            return self.filter(category__code__in=codes)
        return self


class Asset(models.Model):
    STATUS = [
        ('in_stock', '在库'),
        ('in_use', '在用'),
        ('repairing', '维修中'),
        ('idle', '闲置'),
        ('scrapped', '已报废'),
    ]

    # ── 基本信息 ──
    asset_tag = models.CharField('资产编号', max_length=32, unique=True)
    sn = models.CharField('序列号', max_length=64, blank=True, db_index=True)
    category = models.ForeignKey(AssetCategory, on_delete=models.PROTECT, verbose_name='资产类别')
    brand = models.CharField('品牌', max_length=50, blank=True)
    model_spec = models.CharField('型号规格', max_length=100, blank=True)
    asset_name = models.CharField('设备名称', max_length=100, blank=True, db_index=True)
    location = models.ForeignKey(Location, null=True, blank=True, on_delete=models.SET_NULL, verbose_name='存放位置')
    department = models.ForeignKey(Department, null=True, blank=True, on_delete=models.SET_NULL, verbose_name='所属部门')
    custodian = models.ForeignKey('accounts.User', null=True, blank=True,
                                  on_delete=models.SET_NULL, verbose_name='使用人')
    status = models.CharField('状态', max_length=16, choices=STATUS, default='in_stock')

    # ── 财务字段（固化列：可索引可统计，折旧引擎核心输入）──
    purchase_date = models.DateField('投产日期')
    original_value = models.DecimalField('原值(元)', max_digits=12, decimal_places=2)
    useful_life = models.IntegerField('使用年限(年)', null=True, blank=True,
                                      help_text='留空继承类别默认')
    salvage_rate = models.FloatField('残值率', null=True, blank=True,
                                     help_text='留空继承类别默认')

    # ── 扩展字段（零改表）──
    custom = models.JSONField('自定义字段', default=dict, blank=True)

    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    objects = AssetQuerySet.as_manager()

    class Meta:
        ordering = []

    def __str__(self):
        return f'{self.asset_tag} {self.brand} {self.model_spec}'

    # ── 折旧计算（规则引擎基线，全部可审计）──
    @property
    def eff_life(self) -> int:
        """生效使用年限"""
        return self.useful_life or (self.category.default_life if self.category else 8)

    @property
    def eff_salvage_rate(self) -> float:
        return self.salvage_rate if self.salvage_rate is not None else (
            self.category.default_salvage_rate if self.category else 0.05)

    @property
    def used_years(self) -> float:
        """已使用年数（含小数）"""
        days = (timezone.now().date() - self.purchase_date).days
        return round(max(days, 0) / 365.25, 2)

    @property
    def annual_depreciation(self) -> Decimal:
        """年折旧额 = 原值×(1−残值率)/年限 直线法"""
        return (self.original_value * Decimal(str(1 - self.eff_salvage_rate))
                / Decimal(self.eff_life)).quantize(Decimal('0.01'))

    @property
    def current_value(self) -> Decimal:
        """当前净值 = 原值 − 年折旧×已用年数，下限=残值"""
        salvage = (self.original_value * Decimal(str(self.eff_salvage_rate))).quantize(Decimal('0.01'))
        net = self.original_value - self.annual_depreciation * Decimal(str(self.used_years))
        return max(net, salvage)

    @property
    def remaining_life(self) -> float:
        return round(self.eff_life - self.used_years, 2)


class RepairOrder(models.Model):
    """维修工单：AI经济寿命分析的数据燃料"""
    STATUS = [('pending', '待维修'), ('done', '已完成'), ('scrapped', '维修后报废')]

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='repairs', verbose_name='资产')
    report_date = models.DateField('报修日期', default=timezone.localdate)
    finish_date = models.DateField('完成日期', null=True, blank=True)
    fault_desc = models.TextField('故障描述')
    # [{"name":"扫描引擎","cost":400.00}]
    parts_replaced = models.JSONField('更换配件明细', default=list, blank=True)
    labor_cost = models.DecimalField('人工/服务费(元)', max_digits=10, decimal_places=2, default=0)
    vendor = models.CharField('维修商', max_length=64, blank=True)
    status = models.CharField('状态', max_length=12, choices=STATUS, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-report_date']

    @property
    def total_cost(self) -> Decimal:
        parts = sum(Decimal(str(p.get('cost', 0))) for p in (self.parts_replaced or []))
        labor = self.labor_cost if isinstance(self.labor_cost, Decimal) else Decimal(str(self.labor_cost or 0))
        return (parts + labor).quantize(Decimal('0.01'))


class LifecycleLog(models.Model):
    """全生命周期留痕：只增不改不删"""
    ACTIONS = [
        ('create', '入库'), ('assign', '领用'), ('return', '归还'),
        ('transfer', '调拨'), ('repair', '维修'), ('stocktake', '盘点'),
        ('scrap', '报废'), ('update', '信息变更'),
    ]
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='lifecycle', verbose_name='资产')
    action = models.CharField('动作', max_length=16, choices=ACTIONS)
    detail = models.JSONField('详情', default=dict, blank=True)
    operator = models.ForeignKey('accounts.User', null=True, on_delete=models.SET_NULL, verbose_name='操作人')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']

from .orgtree import DeptNode  # noqa: F401 (部门组织树)


class PdaDevice(models.Model):
    """移动设备（PDA/平板）定位台账——与 Asset 可选关联"""
    mac = models.CharField('MAC地址', max_length=17, unique=True, db_index=True)
    device_type = models.CharField('设备类型', max_length=10, blank=True, default='pda')
    name = models.CharField('设备名称', max_length=60, blank=True, default='')
    device_no = models.CharField('设备编号', max_length=40, blank=True, default='')
    device_model = models.CharField('型号', max_length=60, blank=True, default='')
    android_ver = models.CharField('Android版本', max_length=20, blank=True, default='')
    department = models.ForeignKey('Department', verbose_name='责任部门', null=True, blank=True,
                                   on_delete=models.SET_NULL)
    owner = models.CharField('责任人/班组', max_length=40, blank=True, default='')
    asset = models.ForeignKey(Asset, verbose_name='关联资产', null=True, blank=True,
                              on_delete=models.SET_NULL)
    # 心跳上报数据
    ap_bssid = models.CharField('关联AP(BSSID)', max_length=32, blank=True, default='')
    ap_name = models.CharField('AP名称', max_length=60, blank=True, default='')
    zone = models.CharField('所在区域', max_length=40, blank=True, default='', db_index=True)
    rssi = models.IntegerField('信号强度(dBm)', null=True, blank=True)
    ssid = models.CharField('SSID', max_length=40, blank=True, default='')
    battery = models.IntegerField('电量%', null=True, blank=True)
    ip = models.GenericIPAddressField('IP', null=True, blank=True)
    last_seen = models.DateTimeField('最后心跳', null=True, blank=True, db_index=True)
    ring_command_at = models.DateTimeField('响铃指令时间', null=True, blank=True)
    note = models.CharField('备注', max_length=200, blank=True, default='')
    pos_x = models.FloatField('平面图X%', null=True, blank=True)
    pos_y = models.FloatField('平面图Y%', null=True, blank=True)
    allowed_zones = models.JSONField('允许区域', blank=True, default=list)
    linked_by = models.CharField('关联方式', max_length=20, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-last_seen']

    def __str__(self):
        return self.name or self.mac

    @property
    def online(self):
        """15分钟内有心跳/活跃=在线（NAC列表5分钟刷新一次，放宽窗口防误判）"""
        if not self.last_seen:
            return False
        from django.utils import timezone
        return (timezone.now() - self.last_seen).total_seconds() < 900

    @property
    def offline_days(self):
        """离线天数（用于>3天告警）"""
        if not self.last_seen:
            return None
        from django.utils import timezone
        return (timezone.now() - self.last_seen).days

    def to_dict(self):
        from django.utils import timezone
        return {
            'id': self.id, 'mac': self.mac, 'name': self.name,
            'type': self.device_type or 'pda',
            'device_no': self.device_no, 'device_model': self.device_model,
            'android_ver': self.android_ver,
            'department': self.department.name if self.department else '',
            'owner': self.owner, 'asset_id': self.asset_id,
            'ap_bssid': self.ap_bssid, 'ap_name': self.ap_name,
            'zone': self.zone, 'rssi': self.rssi, 'ssid': self.ssid,
            'battery': self.battery, 'ip': self.ip,
            'last_seen': self.last_seen.strftime('%Y-%m-%d %H:%M') if self.last_seen else None,
            'online': self.online,
            'qr_url': '/#/pda-scan?mac=' + self.mac,
            'offline_days': self.offline_days,
            'stale': self.offline_days is not None and self.offline_days >= 3,
            'note': self.note,
            'allowed_zones': self.allowed_zones or [],
            'asset_tag': self.asset.asset_tag if self.asset_id else '',
            'asset_name': self.asset.asset_name if self.asset_id else '',
            'custodian': (self.asset.custodian.username if self.asset and self.asset.custodian else ''),
            'linked_by': self.linked_by,
        }


class PdaScanLog(models.Model):
    """扫码领用/归还登记"""
    device = models.ForeignKey(PdaDevice, verbose_name='设备', on_delete=models.CASCADE,
                               related_name='scan_logs')
    action = models.CharField('动作', max_length=10)  # take / return
    person = models.CharField('经手人', max_length=40)
    note = models.CharField('备注', max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def to_dict(self):
        return {
            'id': self.id, 'device': str(self.device), 'device_mac': self.device.mac,
            'action': self.action,
            'action_text': '领用' if self.action == 'take' else '归还',
            'person': self.person, 'note': self.note,
            'time': self.created_at.strftime('%Y-%m-%d %H:%M'),
        }


class PdaHeartbeatHistory(models.Model):
    """心跳历史快照（趋势图数据源）——每次心跳追加一条"""
    device = models.ForeignKey(PdaDevice, verbose_name='设备', on_delete=models.CASCADE,
                               related_name='hb_history')
    ts = models.DateTimeField('时间', db_index=True, auto_now_add=True)
    battery = models.IntegerField('电量%', null=True, blank=True)
    online = models.BooleanField('在线', default=True)
    zone = models.CharField('区域', max_length=40, blank=True, default='')
    ap_name = models.CharField('AP', max_length=60, blank=True, default='')
    rssi = models.IntegerField('信号', null=True, blank=True)

    class Meta:
        ordering = ['-ts']


class PdaMapConfig(models.Model):
    """平面图配置（单行）：底图 + AP 坐标"""
    floor_image = models.BinaryField('平面图底图', null=True, blank=True)
    image_mime = models.CharField(max_length=40, blank=True, default='')
    ap_coords = models.TextField('AP坐标JSON', blank=True, default='[]')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '平面图配置'

    @classmethod
    def load(cls):
        obj = cls.objects.first()
        if not obj:
            obj = cls.objects.create()
        return obj


class PdaHourlySnapshot(models.Model):
    """终端每小时在线快照（在线率报表数据源）"""
    hour = models.DateTimeField('整点', db_index=True)
    mac = models.CharField('MAC', max_length=17)
    zone = models.CharField('区域', max_length=40, blank=True, default='')
    online = models.BooleanField('在线', default=False)

    class Meta:
        ordering = ['hour']
        verbose_name = '终端每小时快照'


class PdaZoneAlarm(models.Model):
    """区域围栏告警：终端出现在非允许区域"""
    mac = models.CharField('MAC地址', max_length=17, db_index=True)
    device_name = models.CharField('设备名称', max_length=60, blank=True, default='')
    from_zone = models.CharField('原区域', max_length=40, blank=True, default='')
    to_zone = models.CharField('新区域', max_length=40, blank=True, default='')
    ap_name = models.CharField('接入点', max_length=60, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField('已读', default=False, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = '区域围栏告警'


class PdaAcConfig(models.Model):
    """信锐 AC SNMP 对接配置（单行）"""
    ac_ip = models.CharField('AC 地址', max_length=60, blank=True, default='')
    community = models.CharField('SNMP 团体名', max_length=60, blank=True, default='public')
    nac_url = models.CharField('NAC 地址', max_length=120, blank=True, default='')
    nac_user = models.CharField('NAC 账号', max_length=60, blank=True, default='')
    nac_pass = models.CharField('NAC 密码', max_length=120, blank=True, default='')
    ap_cache = models.TextField('AP缓存JSON', blank=True, default='[]')
    last_sync = models.DateTimeField('最近同步', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'AC 对接配置'

    @classmethod
    def load(cls):
        obj = cls.objects.first()
        if not obj:
            obj = cls.objects.create(community='public')
        return obj
