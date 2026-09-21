"""移动设备二维码标签 + 扫码领用/归还登记"""
import json
from datetime import datetime, timedelta

from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import PdaDevice, PdaScanLog, PdaHeartbeatHistory


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pda_labels(request):
    """生成二维码标签数据（前端渲染 QR 图片）
    qr 内容：系统 URL + 设备 MAC，扫码后打开「扫码登记」页自动识别设备
    """
    ids = request.query_params.get('ids', '')
    qs = PdaDevice.objects.all()
    if ids:
        id_list = [int(x) for x in ids.split(',') if x.strip().isdigit()]
        qs = qs.filter(id__in=id_list)
    base = request.build_absolute_uri('/').rstrip('/')
    labels = []
    for d in qs:
        labels.append({
            'id': d.id,
            'mac': d.mac,
            'name': d.name or d.device_no or d.mac,
            'device_no': d.device_no,
            'owner': d.owner,
            'zone': d.zone,
            'qr': f'{base}/#/pda-scan?mac={d.mac}',
        })
    return Response({'labels': labels, 'base': base})


@api_view(['GET'])
@permission_classes([AllowAny])
def pda_scan_lookup(request):
    """扫码登记页查询：按 MAC 查设备当前信息（免登录，供 PDA 扫码后直接看）"""
    from .pda import _norm_mac
    mac = _norm_mac(request.query_params.get('mac'))
    if not mac:
        return Response({'error': 'mac required'}, status=400)
    try:
        d = PdaDevice.objects.get(mac=mac)
    except PdaDevice.DoesNotExist:
        return Response({'found': False, 'mac': mac})
    return Response({'found': True, **d.to_dict()})


