# IT 固定资产管理系统 — 详细设计文档

> 版本 v1.0 | 2026-08-31 | 全自研 Django + Vue3 方案
> 状态：P0 设计定稿 → P1 开发基线

---

## 1. 系统定位

制造业企业内网 IT 固定资产全生命周期管理平台，覆盖：

- **资产范围**：台式/笔记本终端、手持平板、扫描枪、打印头、一体机、显示器等
- **生命周期**：规划 → 采购 → 入库 → 领用 → 调拨 → 维修 → 盘点 → 折旧 → 报废
- **差异化能力（核心）**：AI 经济寿命分析——基于维修成本曲线与折旧残值曲线，
  判断"设备提前报废是否比继续维修更划算"，输出红黄绿健康度与报废建议

## 2. 技术选型

| 层 | 选型 | 理由 |
|----|------|------|
| 后端 | Django 4.2 LTS + DRF | 稳定 LTS、ORM 强、内网部署无外部依赖 |
| 数据库 | SQLite(WAL) 起步 / PostgreSQL 可平移 | 遵循"每模块独立 DB"铁律；asset_db 独立 |
| 前端 | Vue 3 + Element Plus + ECharts | 与现有大屏技术栈一致，暗色主题 |
| AI | Ollama + qwen2.5:7b（可选） | 内网离线；规则引擎不依赖 AI |
| 部署 | Docker Compose（独立 bridge 子网） | 避免与办公网段冲突 |
| 端口 | Nginx 8089（对外） | 避开 8080/8086/8088 |
| 扫码 | USB HID 扫描枪（键盘模拟）+ 手机 H5 | 内网零依赖 |

## 3. 数据模型（ER 摘要）

```
Department 1─n User
AssetCategory 1─n Asset        （类别含默认报废年限/残值率/自定义字段schema）
Location 1─n Asset             （车间/仓库/机房，树形）
User 1─n Asset                 （custodian 使用人）
Asset 1─n RepairOrder          （维修工单：配件明细JSON+费用）
Asset 1─n LifecycleLog         （全流程留痕：入库/领用/调拨/维修/盘点/报废）
Asset 1─n DepreciationSnapshot （年度折旧快照）
Stocktake 1─n StocktakeItem    （盘点任务/明细，扫码确认）
ImportBatch 1─n Asset          （Excel导入批次，错误行JSON留痕）
```

### 3.1 AssetCategory（资产类别）
| 字段 | 类型 | 说明 |
|------|------|------|
| name | varchar(50) | 扫描枪 / 打印头 / 一体机… |
| code | varchar(20) | 唯一编码 SCN / PRT… |
| default_life | int | 默认报废年限（8） |
| default_salvage_rate | float | 残值率 0.05 |
| field_schema | JSON | 自定义字段定义数组（见 §4） |

### 3.2 Asset（资产台账，核心表）
| 字段 | 类型 | 说明 |
|------|------|------|
| asset_tag | varchar(32) 唯一 | ZC-SCN-2026-0001 自动生成 |
| sn | varchar(64) 索引 | 序列号（扫码键） |
| category / brand / model_spec | | 类别、品牌、型号 |
| location / department / custodian | FK | 位置/部门/使用人 |
| status | choice | in_stock/in_use/repairing/idle/scrapped |
| **purchase_date** | date | **投产日期** |
| **original_value** | decimal(12,2) | **原值** |
| **useful_life** | int | **使用年限**（默认继承类别） |
| **salvage_rate** | float | 残值率 |
| custom | JSON | 自定义字段值（按类别schema校验） |
| 计算属性 | | current_value（当前净值）/ used_years / health_level |

### 3.3 RepairOrder（维修工单）
fault_desc 文本、parts JSON[{name,cost}]、labor_cost、vendor、repair_date、status(待维修/完成)
→ `total_cost` property = Σparts + labor

## 4. 自定义字段引擎（零改表）

- schema 存 AssetCategory.field_schema：
  `[{"key":"print_life","label":"打印寿命(万张)","type":"number","required":false}]`
- 类型：text/number/date/select/boolean
- 写入时按 schema 校验，存 Asset.custom JSON
- 前端按类别动态渲染表单控件与表格列
- **新增字段 = 类别管理里点一下，全系统生效，不改表**

