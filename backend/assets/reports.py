"""P3-1 维修记录批量导入 + P3-3 报表导出"""
import io
import datetime
from django.http import HttpResponse
from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill

from .models import Asset, RepairOrder, LifecycleLog


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def repair_template(request):
    """维修记录导入模板"""
    wb = Workbook()
    ws = wb.active
    ws.title = '维修记录导入'
    headers = ['序列号(资产号)', '报修日期(YYYY-MM-DD)', '故障描述', '配件名称',
               '配件费用(元)', '人工费(元)', '维修商', '完成日期(可选)']
    bold = Font(bold=True)
    fill = PatternFill('solid', fgColor='FFF2CC')
    for col, h in enumerate(headers, 1):
        c = ws.cell(1, col, h)
        c.font, c.fill = bold, fill
        ws.column_dimensions[c.column_letter].width = 20
    example = ['NBB-2922', '2024-07-15', '电源模块损坏', '电源模块', 450, 80, 'IBM售后', '2024-07-18']
    for col, v in enumerate(example, 1):
        ws.cell(2, col, v)
    buf = io.BytesIO()
    wb.save(buf)
    resp = HttpResponse(buf.getvalue(),
                        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    resp['Content-Disposition'] = 'attachment; filename=repair_import_template.xlsx'
    return resp


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def repair_batch_import(request):
    """维修记录批量导入：按序列号匹配资产，一行=一条工单（一次只记一个配件，
    多配件请拆多行填同一故障日期）"""
    f = request.FILES.get('file')
    if not f:
        return Response({'error': '请上传 xlsx 文件'}, status=400)
    dry = request.query_params.get('dry_run') in ('1', 'true')
    try:
        wb = load_workbook(f, data_only=True)
    except Exception as e:
        return Response({'error': f'无法解析文件: {e}'}, status=400)

    errors, repairs = [], []
    for i, row in enumerate(wb.active.iter_rows(min_row=2, values_only=True), start=2):
        if not any(v is not None and str(v).strip() for v in row):
            continue
        (sn, rdate, fault, part_name, part_cost, labor, vendor,
         fdate) = (list(row) + [None] * 8)[:8]

        errs = []
        asset = Asset.objects.filter(sn=str(sn or '').strip()).first()
        if not asset:
            errs.append(f'序列号 {sn} 不存在')
        rd = None
        if isinstance(rdate, datetime.datetime):
            rd = rdate.date()
        else:
            try:
                rd = datetime.datetime.strptime(str(rdate).strip()[:10], '%Y-%m-%d').date()
            except Exception:
                errs.append(f'报修日期 {rdate} 格式错误')
        if not fault or not str(fault).strip():
            errs.append('故障描述必填')
        try:
            pc = float(part_cost) if part_cost not in (None, '') else 0
        except (ValueError, TypeError):
            errs.append(f'配件费用 {part_cost} 格式错误')
            pc = 0
        try:
            lc = float(labor) if labor not in (None, '') else 0
        except (ValueError, TypeError):
            errs.append(f'人工费 {labor} 格式错误')
            lc = 0

        fd = None
        if fdate not in (None, ''):
            if isinstance(fdate, datetime.datetime):
                fd = fdate.date()
            else:
                try:
                    fd = datetime.datetime.strptime(str(fdate).strip()[:10], '%Y-%m-%d').date()
                except Exception:
                    pass

        if errs:
            errors.append({'row': i, 'sn': str(sn or ''), 'errors': errs})
        else:
            repairs.append(dict(asset=asset, report_date=rd, fault_desc=str(fault).strip(),
                                parts=[{'name': str(part_name or '配件'), 'cost': pc}],
                                labor=lc, vendor=str(vendor or '').strip(), finish=fd))

    result = {'total': len(repairs) + len(errors), 'valid': len(repairs),
              'errors': errors, 'imported': 0}
    if errors:
        result['message'] = f'存在 {len(errors)} 个错误行'
        return Response(result)

    if not dry:
        with transaction.atomic():
            # 同资产同日同故障 合并为一个工单多配件
            merged = {}
            for r in repairs:
                key = (r['asset'].id, r['report_date'], r['fault_desc'])
                if key in merged:
                    merged[key]['parts'].extend(r['parts'])
                else:
                    merged[key] = r
            for r in merged.values():
                ro = RepairOrder.objects.create(
                    asset=r['asset'], report_date=r['report_date'],
                    fault_desc=r['fault_desc'], parts_replaced=r['parts'],
                    labor_cost=r['labor'], vendor=r['vendor'],
                    status='done', finish_date=r['finish'] or r['report_date'])
                LifecycleLog.objects.create(asset=r['asset'], action='repair',
                                            detail={'cost': float(ro.total_cost),
                                                    'source': 'import'},
                                            operator=request.user)
                result['imported'] += 1
    else:
        result['message'] = '校验通过，可正式导入'
    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_assets(request):
    """资产台账全量导出（含折旧字段）"""
    wb = Workbook()
    ws = wb.active
    ws.title = '资产台账'
    headers = ['资产编号', '序列号', '资产类别', '品牌', '型号规格', '所属部门',
               '投产日期', '使用年限(年)', '原值(元)', '当前净值(元)',
               '已使用(年)', '状态', '维修费累计(元)']
    bold = Font(bold=True)
    for c, h in enumerate(headers, 1):
        ws.cell(1, c, h).font = bold

    qs = Asset.objects.select_related('category', 'department')
    # 与台账列表口径一致：默认不含报废（include_scrapped=1 显式包含）
    if request.query_params.get('include_scrapped') not in ('1', 'true'):
        qs = qs.exclude(status='scrapped')
    cat = request.query_params.get('category') or request.query_params.get('categories')
    if cat:
        ids = [int(x) for x in str(cat).split(',') if x.strip().isdigit()]
        if ids:
            qs = qs.filter(category_id__in=ids)
    elif not request.query_params.get('all_categories'):
        # 与台账列表口径一致：默认只导出口径内类别
        from django.conf import settings
        codes = getattr(settings, 'STATS_CATEGORY_CODES', None)
        if codes:
            qs = qs.filter(category__code__in=codes)
    st = request.query_params.get('status')
    if st:
        sts = [s for s in str(st).split(',') if s]
        qs = qs.filter(status__in=sts)
    # 与列表同款筛选：多词关键字 / 年限段
    kw = request.query_params.get('kw')
    if kw:
        from django.db.models import Q
        words = [w for w in __import__('re').split(r'[\s,，、]+', kw.strip()) if w]
        combined = Q()
        for w in words:
            combined |= (Q(asset_tag__icontains=w) | Q(sn__icontains=w) |
                         Q(brand__icontains=w) | Q(model_spec__icontains=w) |
                         Q(asset_name__icontains=w))
        qs = qs.filter(combined)
    segs_param = request.query_params.get('age_segments')
    if segs_param:
        from datetime import datetime as _dt
        from django.db.models import F, ExpressionWrapper, DurationField
        # 与列表一致的连续边界段
        today = _dt.now().date()
        # 简化：直接用 used_years 注解过滤
        age_expr = ExpressionWrapper(
            (__import__('django.db.models', fromlist=['Value']).Value(today)
             - F('purchase_date')) / 365.25 * 1.0,
            output_field=__import__('django.db.models', fromlist=['FloatField']).FloatField())
        SEG = {'0-2': (None, 2), '3-5': (2, 5), '6-8': (5, 8),
               '8-9': (8, 9), '9-10': (9, 10), '10+': (10, None)}
        from django.db.models import Q as _Q
        segq = _Q()
        for s in str(segs_param).split(','):
            s = s.strip()
            if s in SEG:
                lo, hi = SEG[s]
                if lo is None:
                    segq |= _Q(used_years__lte=hi)
                elif hi is None:
                    segq |= _Q(used_years__gt=lo)
                else:
                    segq |= _Q(used_years__gt=lo, used_years__lte=hi)
        qs = qs.filter(segq)
    if request.query_params.get('overdue') == '1':
        qs = qs.filter(used_years__gt=F('eff_life'))
    if request.query_params.get('no_dept') == '1':
        qs = qs.filter(department__isnull=True)

    r = 2
    for a in qs.iterator():
        repair_sum = sum(float(x.total_cost) for x in a.repairs.filter(status='done'))
        ws.cell(r, 1, a.sn or a.asset_tag)
        ws.cell(r, 2, a.sn)
        ws.cell(r, 3, a.category.name if a.category else '')
        ws.cell(r, 4, a.brand)
        ws.cell(r, 5, a.model_spec)
        ws.cell(r, 6, a.department.name if a.department else '')
        ws.cell(r, 7, a.purchase_date.isoformat() if a.purchase_date else '')
        ws.cell(r, 8, a.eff_life)
        ws.cell(r, 9, float(a.original_value))
        ws.cell(r, 10, float(a.current_value))
        ws.cell(r, 11, a.used_years)
        ws.cell(r, 12, a.get_status_display())
        ws.cell(r, 13, repair_sum)
        r += 1

    buf = io.BytesIO()
    wb.save(buf)
    resp = HttpResponse(buf.getvalue(),
                        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    resp['Content-Disposition'] = 'attachment; filename=assets_export.xlsx'
    return resp


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_scrappage(request):
    """报废预测报表导出（含经济寿命分析结论）"""
    from .economy import analyze_asset
    wb = Workbook()
    ws = wb.active
    ws.title = '报废预测'
    headers = ['资产编号', '名称', '类别', '原值', '当前净值', '已用年限',
               '标准年限', '累计维修费', '维修/净值比', 'λ(年维修增长)',
               '经济寿命(年)', '健康度', '系统建议']
    bold = Font(bold=True)
    for c, h in enumerate(headers, 1):
        ws.cell(1, c, h).font = bold

    r = 2
    for a in Asset.objects.exclude(status='scrapped').in_scope().select_related('category'):
        rep = analyze_asset(a, list(a.repairs.filter(status='done')))
        ws.cell(r, 1, a.sn or a.asset_tag)
        ws.cell(r, 2, f'{a.brand} {a.model_spec}')
        ws.cell(r, 3, a.category.name if a.category else '')
        ws.cell(r, 4, rep['original_value'])
        ws.cell(r, 5, rep['current_value'])
        ws.cell(r, 6, rep['used_years'])
        ws.cell(r, 7, rep['useful_life'])
        ws.cell(r, 8, rep['repair_total'])
        ws.cell(r, 9, rep['repair_vs_value_ratio'] or 0)
        ws.cell(r, 10, rep['lambda'])
        ws.cell(r, 11, rep['econ_life'] or '')
        ws.cell(r, 12, {'red': '报废', 'yellow': '预警', 'green': '正常'}[rep['health_level']])
        ws.cell(r, 13, rep['suggestion'])
        r += 1

    buf = io.BytesIO()
    wb.save(buf)
    resp = HttpResponse(buf.getvalue(),
                        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    resp['Content-Disposition'] = 'attachment; filename=scrappage_forecast.xlsx'
    return resp