@api_view(['POST'])
@permission_classes([AllowAny])
def pda_scan_log(request):
    """扫码领用/归还登记（免登录，扫码即操作）
    body: {mac, action: 'take'|'return', person}
    """
    from .pda import _norm_mac
    mac = _norm_mac(request.data.get('mac'))
    if not mac:
        return Response({'error': 'mac required'}, status=400)
    action = request.data.get('action')
    person = str(request.data.get('person') or '').strip()[:40]
    if action not in ('take', 'return'):
        return Response({'error': 'action must be take/return'}, status=400)
    if not person:
        return Response({'error': 'person required'}, status=400)
    try:
        d = PdaDevice.objects.get(mac=mac)
    except PdaDevice.DoesNotExist:
        return Response({'error': 'device not found'}, status=404)
    log = PdaScanLog.objects.create(
        device=d, action=action, person=person,
        note=str(request.data.get('note') or '')[:200])
    return Response({
        'ok': True,
        'device': d.name or d.mac,
        'action_text': '领用' if action == 'take' else '归还',
        'person': person,
        'time': log.created_at.strftime('%Y-%m-%d %H:%M'),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pda_scan_logs(request):
    """领用/归还记录（最近 200 条）"""
    mac = request.query_params.get('mac', '').strip()
    qs = PdaScanLog.objects.select_related('device').order_by('-created_at')[:200]
    if mac:
        from .pda import _norm_mac
        m = _norm_mac(mac)
        qs = PdaScanLog.objects.filter(device__mac=m).order_by('-created_at')[:200]
    return Response({'logs': [x.to_dict() for x in qs]})


# ── 心跳历史（趋势图数据源） ────────────────────────────────────


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pda_history(request, pk):
    """单台设备心跳历史（最近 N 条：电量曲线+在线状态）"""
    try:
        dev = PdaDevice.objects.get(pk=pk)
    except PdaDevice.DoesNotExist:
        return Response({'error': 'not found'}, status=404)
    limit = min(int(request.query_params.get('limit', 100)), 500)
    rows = (PdaHeartbeatHistory.objects.filter(device=dev)
            .order_by('-ts')[:limit])
    return Response({
        'name': dev.name or dev.mac,
        'points': [{'ts': x.ts.strftime('%m-%d %H:%M'),
                    'battery': x.battery,
                    'online': x.online,
                    'zone': x.zone,
                    'rssi': x.rssi} for x in reversed(rows)],
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pda_guide(request):
    """入网配置指引内容（静态结构化数据，前端渲染）"""
    return Response({'guide': json.loads(open(
        __import__('os').path.join(__import__('os').path.dirname(__file__),
                                   'pda_guide.json'), encoding='utf-8').read())})


# ── 信锐 AC 终端 CSV 导入（无线终端列表导出） ────────────────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pda_sundray_csv(request):
    """解析信锐 AC 导出的无线终端 CSV 并同步到设备台账
    兼容信锐 Web 网管导出格式：自动识别表头列（MAC/终端名/AP/IP/信号/在线时间等）
    """
    from .pda import _norm_mac, _zone_from_ap
    f = request.FILES.get('file')
    if not f:
        return Response({'error': 'file required'}, status=400)
    raw = f.read()
    # 编码探测：信锐导出常见 GBK/UTF-8
    text = None
    for enc in ('utf-8-sig', 'utf-8', 'gbk', 'gb18030'):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        return Response({'error': '无法识别文件编码'}, status=400)

    import csv as _csv
    import io as _io
    reader = _csv.reader(_io.StringIO(text))
    rows = list(reader)
    if not rows:
        return Response({'error': '文件为空'}, status=400)

    # 表头列识别（模糊匹配）
    header = rows[0]
    def find_col(*keys):
        for i, h in enumerate(header):
            hl = str(h).lower()
            if any(k in hl for k in keys):
                return i
        return None
    used = set()

    def find_col(*keys):
        for k in keys:
            for i, h in enumerate(header):
                if i in used:
                    continue
                if k in str(h).lower():
                    used.add(i)
                    return i
        return None

    col_mac = find_col('mac')
    if col_mac is None:
        return Response({'error': '未找到 MAC 列，请确认是信锐无线终端导出文件',
                         'header': header}, status=400)
    col_ip = find_col('ip')
    col_ap = find_col('接入点', 'ap')
    col_rssi = find_col('rssi', '信号')
    col_ssid = find_col('ssid', '服务集')
    col_time = find_col('最近接入', '上线时间', '在线时间', '接入时间', '关联时间')
    col_name = find_col('用户名', '终端名', '主机名', '设备名称', '设备名', '名称')
    col_devtype = find_col('终端类型', '类型')
    col_devname = find_col('设备名称')

    created, updated, skipped = 0, 0, 0
    for row in rows[1:]:
        if len(row) <= col_mac:
            continue
        mac = _norm_mac(row[col_mac])
        if not mac:
            skipped += 1
            continue
        try:
            dev, c = PdaDevice.objects.get_or_create(mac=mac, defaults={})
        except Exception:
            skipped += 1
            continue
        name_val = ''
        if col_devname is not None and col_devname < len(row):
            name_val = str(row[col_devname]).strip()
        if name_val in ('-', '--'):
            name_val = ''
        if not name_val and col_name is not None and col_name < len(row):
            name_val = str(row[col_name]).strip()
        if name_val in ('-', '--'):
            name_val = ''
        if name_val:
            dev.name = name_val[:60]
        if col_devtype is not None and col_devtype < len(row):
            dv = str(row[col_devtype]).strip()[:30]
            if dv:
                dev.note = (dv + ' · ' + (dev.note or ''))[:200]
        if col_ip is not None and col_ip < len(row):
            import re as _re
            ip_candidate = row[col_ip].strip()
            if _re.match(r'^\d{1,3}(\.\d{1,3}){3}$', ip_candidate):
                try:
                    dev.ip = ip_candidate
                except Exception:
                    pass
        if col_ap is not None and col_ap < len(row):
            ap_full = str(row[col_ap]).strip()
            dev.ap_name = (ap_full.split('/')[-1] if '/' in ap_full else ap_full)[:60]
            dev.zone = _zone_from_ap(dev.ap_name) or dev.zone
        if col_rssi is not None and col_rssi < len(row):
            try:
                dev.rssi = int(float(row[col_rssi]))
            except Exception:
                pass
        if col_ssid is not None and col_ssid < len(row):
            dev.ssid = str(row[col_ssid]).strip()[:40]
        dev.last_seen = timezone.now()
        dev.save()
        created += 1 if c else 0
        updated += 0 if c else 1

    return Response({'created': created, 'updated': updated, 'skipped': skipped,
                     'total_rows': len(rows) - 1})


# ── 信锐 SNMP 对接 ──────────────────────────────────────────────
from .models import PdaAcConfig


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pda_snmp_test(request):
    """测试 SNMP 连通性：读 sysDescr/sysName + AP 数量"""
    import tempfile, importlib.util, os
    ip = str(request.data.get('ac_ip') or '').strip()
    community = str(request.data.get('community') or 'public').strip()
    if not ip:
        return Response({'ok': False, 'error': 'AC 地址未填写'})
    # snmp 客户端在 scripts/sundray_snmp.py，容器内路径 /app/backend/scripts/
    snmp_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'sundray_snmp.py')
    if not os.path.exists(snmp_path):
        return Response({'ok': False, 'error': '采集器文件缺失'})
    spec = importlib.util.spec_from_file_location('sundray_snmp', snmp_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        c = mod.SnmpClient(ip, community, timeout=2.0, retries=1)
        descr = c.get(['1.3.6.1.2.1.1.1.0'])[0][1]
        name = c.get(['1.3.6.1.2.1.1.5.0'])[0][1]
        aps = mod.fetch_wac_aps(ip, community)
        return Response({'ok': True,
                         'detail': '设备: %s | 系统: %s | 采集到 %d 台 AP' % (
                             str(name).strip(), str(descr).strip(), len(aps))})
    except Exception as e:
        return Response({'ok': False, 'error': str(e)[:200]})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pda_snmp_sync(request):
    """同步 AP 表到缓存 + 存配置"""
    import importlib.util, os, json as _json
    from django.utils import timezone
    ip = str(request.data.get('ac_ip') or '').strip()
    community = str(request.data.get('community') or 'public').strip()
    if not ip:
        return Response({'ok': False, 'error': 'AC 地址未填写'})
    snmp_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'sundray_snmp.py')
    spec = importlib.util.spec_from_file_location('sundray_snmp', snmp_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        result = mod.fetch_wac_aps(ip, community)
    except Exception as e:
        return Response({'ok': False, 'error': str(e)[:200]})
    aps, online_count = result[0], result[1]
    # 区域推断：AP 名开头连续中文 2-10 字作为区域
    import re as _re
    for a in aps:
        m = _re.match(r'^([\u4e00-\u9fa5]{2,10})', str(a.get('name') or ''))
        a['zone'] = m.group(1) if m else '未分组'
    # AP 不入设备台账（用户只要终端304台），仅存缓存供「查看 AP 清单」
    cfg = PdaAcConfig.load()
    cfg.ac_ip = ip
    cfg.community = community
    cfg.ap_cache = _json.dumps(aps, ensure_ascii=False)
    cfg.last_sync = timezone.now()
    cfg.save()
    return Response({'ok': True, 'ap_count': len(aps), 'online_count': online_count,
                     'last_sync': cfg.last_sync.strftime('%Y-%m-%d %H:%M')})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pda_snmp_config(request):
    """读当前 AC 配置与 AP 缓存"""
    cfg = PdaAcConfig.load()
    import json as _json
    return Response({
        'ac_ip': cfg.ac_ip, 'community': cfg.community,
        'last_sync': cfg.last_sync.strftime('%Y-%m-%d %H:%M') if cfg.last_sync else None,
        'ap_count': len(_json.loads(cfg.ap_cache or '[]')),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pda_snmp_aps(request):
    """AP 清单（含区域推断）"""
    import json as _json
    cfg = PdaAcConfig.load()
    aps = _json.loads(cfg.ap_cache or '[]')
    for a in aps:
        a.setdefault('zone', '未分组')
        a.setdefault('online', False)
    return Response({'ac_ip': cfg.ac_ip, 'community': cfg.community,
                     'last_sync': cfg.last_sync.strftime('%Y-%m-%d %H:%M') if cfg.last_sync else None,
                     'ap_count': len(aps), 'aps': aps})


# ── 信锐 NAC Web 对接（终端表） ────────────────────────────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pda_nac_test(request):
    """测试 NAC 登录 + 终端表接口"""
    import importlib.util, os
    nac_url = str(request.data.get('nac_url') or '').strip()
    user = str(request.data.get('nac_user') or '').strip()
    pw = str(request.data.get('nac_pass') or '').strip()
    if not (nac_url and user and pw):
        return Response({'ok': False, 'error': 'NAC 地址/账号/密码 需填写完整'})
    if not nac_url.startswith('http'):
        nac_url = 'https://' + nac_url
    snmp_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             'scripts', 'sundray_nac_users.py')
    if not os.path.exists(snmp_path):
        return Response({'ok': False, 'error': '采集器文件缺失'})
    spec = importlib.util.spec_from_file_location('sundray_nac_users', snmp_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        opener = mod.login(nac_url, user, pw)
        path, data = mod.fetch_users(nac_url, opener)
        count = len(data) if isinstance(data, list) else 'HTML表'
        return Response({'ok': True,
                         'detail': '登录成功，终端接口 %s，数据 %s 条' % (path, count)})
    except Exception as e:
        return Response({'ok': False, 'error': str(e)[:200]})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pda_nac_sync(request):
    """登录 NAC 拉取终端 → 建档（含接入点拆区域）"""
    import importlib.util, os
    from django.utils import timezone
    nac_url = str(request.data.get('nac_url') or '').strip()
    user = str(request.data.get('nac_user') or '').strip()
    pw = str(request.data.get('nac_pass') or '').strip()
    if not (nac_url and user and pw):
        return Response({'ok': False, 'error': 'NAC 地址/账号/密码 需填写完整'})
    if not nac_url.startswith('http'):
        nac_url = 'https://' + nac_url
    snmp_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             'scripts', 'sundray_nac_users.py')
    spec = importlib.util.spec_from_file_location('sundray_nac_users', snmp_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        opener = mod.login(nac_url, user, pw)
        path, data = mod.fetch_users(nac_url, opener)
    except Exception as e:
        return Response({'ok': False, 'error': str(e)[:200]})
    created, updated = 0, 0
    from .models import PdaDevice
    from .pda import _norm_mac, _zone_from_ap
    rows = data if isinstance(data, list) else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        mac = _norm_mac(row.get('mac') or row.get('MAC地址') or '')
        if not mac:
            continue
        ap_full = str(row.get('ap_name') or row.get('接入点') or '')
        ap_name = ap_full.split('/')[-1] if '/' in ap_full else ap_full
        zone = _zone_from_ap(ap_name) or '未分组'
        dev, c = PdaDevice.objects.get_or_create(mac=mac, defaults={
            'name': str(row.get('device_name') or row.get('用户名') or mac)[:60],
            'device_type': 'pda',
            'zone': zone, 'ap_name': ap_name[:60],
            'ip': str(row.get('ip') or '')[:40],
            'last_seen': timezone.now(),
        })
        if c:
            created += 1
        else:
            updated += 1
            dev.zone = zone or dev.zone
            dev.ap_name = ap_name[:60] or dev.ap_name
            dev.last_seen = timezone.now()
            dev.save(update_fields=['zone', 'ap_name', 'last_seen'])
    cfg = PdaAcConfig.load()
    cfg.nac_url, cfg.nac_user, cfg.nac_pass = nac_url, user, pw
    cfg.save()
    return Response({'ok': True, 'created': created, 'updated': updated, 'total': len(rows)})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pda_nac_config(request):
    """读 NAC 配置（密码脱敏）"""
    cfg = PdaAcConfig.load()
    return Response({'nac_url': cfg.nac_url, 'nac_user': cfg.nac_user,
                     'has_pass': bool(cfg.nac_pass)})


# ── NAC 终端 JSON 直导入（供浏览器端自动同步调用） ──────────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pda_nac_import(request):
    """接收 NAC 终端 JSON 数组，建档/更新（浏览器 CDP 通道自动同步用）"""
    from .models import PdaDevice
    from .pda import _norm_mac, _zone_from_ap
    from django.utils import timezone
    rows = request.data.get('rows') or []
    if not isinstance(rows, list):
        return Response({'ok': False, 'error': 'rows 需为数组'})
    created, updated = 0, 0
    now = timezone.now()
    for x in rows:
        mac = _norm_mac(x.get('mac') or '')
        if not mac:
            continue
        ap_full = str(x.get('ap_name') or '')
        ap_short = str(x.get('_ap_name') or (ap_full.split('/')[-1] if '/' in ap_full else ap_full))
        zone = _zone_from_ap(ap_short) or '未分区'
        username = str(x.get('username') or mac)[:60]
        ttype = str(x.get('terminal_type') or '其他类型')
        ip_full = str(x.get('ip') or '')
        ip = ip_full.split('/')[0][:40]
        # 在线口径 = 出现在 NAC「在线用户」列表（PSK 认证组成员，WiFi 仍关联）
        # NAC 列表本身就是实时关联表：下线终端会从列表消失，每5分钟同步刷新
        # recent_used_time（最近使用时间）另存备查
        rut = str(x.get('recent_used_time') or '')[:19]
        last_seen = now
        dev, c = PdaDevice.objects.get_or_create(mac=mac, defaults={
            'name': username, 'device_type': 'pda', 'zone': zone,
            'ap_name': ap_short[:60], 'ip': ip,
            'note': ((ttype or '其他类型') + (' · 最近接入 ' + rut if rut else ''))[:200],
            'last_seen': last_seen,
        })
        if c:
            created += 1
        else:
            updated += 1
            old_zone = dev.zone
            # 区域围栏检测：有允许区域配置且新区域不在其中 → 告警
            if dev.allowed_zones and zone and zone != old_zone and zone not in dev.allowed_zones:
                try:
                    from .models import PdaZoneAlarm
                    PdaZoneAlarm.objects.create(
                        mac=mac, device_name=username,
                        from_zone=old_zone, to_zone=zone,
                        ap_name=ap_short[:60])
                except Exception:
                    pass
            dev.name = username
            dev.zone = zone
            dev.ap_name = ap_short[:60]
            dev.ip = ip
            if ttype:
                dev.note = (ttype + (' · 最近接入 ' + rut if rut else ''))[:200]
            dev.last_seen = last_seen
            dev.save(update_fields=['name', 'zone', 'ap_name', 'ip', 'note', 'last_seen'])
    return Response({'ok': True, 'created': created, 'updated': updated, 'total': len(rows)})


# ── 终端 ↔ 资产自动关联 ────────────────────────────────────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pda_link_assets(request):
    """自动关联资产：MAC 匹配资产SN → 名称精确/模糊匹配 asset_name"""
    from .models import PdaDevice, Asset
    linked, unmatched = 0, []
    for dev in PdaDevice.objects.filter(asset__isnull=True):
        matched = None
        # ① MAC 匹配资产 SN（去分隔符比较）
        mac_clean = dev.mac.replace(':', '').replace('-', '').upper()
        if len(mac_clean) == 12:
            matched = Asset.objects.filter(sn__iexact=mac_clean).first()
            if not matched:
                matched = Asset.objects.filter(sn__icontains=mac_clean[-8:]).first()
        # ② 名称精确匹配
        if not matched and dev.name and dev.name not in ('-', ''):
            matched = Asset.objects.filter(asset_name__iexact=dev.name.strip()).first()
        # ③ 名称模糊（去数字前后缀的核心词，如"郭玉新PDA21"→"郭玉新"）
        if not matched and dev.name:
            import re as _re
            core = _re.sub(r'(PDA|pda|平板|[0-9]+|-|_)', '', dev.name).strip()
            if len(core) >= 2:
                matched = Asset.objects.filter(asset_name__icontains=core).first()
        if matched:
            dev.asset = matched
            dev.linked_by = 'auto'
            dev.save(update_fields=['asset', 'linked_by'])
            linked += 1
        else:
            unmatched.append(dev.name or dev.mac)
    return Response({'ok': True, 'linked': linked,
                     'unmatched_count': len(unmatched), 'unmatched': unmatched[:50]})


# ── 区域围栏告警 ───────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pda_zone_alarms(request):
    from .models import PdaZoneAlarm
    qs = PdaZoneAlarm.objects.all()
    if str(request.query_params.get('unread', '')) == '1':
        qs = qs.filter(is_read=False)
    rows = [{'id': a.id, 'mac': a.mac, 'device_name': a.device_name,
             'from_zone': a.from_zone, 'to_zone': a.to_zone,
             'ap_name': a.ap_name,
             'created_at': a.created_at.strftime('%Y-%m-%d %H:%M'),
             'is_read': a.is_read} for a in qs[:100]]
    unread = PdaZoneAlarm.objects.filter(is_read=False).count()
    return Response({'ok': True, 'total': qs.count(), 'unread': unread, 'rows': rows})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pda_zone_alarms_read(request):
    """标记告警已读：{'ids': [..]} 或 {'all': true}"""
    from .models import PdaZoneAlarm
    if request.data.get('all'):
        n = PdaZoneAlarm.objects.filter(is_read=False).update(is_read=True)
    else:
        n = PdaZoneAlarm.objects.filter(id__in=request.data.get('ids', [])).update(is_read=True)
    return Response({'ok': True, 'updated': n})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pda_bulk_zone(request):
    """批量设置允许区域：{'kw': '一期PDA', 'zones': ['一期']} —— 名称含 kw 的设备设置允许区域"""
    from .models import PdaDevice
    kw = str(request.data.get('kw') or '').strip()
    zones = request.data.get('zones') or []
    if not kw:
        return Response({'ok': False, 'error': 'kw 必填'})
    qs = PdaDevice.objects.filter(name__icontains=kw)
    n = qs.update(allowed_zones=zones)
    return Response({'ok': True, 'updated': n, 'zones': zones})


# ── 在线率报表 ────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pda_online_report(request):
    """在线率报表：当前区域分布 + 历史小时快照"""
    from .models import PdaDevice
    from django.db.models import Count, Q
    now_aware = timezone.now()
    # 当前区域在线率
    zones = (PdaDevice.objects.filter(device_type='pda')
             .values('zone')
             .annotate(total=Count('id'),
                       online=Count('id', filter=Q(last_seen__gte=now_aware - timedelta(minutes=15))))
             .order_by('-total'))
    zone_rows = [{'zone': (z['zone'] or '未分区'), 'total': z['total'], 'online': z['online'],
                  'rate': round(z['online'] * 100 / z['total'], 1) if z['total'] else 0} for z in zones]
    # 终端类型分布
    from collections import Counter as _Counter
    _types = _Counter()
    for n in PdaDevice.objects.filter(device_type='pda').values_list('note', flat=True):
        _types[(n or '其他类型').split(' · ')[0]] += 1
    type_rows = sorted([{'type': k, 'total': v} for k, v in _types.items()], key=lambda x: -x['total'])
    # 历史快照（最近 48 小时）
    from .models import PdaHourlySnapshot
    since = now_aware - timedelta(hours=48)
    snaps = (PdaHourlySnapshot.objects.filter(hour__gte=since)
             .values('hour').annotate(total=Count('id'), online=Count('id', filter=Q(online=True)))
             .order_by('hour'))
    history = [{'hour': s['hour'].strftime('%m-%d %H:00'), 'total': s['total'], 'online': s['online'],
                'rate': round(s['online'] * 100 / s['total'], 1) if s['total'] else 0} for s in snaps]
    return Response({'ok': True, 'zones': zone_rows, 'types': type_rows, 'history': history})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pda_snapshot_tick(request):
    """写当前小时快照（NAC 同步后由 cron 调用；幂等：同小时覆盖）"""
    from .models import PdaDevice, PdaHourlySnapshot
    from django.db.models import Q
    now_aware = timezone.now()
    hour = now_aware.replace(minute=0, second=0, microsecond=0)
    PdaHourlySnapshot.objects.filter(hour=hour).delete()
    devs = PdaDevice.objects.filter(device_type='pda')
    online_qs = devs.filter(last_seen__gte=now_aware - timedelta(minutes=15))
    batch = []
    for d in devs:
        batch.append(PdaHourlySnapshot(
            hour=hour, mac=d.mac, zone=d.zone or '未分区',
            online=bool(d.last_seen and (now_aware - d.last_seen).total_seconds() < 900)))
    PdaHourlySnapshot.objects.bulk_create(batch, batch_size=500)
    return Response({'ok': True, 'hour': hour.strftime('%Y-%m-%d %H:00'), 'devices': len(batch)})


# ── 批量信息补全工作台 ────────────────────────────────────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pda_bulk_enrich_preview(request):
    """规则预览：{'rules': [{'kw':'一期PDA','zone':'一期','owner':'张三'}, ...]}
    返回每条规则命中的设备数（不执行）"""
    from .models import PdaDevice
    rules = request.data.get('rules') or []
    preview = []
    for r in rules:
        kw = str(r.get('kw') or '').strip()
        if not kw:
            continue
        qs = PdaDevice.objects.filter(device_type='pda', name__icontains=kw)
        sample = list(qs.values_list('name', flat=True)[:5])
        preview.append({'kw': kw, 'zone': r.get('zone', ''), 'owner': r.get('owner', ''),
                        'match': qs.count(), 'sample': sample})
    return Response({'ok': True, 'preview': preview})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pda_bulk_enrich_apply(request):
    """执行规则：命中设备更新 区域/责任人/设备编号前缀"""
    from .models import PdaDevice
    rules = request.data.get('rules') or []
    total = 0
    detail = []
    for r in rules:
        kw = str(r.get('kw') or '').strip()
        if not kw:
            continue
        qs = PdaDevice.objects.filter(device_type='pda', name__icontains=kw)
        n = qs.count()
        updates = {}
        if r.get('zone'):
            updates['zone'] = str(r['zone'])[:40]
        if r.get('owner'):
            updates['owner'] = str(r['owner'])[:40]
        if updates:
            qs.update(**updates)
            total += n
            detail.append({'kw': kw, 'updated': n, **updates})
    return Response({'ok': True, 'total_updated': total, 'detail': detail})


# ── 大屏模式聚合接口 ──────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pda_bigscreen(request):
    """大屏单接口：汇总 + 区域 + 类型 + 告警 + AP 概要"""
    from .models import PdaDevice, PdaZoneAlarm, PdaAcConfig
    from django.db.models import Count, Q
    import json as _json
    now_aware = timezone.now()
    devs = PdaDevice.objects.filter(device_type='pda')
    total = devs.count()
    online = devs.filter(last_seen__gte=now_aware - timedelta(minutes=15)).count()
    stale = devs.filter(Q(last_seen__lt=now_aware - timedelta(days=3)) | Q(last_seen__isnull=True)).count()
    lowbat = devs.filter(battery__lte=20).count()
    # 区域
    zones = (devs.values('zone')
             .annotate(total=Count('id'),
                       on=Count('id', filter=Q(last_seen__gte=now_aware - timedelta(minutes=15))))
             .order_by('-total'))
    zone_rows = [{'zone': (z['zone'] or '未分区'), 'total': z['total'], 'online': z['on'],
                  'rate': round(z['on'] * 100 / z['total'], 1) if z['total'] else 0} for z in zones]
    # 类型
    from collections import Counter as _Counter
    _types = _Counter()
    for n in devs.values_list('note', flat=True):
        _types[(n or '其他类型').split(' · ')[0]] += 1
    type_rows = sorted([{'type': k, 'total': v} for k, v in _types.items()], key=lambda x: -x['total'])
    # 未读告警（最近10条）
    alarms = [{'device': a.device_name, 'from': a.from_zone, 'to': a.to_zone,
               'time': a.created_at.strftime('%m-%d %H:%M')}
              for a in PdaZoneAlarm.objects.filter(is_read=False)[:10]]
    # AP 概要
    cfg = PdaAcConfig.load()
    aps = _safe_load(cfg.ap_cache)
    ap_online = sum(1 for a in aps if a.get('online'))
    # 最近接入 TOP（10台）
    recent = [{'name': d.name or d.mac, 'zone': d.zone or '未分区', 'ap': d.ap_name,
               'time': d.last_seen.strftime('%H:%M') if d.last_seen else '—'}
              for d in devs.order_by('-last_seen')[:10]]
    return Response({
        'ok': True,
        'summary': {'total': total, 'online': online,
                    'offline': total - online, 'lowbat': lowbat, 'stale': stale,
                    'ap_total': len(aps), 'ap_online': ap_online,
                    'server_time': now_aware.strftime('%Y-%m-%d %H:%M:%S')},
        'zones': zone_rows, 'types': type_rows, 'alarms': alarms, 'recent': recent,
    })


def _safe_load(s):
    import json as _json
    try:
        return _json.loads(s or '[]')
    except Exception:
        return []
