from django.utils import timezone
"""资产台账 API 视图：CRUD + 批量导入 + 经济分析 + 盘点"""
import json
import io
from django.db import transaction
from django.http import HttpResponse
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill

from .models import Department, Location, AssetCategory, Asset, RepairOrder, LifecycleLog
from .serializers import (DepartmentSerializer, LocationSerializer, AssetCategorySerializer,
                          AssetListSerializer, AssetDetailSerializer, AssetWriteSerializer,
                          RepairOrderSerializer, LifecycleLogSerializer)
from .economy import analyze_asset


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer


class LocationViewSet(viewsets.ModelViewSet):
    queryset = Location.objects.all()
    serializer_class = LocationSerializer


class AssetCategoryViewSet(viewsets.ModelViewSet):
    queryset = AssetCategory.objects.all()
    serializer_class = AssetCategorySerializer


class AssetViewSet(viewsets.ModelViewSet):
    queryset = Asset.objects.select_related('category', 'location', 'department', 'custodian')

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return AssetWriteSerializer
        if self.action == 'retrieve':
            return AssetDetailSerializer
        return AssetListSerializer

    def create(self, request, *args, **kwargs):
        """创建后用 Detail 序列化器返回（含id/净值/编号等计算字段）"""
        s = self.get_serializer(data=request.data)
        s.is_valid(raise_exception=True)
        instance = s.save()
        out = AssetDetailSerializer(instance, context={'request': request})
        headers = self.get_success_headers(out.data)
        return Response(out.data, status=status.HTTP_201_CREATED, headers=headers)

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        kw = p.get('kw')
        if kw:
            from django.db.models import Q
            import re as _re
            # 多词 OR 检索：按空格/逗号拆词，如「微机 手提电脑」= 匹配任一词；
            # 单词内命中编号/序列号/品牌/型号规格/设备名称任意字段即可
            words = [w for w in _re.split(r'[\s,，、]+', kw.strip()) if w]
            if words:
                combined = Q()
                for w in words:
                    combined |= (Q(asset_tag__icontains=w) | Q(sn__icontains=w) |
                                 Q(brand__icontains=w) | Q(model_spec__icontains=w) |
                                 Q(asset_name__icontains=w))
                qs = qs.filter(combined)
        cat = p.get('category') or p.get('categories')
        if cat:
            # 支持逗号分隔多选：category=3,4（或 categories=3,4）→ id 在集合内
            ids = [int(x) for x in str(cat).split(',') if x.strip().isdigit()]
            qs = qs.filter(category_id__in=ids) if ids else qs.none()
        elif not p.get('all_categories') and self.action != 'retrieve':
            # 统计口径：默认只显示口径内类别；用户显式选类别或传 all_categories=1 时不限制；
            # 单台详情（retrieve）不受口径限制，从任何入口都能打开
            from django.conf import settings
            codes = getattr(settings, 'STATS_CATEGORY_CODES', None)
            if codes:
                qs = qs.filter(category__code__in=codes)
        st = p.get('status')
        if st:
            # 支持逗号分隔多选：status=in_use,idle
            sts = [x for x in str(st).split(',') if x.strip()]
            qs = qs.filter(status__in=sts) if sts else qs.none()
        tt = p.get('terminal_type')
        if tt:
            qs = qs.filter(custom__terminal_type=tt)
        dept = p.get('department')
        if dept:
            qs = qs.filter(department_id=dept)
        # 未分配部门清单：部门为空的资产（不受统计口径限制，方便全量排查补录）
        if p.get('no_dept') in ('1', 'true'):
            qs = qs.filter(department__isnull=True)
        # 超期服役：已用年限 > 标准使用年限（SQLite 原生表达式）
        if p.get('overdue') in ('1', 'true'):
            from django.db.models.expressions import RawSQL
            OVERDUE_SQL = ('(julianday(CURRENT_DATE) - julianday(purchase_date)) / 365.25 > '
                           'COALESCE(useful_life, COALESCE((SELECT default_life FROM assets_assetcategory '
                           'WHERE assets_assetcategory.id=assets_asset.category_id), 8))')
            qs = qs.annotate(_oy=RawSQL(OVERDUE_SQL, [])).filter(_oy=True)
        dn = p.get('dept_node')
        if dn:
            # 部门树节点：支持逗号分隔多选，结果为多个子树的并集
            from .orgtree import DeptNode
            names = set()
            for piece in str(dn).split(','):
                piece = piece.strip()
                if not piece:
                    continue
                try:
                    node = DeptNode.objects.get(pk=piece)
                except (DeptNode.DoesNotExist, ValueError):
                    continue
                names |= node.descendant_dept_names()
            if names:
                qs = qs.filter(department__name__in=names)
        loc = p.get('location')
        if loc:
            qs = qs.filter(location_id=loc)
        cust = p.get('custodian')
        if cust:
            qs = qs.filter(custodian_id=cust)
        # 净值/原值区间（净值是 Python property，用 SQLite 原生表达式近似：
        # 净值 = MAX(原值 - (原值×(1-残值率)/年限)×已用年数, 原值×残值率)，
        # 已用年数 = (今天-投产日期)/365.25 —— 与 Python 计算一致到小数级）
        net_expr = (
            'MAX(original_value - (original_value * (1 - COALESCE(salvage_rate, '
            'COALESCE((SELECT default_salvage_rate FROM assets_assetcategory WHERE id=assets_asset.category_id), 0.05))) '
            '/ COALESCE(useful_life, COALESCE((SELECT default_life FROM assets_assetcategory WHERE id=assets_asset.category_id), 8))) '
            '* ((julianday(\'now\') - julianday(purchase_date)) / 365.25), '
            'original_value * COALESCE(salvage_rate, '
            'COALESCE((SELECT default_salvage_rate FROM assets_assetcategory WHERE id=assets_asset.category_id), 0.05)))'
        )
        try:
            if p.get('net_min'):
                qs = qs.extra(where=[f'{net_expr} >= %s'], params=[float(p['net_min'])])
            if p.get('net_max'):
                qs = qs.extra(where=[f'{net_expr} <= %s'], params=[float(p['net_max'])])
            if p.get('orig_min'):
                qs = qs.filter(original_value__gte=float(p['orig_min']))
            if p.get('orig_max'):
                qs = qs.filter(original_value__lte=float(p['orig_max']))
        except ValueError:
            pass
        # 投产日期区间
        if p.get('pdate_from'):
            qs = qs.filter(purchase_date__gte=p['pdate_from'])
        if p.get('pdate_to'):
            qs = qs.filter(purchase_date__lte=p['pdate_to'])
        # 已用年限区间（与 bigscreen.py 分桶同源：已用年数=(今天-投产日期)/365.25）
        # age_gt 用于「3-5年」等左开区间（>min 且 <=max），避免与相邻段边界重复
        AGE_SQL = '(julianday(CURRENT_DATE) - julianday(purchase_date)) / 365.25'
        try:
            if p.get('age_segments'):
                # 多段多选：age_segments=3-5,6-8 → ((AGE>2 AND <=5) OR (AGE>5 AND <=8))
                # 段边界与 bigscreen.py 分桶严格一致（连续边界：<=2 / >2&<=5 / >5&<=8 / >8）
                SEG_SQL = {'0-2': f'{AGE_SQL} <= 2',
                           '3-5': f'({AGE_SQL} > 2 AND {AGE_SQL} <= 5)',
                           '6-8': f'({AGE_SQL} > 5 AND {AGE_SQL} <= 8)',
                           '8-9': f'({AGE_SQL} > 8 AND {AGE_SQL} <= 9)',
                           '9-10': f'({AGE_SQL} > 9 AND {AGE_SQL} <= 10)',
                           '10+': f'{AGE_SQL} > 10'}
                segs = [SEG_SQL[s.strip()] for s in str(p['age_segments']).split(',')
                        if s.strip() in SEG_SQL]
                if segs:
                    qs = qs.extra(where=['(' + ' OR '.join(segs) + ')'])
            else:
                if p.get('age_gt') not in (None, ''):
                    qs = qs.extra(where=[f'{AGE_SQL} > %s'], params=[float(p['age_gt'])])
                if p.get('age_lte') not in (None, ''):
                    qs = qs.extra(where=[f'{AGE_SQL} <= %s'], params=[float(p['age_lte'])])
        except (ValueError, TypeError):
            pass
        # 报废数据默认不显示（用户需求：统计与列表默认不含报废）；
        # 状态筛选显式勾选「已报废」或传 include_scrapped=1 时才包含
        if p.get('include_scrapped') not in ('1', 'true')                 and p.get('exclude_scrapped') not in ('0', 'false')                 and 'scrapped' not in str(p.get('status') or '').split(','):
            qs = qs.exclude(status='scrapped')
        # 出厂编号（custom JSON 内模糊匹配，大小写不敏感）
        if p.get('made_no'):
            qs = qs.filter(custom__made_no__icontains=p['made_no'].strip())
        # 排序（净值/已用年限是计算值，用 RawSQL 排序，params=[] 防 % 格式化）
        from django.db.models.expressions import RawSQL
        NET_SQL = ('original_value - (original_value * (1 - COALESCE(salvage_rate, 0.05)) '
                   '/ COALESCE(useful_life, 8)) * ((julianday(CURRENT_DATE) - julianday(purchase_date)) / 365.25)')
        ordering = p.get('ordering')
        ORD = {'current_value': (NET_SQL, ''),
               '-current_value': (NET_SQL, 'DESC'),
               'original_value': ('original_value', ''),
               '-original_value': ('original_value', 'DESC'),
               'purchase_date': ('purchase_date', ''),
               '-purchase_date': ('purchase_date', 'DESC'),
               'used_years': ('(julianday(CURRENT_DATE) - julianday(purchase_date))', ''),
               '-used_years': ('(julianday(CURRENT_DATE) - julianday(purchase_date))', 'DESC')}
        if ordering in ORD:
            expr, direction = ORD[ordering]
            sql_expr = RawSQL(expr, [])
            qs = qs.order_by(sql_expr.desc() if direction == 'DESC' else sql_expr)
        return qs

    @action(detail=True, methods=['get'])
    def lifecycle(self, request, pk=None):
        logs = self.get_object().lifecycle.all()[:100]
        return Response(LifecycleLogSerializer(logs, many=True).data)

    @action(detail=True, methods=['get'])
    def economy(self, request, pk=None):
        """单台资产经济寿命分析（规则引擎）"""
        asset = self.get_object()
        report = analyze_asset(asset, asset.repairs.filter(status='done'))
        return Response(report)

    @action(detail=False, methods=['get'])
    def import_template(self, request):
        """下载批量导入模板（含示例行与类别下拉说明）"""
        wb = Workbook()
        ws = wb.active
        ws.title = '资产导入'
        headers = ['序列号', '类别编码', '品牌', '型号规格', '存放位置', '所属部门',
                   '投产日期(YYYY-MM-DD)', '原值(元)', '使用年限(年)', '残值率(0.05)']
        bold = Font(bold=True)
        fill = PatternFill('solid', fgColor='D9E1F2')
        for col, h in enumerate(headers, 1):
            c = ws.cell(1, col, h)
            c.font, c.fill = bold, fill
            ws.column_dimensions[c.column_letter].width = 18
        example = ['CN-A1B2C3', 'SCN', 'Honeywell', 'Xenon 1900', '总装车间', '生产部',
                   '2023-06-15', 3200, 8, 0.05]
        for col, v in enumerate(example, 1):
            ws.cell(2, col, v)
        buf = io.BytesIO()
        wb.save(buf)
        resp = HttpResponse(buf.getvalue(),
                            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        resp['Content-Disposition'] = 'attachment; filename=asset_import_template.xlsx'
        return resp

    @action(detail=False, methods=['post'])
    def batch_import(self, request):
        """
        Excel 批量导入：逐行校验，全部合法才入库（事务），
        错误行带行号返回给前端标红。可选 dry_run=true 只校验不写库。
        """
        f = request.FILES.get('file')
        if not f:
            return Response({'error': '请上传 xlsx 文件'}, status=400)
        dry = request.query_params.get('dry_run') in ('1', 'true')
        try:
            wb = load_workbook(f, data_only=True)
        except Exception as e:
            return Response({'error': f'无法解析文件: {e}'}, status=400)
        ws = wb.active
        cats = {c.code: c for c in AssetCategory.objects.all()}
        deps = {d.name: d for d in Department.objects.all()}
        locs = {l.name: l for l in Location.objects.all()}
        import datetime

        errors, rows = [], []
        for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            if not any(v is not None and str(v).strip() for v in row):
                continue
            (sn, cat_code, brand, model, loc_name, dep_name,
             pdate, value, life, salvage) = (list(row) + [None] * 10)[:10]
            errs = []
            cat = cats.get(str(cat_code or '').strip().upper())
            if not cat:
                errs.append(f'类别编码 {cat_code} 不存在')
            if not sn:
                errs.append('序列号必填')
            elif Asset.objects.filter(sn=str(sn).strip()).exists():
                errs.append(f'序列号 {sn} 已存在')
            pdate_parsed = None
            if isinstance(pdate, datetime.datetime):
                pdate_parsed = pdate.date()
            elif isinstance(pdate, datetime.date):
                pdate_parsed = pdate
            else:
                try:
                    pdate_parsed = datetime.datetime.strptime(str(pdate).strip()[:10], '%Y-%m-%d').date()
                except Exception:
                    errs.append(f'投产日期 {pdate} 格式应为 YYYY-MM-DD')
            if pdate_parsed and pdate_parsed > datetime.date.today():
                errs.append(f'投产日期 {pdate_parsed} 不能晚于今天')
            try:
                value = round(float(value), 2)
                assert value > 0
            except Exception:
                errs.append(f'原值 {value} 必须为正数')
                value = None
            life = int(life) if life else None
            salvage = float(salvage) if salvage not in (None, '') else None
            if errs:
                errors.append({'row': i, 'sn': str(sn or ''), 'errors': errs})
            else:
                rows.append(dict(sn=str(sn).strip(), category=cat, brand=str(brand or '').strip(),
                                 model_spec=str(model or '').strip(),
                                 location=locs.get(str(loc_name or '').strip()),
                                 department=deps.get(str(dep_name or '').strip()),
                                 purchase_date=pdate_parsed, original_value=value,
                                 useful_life=life, salvage_rate=salvage))

        result = {'total': len(rows) + len(errors), 'valid': len(rows),
                  'errors': errors, 'imported': 0}
        if not dry and not errors and rows:
            with transaction.atomic():
                for r in rows:
                    # 直接建模型实例（已校验），编号自动生成 + 入库留痕
                    year = r['purchase_date'].year or 2026
                    from django.utils import timezone as tz
                    year = tz.now().year
                    prefix = f"ZC-{r['category'].code}-{year}-"
                    seq = Asset.objects.filter(asset_tag__startswith=prefix).count() + 1
                    asset = Asset.objects.create(
                        asset_tag=f"{prefix}{seq:05d}",
                        sn=r['sn'], category=r['category'], brand=r['brand'],
                        model_spec=r['model_spec'], location=r['location'],
                        department=r['department'], status='in_stock',
                        purchase_date=r['purchase_date'], original_value=r['original_value'],
                        useful_life=r['useful_life'] if r['useful_life'] else r['category'].default_life,
                        salvage_rate=r['salvage_rate'] if r['salvage_rate'] is not None else r['category'].default_salvage_rate,
                    )
                    LifecycleLog.objects.create(asset=asset, action='create',
                                                detail={'source': 'batch_import'},
                                                operator=request.user)
                    result['imported'] += 1
        elif errors:
            result['message'] = f'存在 {len(errors)} 个错误行，请修正后重新上传'
        elif dry:
            result['message'] = '校验通过，可正式导入'
        return Response(result)

    @action(detail=False, methods=['post'])
    def batch_scrap(self, request):
        """批量报废（P2 预留：暂直接改状态+留痕）"""
        ids = request.data.get('ids', [])
        reason = request.data.get('reason', '')
        count = 0
        for a in Asset.objects.filter(id__in=ids).exclude(status='scrapped'):
            a.status = 'scrapped'
            a.save(update_fields=['status'])
            LifecycleLog.objects.create(asset=a, action='scrap',
                                        detail={'reason': reason}, operator=request.user)
            count += 1
        return Response({'scrapped': count})


class RepairOrderViewSet(viewsets.ModelViewSet):
    queryset = RepairOrder.objects.select_related('asset')
    serializer_class = RepairOrderSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        st = self.request.query_params.get('status')
        if st:
            qs = qs.filter(status=st)
        return qs

    def perform_create(self, serializer):
        instance = serializer.save()
        # 生命周期留痕（与批量导入口径一致）
        from .models import LifecycleLog
        LifecycleLog.objects.create(asset=instance.asset, action='repair',
                                    detail={'cost': float(instance.total_cost),
                                            'status': instance.status,
                                            'source': 'manual'},
                                    operator=self.request.user)
        self._invalidate_caches()

    def perform_update(self, serializer):
        # 完成维修的生命周期留痕已在 RepairOrderSerializer.update 里写（pending→done）
        serializer.save()
        self._invalidate_caches()

    def perform_destroy(self, instance):
        instance.delete()
        self._invalidate_caches()

    @staticmethod
    def _invalidate_caches():
        """工单变化 → 报废预测/经济寿命结果失效，下次访问重算（模型读的是 done 工单，
        金额判定 R1/R2/R4、λ 拟合、健康度红黄绿全部随之更新）"""
        from django.core.cache import cache
        cache.delete('scrappage_forecast_v2')   # 报废预测页全量
        cache.delete('scrappage_slim_v1')       # 工作台红/黄统计 + 风险列表
        # dashboard_overview_v1（60s TTL，含累计维修费）与 bigscreen（60s+stale）
        # 靠短 TTL 自然过期，避免每次建单都触发全量重算


@api_view(['GET'])
def dashboard_overview(request):
    """工作台总览：总数/净值/状态分布/红黄绿（60s 缓存，数据变更低成本容忍）"""
    from django.core.cache import cache
    cached = cache.get('dashboard_overview_v1')
    if cached:
        return Response(cached)
    from django.conf import settings as _settings
    from django.db.models import Sum
    assets = Asset.objects.active().in_scope()
    # 口径内的全部类别编码（STATS_CATEGORY_CODES 为 None 时=全部类别）
    scope_codes = getattr(_settings, 'STATS_CATEGORY_CODES', None)
    scope_done = (RepairOrder.objects.filter(status='done')
                  .filter(asset__category__code__in=scope_codes)
                  if scope_codes else RepairOrder.objects.filter(status='done'))
    by_status = {}
    for st, label in Asset.STATUS:
        by_status[st] = assets.filter(status=st).count()
    # 报废单独统计（口径内：4类里的已报废资产）
    by_status['scrapped'] = (Asset.objects.filter(status='scrapped')
                             .in_scope().count())
    total_value = assets.aggregate(s=Sum('original_value'))['s'] or 0
    from django.db.models.expressions import RawSQL
    NET = ('MAX(original_value - (original_value * (1 - COALESCE(salvage_rate, '
           'COALESCE((SELECT default_salvage_rate FROM assets_assetcategory WHERE assets_assetcategory.id=assets_asset.category_id), 0.05))) '
           '/ COALESCE(useful_life, COALESCE((SELECT default_life FROM assets_assetcategory WHERE assets_assetcategory.id=assets_asset.category_id), 8))) '
           '* ((julianday(CURRENT_DATE) - julianday(purchase_date)) / 365.25), '
           'original_value * COALESCE(salvage_rate, '
           'COALESCE((SELECT default_salvage_rate FROM assets_assetcategory WHERE assets_assetcategory.id=assets_asset.category_id), 0.05)))')
    net_value = assets.annotate(cv=RawSQL(NET, [])).aggregate(s=Sum('cv'))['s'] or 0
    out = {
        'total': assets.count(),
        'total_value': float(total_value),
        'net_value': round(net_value, 2),
        'by_status': by_status,
        'scrapped': by_status.get('scrapped', 0),
        'idle': by_status.get('idle', 0),
        'in_stock': by_status.get('in_stock', 0),
        'repairing': by_status.get('repairing', 0),
        'repair_cost': sum(float(r.total_cost) for r in scope_done),
        'repair_total': scope_done.count(),
        'categories': AssetCategorySerializer(AssetCategory.objects.all(), many=True).data,
    }
    cache.set('dashboard_overview_v1', out, 60)
    return Response(out)


def _cm_summary(items):
    """预警处置对策汇总（专业财务经济师口径）：
    ① 按年限段统计红/黄数量与原值  ② 按对策类型分组计数  ③ 三批更换计划（预算分摊）"""
    def age_bucket(u):
        if u <= 5: return '0-5年'
        if u <= 8: return '5-8年'
        if u <= 10: return '8-10年'
        return '10年以上'

    # ① 年限段 × 健康度矩阵（红黄为处置对象）
    by_age = {}
    for x in items:
        if x['health_level'] == 'green':
            continue
        b = age_bucket(x['used_years'])
        d = by_age.setdefault(b, {'red': 0, 'yellow': 0, 'value': 0.0})
        d['red' if x['health_level'] == 'red' else 'yellow'] += 1
        d['value'] += float(x.get('original_value') or 0)
    age_rows = [{'bucket': b,
                 'red': d['red'], 'yellow': d['yellow'],
                 'total': d['red'] + d['yellow'],
                 'orig_value': round(d['value'], 2)}
                for b, d in sorted(by_age.items(),
                                   key=lambda kv: ['0-5年', '5-8年', '8-10年', '10年以上'].index(kv[0]))]

    # ② 对策类型分组（按首条对策归类）
    from collections import Counter
    cm_counter = Counter()
    for x in items:
        if x['health_level'] == 'green':
            continue
        cm = x.get('countermeasures') or []
        key = cm[0][:14] if cm else '常规监控'
        cm_counter[key] += 1
    cm_rows = [{'action': k, 'count': v} for k, v in cm_counter.most_common()]

    # ③ 分批更换计划：红色按净值升序分三批（先处置残值低/损失小的），黄色第 4 批观察
    reds = sorted([x for x in items if x['health_level'] == 'red'],
                  key=lambda x: float(x.get('current_value') or 0))
    def batch_plan(lst, label, months):
        if not lst:
            return None
        return {'label': label,
                'count': len(lst),
                'net_value': round(sum(float(x.get('current_value') or 0) for x in lst), 2),
                'orig_value': round(sum(float(x.get('original_value') or 0) for x in lst), 2),
                'window': months,
                'samples': [x['display_tag'] for x in lst[:5]],
                # 全量清单（供抽屉内直接查看，免筛选）
                'items': [{'display_tag': x.get('display_tag'),
                           'name': (x.get('name') or '')[:24],
                           'category': x.get('category') or '',
                           'department': x.get('department') or '',
                           'used_years': x.get('used_years'),
                           'current_value': x.get('current_value'),
                           'original_value': x.get('original_value')}
                          for x in lst]}
    batches = [b for b in [
        batch_plan(reds[:len(reds) // 3], '第一批（立即处置）', '0-3个月'),
        batch_plan(reds[len(reds) // 3: len(reds) * 2 // 3], '第二批（纳入季度计划）', '3-6个月'),
        batch_plan(reds[len(reds) * 2 // 3:], '第三批（年度预算安排）', '6-12个月'),
    ] if b]

    total_red = sum(1 for x in items if x['health_level'] == 'red')
    return {'total_red': total_red,
            'total_yellow': sum(1 for x in items if x['health_level'] == 'yellow'),
            'by_age': age_rows,
            'by_action': cm_rows,
            'batches': batches,
            'replace_total': sum(1 for x in items if x['health_level'] != 'green')}


def _compute_scrappage():
    """全量经济寿命分析（约12s），结果写入缓存：全量+精简双份"""
    from django.core.cache import cache
    out = []
    for a in Asset.objects.active().in_scope().select_related('category').prefetch_related('repairs'):
        rep = analyze_asset(a, [r for r in a.repairs.all() if r.status == 'done'])
        rep['id'] = a.id
        rep['asset_tag'] = a.asset_tag
        rep['display_tag'] = a.sn or a.asset_tag
        rep['name'] = f'{a.brand} {a.model_spec}'
        rep['category'] = a.category.name
        rep['department'] = a.department.name if a.department else ''
        out.append(rep)
    order = {'red': 0, 'yellow': 1, 'green': 2}
    out.sort(key=lambda x: order[x['health_level']])
    payload = {'items': out,
               'red': sum(1 for x in out if x['health_level'] == 'red'),
               'yellow': sum(1 for x in out if x['health_level'] == 'yellow'),
               'green': sum(1 for x in out if x['health_level'] == 'green'),
               'computed_at': timezone.localtime().strftime('%Y-%m-%d %H:%M')}
    # 预警处置对策汇总（财务经济师口径）：按年限段+触发规则分组统计，生成分批更换建议
    payload['countermeasure_summary'] = _cm_summary(out)
    cache.set('scrappage_forecast_v2', payload, 86400)
    # 精简版（工作台专用）：统计 + TOP12，几 KB
    slim = {'red': payload['red'], 'yellow': payload['yellow'],
            'green': payload['green'], 'computed_at': payload['computed_at'],
            'items': [{k: r[k] for k in ('id', 'asset_tag', 'display_tag', 'name',
                                          'current_value', 'econ_life',
                                          'health_level', 'suggestion')}
                       for r in out[:12]]}
    cache.set('scrappage_slim_v1', slim, 86400)
    return payload


def _scrappage_bg_refresh():
    """后台线程：预计算 + 每 8 分钟自动刷新（用户请求永不触发计算）"""
    import threading, time as _time
    def _loop():
        _time.sleep(5)  # 等应用就绪
        while True:
            try:
                _compute_scrappage()
            except Exception:
                pass
            _time.sleep(480)
    t = threading.Thread(target=_loop, daemon=True)
    t.start()


@api_view(['GET'])
def scrappage_forecast(request):
    """报废预测看板：只读缓存；缓存为空时才同步计算（正常情况后台已预热）"""
    from django.core.cache import cache
    cached = cache.get('scrappage_forecast_v2')
    if cached:
        return Response(cached)
    payload = _compute_scrappage()
    return Response(payload)


@api_view(['GET'])
def scrappage_slim(request):
    """工作台专用：精简结果（统计+TOP12），毫秒级"""
    from django.core.cache import cache
    slim = cache.get('scrappage_slim_v1')
    if slim:
        return Response(slim)
    _compute_scrappage()
    slim = cache.get('scrappage_slim_v1') or {'red': 0, 'yellow': 0, 'green': 0, 'items': []}
    return Response(slim)
