"""P1 冒烟测试：登录→类别(自定义字段)→资产→经济分析→维修后分析"""
import urllib.request, urllib.error, json

BASE = "http://127.0.0.1:8089/api"

def req(path, method="GET", data=None, token=None):
    r = urllib.request.Request(f"{BASE}{path}", method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    body = json.dumps(data).encode() if data else None
    try:
        resp = urllib.request.urlopen(r, body, timeout=10)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")

# 1. 登录
code, r = req("/auth/login/", "POST", {"username": "admin", "password": "admin123"})
print("1.login:", code)
tok = r["access"]

# 2. 类别（自定义字段 schema）
code, r = req("/categories/", "POST", {
    "name": "扫描枪", "code": "SCN", "default_life": 8, "default_salvage_rate": 0.05,
    "field_schema": [
        {"key": "scan_engine", "label": "扫描引擎", "type": "text", "required": False},
        {"key": "read_rate", "label": "识读率", "type": "number", "required": False}
    ]
}, tok)
print("2.category:", code, r.get("name"), "schema字段数:", len(r.get("field_schema", [])))
cat_id = r["id"]

# 3. 部门 + 位置
code, d = req("/departments/", "POST", {"name": "生产部", "code": "PROD"}, tok)
code, l = req("/locations/", "POST", {"name": "总装车间"}, tok)
print("3.dept/loc:", code, d.get("name"), l.get("name"))

# 4. 资产（财务字段+自定义字段）
code, a = req("/assets/", "POST", {
    "sn": "CN-TEST-001", "category": cat_id, "brand": "Honeywell", "model_spec": "Xenon 1900",
    "location": l["id"], "department": d["id"], "status": "in_use",
    "purchase_date": "2021-06-15", "original_value": 3000,
    "custom": {"scan_engine": "Imager 2D", "read_rate": 98}
}, tok)
print("4.asset:", code, a.get("asset_tag"), "| 净值:", a.get("current_value"), "| 已用年:", a.get("used_years"))
aid = a["id"]

# 5. 经济分析（无维修记录 → green）
code, e = req(f"/assets/{aid}/economy", token=tok)
print("5.economy:", "健康度:", e.get("health_level"), "| 年折旧:", e.get("annual_depreciation"), "| 净值:", e.get("current_value"))

# 6. 补两笔维修（第3年450 第4年980）→ 应触发 R2/R4/R3
req("/repairs/", "POST", {"asset": aid, "report_date": "2024-07-01", "fault_desc": "扫描引擎故障",
                          "parts_replaced": [{"name": "扫描引擎", "cost": 400}], "labor_cost": 50,
                          "status": "done", "finish_date": "2024-07-03"}, tok)
req("/repairs/", "POST", {"asset": aid, "report_date": "2025-09-01", "fault_desc": "主板损坏",
                          "parts_replaced": [{"name": "主板", "cost": 900}], "labor_cost": 80,
                          "status": "done", "finish_date": "2025-09-05"}, tok)
code, e = req(f"/assets/{aid}/economy", token=tok)
print("6.after-repairs: 累计维修:", e.get("repair_total"), "| λ:", e.get("lambda"),
      "| 经济寿命:", e.get("econ_life"), "| 健康度:", e.get("health_level"))
print("   命中规则:", [(h["rule"], h["level"]) for h in e.get("rules_hit", [])])
print("   建议:", e.get("suggestion"))

# 7. 模板下载 & dry_run 校验
code, hdr = req("/assets/import_template", token=tok)
print("7.template:", "(二进制响应，HTTP", code, ")")
print("\n=== P1 后端冒烟测试完成 ===")
