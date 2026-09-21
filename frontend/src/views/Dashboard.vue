<template>
  <div>
    <h1 class="page-title">工作台 · 资产全景
      <el-tag type="info" size="small" style="margin-left:10px">统计口径：办公设备 + 无形资产（软件）</el-tag>
    </h1>

    <!-- 第一排：核心 KPI（老板视角 6 卡） -->
    <el-row :gutter="12">
      <el-col :span="4"><div class="stat-card"><div class="label">资产总数</div>
        <div class="value">{{ ov.total ?? '-' }}</div><div class="sub">不含已报废</div></div></el-col>
      <el-col :span="4"><div class="stat-card"><div class="label">原值总额</div>
        <div class="value">¥{{ fmtYi(ov.total_value) }}</div><div class="sub">全量账面价值</div></div></el-col>
      <el-col :span="4"><div class="stat-card"><div class="label">当前净值</div>
        <div class="value" style="color:var(--green)">¥{{ fmtYi(ov.net_value) }}</div>
        <div class="sub">占原值 {{ pct(ov.net_value, ov.total_value) }}%</div></div></el-col>
      <el-col :span="4"><div class="stat-card"><div class="label">已报废</div>
        <div class="value" style="color:var(--text-dim)">{{ ov.scrapped ?? '-' }}</div>
        <div class="sub">占总量 {{ pct(ov.scrapped, (ov.total||0)+(ov.scrapped||0)) }}%</div></div></el-col>
      <el-col :span="4"><div class="stat-card"><div class="label">累计维修费</div>
        <div class="value" style="color:var(--yellow)">¥{{ fmtWan(ov.repair_cost) }}</div>
        <div class="sub">{{ ov.repair_total ?? 0 }} 笔工单</div></div></el-col>
      <el-col :span="4"><div class="stat-card"><div class="label">报废风险(红/黄)</div>
        <div class="value">
          <span style="color:var(--red)">{{ sc.red ?? '…' }}</span>
          <span style="color:var(--text-dim)"> / </span>
          <span style="color:var(--yellow)">{{ sc.yellow ?? '…' }}</span>
        </div><div class="sub">经济寿命模型判定</div></div></el-col>
    </el-row>

    <!-- 第二排：五大老板视角 -->
    <el-row :gutter="12" style="margin-top:12px">
      <el-col :span="4"><div class="stat-card kpi-mini">
        <div class="label">🏥 带病运行</div>
        <div class="value" style="color:var(--red)">{{ kpi.broken ?? '-' }}</div>
        <div class="sub">维修≥2次仍在用</div></div></el-col>
      <el-col :span="4"><div class="stat-card kpi-mini">
        <div class="label">⏳ 超期服役</div>
        <div class="value" style="color:var(--yellow)">{{ kpi.overdue ?? '-' }}</div>
        <div class="sub">已用超过标准年限</div></div></el-col>
      <el-col :span="4"><div class="stat-card kpi-mini">
        <div class="label">闲置资产</div>
        <div class="value">{{ ov.idle ?? 0 }}</div>
        <div class="sub">闲置+在库 待调配</div></div></el-col>
      <el-col :span="4"><div class="stat-card kpi-mini">
        <div class="label">🚚 维修中</div>
        <div class="value" style="color:var(--yellow)">{{ ov.repairing ?? 0 }}</div>
        <div class="sub">当前不可用</div></div></el-col>
      <el-col :span="4"><div class="stat-card kpi-mini">
        <div class="label">🏢 覆盖部门</div>
        <div class="value">{{ ov.dept_count ?? '-' }}</div>
        <div class="sub">有资产的部门数</div></div></el-col>
      <el-col :span="4"><div class="stat-card kpi-mini">
        <div class="label">📱 本年新增</div>
        <div class="value" style="color:var(--accent)">{{ kpi.new_this_year ?? '-' }}</div>
        <div class="sub">{{ year }} 年投产</div></div></el-col>
    </el-row>

    <!-- 第三排：四图 -->
    <el-row :gutter="12" style="margin-top:12px;align-items:stretch">
      <el-col :span="7" style="display:flex">
        <el-card style="flex:1" :body-style="{flex:1,overflow:'hidden'}"><template #header>资产状态分布</template>
          <div ref="statusChart" style="height:300px"></div>
        </el-card>
      </el-col>
      <el-col :span="8" style="display:flex">
        <el-card style="flex:1" :body-style="{flex:1,overflow:'hidden'}"><template #header>资产原值 TOP8 部门（万元）</template>
          <div v-if="deptRows.length" class="dept-box">
            <router-link class="s-row click" v-for="(d, i) in deptRows" :key="'d'+i" :to="d.to"
                 :title="'点击查看 ' + d.name + ' 资产明细'">
              <span class="rk" :class="'rk' + (i < 3 ? i + 1 : 'n')">{{ i + 1 }}</span>
              <span class="nm" :title="d.name">{{ d.name }}</span>
              <div class="bar-wrap"><div class="bar" :style="{ width: d.pct + '%' }"></div></div>
              <span class="val">{{ d.wan }}万</span>
            </router-link>
          </div>
          <div v-else ref="deptChart" style="height:260px"></div>
        </el-card>
      </el-col>
      <el-col :span="9" style="display:flex">
        <el-card style="flex:1" :body-style="{flex:1,overflow:'hidden'}"><template #header>资产年限结构（台数）</template>
          <div ref="ageChart" style="height:300px"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 第四排：两张表 -->
    <el-row :gutter="12" style="margin-top:12px;align-items:stretch">
      <el-col :span="14" style="display:flex">
        <el-card class="eq-card">
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span>{{ (sc.red || 0) + (sc.yellow || 0) > 0 ? '🔴 报废风险 TOP（经济寿命分析）' : '🟢 健康资产 TOP（当前无报废风险）' }}
                <el-tooltip content="系统每 8 分钟自动重算口径内资产的经济寿命" placement="top">
                  <span style="font-size:12px;color:var(--text-dim);cursor:help">
                    {{ sc.computed_at ? '· 更新于 ' + sc.computed_at : '' }}</span>
                </el-tooltip></span>
              <el-button size="small" @click="$router.push('/economy')">查看全部</el-button>
            </div>
          </template>
          <div class="dash-scroll risk-h" v-if="riskRows.length">
            <div class="scroll-viewport">
              <div class="scroll-body" :class="{ anim: riskRows.length >= 5 }">
                <div class="r-row" v-for="(r, i) in riskRows.concat(riskRows)" :key="'r'+i"
                     :title="r.suggestion">
                  <span class="dot" :style="{ color: levelColor(r.health_level) }">●</span>
                  <span class="tag">{{ r.display_tag }}</span>
                  <span class="nm2">{{ r.name }}</span>
                  <span class="money">¥{{ fmt(r.current_value) }}</span>
                  <span class="life">{{ r.econ_life ? r.econ_life + '年' : '—' }}</span>
                  <span class="sug">{{ r.suggestion }}</span>
                </div>
              </div>
            </div>
          </div>
          <el-empty v-else description="经济寿命分析计算中…" :image-size="60" />
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card>
          <template #header>类别价值分布（原值万元）</template>
          <div ref="catChart" style="height:280px"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 第五排：待办提醒（老板关心的行动项） -->
    <el-row :gutter="12" style="margin-top:12px">
      <el-col :span="24">
        <el-card>
          <template #header><span>📋 管理行动提示</span></template>
          <div class="dash-scroll todo-h" v-if="todos.length">
            <div class="scroll-viewport">
              <div class="scroll-body" :class="{ anim: todos.length >= 3 }">
                <div class="todo-item" v-for="(t, i) in todos.concat(todos)" :key="'t'+i"
                     :style="{ borderLeftColor: t.color }">
                  <b>{{ t.title }}</b> — {{ t.desc }}
                  <el-button v-if="t.to" link type="primary" size="small"
                             style="margin-left:8px" @click="$router.push(t.to)">{{ t.action }} →</el-button>
                </div>
              </div>
            </div>
          </div>
          <div v-else style="color:var(--text-dim)">暂无待办提示</div>
        </el-card>
      </el-col>
    </el-row>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import api from '../api'

