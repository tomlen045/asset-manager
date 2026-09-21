"""P4 AI 报告服务：
分层铁律（用户决策 D8）：
- 规则引擎算数字（可审计可解释）——永远可用
- LLM 只生成中文话术报告——Ollama 挂掉自动降级为模板话术
"""
import json
import time
import urllib.request
import socket

from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Asset
from .economy import analyze_asset

OLLAMA_BASE = getattr(settings, 'OLLAMA_BASE', 'http://ollama:11434')
OLLAMA_MODEL = getattr(settings, 'OLLAMA_MODEL', 'qwen2.5:7b')
OLLAMA_TIMEOUT = getattr(settings, 'OLLAMA_TIMEOUT', 60)

HEALTH_TXT = {'red': '报废', 'yellow': '预警', 'green': '健康'}


def _template_report(a, rep):
    """规则模板话术（LLM 不可用时的降级，也作为数字底稿）"""
    name = f'{a.brand} {a.model_spec}'.strip() or a.asset_tag
    lines = [
        f'【资产处置分析报告】{a.asset_tag} {name}',
        '',
        f'一、基本情况：该资产于 {a.purchase_date or "未知"} 投入使用，原值 {rep["original_value"]} 元，'
        f'标准使用年限 {rep["useful_life"]} 年，已使用 {rep["used_years"]} 年，'
        f'当前净值 {rep["current_value"]} 元。',
        '',
        f'二、维修情况：累计维修 {len(a.repairs.filter(status="done"))} 次，维修总费用 {rep["repair_total"]} 元，'
        f'占当前净值比例 {round((rep["repair_vs_value_ratio"] or 0) * 100, 1)}%'
        f'（报废警戒线为 60%）。',
        '',
        f'三、经济寿命测算：按维修费用增长趋势拟合，年维修增量 λ={rep["lambda"]} 元/年，'
        f'经济寿命 T=√(2×(原值−残值)÷λ)={rep["econ_life"] or "不适用"} 年，'
        f'低于法定报废年限 {rep["useful_life"]} 年，应将报废期缩短至 {rep["econ_life"] or "—"} 年。',
        '',
        f'四、处置结论：健康度评级【{HEALTH_TXT[rep["health_level"]]}】。{rep["suggestion"]}。',
        '',
        f'五、命中规则：{"；".join(r["msg"] if isinstance(r, dict) else str(r) for r in rep["rules_hit"]) if rep["rules_hit"] else "无"}。',
    ]
    return '\n'.join(lines)


