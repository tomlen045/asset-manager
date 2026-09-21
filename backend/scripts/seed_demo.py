# -*- coding: utf-8 -*-
"""
演示数据种子脚本 —— 生成一套通用制造业场景的仿真数据（无任何真实数据）。

用法:
  cd backend
  python manage.py shell < scripts/seed_demo.py
  # 或
  python scripts/seed_demo.py          (需先配置 DJANGO_SETTINGS_MODULE)

幂等：重复执行会先清空业务数据再重建。所有序列号/MAC 均为合成数据。
"""
import os
import sys
import random
from datetime import date, timedelta, datetime

import django
from django.utils import timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from assets.models import (Department, Location, AssetCategory, Asset,
                           RepairOrder, LifecycleLog, PdaDevice)
from assets.flows import AssetFlow, Stocktake, StocktakeItem
from assets.orgtree import DeptNode

random.seed(42)  # 固定随机种子，每次生成的数据一致

U = get_user_model()

# ── 清空旧数据（演示库专用）──
for M in [StocktakeItem, Stocktake, AssetFlow, LifecycleLog, RepairOrder,
          PdaDevice, Asset, Location, DeptNode, AssetCategory, Department]:
    M.objects.all().delete()
U.objects.filter(username__startswith='demo_').delete()

# ── 用户（admin 优先创建，供盘点等 created_by 使用）──
admin, created = U.objects.get_or_create(
    username='admin', defaults={'is_staff': True, 'is_superuser': True,
                                'email': 'admin@local'})
if created:
    admin.set_password('admin123'); admin.save()
users = {'admin': admin}
for uname, emp in [('demo_zhang', 'A1001'), ('demo_li', 'A1002'),
                   ('demo_wang', 'A1003'), ('demo_chen', 'A1004')]:
    users[uname], _ = U.objects.get_or_create(
        username=uname, defaults={'employee_id': emp, 'is_staff': False})

# ── 部门 ──
dept_names = ['生产部', '设备部', '品质部', '仓储物流部', '信息技术部', '财务部', '行政部']
depts = {d: Department.objects.create(name=d, code=f'D{i+1:02d}')
         for i, d in enumerate(dept_names)}

# ── 位置（树形：厂区 → 车间/库房）──
loc_plant = Location.objects.create(name='一号厂区')
loc_ware = Location.objects.create(name='中心仓库', parent=loc_plant, department=depts['仓储物流部'])
loc_it = Location.objects.create(name='信息机房', parent=loc_plant, department=depts['信息技术部'])
locations = []
for wname in ['总装车间', '焊装车间', '涂装车间', '冲压车间', '包装车间']:
    locations.append(Location.objects.create(name=wname, parent=loc_plant, department=depts['生产部']))
for i in range(1, 4):
    locations.append(Location.objects.create(name=f'成品库{i}号', parent=loc_ware))
locations.append(Location.objects.create(name='工位暂存区', parent=loc_ware))

# ── 类别（含自定义字段 schema 演示）──
cat_defs = [
    ('手持终端', 'PDA', 6, 0.05, [
        {'key': 'scan_engine', 'label': '扫描引擎', 'type': 'text', 'required': False},
        {'key': 'battery_cycles', 'label': '电池循环次数', 'type': 'number', 'required': False}]),
    ('无线扫描枪', 'SCN', 8, 0.05, [
        {'key': 'read_rate', 'label': '识读率(%)', 'type': 'number', 'required': False}]),
    ('工业打印机', 'PRT', 10, 0.05, [
        {'key': 'print_life', 'label': '打印寿命(万张)', 'type': 'number', 'required': False}]),
    ('台式电脑', 'PC', 6, 0.03, []),
    ('笔记本电脑', 'NB', 5, 0.03, []),
    ('显示器', 'MON', 8, 0.02, []),
    ('网络交换机', 'NET', 10, 0.05, []),
]
cats = {}
for name, code, life, sal, schema in cat_defs:
    cats[code] = AssetCategory.objects.create(
        name=name, code=code, default_life=life, default_salvage_rate=sal,
        field_schema=schema)

