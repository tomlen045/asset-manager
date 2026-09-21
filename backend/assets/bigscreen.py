"""P2-2 大屏聚合接口 + P2-3 仪表盘增强数据"""
import time
from django.db.models import Count, Sum, Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Asset, AssetCategory, RepairOrder
from .flows import Stocktake, AssetFlow


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bigscreen_data(request):
    from django.core.cache import cache
    key = 'bigscreen_data_v2'
    soft_key = 'bigscreen_data_v2_soft'      # 过期旧值（stale 层）
    lock_key = 'bigscreen_data_v2_lock'      # 重算互斥锁
    cached = cache.get(key)
    if cached:
        return Response(cached)
    # stale-while-revalidate：软过期秒回旧数据，后台单线程重算，用户永不撞 7s 重算墙
    stale = cache.get(soft_key)
    if stale and cache.add(lock_key, '1', 30):     # add=原子操作，只有一个请求拿到锁
        import threading
        threading.Thread(target=_rebuild_bigscreen_cache, kwargs={'request_path': request.path},
                         daemon=True).start()
        return Response(stale)
    if stale:
        return Response(stale)                     # 已有线程在算，其余请求也走旧值
    # 冷启动（无缓存无 stale，如刚重启）：加锁只算一次，其他请求短暂等待后读缓存
    if cache.add(lock_key, '1', 60):
        try:
            result = _compute_bigscreen()
            cache.set(key, result, 600)
            cache.set(soft_key, result, 86400)
            return Response(result)
        finally:
            cache.delete(lock_key)
    else:
        for _ in range(120):                       # 最多等 12s，让拿到锁的请求算完
            time.sleep(0.1)
            r2 = cache.get(key)
            if r2:
                return Response(r2)
        # 兜底：超时自己算（不应发生）
        result = _compute_bigscreen()
        cache.set(key, result, 600)
        cache.set(soft_key, result, 86400)
        return Response(result)