const ov = ref({})
const sc = ref({})
const kpi = ref({})
const bsData = ref({})
const statusChart = ref(), deptChart = ref(), ageChart = ref(), catChart = ref()

const year = new Date().getFullYear()
const fmt = n => n == null ? '-' : Number(n).toLocaleString('zh-CN', { maximumFractionDigits: 0 })
const fmtYi = n => n == null ? '-' : (n / 1e8).toFixed(2) + ' 亿'
const fmtWan = n => n == null ? '-' : (n / 1e4).toFixed(1) + ' 万'
const pct = (a, b) => (a && b) ? Math.round(a / b * 100) : 0
const levelColor = l => ({ red: 'var(--red)', yellow: 'var(--yellow)', green: 'var(--green)' }[l])
const levelText = l => ({ red: '报废', yellow: '预警', green: '正常' }[l] || l)

// 年限段点击 → 直接跳转资产台账（带已用年限区间筛选）
import { useRouter } from 'vue-router'
const router = useRouter()
function goAgeList(label) {
  // 区间与后端 bigscreen.py 分桶严格一致（连续边界，避免漏资产）：
  // 0-2=≤2，3-5=>2且≤5，6-8=>5且≤8，8-9=>8且≤9，9-10=>9且≤10，10年以上=>10
  const r = { '0-2年':   { max: 2 },
              '3-5年':   { min: 2,  max: 5 },
              '6-8年':   { min: 5,  max: 8 },
              '8-9年':   { min: 8,  max: 9 },
              '9-10年':  { min: 9,  max: 10 },
              '10年以上': { min: 10 } }[label]
  if (!r) return
  const query = {}
  if (r.min != null) query.age_gt = String(r.min)
  if (r.max != null) query.age_lte = String(r.max)
  // 分桶口径=非报废（在用/在库/维修/闲置），台账默认含报废 → 带上排除标记保证条数一致
  query.exclude_scrapped = '1'
  router.push({ path: '/assets', query })
}

