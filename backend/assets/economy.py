"""
AI 经济寿命分析引擎
设计原则：规则引擎算数字（可审计）→ LLM 只做解释（不碰钱）
"""
import math
from datetime import date
from decimal import Decimal


def fit_deterioration_lambda(yearly_costs: dict) -> float:
    """
    拟合维修费年增长额 λ（低劣化参数）。
    yearly_costs: {年份偏移(第N年): 费用}  如 {3:400, 4:900, 5:1200}
    用最小二乘线性拟合 cost = a + λ*t，λ 即年均增长。
    数据点<2 时返回 0（无法拟合，经济寿命模型不适用）。
    """
    pts = sorted((t, float(c)) for t, c in yearly_costs.items() if c > 0)
    if len(pts) < 2:
        return 0.0
    n = len(pts)
    sx = sum(t for t, _ in pts)
    sy = sum(c for _, c in pts)
    sxx = sum(t * t for t, _ in pts)
    sxy = sum(t * c for t, c in pts)
    denom = n * sxx - sx * sx
    if denom == 0:
        return 0.0
    lam = (n * sxy - sx * sy) / denom
    return max(round(lam, 2), 0.0)


def analyze_asset(asset, repairs, settings=None) -> dict:
    """
    经济寿命分析主入口。
    asset: Asset 实例；repairs: 已完成的 RepairOrder 列表
    settings: 阈值配置 dict（可空，用默认）
    返回结构化报告（不含 AI 文字——文字由 ai 层生成）
    """
    s = {'r1_ratio': 0.6, 'r2_ratio': 0.5, 'r4_ratio': 1.5,
         # ── 公司标准（2026-09 用户决策）：固定资产服役一般 6-8 年 ──
         # R5 超期服役：超过标准年限→黄；超过 1.5 倍→红（设备安全视角，与维修无关）
         'r5_red_mult': 1.5,
         # R6 维修频率：1 个标准年限内维修≥3 次（反复故障）→黄
         'r6_count': 3,
         # R7 净值兜底：净值已折到残值（折旧提完）且仍在用 → 黄
         'r7_net_floor_ratio': 1.02,
         'r7_min_value': 500,          # 原值低于此不触发（残值太小无意义）
         # R8 零维修超期盲区：超期且从未维修（可能是没人报修）→ 黄（信息不全提示）
         #    触发条件：used > life 且维修记录 0
         **(settings or {})}
    original = float(asset.original_value)
    net = float(asset.current_value)
    used = asset.used_years
    life = asset.eff_life
    remaining = max(life - used, 0)

    # 维修成本按年聚合（相对投产日期的年份偏移）
    yearly, total_repair, max_single = {}, Decimal('0'), Decimal('0')
    for r in repairs:
        c = r.total_cost
        total_repair += c
        max_single = max(max_single, c)
        y = (r.report_date - asset.purchase_date).days // 365 + 1
        yearly[y] = float(yearly.get(y, 0)) + float(c)

    total_ratio = float(total_repair) / original if original else 0
    net_ratio = float(total_repair) / net if net > 0 else float('inf')
    lam = fit_deterioration_lambda(yearly)

    # 经济寿命（低劣化数值法）
    econ_life = round(math.sqrt(2 * original * (1 - asset.eff_salvage_rate) / lam), 2) if lam > 0 else None

    # ── 决策规则 ──
    hit = []
    if net > 0 and float(max_single) > net * s['r1_ratio']:
        hit.append(('R1', 'red', f'单次最高维修费 {max_single} 元已超当前净值({net:.0f}元)的{s["r1_ratio"]:.0%}，本次建议报废'))
    if total_ratio > s['r2_ratio']:
        hit.append(('R2', 'yellow', f'累计维修费 {total_repair} 元已达原值的{total_ratio:.0%}，维修成本预警'))
    if econ_life and econ_life < remaining:
        hit.append(('R3', 'red', f'低劣化模型经济寿命 {econ_life} 年 < 剩余法定寿命 {remaining} 年，报废期建议缩短'))
    annual_dep = float(asset.annual_depreciation)
    this_year = date.today().year
    this_year_cost = sum(c for y, c in yearly.items() if (asset.purchase_date + __import__('datetime').timedelta(days=365 * (y - 1))).year == this_year or y == max(yearly) and not yearly)
    # 简化：取最近一年维修费
    recent_cost = yearly[max(yearly)] if yearly else 0
    if annual_dep > 0 and recent_cost > annual_dep * s['r4_ratio']:
        hit.append(('R4', 'yellow', f'最近年度维修费 {recent_cost:.0f} 元 > 年折旧 {annual_dep:.0f} 元×{s["r4_ratio"]:.1f}，修不如换'))
    # R5 超期服役（2026-09 新增，公司标准 6-8 年）：与维修数据无关，纯年限判定
    #    黄：已用 > 标准年限；红：已用 > 标准年限×1.5
    if used > life * s['r5_red_mult']:
        hit.append(('R5', 'red', f'已用 {used:.1f} 年达标准年限 {life} 年的 {used / life:.1f} 倍（≥{s["r5_red_mult"]}倍），超期服役严重，建议优先报废更新'))
    elif used > life:
        hit.append(('R5', 'yellow', f'已用 {used:.1f} 年超过标准年限 {life} 年，超期服役'))
    # R6 维修频率：一个标准年限周期内维修≥3 次（反复故障机）
    if len(repairs) >= s['r6_count'] and life > 0:
        freq = len(repairs) / (used if used > 0 else 1) * life  # 折算到标准年限内的次数
        if freq >= s['r6_count']:
            hit.append(('R6', 'yellow', f'已用 {used:.1f} 年维修 {len(repairs)} 次（折算标准年限内 {freq:.1f} 次≥{s["r6_count"]}），反复故障设备'))
    # R7 净值兜底：折旧已提完（净值触到残值地板）且仍在用 → 持有零成本但账面已尽
    salvage = original * asset.eff_salvage_rate
    if (original >= s['r7_min_value'] and net <= salvage * s['r7_net_floor_ratio']
            and used >= life):
        hit.append(('R7', 'yellow', f'净值 {net:.0f} 元已到残值 {salvage:.0f} 元（折旧提完）仍在服役，账面价值耗尽'))
    # R8 零维修超期盲区：超期服役却从无维修记录 → 数据不全提示（可能是没人报修）
    if used > life and len(repairs) == 0:
        hit.append(('R8', 'yellow', f'超期服役 {used - life:.1f} 年且无维修记录，故障数据缺失，建议人工核查工况'))

    level = 'green'
    if any(h[1] == 'red' for h in hit):
        level = 'red'
    elif any(h[1] == 'yellow' for h in hit):
        level = 'yellow'

    return {
        'asset_tag': asset.asset_tag,
        'original_value': original,
        'annual_depreciation': annual_dep,
        'current_value': round(net, 2),
        'used_years': used,
        'useful_life': life,
        'remaining_life': round(remaining, 2),
        'repair_total': float(total_repair),
        'repair_max_single': float(max_single),
        'repair_vs_value_ratio': round(net_ratio, 3) if net > 0 else None,
        'repair_yearly': {str(k): v for k, v in sorted(yearly.items())},
        'lambda': lam,
        'econ_life': econ_life,
        'rules_hit': [{'rule': r, 'level': lv, 'msg': m} for r, lv, m in hit],
        'health_level': level,
        'suggestion': _suggestion(level, hit, econ_life, remaining),
        'countermeasures': _countermeasures(level, hit, econ_life, remaining, net),
    }