def _compute_bigscreen():
    """数据大屏聚合：一次拉全所有大屏图表数据（60s 硬缓存 + stale 层，轮询不重复计算）"""
    active = Asset.objects.exclude(status='scrapped').in_scope()

    # 1. 核心 KPI
    total = active.count()
    total_value = active.aggregate(s=Sum('original_value'))['s'] or 0
    # 净值总额：SQL 原生表达式全量计算（与 Python current_value 公式一致）
    from django.db.models.expressions import RawSQL
    NET_SQL = ('MAX(original_value - (original_value * (1 - COALESCE(salvage_rate, '
               'COALESCE((SELECT default_salvage_rate FROM assets_assetcategory WHERE assets_assetcategory.id=assets_asset.category_id), 0.05))) '
               '/ COALESCE(useful_life, COALESCE((SELECT default_life FROM assets_assetcategory WHERE assets_assetcategory.id=assets_asset.category_id), 8))) '
               '* ((julianday(CURRENT_DATE) - julianday(purchase_date)) / 365.25), '
               'original_value * COALESCE(salvage_rate, '
               'COALESCE((SELECT default_salvage_rate FROM assets_assetcategory WHERE assets_assetcategory.id=assets_asset.category_id), 0.05)))')
    net_value = (active.annotate(cv=RawSQL(NET_SQL, []))
                 .aggregate(s=__import__('django.db.models', fromlist=['Sum']).Sum('cv'))['s'] or 0)
    by_status = dict(active.order_by().values_list('status').annotate(n=Count('id')))

    # 2. 类别分布（TOP8）
    by_cat = list(active.order_by().values('category__name', 'category__code', 'category__id')
                  .annotate(n=Count('id'), value=Sum('original_value'))
                  .order_by('-n')[:8])

    # 3. 部门分布（大部门归并 TOP10 + 其他合计 + 占比）
    #    部门名规则：'生产部 机械1科 管理组' → 大部门='生产部'（取第一个分隔符前缀）
    all_dept_rows = list(active.order_by().values('department__name')
                         .annotate(n=Count('id')).order_by('-n'))
    merged = {}

    def _big_dept(name):
        if not name:
            return '未分配部门'
        for sep in (' ', '－', '·', '-', '/'):
            if sep in name:
                return name.split(sep)[0].strip()
        return name

    for r in all_dept_rows:
        b = _big_dept(r['department__name'])
        merged[b] = merged.get(b, 0) + r['n']
    # 软件等无部门资产归入"无形资产"
    if '未分配部门' in merged:
        merged['无形资产'] = merged.pop('未分配部门')
    ordered = sorted(merged.items(), key=lambda x: -x[1])
    grand = sum(n for _, n in ordered)
    top = ordered[:10]
    others = sum(n for _, n in ordered[10:])
    by_dept = [
        {'department__name': name, 'n': n, 'pct': round(n / grand * 100, 1)}
        for name, n in top
    ]
    if others:
        by_dept.append({'department__name': '其他（%d个部门）' % (len(ordered) - 10),
                        'n': others, 'pct': round(others / grand * 100, 1)})

    # 4. 年限结构（按已用年数分桶；8年以上细分为 8-9/9-10/10年以上）
    buckets = {'0-2年': 0, '3-5年': 0, '6-8年': 0,
               '8-9年': 0, '9-10年': 0, '10年以上': 0}
    for a in active.only('purchase_date'):
        used = a.used_years
        if used <= 2:
            buckets['0-2年'] += 1
        elif used <= 5:
            buckets['3-5年'] += 1
        elif used <= 8:
            buckets['6-8年'] += 1
        elif used <= 9:
            buckets['8-9年'] += 1
        elif used <= 10:
            buckets['9-10年'] += 1
        else:
            buckets['10年以上'] += 1

    # 5. 维修统计（口径内资产的工单，与工作台/报废预测同口径）
    repair_total = RepairOrder.objects.filter(asset__in=active).count()
    repair_pending = RepairOrder.objects.filter(asset__in=active, status='pending').count()
    repair_cost = sum(float(r.total_cost)
                      for r in RepairOrder.objects.filter(asset__in=active, status='done'))
    recent_repairs = list(RepairOrder.objects.select_related('asset')
                          .order_by('-report_date')
                          .values('asset__asset_tag', 'asset__brand', 'fault_desc',
                                  'report_date', 'status')[:8])

    # 6. 报废风险（经济寿命分析概览）
    from .economy import analyze_asset
    risk = {'red': 0, 'yellow': 0, 'green': 0}
    risk_items = []
    for a in active.select_related('category').prefetch_related('repairs').all():
        rep = analyze_asset(a, [x for x in a.repairs.all() if x.status == 'done'])
        risk[rep['health_level']] += 1
        if rep['health_level'] == 'red' and len(risk_items) < 10:
            risk_items.append({
                'asset_tag': a.asset_tag, 'name': f'{a.brand} {a.model_spec}',
                'econ_life': rep['econ_life'], 'suggestion': rep['suggestion'],
            })

    # 7. 最近流程单
    recent_flows = list(AssetFlow.objects.select_related('asset', 'applicant')
                        .values('flow_no', 'flow_type', 'asset__asset_tag',
                                'applicant__username', 'status', 'created_at')[:8])

    # 7.4 工作台扩展：部门原值TOP8 / 带病运行 / 超期服役 / 本年新增
    # 带 department__id：TOP8 行点击跳台账按部门筛选（views.py 的 ?department=<id>）
    by_dept_value = list(active.order_by().values('department__name', 'department__id')
                         .annotate(value=Sum('original_value'))
                         .order_by('-value')[:8])

    broken = overdue = new_this_year = 0
    import datetime as _dt
    _y = _dt.date.today().year
    for a in active.select_related('category').prefetch_related('repairs'):
        done = [x for x in a.repairs.all() if x.status == 'done']
        if len(done) >= 2:
            broken += 1
        if a.used_years > (a.useful_life or 8):
            overdue += 1
        if a.purchase_date and a.purchase_date.year == _y:
            new_this_year += 1

    kpi_extra = {'broken': broken, 'overdue': overdue, 'new_this_year': new_this_year,
                 # 未分配部门 = 全库口径（与「未分配部门」清单页一致，含报废——报废资产归属同样要落实）
                 'no_dept': Asset.objects.filter(department__isnull=True).count()}

    # 7.5 生产类终端统计
    terminals = active.filter(custom__terminal_type='生产类终端')
    term_stats = {
        'total': terminals.count(),
        'by_cat': list(terminals.order_by().values('category__name')
                       .annotate(n=Count('id')).order_by('-n')[:5]),
        'by_dept': list(terminals.order_by().values('department__name')
                        .annotate(n=Count('id')).order_by('-n')[:5]),  # 明细留接口
        'value': float(terminals.aggregate(s=Sum('original_value'))['s'] or 0),
    }

    # 8. 盘点概况
    st = Stocktake.objects.filter(status='ongoing').first()
    stocktake = st.stats() if st else {'total': 0, 'found': 0, 'missing': 0,
                                       'unexpected': 0, 'progress': 0}
    stocktake_name = st.name if st else ''
    stocktake_found = list(
        st.items.filter(found=True, unexpected=False)
        .select_related('asset')
        .order_by('-found_at')
        .values('asset__asset_tag', 'asset__brand', 'asset__model_spec', 'found_at')[:20]
    ) if st else []

    result = {
        'kpi': {
            'total': total, 'total_value': float(total_value),
            'net_value': round(net_value, 2),
            'scrapped': Asset.objects.filter(status='scrapped').in_scope().count(),
            'repair_total': repair_total, 'repair_pending': repair_pending,
            'repair_cost': round(repair_cost, 2),
        },
        'by_status': by_status, 'by_cat': by_cat, 'by_dept': by_dept,
        'age_buckets': buckets,
        'risk': risk, 'risk_items': risk_items,
        'recent_repairs': recent_repairs, 'recent_flows': recent_flows,
        'stocktake': stocktake, 'stocktake_name': stocktake_name,
        'stocktake_found': stocktake_found, 'terminals': term_stats,
        'by_dept_value': by_dept_value, 'kpi_extra': kpi_extra,
        'new_this_year': new_this_year,
    }
    return result