// 部门原值滚动行（全量部门按原值排序，取 TOP10；pct=相对第一名的宽度）
// to=点击跳转目标：id 优先（台账按部门筛选+排除报废）；「未分配」带 no_dept=1 查无部门资产
const deptRows = computed(() => {
  const list = (bsData.value.by_dept_value || [])
    .map(x => ({ name: x.department__name || '未分配',
                 id: x.department__id ?? null,
                 wan: Math.round(x.value / 1e4) }))
    .slice(0, 10)
  const max = Math.max(...list.map(d => d.wan), 1)
  return list.map(d => ({
    ...d, pct: Math.max(4, Math.round(d.wan / max * 100)),
    to: d.id != null
      ? { path: '/assets', query: { department: String(d.id), exclude_scrapped: '1' } }
      : { path: '/assets', query: { no_dept: '1' } },
  }))
})

// 风险滚动行（红优先，最多 12 条）
const riskRows = computed(() => (sc.value.items || []).slice(0, 12))

const todos = computed(() => {
  const t = []
  if ((sc.value.red || 0) > 0)
    t.push({ color: 'var(--red)', title: `${sc.value.red} 台资产达到报废标准`,
             desc: '继续维修不经济，建议走报废流程', to: '/economy', action: '查看清单' })
  if ((kpi.value.broken || 0) > 0)
    t.push({ color: 'var(--red)', title: `${kpi.value.broken} 台设备维修≥2次仍在用`,
             desc: '重复维修成本高，建议评估以旧换新', to: '/economy', action: '经济分析' })
  if ((kpi.value.overdue || 0) > 0)
    t.push({ color: 'var(--yellow)', title: `${kpi.value.overdue} 台已超期服役`,
             desc: '超过标准使用年限，存在安全隐患',
             to: '/assets?overdue=1&exclude_scrapped=1', action: '查看台账' })
  if ((ov.value.idle || 0) + (ov.value.in_stock || 0) > 0)
    t.push({ color: 'var(--accent)', title: `${(ov.value.idle || 0) + (ov.value.in_stock || 0)} 台闲置/在库`,
             desc: '可内部调拨盘活，提高利用率', to: '/assets?status=in_stock', action: '查看' })
  if ((ov.value.repairing || 0) > 0)
    t.push({ color: 'var(--yellow)', title: `${ov.value.repairing} 台维修中`,
             desc: '关注维修进度，尽快恢复生产', to: '/repairs', action: '维修单' })
  const st = (new Date()).getMonth() + 1
  t.push({ color: 'var(--green)', title: '年度盘点建议',
           desc: `已到 ${st} 月，建议完成本轮资产盘点`, to: '/stocktakes', action: '去盘点' })
  const noDept = kpi.value.no_dept || 0
  if (noDept > 0)
    t.push({ color: 'var(--yellow)', title: `${noDept} 台资产未分配部门`,
             desc: '归属不明影响盘点与责任落实，建议尽快补录',
             to: '/unassigned-dept', action: '去补录' })
  return t
})

