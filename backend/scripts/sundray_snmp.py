#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
信锐(Sundray) AC SNMP 采集器 —— 纯 socket 实现，零第三方依赖
用法:
  sundray_snmp.py discover                 # 扫描 192.168.1.0/24 找信锐设备
  sundray_snmp.py walk <ip> <community> <oid>   # 遍历 OID 树
  sundray_snmp.py stations <ip> <community>     # 拉取无线终端表
  sundray_snmp.py report <ip> <community> <api_url> <token>  # 全量采集并上报心跳
"""
import socket
import struct
import sys
import time

# ── BER/ASN.1 编解码（SNMP v2c 最小实现）────────────────────────
ASN_INT = 0x02
ASN_OCTSTR = 0x04
ASN_NULL = 0x05
ASN_OID = 0x06
ASN_SEQ = 0x30
ASN_IPADDR = 0x40
ASN_COUNTER = 0x41
ASN_GAUGE = 0x42
ASN_TIMETICKS = 0x43
ASN_OPAQUE = 0x44
ASN_COUNTER64 = 0x46
# PDU
PDU_GET = 0xA0
PDU_GETNEXT = 0xA1
PDU_RESPONSE = 0xA2


def _len(n):
    if n < 0x80:
        return bytes([n])
    out = b''
    while n:
        out = bytes([n & 0xFF]) + out
        n >>= 8
    return bytes([0x80 | len(out)]) + out


def tlv(tag, value):
    return bytes([tag]) + _len(len(value)) + value


def enc_int(v):
    if v == 0:
        return tlv(ASN_INT, b'\x00')
    neg = v < 0
    if neg:
        v = -v - 1
    out = b''
    while v:
        out = bytes([v & 0xFF]) + out
        v >>= 8
    if neg:
        out = bytes([(out[0] ^ 0xFF) | 0x80]) + out[1:] if out else b'\xff'
    elif out[0] & 0x80:
        out = b'\x00' + out
    return tlv(ASN_INT, out)


def enc_oid(oid):
    parts = [int(x) for x in oid.strip('.').split('.')]
    first = parts[0] * 40 + parts[1]
    out = bytes([first])
    for p in parts[2:]:
        if p < 0x80:
            out += bytes([p])
        else:
            sub = b''
            while p:
                sub = bytes([(p & 0x7F) | (0x80 if sub else 0)]) + sub
                p >>= 7
            out += sub
    return tlv(ASN_OID, out)


def enc_str(s):
    return tlv(ASN_OCTSTR, s.encode('utf-8') if isinstance(s, str) else s)


def enc_null():
    return tlv(ASN_NULL, b'')


def _read_len(data, pos):
    b = data[pos]
    pos += 1
    if b & 0x80:
        n = b & 0x7F
        val = int.from_bytes(data[pos:pos + n], 'big')
        return val, pos + n
    return b, pos


def _parse_tlv(data, pos):
    tag = data[pos]
    pos += 1
    length, pos = _read_len(data, pos)
    value = data[pos:pos + length]
    return tag, value, pos + length


def dec_oid(raw):
    first = raw[0]
    a, b = first // 40, first % 40
    out = [str(a), str(b)]
    i = 1
    while i < len(raw):
        v = 0
        while raw[i] & 0x80:
            v = (v << 7) | (raw[i] & 0x7F)
            i += 1
        v = (v << 7) | raw[i]
        i += 1
        out.append(str(v))
    return '.'.join(out)


def dec_value(tag, raw):
    if tag == ASN_INT:
        v = int.from_bytes(raw, 'big', signed=True)
        return v
    if tag == ASN_OID:
        return dec_oid(raw)
    if tag == ASN_TIMETICKS or tag == ASN_COUNTER or tag == ASN_GAUGE:
        return int.from_bytes(raw, 'big')
    if tag == ASN_COUNTER64:
        return int.from_bytes(raw, 'big')
    if tag == ASN_IPADDR:
        return '.'.join(str(x) for x in raw)
    if tag == ASN_OCTSTR:
        try:
            s = raw.decode('utf-8')
            if all(31 < ord(c) < 127 or c in '\r\n\t' for c in s):
                return s
        except UnicodeDecodeError:
            pass
        return raw.hex()
    if tag == ASN_NULL:
        return None
    return raw.hex()


class SnmpClient(object):
    def __init__(self, host, community='public', timeout=2.0, retries=2,
                 min_interval=0.02):
        self.host = host
        self.community = community
        self.timeout = timeout
        self.retries = retries
        self.min_interval = min_interval  # 请求间最小间隔，防触发安全策略
        self._last_req = 0.0
        self.req_id = int(time.time()) & 0x7FFFFFFF
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(timeout)

    def _pdu(self, tag, varbinds):
        self.req_id += 1
        vb_list = b''
        for oid, val_tag, val_enc in varbinds:
            if val_enc is None:
                vb = tlv(ASN_SEQ, enc_oid(oid) + enc_null())
            else:
                vb = tlv(ASN_SEQ, enc_oid(oid) + tlv(val_tag, val_enc))
            vb_list += vb
        pdu = (enc_int(self.req_id) + enc_int(0) + enc_int(0)
               + tlv(ASN_SEQ, vb_list))
        return tlv(tag, pdu)

    def _send_recv(self, pdu):
        # 限速：距上次请求不足 min_interval 时等待，避免高速探测触发安全策略
        now = time.time()
        wait = self.min_interval - (now - self._last_req)
        if wait > 0:
            time.sleep(wait)
        msg = tlv(0x30, tlv(ASN_INT, b'\x01') + enc_str(self.community) + pdu)
        last_err = None
        for _ in range(self.retries + 1):
            try:
                self.sock.sendto(msg, (self.host, 161))
                self._last_req = time.time()
                data, _ = self.sock.recvfrom(65535)
                return data
            except socket.timeout as e:
                last_err = e
        raise IOError('SNMP timeout: %s' % last_err)

    def get(self, oids):
        if isinstance(oids, str):
            oids = [oids]
        vbs = [(o, None, None) for o in oids]
        data = self._send_recv(self._pdu(PDU_GET, vbs))
        return self._parse_vars(data)

    def getnext_raw(self, oid):
        data = self._send_recv(self._pdu(PDU_GETNEXT, [(oid, None, None)]))
        return self._parse_vars(data)

    def walk(self, base_oid, max_rows=2000):
        """遍历子树，返回 [(oid, value)]"""
        out = []
        oid = base_oid
        for _ in range(max_rows):
            try:
                vars_ = self.getnext_raw(oid)
            except IOError:
                break
            if not vars_:
                break
            next_oid, val = vars_[0]
            if not next_oid.startswith(base_oid):
                break
            out.append((next_oid, val))
            oid = next_oid
        return out

    def _parse_vars(self, data):
        # 外层 SEQUENCE
        tag, body, _ = _parse_tlv(data, 0)
        pos = 0
        # version
        t, v, pos = _parse_tlv(body, pos)
        # community
        t, v, pos = _parse_tlv(body, pos)
        # PDU
        t, pdu, pos = _parse_tlv(body, pos)
        # PDU 内部: request-id, error-status, error-index, varbind list
        p = 0
        t, reqid, p = _parse_tlv(pdu, p)
        t, errstat, p = _parse_tlv(pdu, p)
        err = int.from_bytes(errstat, 'big', signed=True)
        if err != 0:
            raise IOError('SNMP error-status=%d' % err)
        t, erridx, p = _parse_tlv(pdu, p)
        t, vbl, p = _parse_tlv(pdu, p)
        out = []
        vp = 0
        while vp < len(vbl):
            tag_vb, vb, vp = _parse_tlv(vbl, vp)
            # vb = SEQUENCE(oid, value)
            t2, oid_raw, p2 = _parse_tlv(vb, 0)
            oid = dec_oid(oid_raw)
            t3, val_raw, p3 = _parse_tlv(vb, p2)
            out.append((oid, dec_value(t3, val_raw)))
        return out


def norm_mac(mac_str):
    """把各种 MAC 格式归一为 aa:bb:cc:dd:ee:ff"""
    import re
    s = re.sub(r'[^0-9a-fA-F]', '', str(mac_str)).lower()
    if len(s) != 12:
        return None
    return ':'.join(s[i:i + 2] for i in range(0, 12, 2))


# ── 信锐无线终端表探测 ──────────────────────────────────────────
# 信锐企业号: 可能挂在 1.3.6.1.4.1.12269 (Sundray/信锐) 下
# 备选探测列表：标准无线 MIB + 信锐私有 MIB 常见路径
SUNDRAY_ENTERPRISE = '1.3.6.1.4.1.12269'
# 标准 MIB-II
OID_SYSDESCR = '1.3.6.1.2.1.1.1.0'
OID_SYSNAME = '1.3.6.1.2.1.1.5.0'
# 信锐可能的无线终端表根（walk 后人工确认）
CANDIDATE_STATION_ROOTS = [
    '1.3.6.1.4.1.12269',         # sundray enterprise 全树探测入口
]




# ── 信锐 WAC AP 表采集（已实机验证：45577.2.12.1.6.<row>.<col>.<idx>）──
OID_WAC_ROOT = '1.3.6.1.4.1.45577.2.12.1.6'
ROW = '1'                      # 行索引固定为 1
COL_NAME = 2                   # 6.<row>.<col>.<idx> = 6.1.2.<idx> = AP 名称
COL_MAC = 3                    # 6.1.3.<idx> = AP MAC


def fetch_wac_aps(ip, community='public'):
    """采集信锐 WAC 的 AP 清单：[{name, mac}]。任何一台失败抛 IOError。"""
    c = SnmpClient(ip, community, timeout=2.0, retries=2)
    # 名称列: 6.1.2.x
    names = {}
    base_name = '%s.%s.%d.' % (OID_WAC_ROOT, ROW, COL_NAME)
    oid = base_name.rstrip('.')
    for _ in range(5000):
        vars_ = c.getnext_raw(oid)
        if not vars_:
            break
        no, val = vars_[0]
        if not no.startswith(base_name):
            break
        idx = no[len(base_name):]
        if isinstance(val, str) and val and all(ch in '0123456789abcdef' for ch in val.lower()) and len(val) % 2 == 0:
            try:
                val = bytes.fromhex(val).decode('utf-8')
            except Exception:
                pass
        names[idx] = str(val).strip()
        oid = no
    # MAC 列: 6.1.3.x
    macs = {}
    base_mac = '%s.%s.%d.' % (OID_WAC_ROOT, ROW, COL_MAC)
    oid = base_mac.rstrip('.')
    for _ in range(5000):
        vars_ = c.getnext_raw(oid)
        if not vars_:
            break
        no, val = vars_[0]
        if not no.startswith(base_mac):
            break
        idx = no[len(base_mac):]
        macs[idx] = norm_mac(val) or str(val)
        oid = no
    # 扩展列: IP(5) 型号(7) SN(8) 固件(10) CPU(11) 内存(12) 在线时长(15) 组(18) 接入人数(19) 流量(20,21)
    extra_cols = {5: 'ip', 7: 'model', 8: 'sn', 10: 'firmware', 11: 'cpu', 12: 'mem',
                  15: 'uptime', 18: 'group', 19: 'sta_count', 20: 'tx', 21: 'rx'}
    extra = {}   # idx -> {key: val}
    for col, key in extra_cols.items():
        base_c = '%s.%s.%d.' % (OID_WAC_ROOT, ROW, col)
        oid = base_c.rstrip('.')
        for _ in range(5000):
            vars_ = c.getnext_raw(oid)
            if not vars_:
                break
            no, val = vars_[0]
            if not no.startswith(base_c):
                break
            idx = no[len(base_c):]
            v = str(val).strip()
            if isinstance(val, str) and val and all(ch in '0123456789abcdef' for ch in val.lower()) and len(val) % 2 == 0 and len(val) > 8:
                try:
                    dec = bytes.fromhex(val).decode('utf-8')
                    if all(ord(ch) >= 32 or ch in '\t\n' for ch in dec):
                        v = dec
                except Exception:
                    pass
            extra.setdefault(idx, {})[key] = v
            oid = no
    # 在线 AP MAC 表: 7.1.3.x（在线 AP 的 MAC 列表）
    online_macs = set()
    base_on = '1.3.6.1.4.1.45577.2.12.1.7.1.3.'
    oid = base_on.rstrip('.')
    for _ in range(5000):
        vars_ = c.getnext_raw(oid)
        if not vars_:
            break
        no, val = vars_[0]
        if not no.startswith(base_on):
            break
        mac = norm_mac(val)
        if mac:
            online_macs.add(mac)
        oid = no
    aps = []
    for idx, name in names.items():
        mac = macs.get(idx, '')
        ex = extra.get(idx, {})
        aps.append({'index': idx, 'name': name, 'mac': mac,
                    'online': mac in online_macs if mac else False,
                    'ip': ex.get('ip', ''), 'model': ex.get('model', ''),
                    'sn': ex.get('sn', ''), 'firmware': ex.get('firmware', ''),
                    'cpu': ex.get('cpu', ''), 'mem': ex.get('mem', ''),
                    'uptime': ex.get('uptime', ''), 'group': ex.get('group', ''),
                    'sta_count': ex.get('sta_count', ''), 'tx': ex.get('tx', ''),
                    'rx': ex.get('rx', '')})
    return aps, len(online_macs)


def discover(net_prefix='192.168.1', community='public', start=1, end=254):
    """扫描网段找信锐设备（sysDescr 含 Sundray/信锐）"""
    found = []
    for i in range(start, end + 1):
        ip = '%s.%d' % (net_prefix, i)
        try:
            c = SnmpClient(ip, community, timeout=0.6, retries=0)
            vars_ = c.get([OID_SYSDESCR, OID_SYSNAME])
            descr = str(vars_[0][1])
            name = str(vars_[1][1])
            low = descr.lower()
            if 'sundray' in low or '信锐' in descr or 'sundray' in name.lower():
                found.append((ip, name, descr[:80]))
                print('[FOUND] %s  %s  %s' % (ip, name, descr[:80]))
        except Exception:
            pass
    print('扫描完成，发现 %d 台信锐设备' % len(found))
    return found


def cmd_stations(ip, community):
    """探测无线终端表：walk 企业根，打印有数据的分支"""
    c = SnmpClient(ip, community)
    print('sysDescr:', c.get([OID_SYSDESCR])[0][1])
    print('sysName:', c.get([OID_SYSNAME])[0][1])
    print()
    print('=== walk enterprise 根（前 60 条）===')
    rows = c.walk(SUNDRAY_ENTERPRISE, max_rows=60)
    for oid, val in rows:
        print(oid, '=', repr(val)[:80])
    if not rows:
        print('（企业根无数据，尝试标准无线 MIB dot11）')
        rows = c.walk('1.3.6.1.2.1.17', max_rows=20)
        for oid, val in rows:
            print(oid, '=', repr(val)[:80])


def cmd_report(ip, community, api_url, token):
    """全量采集终端并上报心跳（给 crontab 用）"""
    # 由 cmd_stations 确认表结构后补全解析逻辑
    raise NotImplementedError('表结构确认后实现')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == 'discover':
        discover(sys.argv[2] if len(sys.argv) > 2 else '192.168.1',
                 sys.argv[3] if len(sys.argv) > 3 else 'public')
    elif cmd == 'walk':
        c = SnmpClient(sys.argv[2], sys.argv[3])
        for oid, val in c.walk(sys.argv[4], max_rows=200):
            print(oid, '=', repr(val)[:100])
    elif cmd == 'get':
        c = SnmpClient(sys.argv[2], sys.argv[3])
        for oid, val in c.get(sys.argv[4:]):
            print(oid, '=', repr(val))
    elif cmd == 'stations':
        cmd_stations(sys.argv[2], sys.argv[3])
    else:
        print('unknown cmd:', cmd)
        sys.exit(1)
