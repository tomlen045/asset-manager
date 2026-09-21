#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
华为AC 终端数据采集脚本（部署在宿主机 crontab，每 5 分钟）
用法：
  huawei_ac_collect.py                    # 按配置采集并上报
  huawei_ac_collect.py --test             # 只打印解析结果不上报
配置（环境变量或同目录 huawei_ac.conf JSON）：
  AC_HOST, AC_USER, AC_PASS, AC_PORT(默认22), SERVER(默认 http://127.0.0.1:8091)
crontab:
  */5 * * * * /usr/bin/python3 /data/scripts/huawei_ac_collect.py >> /var/log/ac_collect.log 2>&1
"""
import sys
import json
import time
import subprocess
import urllib.request

# ── 配置（优先环境变量） ──────────────────────────────
CFG = {
    'AC_HOST': '192.168.1.2',       # ← 改成你的华为AC管理IP
    'AC_USER': 'admin',
    'AC_PASS': 'AC密码',
    'AC_PORT': '22',
    'SERVER':  'http://127.0.0.1:8091',
    'TOKEN':   'change-me-pda-token',
}
try:
    with open('/data/scripts/huawei_ac.conf') as f:
        CFG.update(json.load(f))
except Exception:
    pass
import os
for k in CFG:
    if os.environ.get(k):
        CFG[k] = os.environ[k]


def ssh_ac(command):
    """SSH 到华为 AC 执行命令，返回输出。华为设备需先关闭分屏：screen-length 0 temporary"""
    full = 'screen-length 0 temporary\n' + command
    r = subprocess.run(
        ['sshpass', '-p', CFG['AC_PASS'], 'ssh', '-p', CFG['AC_PORT'],
         '-o', 'StrictHostKeyChecking=no',
         '-o', 'UserKnownHostsFile=/dev/null',
         '-o', 'ConnectTimeout=10',
         '%s@%s' % (CFG['AC_USER'], CFG['AC_HOST']),
         full],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45)
    if r.returncode != 0:
        raise RuntimeError('SSH failed: %s' % r.stderr.decode('utf-8', 'replace')[:200])
    return r.stdout.decode('utf-8', 'replace')


def parse_station(output):
    """解析 display station all（华为 V200R 版本通用格式）
    示例行:
    HUAWEI# display station all
    MAC          AP ID  AP组         SSID      ...  RSSI(dBm)  ...
    aabb-ccdd-ee01  3   default      Office-WiFi   ...  -52        ...
    """
    devices = []
    for line in output.splitlines():
        line = line.strip()
        m = None
        # MAC 形如 aabb-ccdd-ee01 / AA-BB-CC-DD-EE-01 / aabb.ccdd.ee01
        if '-' in line or '.' in line or ':' in line:
            parts = line.split()
            if len(parts) >= 4 and all(ch in '0123456789abcdefABCDEF-:.' for ch in parts[0]) \
               and any(x in parts[0] for x in ('-', '.', ':')) and len(parts[0]) >= 14:
                m = parts
        if not m:
            continue
        mac_raw, ap_id, ssid = m[0], m[1], m[3]
        rssi = None
        for p in m:
            p = p.strip()
            if p.startswith('-') and p[1:].isdigit():
                rssi = int(p)
                break
        devices.append({
            'mac': mac_raw,
            'ap_id': ap_id,
            'ap_name': ap_id,        # 若 AC 配置了 AP 名称显示列则更友好
            'ssid': ssid,
            'rssi': rssi,
        })
    return devices


def parse_roam_track(output):
    """解析 display station roam-track mac xxxx（漫游轨迹）
    格式参考:
    漫游轨迹:
    ----------------------------------------------------------
    漫游开始时间        AP名称       漫游原因
    2026-09-09 10:23:45 AP-A区-03   干扰漫游
    """
    tracks = []
    for line in output.splitlines():
        line = line.strip()
        parts = line.split()
        if len(parts) >= 3 and parts[0].count('-') == 2 and ':' in parts[1]:
            tracks.append({'time': parts[0] + ' ' + parts[1],
                           'ap': parts[2], 'reason': parts[3] if len(parts) > 3 else ''})
    return tracks


def collect():
    out = ssh_ac('display station all')
    devices = parse_station(out)
    print(time.strftime('%F %T'), 'parsed stations:', len(devices))
    if '--test' in sys.argv:
        print(json.dumps(devices, ensure_ascii=False, indent=1))
        return
    # 逐台上报心跳
    ok = fail = 0
    for d in devices:
        try:
            body = json.dumps(d).encode()
            req = urllib.request.Request(
                CFG['SERVER'] + '/api/pda/heartbeat/', data=body,
                headers={'Content-Type': 'application/json', 'X-Pda-Token': CFG['TOKEN']})
            urllib.request.urlopen(req, timeout=15)
            ok += 1
        except Exception as e:
            fail += 1
            print('report fail %s: %s' % (d['mac'], str(e)[:80]))
    print('reported ok=%d fail=%d' % (ok, fail))


if __name__ == '__main__':
    collect()
