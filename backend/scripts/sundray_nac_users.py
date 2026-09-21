#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
信锐 NAC 无线用户采集器 —— 模拟登录 NAC Web 平台拉取在线终端表
用法:
  sundray_nac_users.py <nac_base> <username> <password> [output.json]
  例: sundray_nac_users.py https://192.168.1.100 admin 'password' /tmp/users.json
输出 JSON: [{mac, username, dev_type, device_name, ip, ap_name, last_seen}]
"""
import ssl
import sys
import json
import re
import urllib.request
import urllib.parse
import http.cookiejar
import socket

ssl._create_default_https_context = ssl._create_unverified_context  # NAC 自签证书


def make_opener():
    cj = http.cookiejar.CookieJar()
    return urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cj)), cj


def get_csrf(html):
    m = re.search(r'name="S_T" value="([0-9a-f]+)"', html)
    return m.group(1) if m else ''


def login(base, user, pw):
    opener, cj = make_opener()
    r = opener.open(base + '/index.php/welcome/login', timeout=15)
    html = r.read().decode('utf-8', 'replace')
    token = get_csrf(html)
    data = urllib.parse.urlencode({
        'username': user, 'password': pw,
        'S_T': token, 'nci': '0',
    }).encode()
    req = urllib.request.Request(base + '/index.php/welcome/login', data=data)
    resp = opener.open(req, timeout=15)
    body = resp.read().decode('utf-8', 'replace')
    # 登录成功判定：跳转或页面不再含 login 表单
    if 'welcome/login' in resp.geturl() and 'name="password"' in body:
        raise IOError('NAC 登录失败（账号密码错误或需要验证码）')
    return opener


def parse_html_table(html):
    """解析 NAC 页面里的数据表格 → [[col1, col2, ...], ...]"""
    rows = []
    for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.S | re.I):
        cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', tr, re.S | re.I)
        cells = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
        if any(cells):
            rows.append(cells)
    return rows


def fetch_users(base, opener):
    """拉取在线用户列表（尝试多个已知接口路径）"""
    candidates = [
        '/index.php/terminal/user_list',
        '/index.php/terminal/online_user',
        '/index.php/terminal/wireless_user',
        '/index.php/terminal/wlan_user',
        '/index.php/welcome/user_list',
        '/index.php/online_user/list',
        '/index.php/ac/online_user',
    ]
    last_err = None
    for path in candidates:
        try:
            r = opener.open(base + path, timeout=20)
            body = r.read().decode('utf-8', 'replace')
            # JSON 接口
            try:
                data = json.loads(body)
                if isinstance(data, (dict, list)):
                    return path, data
            except ValueError:
                pass
            # HTML 表格 → 解析 <tr><td> 行
            if '<table' in body and ('MAC' in body or 'mac' in body or '接入点' in body):
                rows = parse_html_table(body)
                if rows:
                    return path, rows
        except Exception as e:
            last_err = e
    raise IOError('未找到终端列表接口: %s' % last_err)


if __name__ == '__main__':
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    base, user, pw = sys.argv[1], sys.argv[2], sys.argv[3]
    if not base.startswith('http'):
        base = 'https://' + base
    opener = login(base, user, pw)
    print('登录成功')
    path, data = fetch_users(base, opener)
    print('数据来自:', path)
    if isinstance(data, str):
        print(data[:2000])
    else:
        print(json.dumps(data, ensure_ascii=False)[:2000])