def _llm_report(a, rep, base_text):
    """调 Ollama 把规则底稿改写成管理层可读的报告；失败返回 None"""
    name = f'{a.brand} {a.model_spec}'.strip() or a.asset_tag
    prompt = (
        '你是制造业企业的资产处置顾问。请把下面这份资产分析底稿改写成一份给管理层看的简短中文报告，'
        '要求：①保留全部数字不得修改 ②用专业但通俗的语言 ③给出明确的处置建议（继续使用/加强监控/停止维修申请报废）'
        '④控制在300字以内。底稿：\n' + base_text)

    body = json.dumps({
        'model': OLLAMA_MODEL,
        'messages': [{'role': 'user', 'content': prompt}],
        'stream': False,
        'options': {'temperature': 0.3, 'num_predict': 160},
        'keep_alive': '30m',
    }).encode()

    socket.setdefaulttimeout(OLLAMA_TIMEOUT)
    try:
        req = urllib.request.Request(
            f'{OLLAMA_BASE}/api/chat', data=body,
            headers={'Content-Type': 'application/json'})
        resp = urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT)
        data = json.loads(resp.read())
        text = (data.get('message') or {}).get('content', '').strip()
        if text:
            return text
    except Exception:
        pass
    return None


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ai_report(request, pk):
    """单台资产生成 AI 分析报告
    提速：①结果缓存（资产/维修未变直接秒回）②返回 pending+后台线程预生成
    前端轮询 ai_report_status 拿结果"""
    from django.core.cache import cache
    try:
        a = Asset.objects.select_related('category', 'department').get(pk=pk)
    except Asset.DoesNotExist:
        return Response({'error': 'not found'}, status=404)

    # 缓存键：资产版本（updated_at）+ 维修次数（维修变化即失效）
    ckey = f'ai_report_v1_{a.id}_{int(a.updated_at.timestamp())}_{a.repairs.filter(status="done").count()}'
    rep = analyze_asset(a, list(a.repairs.filter(status='done')))
    base = _template_report(a, rep)
    want_llm = bool(request.data.get('use_llm', True))

    def _payload(report_text, engine):
        return {
            'asset_tag': a.sn or rep['asset_tag'],
            'name': f'{a.brand} {a.model_spec}'.strip(),
            'health_level': rep['health_level'],
            'metrics': {k: rep[k] for k in ('original_value', 'current_value', 'used_years',
                                            'useful_life', 'repair_total',
                                            'lambda', 'econ_life') if k in rep},
            'rules_hit': rep['rules_hit'],
            'suggestion': rep['suggestion'],
            'report': report_text,
            'engine': engine,
        }

    # LLM 版缓存命中 → 直接返回润色版
    llm_cached = cache.get(ckey + '_llm')
    if want_llm and llm_cached:
        return Response(_payload(llm_cached, 'ollama'))

    # 立即返回模板版（秒回，数字完整可读）；后台线程 LLM 润色后写缓存
    if want_llm and cache.add(f'ai_llm_lock_{a.id}', '1', 180):
        import threading
        def _polish():
            try:
                llm_text = _llm_report(a, rep, base)
                if llm_text:
                    cache.set(ckey + '_llm', llm_text, 86400)
            except Exception:
                pass
            finally:
                cache.delete(f'ai_llm_lock_{a.id}')
        threading.Thread(target=_polish, daemon=True).start()

    payload = _payload(base, 'template')
    cache.set(ckey, payload, 86400)
    return Response(payload)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_report_status(request, pk):
    """轮询 LLM 润色是否完成：done=润色版已就绪；pending=仍在生成"""
    from django.core.cache import cache
    try:
        a = Asset.objects.select_related('category').get(pk=pk)
    except Asset.DoesNotExist:
        return Response({'error': 'not found'}, status=404)
    ckey = (f'ai_report_v1_{a.id}_{int(a.updated_at.timestamp())}_'
            f'{a.repairs.filter(status="done").count()}')
    llm = cache.get(ckey + '_llm')
    if llm:
        return Response({'status': 'done', 'report': llm, 'engine': 'ollama'})
    if cache.get(f'ai_llm_lock_{a.id}'):
        return Response({'status': 'pending'})
    return Response({'status': 'none'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ai_report_batch(request):
    """批量预热红/黄资产报告 —— 立即返回，后台线程计算。
    历史教训：同步实现要对全量资产跑 analyze_asset（~20s CPU），把 Django
    单进程整个卡死，期间所有 API/静态请求超时 = "页面卡顿+请求失败"。
    现在：锁 300s 防重复触发，结果由后台线程写缓存，调用方秒回。"""
    from django.core.cache import cache
    import threading

    if not cache.add('ai_report_batch_lock', '1', 300):
        return Response({'count': 0, 'llm': False, 'skipped': 'cooldown', 'reports': []})

    use_llm = bool(request.data.get('use_llm', False))
    limit = min(int(request.data.get('limit', 10)), 20)

    def _run_batch():
        try:
            out = []
            qs = (Asset.objects.exclude(status='scrapped').in_scope()
                  .select_related('category', 'department'))
            for a in qs:
                rep = analyze_asset(a, list(a.repairs.filter(status='done')))
                if rep['health_level'] != 'green':
                    out.append((a, rep))
                if len(out) >= limit * 3:
                    break
            # 红优先、再黄
            out.sort(key=lambda x: {'red': 0, 'yellow': 1}.get(x[1]['health_level'], 2))

            results = []
            for a, rep in out[:limit]:
                base = _template_report(a, rep)
                engine = 'template'
                text = base
                if use_llm:
                    llm_text = _llm_report(a, rep, base)
                    if llm_text:
                        text, engine = llm_text, 'ollama'
                results.append({
                    'asset_tag': a.sn or rep['asset_tag'],
                    'name': f'{a.brand} {a.model_spec}'.strip(),
                    'health_level': rep['health_level'],
                    'report': text, 'engine': engine,
                })
                # 同步写入单台缓存（详情页直接命中，秒回）
                ckey = (f'ai_report_v1_{a.id}_{int(a.updated_at.timestamp())}'
                        f'_{a.repairs.filter(status="done").count()}')
                cache.set(ckey, {
                    'asset_tag': results[-1]['asset_tag'],
                    'name': results[-1]['name'],
                    'health_level': rep['health_level'],
                    'metrics': {k: rep[k] for k in ('original_value', 'current_value', 'used_years',
                                                    'useful_life', 'repair_total',
                                                    'lambda', 'econ_life') if k in rep},
                    'rules_hit': rep['rules_hit'],
                    'suggestion': rep['suggestion'],
                    'report': text, 'engine': engine,
                }, 86400)
            cache.set('ai_report_batch_last', {'count': len(results), 'at': time.time()}, 86400)
        except Exception:
            pass
        finally:
            cache.delete('ai_report_batch_lock')

    threading.Thread(target=_run_batch, daemon=True).start()
    # 注意：函数内不再引用 request（线程里访问已结束的请求对象不安全）
    return Response({'count': -1, 'llm': use_llm, 'skipped': 'background_started',
                     'reports': []})