## 5. 折旧与 AI 经济寿命引擎（P3 核心）

### 5.1 规则引擎（可审计，AI 不参与计算）
```
年折旧   = 原值 × (1−残值率) / 使用年限            （直线法）
当前净值 = 原值 − 年折旧 × 已使用年数
累计维修 = Σ(维修工单.total_cost)
维修占比 = 累计维修 / 当前净值

低劣化模型：年维修增长 λ（对年度维修序列线性拟合斜率，向下取0保护）
经济寿命 T = √( 2×原值×(1−残值率) / λ )    （λ>0 时有效）

决策规则（阈值可配置于 SystemSetting）：
R1 单次维修费 > 净值×60%        → 🔴 本次建议报废
R2 累计维修费 > 原值×50%        → 🟡 维修成本预警
R3 经济寿命T < (使用年限−已用)  → 🔴 报废期缩短至T年
R4 当年维修费 > 年折旧×1.5      → 🟡 修不如换
R5 闲置>12个月 且 净值<1000     → 🟡 建议处置
健康度 = R命中规则取最严：🔴/🟡/🟢
```

### 5.2 AI 层（Ollama，仅生成文字）
- 输入：规则引擎结构化结果（JSON）
- 输出：中文报告段落（资产健康档案、报废建议措辞）
- 失败降级：模板文字拼接，不阻塞
- ChatBI 问数：自然语言 → 受控查询（白名单指标：维修费TOP、报废预测清单等）

### 5.3 展示
- 资产详情：成本交叉曲线（累计维修 vs 净值，交点=经济报废点）
- 看板：全厂红黄绿分布、年度报废预测清单、维修费TOP10

## 6. API 清单（DRF，前缀 /api/v1）

```
POST /auth/login                 POST /auth/logout
GET/POST /categories             PATCH/DELETE /categories/{id}
GET/POST /locations              GET/POST /departments
GET/POST /assets                 GET/PATCH/DELETE /assets/{id}
GET  /assets/{id}/lifecycle      GET /assets/{id}/economy   ← 经济分析
POST /assets/batch_import        GET  /import/template      GET /import/batches
GET/POST /repairs                PATCH /repairs/{id}  (完成→写LifecycleLog)
GET/POST /stocktakes             POST /stocktakes/{id}/scan  ← 扫码盘点
GET  /dashboard/overview         GET /dashboard/scrappage   ← 报废预测
POST /ai/chat                    POST /ai/report/{asset_id}
```

## 7. 页面清单（Vue3，暗色）

| 页面 | 路由 | 核心元素 |
|------|------|---------|
| 登录 | /login | |
| 工作台 | /dashboard | 资产总数/净值/红黄绿环/报废预测列表 |
| 资产台账 | /assets | 多条件筛选、批量导入按钮、状态标签 |
| 资产详情 | /assets/:id | 基本信息卡+财务卡+生命周期时间轴+成本交叉曲线+维修记录 |
| 类别管理 | /categories | 含自定义字段编辑器 |
| 批量导入 | /assets/import | 模板下载/上传预览/错误行标红 |
| 盘点 | /stocktakes | 任务列表/扫码输入框(自动聚焦)/差异报告 |
| 维修管理 | /repairs | 工单列表/完成登记 |
| 报废分析 | /economy | 红黄绿全厂分布+报废预测清单 |

## 8. 安全与合规

- 登录 JWT（SimpleJWT），密码 PBKDF2
- 操作全留痕（LifecycleLog 不可删改）
- 独立 DB 文件 + 每日备份脚本（wal_checkpoint 后复制）
- 内网部署，无外联（AI 走内网 Ollama）

## 9. 分期计划

| 期 | 范围 | 验收 |
|----|------|------|
| P1（本周） | 登录/类别/自定义字段/资产CRUD/批量导入/台账页 | 导入50台真实资产；新增自定义字段不改库 |
| P2 | 领用/调拨/报废流+维修工单+扫码盘点 | 扫描枪完成一轮盘点 |
| P3 | 折旧引擎+经济寿命分析+曲线图 | 3台老设备输出报废分析 |
| P4 | Ollama 报告+ChatBI | 自然语言问"维修费TOP5打印头" |