# ── 资产台账（约 420 台，品牌型号为市面通用型号）──
BRAND_MODELS = {
    'PDA': [('Zebra', 'TC22'), ('Honeywell', 'CT60'), ('优博讯', 'i6310')],
    'SCN': [('Zebra', 'DS2208'), ('Honeywell', '1900GSR'), ('新大陆', 'HR32')],
    'PRT': [('Zebra', 'ZT411'), ('TSC', 'TTP-244 Pro'), ('博思得', 'G6000')],
    'PC': [('联想', 'ThinkCentre M740'), ('戴尔', 'OptiPlex 7090'), ('惠普', 'ProDesk 480')],
    'NB': [('联想', 'ThinkPad E14'), ('戴尔', 'Latitude 5420'), ('惠普', 'EliteBook 840')],
    'MON': [('戴尔', 'P2422H'), ('AOC', '24B2XH'), ('联想', 'L24i-30')],
    'NET': [('华为', 'S5735S'), ('H3C', 'S5130S'), ('锐捷', 'RG-NBS3100')],
}
AREAS = ['A区', 'B区', 'C区', 'D区']

asset_pool = []
tag_seq = {}
for code, n_per in [('PDA', 40), ('SCN', 60), ('PRT', 25), ('PC', 120),
                    ('NB', 60), ('MON', 90), ('NET', 25)]:
    cat = cats[code]
    for i in range(n_per):
        brand, model = random.choice(BRAND_MODELS[code])
        tag_seq[code] = tag_seq.get(code, 0) + 1
        tag = f'ZC-{code}-2026-{tag_seq[code]:04d}'
        age_years = round(random.uniform(0.3, cat.default_life + 1.5), 1)
        pdate = date.today() - timedelta(days=int(age_years * 365.25))
        lo, hi = {'PDA': (3500, 7000), 'SCN': (1200, 2800), 'PRT': (5000, 15000),
                  'PC': (3500, 6500), 'NB': (5000, 11000), 'MON': (700, 1600),
                  'NET': (4000, 12000)}[code]
        value = round(random.uniform(lo, hi), 2)
        r = random.random()
        if age_years > cat.default_life * 0.9 and r < 0.25:
            status = 'scrapped' if r < 0.12 else 'idle'
        elif r < 0.10:
            status = 'in_stock'
        elif r < 0.16:
            status = 'repairing'
        else:
            status = 'in_use'
        custom = {}
        if code == 'PDA':
            custom = {'scan_engine': random.choice(['SE4710', 'N6603', 'HD4000']),
                      'battery_cycles': random.randint(150, 900)}
        elif code == 'SCN':
            custom = {'read_rate': random.randint(92, 100)}
        elif code == 'PRT':
            custom = {'print_life': random.randint(20, 480)}
        a = Asset.objects.create(
            asset_tag=tag, sn=f'SN-DEMO-{code}-{i+1:05d}',
            category=cat, brand=brand, model_spec=model,
            asset_name=f'{cat.name}-{model}',
            location=random.choice(locations) if status in ('in_use', 'repairing') else (
                loc_ware if status == 'in_stock' else random.choice(locations)),
            department=random.choice(list(depts.values())),
            custodian=random.choice(list(users.values())) if status == 'in_use' else None,
            status=status, purchase_date=pdate,
            original_value=value,
            useful_life=cat.default_life, salvage_rate=cat.default_salvage_rate,
            custom=custom)
        LifecycleLog.objects.create(asset=a, action='create',
                                    detail={'source': 'demo-seed'}, operator=None)
        asset_pool.append(a)

# ── 维修工单（喂饱经济寿命引擎：老设备维修费递增）──
repairable = [a for a in asset_pool if a.used_years > 1.5]
for a in random.sample(repairable, min(90, len(repairable))):
    n = random.randint(1, 4)
    for k in range(n):
        rdate = date.today() - timedelta(days=random.randint(30, int(a.used_years * 340)))
        sev = random.choice([80, 150, 300, 600, 1200, 2400])
        RepairOrder.objects.create(
            asset=a, report_date=rdate,
            finish_date=rdate + timedelta(days=random.randint(1, 12)),
            fault_desc=random.choice(['扫描头不识读', '电源模块损坏', '打印头断针', '无法开机',
                                      '屏幕碎裂', '电池鼓包', '键盘失灵', '网口故障', '风扇异响']),
            parts_replaced=[{'name': random.choice(['扫描引擎', '电源板', '打印头', '电池', '主板', '显示屏']),
                             'cost': round(sev * random.uniform(0.5, 1.1), 2)}],
            labor_cost=round(random.uniform(80, 400), 2),
            vendor=random.choice(['本地服务商A', '厂家授权维修中心', '第三方维修B']),
            status='done')
    # 老设备追加高维修成本 → 经济寿命曲线出现交点
    if a.used_years > a.eff_life * 0.75 and random.random() < 0.5:
        rd = date.today() - timedelta(days=random.randint(10, 90))
        RepairOrder.objects.create(
            asset=a, report_date=rd, finish_date=rd + timedelta(days=5),
            fault_desc='多次维修后再次故障',
            parts_replaced=[{'name': '核心部件', 'cost': round(random.uniform(1500, 4200), 2)}],
            labor_cost=350, vendor='厂家授权维修中心', status='done')