def _countermeasures(level, hit, econ_life, remaining, net):
    """维修预警（黄）的分级处置对策：按触发规则给出可执行动作+预算指引。
    红色（建议报废）给报废流程指引；绿色给常规管理要求。"""
    actions = []
    rules = {r[0]: r for r in hit}
    if 'R2' in rules:
        actions.append('冻结常规维修预算，转入以旧换新评估；联系供应商评估残值变现价值')
    if 'R4' in rules:
        actions.append('按「修 vs 换」全周期成本比选：预估下一周期维修费，超过设备重置价 30% 即停止大修')
    if 'R5' in rules and 'R5' in rules and rules['R5'][1] == 'red':
        actions.append('列入年度更新计划优先批次；继续使用须每季度做安全检测并留档')
    elif 'R5' in rules:
        actions.append('制定分批替换计划（建议 12 个月内落地）；超期期间每半年安全检测一次')
    if 'R6' in rules:
        actions.append('组织故障根因分析（使用环境/操作规范/配件质量），出具维修价值评估报告')
    if 'R7' in rules:
        actions.append('会计上转「固定资产清理」跟踪；可评估内部调拨至低强度岗位延寿使用')
    if 'R8' in rules:
        actions.append('安排现场巡检确认实际工况；补录维修与使用台账，消除数据盲区')
    if 'R1' in rules:
        actions.append('本次维修后启动报废鉴定流程；留存维修报价单作为报废依据')
    if 'R3' in rules and econ_life:
        actions.append(f'按经济寿命 {econ_life} 年重排报废批次，预留预算 {remaining:.0f} 年内完成更新')
    if not actions:
        if level == 'red':
            actions.append('停止维修投入，启动报废鉴定流程')
        elif level == 'yellow':
            actions.append('纳入季度重点监控清单，控制维修预算')
        else:
            actions.append('按日常保养规程执行；持续跟踪维修记录')
    return actions


def _suggestion(level, hit, econ_life, remaining):
    if level == 'red':
        if any(r[0] == 'R3' for r in hit) and econ_life:
            return f'建议纳入下一批报废计划：经济寿命约 {econ_life} 年，短于标准剩余 {remaining:.1f} 年'
        if any(r[0] == 'R5' for r in hit):
            return '建议优先报废更新：超期服役严重，存在安全隐患'
        return '建议报废：继续维修不经济'
    if level == 'yellow':
        if any(r[0] == 'R5' for r in hit):
            return '超期服役：安排替换计划，控制维修投入'
        if any(r[0] == 'R8' for r in hit):
            return '数据待核查：超期服役但无维修记录，建议人工确认工况'
        return '加强监控：控制维修预算，评估以旧换新方案'
    return '正常'
