"""移动设备（PDA/平板）定位服务：
- 心跳上报（PDA 端小工具每 5 分钟 POST）
- 设备台账 CRUD + 批量导入
- 区域聚合看板
- MQTT 响铃指令（mosquitto pub）
"""
import json
import re
import subprocess
from datetime import timedelta

from django.db.models import Q

from django.conf import settings
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import PdaDevice, Department

HEARTBEAT_TOKEN = getattr(settings, 'PDA_HEARTBEAT_TOKEN', 'change-me-pda-token')
MQTT_HOST = getattr(settings, 'PDA_MQTT_HOST', '127.0.0.1')
MQTT_PORT = getattr(settings, 'PDA_MQTT_PORT', 1883)
MQTT_USER = getattr(settings, 'PDA_MQTT_USER', '')
MQTT_PASS = getattr(settings, 'PDA_MQTT_PASS', '')


def _norm_mac(mac):
    """MAC 标准化为小写冒号分隔"""
    hexs = re.sub(r'[^0-9a-fA-F]', '', str(mac or ''))
    if len(hexs) != 12:
        return None
    return ':'.join(hexs[i:i + 2].lower() for i in range(0, 12, 2))


def _zone_from_ap(ap_name):
    """从 AP 名称提取区域：一期AP-14→一期；AP-A区-03→A区；涂装AP01→涂装；AP49→''"""
    if not ap_name:
        return ''
    m = re.search(r'([A-Za-z\u4e00-\u9fa5]{1,6}区)(?:[-_/\d]|$)', ap_name)
    if m:
        return m.group(1)
    m = re.match(r'^([\u4e00-\u9fa5]{2,12}?)(?:AP|ap)[-_]?\d*$', ap_name)
    if m and m.group(1):
        return m.group(1)
    return 


# ── 心跳上报（PDA 端调用，token 鉴权） ──────────────────────────
@api_view(['POST'])
@permission_classes([AllowAny])
def pda_heartbeat(request):
    tok = (request.headers.get('X-Pda-Token') or request.data.get('token') or '')
    if tok != HEARTBEAT_TOKEN:
        return Response({'error': 'bad token'}, status=403)
    mac = _norm_mac(request.data.get('mac'))
    if not mac:
        return Response({'error': 'mac required'}, status=400)

    ap_name = str(request.data.get('ap_name') or request.data.get('ap_id') or '')[:60]
    dev, created = PdaDevice.objects.get_or_create(
        mac=mac,
        defaults={'name': str(request.data.get('name') or '')[:60],
                  'device_model': str(request.data.get('model') or '')[:60],
                  'android_ver': str(request.data.get('android') or '')[:20]}
    )
    # 自动区域推断（AP 名首段）
    zone = _zone_from_ap(ap_name) or dev.zone
    battery = request.data.get('battery')
    dev.ap_bssid = str(request.data.get('bssid') or dev.ap_bssid)[:32]
    dev.ap_name = ap_name or dev.ap_name
    dev.zone = zone
    dev.rssi = int(request.data['rssi']) if str(request.data.get('rssi', '')).lstrip('-').isdigit() else dev.rssi
    dev.battery = int(battery) if str(battery).lstrip('-').isdigit() else dev.battery
    dev.ssid = str(request.data.get('ssid') or dev.ssid)[:40]
    dev.ip = request.data.get('ip') or dev.ip
    dev.last_seen = timezone.now()
    dev.save(update_fields=['ap_bssid', 'ap_name', 'zone', 'rssi', 'battery',
                            'ssid', 'ip', 'last_seen', 'updated_at'])
    # 历史快照（趋势图数据源）
    try:
        from .models import PdaHeartbeatHistory
        PdaHeartbeatHistory.objects.create(
            device=dev, battery=dev.battery, online=True,
            zone=dev.zone, ap_name=dev.ap_name, rssi=dev.rssi)
    except Exception:
        pass
    # 若有挂起的响铃指令，返回给设备执行
    ring = bool(dev.ring_command_at and (timezone.now() - dev.ring_command_at).total_seconds() < 600)
    resp = {'ok': True, 'created': created, 'zone': dev.zone}
    if ring:
        resp['ring'] = True
        dev.ring_command_at = None
        dev.save(update_fields=['ring_command_at'])
    return Response(resp)


