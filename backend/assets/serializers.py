from rest_framework import serializers
from .models import Department, Location, AssetCategory, Asset, RepairOrder, LifecycleLog


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = '__all__'


class LocationSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True, default='')

    class Meta:
        model = Location
        fields = ['id', 'name', 'parent', 'department', 'department_name']


class AssetCategorySerializer(serializers.ModelSerializer):
    asset_count = serializers.SerializerMethodField()

    class Meta:
        model = AssetCategory
        fields = '__all__'

    def get_asset_count(self, obj):
        return obj.asset_set.count()


class AssetListSerializer(serializers.ModelSerializer):
    """列表页：轻量 + 折旧关键值"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_code = serializers.CharField(source='category.code', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True, default='')
    department_name = serializers.CharField(source='department.name', read_only=True, default='')
    custodian_name = serializers.CharField(source='custodian.username', read_only=True, default='')
    display_tag = serializers.SerializerMethodField()

    class Meta:
        model = Asset
        fields = ['id', 'asset_tag', 'display_tag', 'sn', 'category', 'category_name', 'category_code',
                  'brand', 'model_spec', 'asset_name', 'status', 'location', 'location_name',
                  'department', 'department_name', 'custodian', 'custodian_name',
                  'purchase_date', 'original_value', 'useful_life', 'salvage_rate',
                  'used_years', 'current_value', 'remaining_life', 'custom']

    def get_display_tag(self, obj):
        return obj.sn or obj.asset_tag


class AssetDetailSerializer(AssetListSerializer):
    repair_count = serializers.SerializerMethodField()
    repair_total = serializers.SerializerMethodField()

    class Meta(AssetListSerializer.Meta):
        fields = AssetListSerializer.Meta.fields + ['repair_count', 'repair_total', 'created_at', 'updated_at']

    def get_repair_count(self, obj):
        return obj.repairs.count()

    def get_repair_total(self, obj):
        return float(sum(r.total_cost for r in obj.repairs.all()))


class AssetWriteSerializer(serializers.ModelSerializer):
    """创建/更新：自动生成编号、继承默认折旧参数、留痕"""
    class Meta:
        model = Asset
        fields = ['sn', 'category', 'brand', 'model_spec', 'asset_name', 'location', 'department',
                  'custodian', 'status', 'purchase_date', 'original_value',
                  'useful_life', 'salvage_rate', 'custom']

    def validate(self, attrs):
        # model_spec 变更时自动拆出设备名称（导入规律："设备名称 / 型号规格"）；
        # 未显式传 asset_name 时保持派生一致
        ms = attrs.get('model_spec')
        if ms is not None and ' / ' in ms and not attrs.get('asset_name'):
            attrs['asset_name'] = ms.split(' / ', 1)[0].strip()
        cat = attrs.get('category') or (self.instance.category if self.instance else None)
        if not cat:
            raise serializers.ValidationError('必须指定资产类别')
        if attrs.get('purchase_date'):
            today = serializers.DateField().to_internal_value
            # purchase_date 不能晚于今天
            import datetime
            if attrs['purchase_date'] > datetime.date.today():
                raise serializers.ValidationError({'purchase_date': '投产日期不能晚于今天'})
        # custom 按 schema 校验
        schema = cat.field_schema or []
        custom = attrs.get('custom') or {}
        for f in schema:
            v = custom.get(f['key'])
            if f.get('required') and (v is None or v == ''):
                raise serializers.ValidationError({'custom': f'缺少必填自定义字段: {f["label"]}'})
            if v is not None and f['type'] == 'number':
                try:
                    float(v)
                except (TypeError, ValueError):
                    raise serializers.ValidationError({'custom': f'{f["label"]} 必须是数字'})
        return attrs

    def create(self, validated):
        cat = validated['category']
        if validated.get('useful_life') is None:
            validated['useful_life'] = cat.default_life
        if validated.get('salvage_rate') is None:
            validated['salvage_rate'] = cat.default_salvage_rate
        # 自动编号 ZC-{类别码}-{年}-{5位流水}
        from django.utils import timezone
        year = timezone.now().year
        prefix = f'ZC-{cat.code}-{year}-'
        last = Asset.objects.filter(asset_tag__startswith=prefix).count() + 1
        validated['asset_tag'] = f'{prefix}{last:05d}'
        instance = super().create(validated)
        LifecycleLog.objects.create(asset=instance, action='create',
                                    detail={'source': 'manual'}, operator=self.context['request'].user)
        return instance

    def update(self, instance, validated):
        old = {f: getattr(instance, f.id if hasattr(f, 'id') else f) for f in []}  # noop
        changed = {k: (getattr(instance, k), v) for k, v in validated.items()
                   if getattr(instance, k, None) != v and k not in ('custom',)}
        instance = super().update(instance, validated)
        if changed:
            LifecycleLog.objects.create(asset=instance, action='update',
                                        detail={k: [str(a), str(b)] for k, (a, b) in changed.items()},
                                        operator=self.context['request'].user)
        return instance


class RepairOrderSerializer(serializers.ModelSerializer):
    asset_tag = serializers.CharField(source='asset.asset_tag', read_only=True)
    # 台账口径的资产编号（sn 即原始台账表格的「资产号」，如 NBB-2805/BG001-861）
    display_tag = serializers.SerializerMethodField()
    total_cost = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = RepairOrder
        fields = '__all__'

    def get_display_tag(self, obj):
        return obj.asset.sn or obj.asset.asset_tag

    def update(self, instance, validated):
        prev_status = instance.status
        instance = super().update(instance, validated)
        if prev_status == 'pending' and instance.status == 'done':
            LifecycleLog.objects.create(asset=instance.asset, action='repair',
                                        detail={'cost': float(instance.total_cost),
                                                'parts': instance.parts_replaced,
                                                'vendor': instance.vendor},
                                        operator=self.context['request'].user)
        return instance


class LifecycleLogSerializer(serializers.ModelSerializer):
    operator_name = serializers.CharField(source='operator.username', read_only=True, default='')

    class Meta:
        model = LifecycleLog
        fields = ['id', 'action', 'detail', 'operator_name', 'created_at']
