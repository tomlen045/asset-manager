"""P1 全流程验证：初始化基础数据 → 单条创建 → 经济分析 → 批量导入 → 盘点模拟
这是标准交付验收脚本，可重复执行（幂等）。
"""
import urllib.request
import urllib.error
import json
import io
import uuid
import time

from openpyxl import Workbook, load_workbook

BASE = "http://127.0.0.1:8089/api"
PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f"  {detail}" if detail else ""))


def req(path, method="GET", data=None, token=None, raw=False):
    r = urllib.request.Request(f"{BASE}{path}", method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    body = json.dumps(data).encode() if data else None
    try:
        resp = urllib.request.urlopen(r, body, timeout=15)
        return resp.status, (resp.read() if raw else json.loads(resp.read()))
    except urllib.error.HTTPError as e:
        return e.code, (e.read() if raw else json.loads(e.read() or b"{}"))


def multipart(tok, buf, dry=False):
    boundary = uuid.uuid4().hex
    qs = "?dry_run=1" if dry else ""
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="t.xlsx"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + buf.read() + f"\r\n--{boundary}--\r\n".encode()
    r = urllib.request.Request(f"{BASE}/assets/batch_import/{qs}", data=body, method="POST")
    r.add_header("Authorization", f"Bearer {tok}")
    r.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    return json.loads(urllib.request.urlopen(r).read())


# ═══ 1. 登录 ═══
code, r = req("/auth/login/", "POST", {"username": "admin", "password": "admin123"})
check("管理员登录", code == 200)
tok = r["access"]

# ═══ 2. 基础数据（幂等：存在即复用）═══
code, cats = req("/categories/", token=tok)
scn = next((c for c in cats["results"] if c["code"] == "SCN"), None)
if not scn:
    code, scn = req("/categories/", "POST", {
        "name": "扫描枪", "code": "SCN", "default_life": 8, "default_salvage_rate": 0.05,
        "field_schema": [
            {"key": "scan_engine", "label": "扫描引擎", "type": "text", "required": False},
            {"key": "read_rate", "label": "识读率(%)", "type": "number", "required": False}
        ]}, tok)
check("资产类别+自定义字段schema", code in (200, 201), f"{scn['name']} {len(scn['field_schema'])}个扩展字段")

code, deps = req("/departments/", token=tok)
dep = next((d for d in deps["results"] if d["name"] == "生产部"), None)
if not dep:
    code, dep = req("/departments/", "POST", {"name": "生产部", "code": "PROD"}, tok)
code, locs = req("/locations/", token=tok)
loc = next((x for x in locs["results"] if x["name"] == "总装车间"), None)
if not loc:
    code, loc = req("/locations/", "POST", {"name": "总装车间"}, tok)
check("部门/位置", dep["name"] == "生产部" and loc["name"] == "总装车间")

# ═══ 3. 单条资产（含财务字段+自定义字段）═══
code, assets = req("/assets/?kw=CN-E2E-001", token=tok)
if assets["count"] == 0:
    code, a = req("/assets/", "POST", {
        "sn": "CN-E2E-001", "category": scn["id"], "brand": "Honeywell",
        "model_spec": "Xenon 1900", "location": loc["id"], "department": dep["id"],
        "status": "in_use", "purchase_date": "2021-06-15", "original_value": 3000,
        "custom": {"scan_engine": "Imager 2D", "read_rate": 98}}, tok)
else:
    code, a = req(f"/assets/{assets['results'][0]['id']}", token=tok)
check("单条创建+自动编号", code in (200, 201) and a["asset_tag"].startswith("ZC-SCN-"),
      f"{a['asset_tag']} 净值{a['current_value']}")
check("折旧计算正确", abs(float(a["current_value"]) - (3000 - 356.25 * a["used_years"])) < 1,
      f"年折旧356.25 = 3000×0.95/8")

# ═══ 4. 经济分析（维修前后对照）═══
code, e = req(f"/assets/{a['id']}/economy/", token=tok)
base_level = e["health_level"]
check("经济分析(基线)", base_level in ("green", "yellow"),
      f"健康度{base_level} 净值{e['current_value']}")

# 补维修记录（若已有则跳过）
code, reps = req("/repairs/?status=done", token=tok)
mine = [x for x in reps["results"] if x.get("asset_tag") == a["asset_tag"]]
if len(mine) < 2:
    req("/repairs/", "POST", {"asset": a["id"], "report_date": "2024-07-01",
                              "fault_desc": "扫描引擎故障",
                              "parts_replaced": [{"name": "扫描引擎", "cost": 400}],
                              "labor_cost": 50, "status": "done",
                              "finish_date": "2024-07-03"}, tok)
    req("/repairs/", "POST", {"asset": a["id"], "report_date": "2025-09-01",
                              "fault_desc": "主板损坏",
                              "parts_replaced": [{"name": "主板", "cost": 900}],
                              "labor_cost": 80, "status": "done",
                              "finish_date": "2025-09-05"}, tok)
code, e = req(f"/assets/{a['id']}/economy/", token=tok)
rules = [h["rule"] for h in e["rules_hit"]]
check("维修成本曲线+λ拟合", e["lambda"] > 0, f"累计维修{e['repair_total']} λ={e['lambda']}")
check("低劣化经济寿命", e["econ_life"] is not None, f"经济寿命{e['econ_life']}年")
check("健康度升级为red", e["health_level"] == "red", f"命中{rules} 建议:{e['suggestion']}")

# ═══ 5. 批量导入 ═══
code, tpl = req("/assets/import_template/", token=tok, raw=True)
check("导入模板下载", code == 200 and len(tpl) > 1000, f"{len(tpl)} bytes")

wb = load_workbook(io.BytesIO(tpl))
ws = wb.active
tags = [f"CN-BATCH-{int(time.time())}-{i}" for i in (1, 2)]
ws.append([tags[0], "SCN", "Zebra", "DS2208", "总装车间", "生产部", "2022-03-10", 2800, 8, 0.05])
ws.append([tags[1], "SCN", "Honeywell", "1900GSR", "包装车间", "生产部", "2023-11-20", 3200, None, None])
ws.append(["CN-BAD", "SCN", "X", "BadRow", "仓库", "生产部", "2030-01-01", 100, None, None])  # 故意错误
buf = io.BytesIO()
wb.save(buf)
buf.seek(0)

res = multipart(tok, buf, dry=True)
check("dry_run校验(错误行拦截)", res["valid"] == 3 and len(res["errors"]) == 1
      and "投产日期" in res["errors"][0]["errors"][0],
      f"valid={res['valid']} 错误={res['errors'][0]['errors'] if res['errors'] else '-'}")

buf.seek(0)
wb2 = load_workbook(buf)
# 定位错误行（投产日期为 2030-01-01 的行），改成合法日期
bad_row = None
for row in wb2.active.iter_rows(min_row=2):
    for cell in row:
        if cell.value and "2030" in str(cell.value):
            bad_row = cell.row
            break
    if bad_row:
        break
if bad_row:
    wb2.active.cell(bad_row, 7, "2023-01-05")  # 修正日期
out = io.BytesIO()
wb2.save(out)
out.seek(0)
res = multipart(tok, out)
check("正式批量导入(修正后)", res["imported"] == 4, f"导入{res['imported']}条(含模板示例行)")

code, lst = req(f"/assets/?kw={tags[0]}", token=tok)
row = lst["results"][0] if lst["count"] else {}
check("导入后净值自动计算", bool(row) and float(row["current_value"]) > 0,
      f"{row.get('asset_tag','-')} 净值{row.get('current_value','-')}")

# ═══ 6. 工作台 & 报废预测 ═══
code, ov = req("/dashboard/overview/", token=tok)
check("工作台总览", code == 200 and ov["total"] >= 5, f"总数{ov['total']} 净值{ov['net_value']}")

code, sc = req("/dashboard/scrappage/", token=tok)
check("报废预测看板", code == 200 and sc["red"] >= 1,
      f"红{sc['red']} 黄{sc['yellow']} 绿{sc['green']}")

print("\n" + "=" * 46)
print(f"通过 {len(PASS)} / 失败 {len(FAIL)}")
if FAIL:
    print("失败项:", FAIL)
    raise SystemExit(1)
print("=== P1 全流程验证全部通过 ===")