# ── 设备列表 + 区域聚合 ────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pda_devices(request):
    qs = PdaDevice.objects.select_related('department', 'asset')
    kw = request.query_params.get('kw', '').strip()
    if kw:
        qs = qs.filter(Q(name__icontains=kw) | Q(mac__icontains=kw) |
                       Q(device_no__icontains=kw) | Q(owner__icontains=kw) |
                       Q(ap_name__icontains=kw) | Q(zone__icontains=kw))
    zone = request.query_params.get('zone', '').strip()
    if zone:
        qs = qs.filter(zone=zone)
    state = request.query_params.get('state', '').strip()
    now = timezone.now()
    if state == 'online':
        qs = qs.filter(last_seen__gte=now - timedelta(minutes=15))
    elif state == 'offline':
        qs = qs.filter(Q(last_seen__lt=now - timedelta(minutes=5)) | Q(last_seen__isnull=True))
    elif state == 'stale':
        qs = qs.filter(Q(last_seen__lt=now - timedelta(days=3)) | Q(last_seen__isnull=True))
    elif state == 'lowbat':
        qs = qs.filter(battery__lte=20)

    items = []
    for d in qs:
        dd = d.to_dict()
        dd['type'] = (d.device_type or 'pda')
        # NAC 列表每5分钟刷新一次，在线窗口放宽到15分钟
        dd['online'] = bool(d.last_seen and (now - d.last_seen).total_seconds() < 900)
        items.append(dd)
    # AP 条目合并（来自信锐 SNMP 缓存）——用户明确只要终端，AP 不并入清单（AP 数据走「查看 AP 清单」）
    pass
    # 区域聚合
    zones = {}
    for it in items:
        if it.get('type') == 'ap' or it.get('device_type') == 'ap':
            continue
        z = it['zone'] or '未分区'
        d = zones.setdefault(z, {'zone': z, 'total': 0, 'online': 0, 'lowbat': 0, 'stale': 0})
        d['total'] += 1
        if it['online']:
            d['online'] += 1
        if it['battery'] is not None and it['battery'] <= 20:
            d['lowbat'] += 1
        if it['stale']:
            d['stale'] += 1
    # AP 分组（信锐 AC SNMP 缓存）
    ap_zones = {}
    try:
        from .models import PdaAcConfig
        import json as _json
        cfg = PdaAcConfig.load()
        for a in _json.loads(cfg.ap_cache or '[]'):
            z = a.get('zone') or '未分组'
            d = ap_zones.setdefault(z, {'ap_total': 0, 'ap_online': 0})
            d['ap_total'] += 1
            if a.get('online'):
                d['ap_online'] += 1
    except Exception:
        pass
    # 合并到区域看板：AP 区域 ∪ PDA 区域
    all_zones = set(zones) | set(ap_zones)
    merged = []
    for z in all_zones:
        pz = zones.get(z, {'zone': z, 'total': 0, 'online': 0, 'lowbat': 0, 'stale': 0})
        az = ap_zones.get(z, {'ap_total': 0, 'ap_online': 0})
        merged.append({'zone': z,
                       'total': pz['total'], 'online': pz['online'],
                       'lowbat': pz['lowbat'], 'stale': pz['stale'],
                       'ap_total': az['ap_total'], 'ap_online': az['ap_online']})
    ap_total = sum(m['ap_total'] for m in merged)
    ap_online = sum(m['ap_online'] for m in merged)
    ap_items = [x for x in items if x.get('type') == 'ap' or x.get('device_type') == 'ap']
    pda_items = [x for x in items if x not in ap_items]
    summary = {
        'total': len(pda_items),
        'online': sum(1 for x in pda_items if x['online']),
        'lowbat': sum(1 for x in pda_items if x['battery'] is not None and x['battery'] <= 20),
        'stale': sum(1 for x in pda_items if x['stale']),
        'ap_total': ap_total,
        'ap_online': ap_online,
        'zones': sorted(merged, key=lambda d: -(d['total'] + d['ap_total'])),
    }
    return Response({'items': items, 'summary': summary})