let _catChart = null
function mkChart(el, option, onClick) {
  if (!el) return
  const inst = echarts.init(el)
  inst.setOption(option)
  if (onClick) inst.on('click', onClick)
  return inst
}
function mkResizeableChart(el, option, onClick) {
  if (!el) return
  _catChart = echarts.init(el)
  _catChart.setOption(option)
  if (onClick) _catChart.on('click', onClick)
}

function onWinResize() { if (_catChart) _catChart.resize() }

onMounted(async () => {
  window.addEventListener('resize', onWinResize)
  // 不再自动触发 ai_report_batch：后台线程全量扫 18531 行会与前台查询争抢
  // SQLite 锁 + GIL（实测把 bigscreen 拖到 40s）。预热改由部署脚本跑一次，
  // 单台报告由资产详情页用户手动生成。
  // 先渲染快的两个接口（KPI 卡 + 三图）
  const [o, bs] = await Promise.all([
    api.get('/dashboard/overview/'),
    api.get('/bigscreen/'),
  ])
  bsData.value = bs
  ov.value = { ...o, ...bs.kpi, scrapped: bs.kpi.scrapped, repair_cost: bs.kpi.repair_cost,
               repair_total: bs.kpi.repair_total, dept_count: (bs.by_dept || []).length }
  kpi.value = bs.kpi_extra || {}
  kpi.value.new_this_year = (bs.new_this_year ?? 0)
  renderCharts({ ...bs, scrapped_total: o.scrapped })

  // 精简报废分析（后台预计算，毫秒级）：风险卡 + TOP 表
  try {
    const s = await api.get('/dashboard/scrappage_slim/')
    sc.value = { red: s.red, yellow: s.yellow, green: s.green,
                 items: s.items, computed_at: s.computed_at }
  } catch (e) { /* 风险表保持加载态 */ }


function renderCharts(bs) {
  const st = bs.by_status || {}
  mkChart(statusChart.value, {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, textStyle: { color: '#6b7a99', fontSize: 12 } },
    series: [{
      type: 'pie', radius: ['42%', '68%'], center: ['50%', '44%'],
      label: { color: '#6b7a99', fontSize: 12, formatter: '{b}\n{c}' },
      data: [
        { name: '在用', value: st.in_use || 0, itemStyle: { color: '#3477f6' } },
        { name: '在库', value: st.in_stock || 0, itemStyle: { color: '#12a578' } },
        { name: '维修中', value: st.repairing || 0, itemStyle: { color: '#d98f1f' } },
        { name: '闲置', value: st.idle || 0, itemStyle: { color: '#9aa8c7' } },
        { name: '已报废', value: bs.scrapped_total || 0, itemStyle: { color: '#c0c9dd' } },
      ].filter(x => x.value > 0),
    }],
  }, p => {
    const map = { '在用': 'in_use', '在库': 'in_stock', '维修中': 'repairing', '闲置': 'idle', '已报废': 'scrapped' }
    const st = map[p.name]
    if (st === 'scrapped') router.push({ path: '/assets', query: { status: 'scrapped', include_scrapped: '1' } })
    else if (st) router.push({ path: '/assets', query: { status: st, exclude_scrapped: '1' } })
  })


  // 年限结构柱图
  const buckets = bs.age_buckets || {}
  mkChart(ageChart.value, {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 14, top: 24, bottom: 26 },
    xAxis: { type: 'category', data: Object.keys(buckets),
             axisLabel: { color: '#6b7a99', fontSize: 12 },
             axisLine: { lineStyle: { color: '#dfe5f1' } } },
    yAxis: { type: 'value', axisLabel: { color: '#6b7a99' },
             splitLine: { lineStyle: { color: '#eef1f6' } } },
    series: [{ type: 'bar', barWidth: '46%', data: Object.values(buckets),
               label: { show: true, position: 'top', color: '#243044', fontSize: 12 },
               itemStyle: { color: p2 => {
                 const keys = Object.keys(buckets)
                 const k = keys[p2.dataIndex]
                 return { '0-2年': '#12a578', '3-5年': '#3477f6',
                          '6-8年': '#d98f1f', '8-9年': '#e5455e',
                          '9-10年': '#c2417a', '10年以上': '#8f1d3f' }[k] || '#3477f6'
               } } }],
  }, params => goAgeList(params.name))

  // 类别价值分布（原值 TOP8 横向条形）——点击跳台账对应类别清单
  const cats = (bs.by_cat || []).slice().reverse()
  const catClick = (p) => {
    const c = (bs.by_cat || []).find(x => x.category__name === p.name)
    if (!c || c.category__id == null) return
    router.push({ path: '/assets', query: { categories: String(c.category__id), exclude_scrapped: '1' } })
  }
  mkResizeableChart(catChart.value, {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' },
               valueFormatter: v => '¥' + Number(v).toLocaleString() + ' 万' },
    grid: { left: 110, right: 40, top: 8, bottom: 22 },
    xAxis: { type: 'value', axisLabel: { color: '#6b7a99' }, splitLine: { lineStyle: { color: '#eef1f6' } } },
    yAxis: { type: 'category', data: cats.map(c => c.category__name),
             axisLabel: { color: '#243044', fontSize: 11.5, width: 100, overflow: 'truncate' } },
    series: [{ type: 'bar', barWidth: '55%',
               data: cats.map(c => Math.round((c.value || 0) / 1e4)),
               itemStyle: { color: '#6f5bd4', borderRadius: [0, 4, 4, 0] } }],
  }, catClick)
}
})
</script>

