"""P1-4 批量导入测试：模板下载 → 构造数据 → dry_run校验 → 正式导入"""
import urllib.request
import json
import io
import uuid
import time

from openpyxl import Workbook, load_workbook

BASE = "http://127.0.0.1:8089/api"


def login():
    req = urllib.request.Request(f"{BASE}/auth/login/", method="POST")
    req.add_header("Content-Type", "application/json")
    resp = urllib.request.urlopen(
        req, json.dumps({"username": "admin", "password": "admin123"}).encode())
    return json.loads(resp.read())["access"]


def multipart_upload(tok, buf):
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="t.xlsx"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + buf.read() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(f"{BASE}/assets/batch_import/", data=body, method="POST")
    req.add_header("Authorization", f"Bearer {tok}")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    try:
        return json.loads(urllib.request.urlopen(req).read())
    except urllib.error.HTTPError as e:
        print("   upload error:", e.code, e.read().decode()[:300])
        raise


tok = login()

# 1. 模板下载
req = urllib.request.Request(f"{BASE}/assets/import_template")
req.add_header("Authorization", f"Bearer {tok}")
data = urllib.request.urlopen(req).read()
print("1.template xlsx:", len(data), "bytes")

# 2. 构造导入数据：2行合法 + 1行错误（未来日期）
wb = load_workbook(io.BytesIO(data))
ws = wb.active
ws.append(["CN-IMP-001", "SCN", "Zebra", "DS2208", "总装车间", "生产部", "2022-03-10", 2800, 8, 0.05])
ws.append(["CN-IMP-002", "SCN", "Honeywell", "1900GSR", "包装车间", "生产部", "2023-11-20", 3200, None, None])
ws.append(["CN-IMP-003", "SCN", "BadRow", "X", "仓库", "生产部", "2030-01-01", 100, None, None])
buf = io.BytesIO()
wb.save(buf)
buf.seek(0)

# 3. dry_run 校验
buf.seek(0)
resp = multipart_upload(tok, buf)
print("2.dry_run: total", resp["total"], "| valid", resp["valid"], "| errors", len(resp["errors"]))
for e in resp["errors"]:
    print("   错误行", e["row"], "->", e["errors"])

# 4. 修正错误后正式导入
buf.seek(0)
wb2 = load_workbook(buf)
ws2 = wb2.active
ws2.cell(4, 8, None)  # 保留错误行演示跳过逻辑？不——正式导入要求全对，改掉错误日期
ws2.cell(4, 7, "2023-01-05")
out = io.BytesIO()
wb2.save(out)
out.seek(0)
resp = multipart_upload(tok, out)
print("3.import:", json.dumps(resp, ensure_ascii=False))

# 5. 验证导入的资产
req = urllib.request.Request(f"{BASE}/assets/?kw=CN-IMP")
req.add_header("Authorization", f"Bearer {tok}")
assets = json.loads(urllib.request.urlopen(req).read())
print("4.query:", assets["count"], "条导入资产")
for a in assets["results"]:
    print(f"   {a['asset_tag']} {a['brand']} {a['model_spec']} 原值{a['original_value']} 净值{a['current_value']}")

print("\n=== P1-4 批量导入测试完成 ===")
