"""P3-2 资产详情经济曲线增强版数据端点：返回交叉点+阈值线数据"""
import math
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from assets.models import Asset
from assets.economy import analyze_asset


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def economy_chart(request, pk):
    try:
        a = Asset.objects.select_related('category').get(pk=pk)
    except Asset.DoesNotExist:
        return Response({'error': 'not found'}, status=404)
    rep = analyze_asset(a, list(a.repairs.filter(status='done')))

    years = rep['useful_life']
    orig = rep['original_value']
    annual = rep['annual_depreciation']
    salvage = orig * (1 - a.eff_salvage_rate) / a.eff_life * 0  # 净值下限=总残值
    salvage_floor = orig * a.eff_salvage_rate

    xs, repair_line, value_line = [], [], []
    byY = {int(k): v for k, v in (rep['repair_yearly'] or {}).items()}
    cum = 0
    for t in range(0, years + 1):
        xs.append(f'第{t}年')
        cum += byY.get(t, 0)
        repair_line.append(round(cum, 0))
        value_line.append(round(max(orig - annual * t, salvage_floor), 0))

    # 交叉点：累计维修线超过净值线的第 N 年
    cross = None
    for t in range(len(xs)):
        if repair_line[t] > value_line[t] > 0:
            cross = xs[t]
            break

    # 当前时间标记（已用年数位置）
    used_idx = min(int(round(rep['used_years'])), years)

    # 60% 阈值线（单次维修报废线，相对当前净值）
    threshold = round(rep['current_value'] * 0.6, 0)

    return Response({
        'chart': {'x': xs, 'repair': repair_line, 'value': value_line},
        'cross_point': cross,
        'used_years_idx': used_idx,
        'threshold_line': threshold,
        'econ_life': rep['econ_life'],
        'health_level': rep['health_level'],
        'suggestion': rep['suggestion'],
        'rules_hit': rep['rules_hit'],
    })