<style scoped>
.kpi-mini { border-left: 3px solid var(--accent); }
.todo-item {
  border-left: 3px solid var(--accent);
  background: var(--bg-page);
  padding: 8px 12px;
  border-radius: 0 6px 6px 0;
  font-size: 13.5px;
}
/* 第四排等高：类别卡与报废风险卡拉伸同高 */
.eq-card { flex: 1; display: flex; flex-direction: column; }
.eq-card > :deep(.el-card__body) {
  flex: 1; min-height: 0; overflow: hidden;
  display: flex; flex-direction: column;
}
.eq-card > :deep(.el-card__body) > * { flex: 1; min-height: 0; }
/* 滚动组件（与大屏同款交互） */
.dash-scroll { position: relative; overflow: hidden; }
.scroll-viewport { overflow: hidden; }
.scroll-body { display: flex; flex-direction: column; }
.scroll-body.anim { animation: dash-scroll-up 22s linear infinite; }
.scroll-body.anim:hover { animation-play-state: paused; }
@keyframes dash-scroll-up {
  0% { transform: translateY(0); }
  100% { transform: translateY(-50%); }
}
/* 部门行（容器 300px，8 行均匀填满） */
.dept-box { height: 100%; display: flex; flex-direction: column;
            justify-content: space-around; }
.s-row { display: flex; align-items: center; gap: 8px; padding: 4px;
         border-bottom: 1px dashed var(--border); font-size: 13px; }
/* 可点击行（TOP8 部门 → 跳台账筛选） */
.s-row.click { cursor: pointer; transition: background .15s;
               text-decoration: none; color: inherit; display: flex; }
.s-row.click:hover { background: var(--bg-panel); }
.s-row.click:hover .nm { color: var(--accent); }
.s-row .rk { width: 22px; height: 22px; border-radius: 50%; flex: none;
             display: flex; align-items: center; justify-content: center;
             font-size: 12px; font-weight: 600; color: #fff; background: #b9c3d8; }
.s-row .rk1 { background: #d9a514; }
.s-row .rk2 { background: #7d92c4; }
.s-row .rk3 { background: #b0793f; }
.s-row .nm { width: 150px; flex: none; overflow: hidden; text-overflow: ellipsis;
             white-space: nowrap; color: var(--text-main); }
.s-row .bar-wrap { flex: 1; height: 8px; background: var(--bg-panel);
                   border-radius: 4px; overflow: hidden; }
.s-row .bar { height: 100%; background: linear-gradient(90deg, #3477f6, #6fa3ff);
              border-radius: 4px; }
.s-row .val { width: 78px; text-align: right; flex: none;
              color: var(--text-dim); font-variant-numeric: tabular-nums; }
/* 风险行 */
.risk-h .scroll-viewport { height: 280px; }
.r-row { display: flex; align-items: center; gap: 10px; padding: 7px 4px;
         border-bottom: 1px dashed var(--border); font-size: 13px; }
.r-row .dot { flex: none; }
.r-row .tag { width: 110px; flex: none; font-weight: 500; color: var(--text-main); }
.r-row .nm2 { width: 170px; flex: none; overflow: hidden; text-overflow: ellipsis;
              white-space: nowrap; }
.r-row .money { width: 90px; text-align: right; flex: none; color: var(--text-dim); }
.r-row .life { width: 70px; flex: none; text-align: center; }
.r-row .sug { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
              color: var(--text-dim); }
/* 待办 */
.todo-h .scroll-viewport { max-height: 160px; }
</style>