def _rebuild_bigscreen_cache(request_path=''):
    """后台重算 bigscreen 聚合（供 stale-while-revalidate 调用）"""
    from django.core.cache import cache
    try:
        result = _compute_bigscreen()
        cache.set('bigscreen_data_v2', result, 600)
        cache.set('bigscreen_data_v2_soft', result, 86400)
    except Exception:
        pass
    finally:
        cache.delete('bigscreen_data_v2_lock')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_repair_stats(request):
    """仪表盘-报修明细统计（按月）"""
    rows = (RepairOrder.objects
            .extra(select={"month": "strftime('%%Y-%%m', report_date)"})
            .values('month')
            .annotate(n=Count('id'), cost=Sum('labor_cost'))
            .order_by('month')[:12])
    return Response({'months': list(rows)})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stocktake_stats(request):
    """仪表盘-盘点详情"""
    sts = Stocktake.objects.all()[:5]
    out = []
    for st in sts:
        s = st.stats()
        out.append({'id': st.id, 'name': st.name, 'status': st.status,
                    'created_at': st.created_at, **s})
    return Response({'items': out})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dept_tree(request):
    """部门树（级联结构）：[{name, id, count(全部), active(在用), children}]"""
    from assets.orgtree import DeptNode
    from assets.models import Asset
    from django.db.models import Count, Q

    name_cnt = {}
    name_act = {}
    # 注意：Django3.2+SQLite 下同 annotate 双 Count(filter=) 会生成错误 GROUP BY，
    # 必须拆两次查询
    for r in Asset.objects.values('department__name').annotate(n=Count('id')):
        name_cnt[r['department__name'] or ''] = r['n']
    for r in (Asset.objects.exclude(status='scrapped').in_scope()
              .values('department__name').annotate(n=Count('id'))):
        name_act[r['department__name'] or ''] = r['n']

    src_cnt = {}
    for full, n in name_cnt.items():
        src_cnt[full] = (n, name_act.get(full, 0))

    nodes = DeptNode.objects.select_related('parent').order_by('order', 'id')
    by_parent = {}
    for n in nodes:
        by_parent.setdefault(n.parent_id, []).append(n)

    def build(node):
        children = by_parent.get(node.id, [])
        kids = [build(ch) for ch in children]
        own_all = own_act = 0
        for full in (node.src_names or []):
            a, b = src_cnt.get(full, (0, 0))
            own_all += a
            own_act += b
        total_all = own_all + sum(k['count'] for k in kids)
        total_act = own_act + sum(k['active'] for k in kids)
        return {'name': node.name, 'id': node.id,
                'count': total_all, 'active': total_act, 'children': kids}

    roots = by_parent.get(None, [])
    return Response({'tree': [build(n) for n in roots]})