# ── 资产流程（领用/调拨/归还，含待审批）──
flow_no = 0
for _ in range(24):
    flow_no += 1
    ft = random.choice(['assign', 'transfer', 'return'])
    a = random.choice([x for x in asset_pool if x.status == 'in_use'])
    AssetFlow.objects.create(
        flow_no=f'FL2026{flow_no:05d}', flow_type=ft, asset=a,
        to_user=random.choice(list(users.values())),
        to_department=random.choice(list(depts.values())),
        to_location=random.choice(locations),
        reason=random.choice(['新员工入职配置', '车间产能扩充', '设备老化更换', '项目临时借用']),
        status=random.choice(['pending', 'approved', 'approved', 'rejected']),
        applicant=random.choice(list(users.values())),
        approver=random.choice(list(users.values())) if random.random() < 0.6 else None,
        created_at=timezone.now() - timedelta(days=random.randint(1, 60)))

# ── 盘点任务（一个已完成 92%，一个进行中）──
st1 = Stocktake.objects.create(
    name='2026年Q2车间扫描枪盘点', category=cats['SCN'],
    department=depts['生产部'], status='finished',
    created_by=admin,
    finished_at=timezone.now() - timedelta(days=20))
scn_assets = [a for a in asset_pool
              if a.category.code == 'SCN' and a.department_id == depts['生产部'].id
              and a.status != 'scrapped']
for a in scn_assets:
    found = random.random() < 0.92
    StocktakeItem.objects.create(
        stocktake=st1, asset=a, found=found,
        found_at=timezone.now() - timedelta(days=random.randint(21, 30)) if found else None,
        note='' if found else '未找到，已挂账外')
st2 = Stocktake.objects.create(
    name='2026年Q3手持终端盘点', category=cats['PDA'],
    department=depts['生产部'], status='ongoing',
    created_by=admin)
# 盘点明细必须与任务口径一致（类别+部门，排除报废），否则进度会超过100%
st2_scope = [x for x in asset_pool
             if x.category.code == 'PDA' and x.department_id == depts['生产部'].id
             and x.status != 'scrapped']
for a in st2_scope:
    found = random.random() < 0.45
    StocktakeItem.objects.create(stocktake=st2, asset=a, found=found)

# ── PDA 设备与心跳（合成 MAC，坐标为演示平面图打点）──
pda_assets = [a for a in asset_pool if a.category.code == 'PDA' and a.status == 'in_use']
for i, a in enumerate(pda_assets[:24]):
    online = random.random() < 0.75
    PdaDevice.objects.create(
        mac=f'AA:BB:CC:{random.randint(16,255):02X}:{random.randint(16,255):02X}:{i+1:02X}',
        device_type='pda', name=f'车间PDA-{i+1:02d}', device_no=f'PDA-{i+1:03d}',
        device_model=a.model_spec, android_ver=random.choice(['9', '11', '13']),
        department=random.choice(list(depts.values())),
        owner=random.choice(['甲班', '乙班', '丙班']),
        asset=a,
        ap_name=f'AP-{random.choice(AREAS)}-{random.randint(1, 12):02d}',
        zone=random.choice(['总装车间', '焊装车间', '涂装车间', '包装车间', '成品库']),
        rssi=random.randint(-70, -40) if online else None,
        ssid='Plant-WiFi', battery=random.randint(15, 100) if online else None,
        ip=f'10.66.{random.randint(1, 8)}.{random.randint(10, 250)}' if online else None,
        last_seen=timezone.now() - timedelta(minutes=random.randint(0, 5)) if online
                  else timezone.now() - timedelta(days=random.randint(2, 30)),
        pos_x=round(random.uniform(8, 92), 1), pos_y=round(random.uniform(8, 92), 1))

print('=== DEMO DATA SEEDED ===')
print(f"departments={Department.objects.count()} locations={Location.objects.count()} "
      f"categories={AssetCategory.objects.count()} assets={Asset.objects.count()} "
      f"repairs={RepairOrder.objects.count()} flows={AssetFlow.objects.count()} "
      f"stocktakes={Stocktake.objects.count()} pda={PdaDevice.objects.count()}")