# ── 设备编辑（责任人/部门/关联资产/备注） ───────────────────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pda_update(request, pk):
    try:
        dev = PdaDevice.objects.get(pk=pk)
    except PdaDevice.DoesNotExist:
        return Response({'error': 'not found'}, status=404)
    d = request.data
    if 'name' in d:
        dev.name = str(d['name'])[:60]
    if 'device_no' in d:
        dev.device_no = str(d['device_no'])[:40]
    if 'owner' in d:
        dev.owner = str(d['owner'])[:40]
    if 'note' in d:
        dev.note = str(d['note'])[:200]
    if 'allowed_zones' in d:
        zones = d['allowed_zones']
        dev.allowed_zones = [str(z)[:40] for z in zones] if isinstance(zones, list) else []
    if 'department' in d:
        dev.department = Department.objects.filter(pk=d['department']).first() if d['department'] else None
    if 'asset' in d:
        from .models import Asset
        dev.asset = Asset.objects.filter(pk=d['asset']).first() if d['asset'] else None
    dev.save(update_fields=['name', 'device_no', 'owner', 'note', 'department', 'asset', 'allowed_zones'] if 'allowed_zones' in d else None)
    return Response(dev.to_dict())


# ── MQTT 响铃指令 ──────────────────────────────────────────────
def _mqtt_pub(topic, payload):
    """MQTT PUBLISH: paho (bundled) first, mosquitto_pub fallback"""
    try:
        import paho.mqtt.publish as publish
        publish.single(topic, payload, hostname=MQTT_HOST, port=int(MQTT_PORT),
                       auth=(MQTT_USER, MQTT_PASS) if MQTT_USER else None)
        return None
    except ImportError:
        err1 = 'paho not installed'
    except Exception as e:
        err1 = str(e)
    else:
        err1 = None
    try:
        cmd = ['mosquitto_pub', '-h', MQTT_HOST, '-p', str(MQTT_PORT), '-t', topic, '-m', payload]
        if MQTT_USER:
            cmd += ['-u', MQTT_USER, '-P', MQTT_PASS]
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8)
        return None if r.returncode == 0 else (r.stderr.decode('utf-8', 'replace') or 'mosquitto_pub failed')
    except FileNotFoundError:
        return err1 or 'mosquitto_pub not installed'
    except Exception as e:
        return str(e)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pda_ring(request, pk):
    """下发响铃指令：写 ring_command_at + MQTT 发布（PDA 心跳时也会带回响铃标志）"""
    try:
        dev = PdaDevice.objects.get(pk=pk)
    except PdaDevice.DoesNotExist:
        return Response({'error': 'not found'}, status=404)
    dev.ring_command_at = timezone.now()
    dev.save(update_fields=['ring_command_at'])
    topic = f'pda/{dev.mac}/ring'
    payload = json.dumps({'cmd': 'ring', 'mac': dev.mac, 'ts': timezone.now().isoformat()})
    err = _mqtt_pub(topic, payload)
    return Response({'ok': err is None, 'mqtt_error': err,
                     'note': '指令已保存，设备下次心跳时也会带回响铃标志' if err else 'MQTT 已发布'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pda_bulk_import(request):
    """批量导入：支持两种方式
    ① Excel 文件上传（multipart，file=xxx.xlsx）——主推
    ② JSON rows=[{mac, name, device_no, owner, zone, ap_name, department}]（粘贴文本解析后）
    """
    f = request.FILES.get('file')
    rows = []
    if f:
        # ── Excel 文件导入 ──
        try:
            from openpyxl import load_workbook
            wb = load_workbook(f, data_only=True)
        except Exception as e:
            return Response({'error': f'无法解析 Excel 文件: {e}'}, status=400)
        ws = wb.active
        headers = ['mac', 'name', 'device_no', 'device_model', 'owner',
                   'department', 'zone', 'ap_name', 'note']
        zh = {'MAC地址': 'mac', '设备名称': 'name', '设备编号': 'device_no',
              '设备型号': 'device_model', '责任人': 'owner', '部门': 'department',
              '区域': 'zone', 'AP名称': 'ap_name', '备注': 'note'}
        for i, row in enumerate(ws.iter_rows(min_row=1, values_only=True), start=1):
            if not any(v is not None and str(v).strip() for v in row):
                continue
            cells = [str(v).strip() if v is not None else '' for v in row]
            if i == 1 and ('MAC' in cells[0].upper() or cells[0] in zh):
                continue  # 首行表头
            d = {}
            for j, key in enumerate(headers):
                d[key] = cells[j] if j < len(cells) else ''
            rows.append(d)
        if not rows:
            return Response({'error': 'Excel 中没有数据行（首行表头已忽略）'}, status=400)
    else:
        rows = request.data.get('rows') or []
    created, updated, errors = 0, 0, []
    for i, row in enumerate(rows):
        mac = _norm_mac(row.get('mac'))
        if not mac:
            errors.append(f'第{i + 1}行 MAC 无效: {row.get("mac")}')
            continue
        dept = Department.objects.filter(name=str(row.get('department') or '')).first()
        dev, c = PdaDevice.objects.update_or_create(
            mac=mac,
            defaults={'name': str(row.get('name') or '')[:60],
                      'device_no': str(row.get('device_no') or '')[:40],
                      'device_model': str(row.get('device_model') or '')[:60],
                      'owner': str(row.get('owner') or '')[:40],
                      'zone': str(row.get('zone') or _zone_from_ap(row.get('ap_name') or ''))[:40],
                      'ap_name': str(row.get('ap_name') or '')[:60],
                      'note': str(row.get('note') or '')[:200],
                      'department': dept})
        created += 1 if c else 0
        updated += 0 if c else 1
    return Response({'created': created, 'updated': updated, 'errors': errors,
                     'total': len(rows)})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pda_import_template(request):
    """下载 PDA 台账 Excel 导入模板（含示例行）"""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from django.http import HttpResponse
    import io
    wb = Workbook()
    ws = wb.active
    ws.title = 'PDA台账导入'
    headers = ['MAC地址', '设备名称', '设备编号', '设备型号', '责任人',
               '部门', '区域', 'AP名称', '备注']
    bold = Font(bold=True)
    fill = PatternFill('solid', fgColor='D9E1F2')
    for col, h in enumerate(headers, 1):
        c = ws.cell(1, col, h)
        c.font, c.fill = bold, fill
        ws.column_dimensions[c.column_letter].width = 18
    examples = [
        ['AABBCCDDEE01', '车间PDA-01', 'PDA-001', 'Honeywell EDA52', '张三', '生产部', 'A区', 'AP-A区-01', '装配一组'],
        ['AABBCCDDEE02', '车间PDA-02', 'PDA-002', 'Honeywell EDA52', '李四', '生产部', 'B区', 'AP-B区-05', ''],
    ]
    for r, ex in enumerate(examples, 2):
        for col, v in enumerate(ex, 1):
            ws.cell(r, col, v)
    buf = io.BytesIO()
    wb.save(buf)
    resp = HttpResponse(buf.getvalue(),
                        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    resp['Content-Disposition'] = 'attachment; filename=pda_import_template.xlsx'
    return resp

import os


# ── 批量删除 ────────────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pda_bulk_delete(request):
    """批量删除设备：ids=[1,2,3] 或 all=true 清空（慎用）"""
    ids = request.data.get('ids') or []
    if request.data.get('all'):
        n, _ = PdaDevice.objects.all().delete()
        return Response({'deleted': n})
    if not ids:
        return Response({'error': 'ids required'}, status=400)
    n, _ = PdaDevice.objects.filter(id__in=ids).delete()
    return Response({'deleted': n})


# ── 华为 AC 对接 ────────────────────────────────────────────────
AC_CFG = getattr(settings, 'PDA_AC_CONFIG', {})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pda_ac_test(request):
    """测试宿主机到华为 AC 的 SSH 连通性"""
    cfg = request.data
    host = str(cfg.get('ac_host') or '')
    if not host:
        return Response({'ok': False, 'error': 'AC IP 未填写'})
    try:
        r = subprocess.run(
            ['sshpass', '-p', str(cfg.get('ac_pass') or ''), 'ssh', '-p',
             str(cfg.get('ac_port') or '22'), '-o', 'StrictHostKeyChecking=no',
             '-o', 'ConnectTimeout=8', '%s@%s' % (cfg.get('ac_user'), host),
             'display version'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
        if r.returncode == 0:
            ver = r.stdout.decode('utf-8', 'replace')
            detail = ver.splitlines()[1].strip() if len(ver.splitlines()) > 1 else 'connected'
            return Response({'ok': True, 'detail': detail[:100]})
        return Response({'ok': False, 'error': r.stderr.decode('utf-8', 'replace')[:150]})
    except FileNotFoundError:
        return Response({'ok': False, 'error': '宿主机未安装 sshpass'})
    except subprocess.TimeoutExpired:
        return Response({'ok': False, 'error': '连接超时'})
    except Exception as e:
        return Response({'ok': False, 'error': str(e)[:150]})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pda_ac_script(request):
    """下载预填配置的华为 AC 采集脚本"""
    import io
    from django.http import HttpResponse
    script_path = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                '..', 'scripts', 'huawei_ac_collect.py'))
    content = open(script_path, 'r', encoding='utf-8').read()
    content = content.replace("'AC_HOST': '192.168.1.2'",
                              "'AC_HOST': '%s'" % request.query_params.get('ac_host', ''))
    content = content.replace("'AC_USER': 'admin'",
                              "'AC_USER': '%s'" % request.query_params.get('ac_user', 'admin'))
    content = content.replace("'AC_PASS': 'AC密码'",
                              "'AC_PASS': '%s'" % request.query_params.get('ac_pass', ''))
    content = content.replace("'AC_PORT': '22'",
                              "'AC_PORT': '%s'" % request.query_params.get('ac_port', '22'))
    resp = HttpResponse(content.encode('utf-8'), content_type='application/x-python')
    resp['Content-Disposition'] = 'attachment; filename=huawei_ac_collect.py'
    return resp


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pda_track(request, pk):
    """漫游轨迹（宿主机 SSH 华为 AC 执行 roam-track）"""
    try:
        dev = PdaDevice.objects.get(pk=pk)
    except PdaDevice.DoesNotExist:
        return Response({'error': 'not found'}, status=404)
    cfg = AC_CFG
    if not cfg.get('AC_HOST'):
        return Response({'tracks': [], 'note': '未配置 AC 对接'})
    try:
        import sys
        r = subprocess.run(
            ['sshpass', '-p', cfg.get('AC_PASS', ''), 'ssh', '-p', str(cfg.get('AC_PORT', '22')),
             '-o', 'StrictHostKeyChecking=no', '-o', 'ConnectTimeout=10',
             '%s@%s' % (cfg.get('AC_USER', 'admin'), cfg['AC_HOST']),
             'screen-length 0 temporary'],
            input=('display station roam-track mac %s\n' % dev.mac).encode(),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        out = r.stdout.decode('utf-8', 'replace')
        sys.path.insert(0, os.path.normpath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)), '..', 'scripts')))
        from huawei_ac_collect import parse_roam_track
        return Response({'tracks': parse_roam_track(out)})
    except Exception as e:
        return Response({'tracks': [], 'note': str(e)[:120]})


