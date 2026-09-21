#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""信锐 NAC 在线用户拉取（Cookie 模式）
用法: sundray_nac_cookie_pull.py <phpsessid>
"""
import urllib.request, ssl, sys, re, json

ssl._create_default_https_context = ssl._create_unverified_context
BASE = 'https://192.168.1.100'  # NAC 地址，按实际环境修改

def pull(sessid):
    opener = urllib.request.build_opener()
    opener.addheaders = [
        ('Cookie', 'PHPSESSID=' + sessid),
        ('Referer', BASE + '/index.php/welcome/index'),
        ('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'),
    ]
    # 尝试多个终端列表页面
    candidates = [
        '/index.php/terminal/user_list',
        '/index.php/terminal/online_user',
        '/index.php/terminal/wireless_user',
        '/index.php/welcome/index',
    ]
    for p in candidates:
        try:
            r = opener.open(BASE + p, timeout=20)
            body = r.read().decode('utf-8', 'replace')
            if 'name="password"' in body:
                print('SESSION_EXPIRED')
                return
            # 解析表格行
            rows = []
            for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', body, re.S | re.I):
                cells = [re.sub(r'<[^>]+>', '', c).strip()
                         for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', tr, re.S | re.I)]
                if len(cells) >= 6 and any(':' in c and len(c) >= 14 for c in cells):
                    rows.append(cells)
            if rows:
                print('PAGE:', p)
                print('ROWS:', len(rows))
                for row in rows[:10]:
                    print(' | '.join(c[:24] for c in row))
                return
        except Exception as e:
            print(p, 'ERR', str(e)[:60])
    print('NO_DATA')

if __name__ == '__main__':
    pull(sys.argv[1])