# ── 平面图可视化 ────────────────────────────────────────────────
from .models import PdaMapConfig


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pda_map_data(request):
    """平面图数据：底图(base64) + 设备点位 + AP 坐标"""
    cfg = PdaMapConfig.load()
    devices = [d.to_dict() for d in PdaDevice.objects.select_related('department')]
    for d in devices:
        obj = PdaDevice.objects.get(pk=d['id'])
        d['pos_x'] = obj.pos_x
        d['pos_y'] = obj.pos_y
    img = None
    if cfg.floor_image:
        import base64
        img = 'data:%s;base64,%s' % (cfg.image_mime or 'image/png',
                                     base64.b64encode(cfg.floor_image).decode())
    return Response({
        'image': img,
        'devices': devices,
        'ap_coords': json.loads(cfg.ap_coords or '[]'),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pda_map_upload(request):
    """上传平面图底图（multipart: image）"""
    import base64
    f = request.FILES.get('image')
    if not f:
        return Response({'error': 'image required'}, status=400)
    cfg = PdaMapConfig.load()
    cfg.floor_image = f.read()
    cfg.image_mime = f.content_type or 'image/png'
    cfg.save()
    return Response({'ok': True, 'size': len(cfg.floor_image or b'')})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pda_map_save(request):
    """保存点位：devices=[{id,pos_x,pos_y}] + ap_coords=[{name,x,y}]"""
    cfg = PdaMapConfig.load()
    for row in request.data.get('devices') or []:
        try:
            dev = PdaDevice.objects.get(pk=row['id'])
        except PdaDevice.DoesNotExist:
            continue
        dev.pos_x = row.get('pos_x')
        dev.pos_y = row.get('pos_y')
        dev.save(update_fields=['pos_x', 'pos_y'])
    if 'ap_coords' in request.data:
        cfg.ap_coords = json.dumps(request.data['ap_coords'], ensure_ascii=False)
        cfg.save()
    return Response({'ok': True})
