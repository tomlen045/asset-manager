<template>
  <div class="bigscreen">
    <!-- 顶部标题栏 -->
    <header class="bs-header">
      <div class="bs-time">{{ now }}</div>
      <h1>IT 固定资产管理数据大屏</h1>
      <div class="bs-sub">IT ASSET MANAGEMENT DASHBOARD</div>
      <button class="bs-exit" @click="$router.push('/dashboard')">退出全屏</button>
    </header>

    <!-- KPI 行 -->
    <section class="bs-kpis">
      <div class="bs-kpi"><div class="v">{{ kpi.total ?? 0 }}</div><div class="l">资产总数</div></div>
      <div class="bs-kpi"><div class="v">¥{{ fmt(kpi.total_value) }}</div><div class="l">原值总额</div></div>
      <div class="bs-kpi"><div class="v" style="color:var(--green)">¥{{ fmt(kpi.net_value) }}</div><div class="l">净值总额</div></div>
      <div class="bs-kpi"><div class="v" style="color:var(--yellow)">{{ kpi.repair_total ?? 0 }}</div><div class="l">累计维修</div></div>
      <div class="bs-kpi"><div class="v" style="color:var(--red)">{{ risk.red ?? 0 }}</div><div class="l">报废风险</div></div>
      <div class="bs-kpi"><div class="v" style="color:var(--text-dim)">{{ kpi.scrapped ?? 0 }}</div><div class="l">已报废</div></div>
    </section>

    <!-- 主体三列 -->
    <section class="bs-grid">
      <div class="bs-col">
        <div class="bs-panel">
          <h3>资产状态分布</h3>
          <div ref="statusChart" class="bs-chart"></div>
        </div>
        <div class="bs-panel">
          <h3>资产年限结构</h3>
          <div ref="ageChart" class="bs-chart"></div>
        </div>
      </div>

      <div class="bs-col bs-col-mid">
        <div class="bs-panel" style="flex:0 0 42%">
          <h3>资产类别分布 TOP8</h3>
          <div ref="catChart" class="bs-chart"></div>
        </div>
        <div class="bs-panel" style="flex:1">
          <h3>报废风险 TOP10（经济寿命分析）</h3>
          <div class="bs-table">
            <table>
              <thead><tr><th>健康</th><th>编号</th><th>名称</th><th>经济寿命</th><th>建议</th></tr></thead>
              <tbody>
                <tr v-for="it in riskItems" :key="it.asset_tag">
                  <td><span class="risk-dot" style="--d:var(--red)">🔴</span></td>
                  <td>{{ it.asset_tag }}</td>
                  <td class="ellipsis">{{ it.name }}</td>
                  <td>{{ it.econ_life ? it.econ_life + '年' : '—' }}</td>
                  <td class="ellipsis">{{ it.suggestion }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div class="bs-col">
        <div class="bs-panel">
          <h3>部门分布 TOP10</h3>
          <div class="bs-scroll" v-if="deptRows.length">
            <div class="scroll-viewport">
              <div class="scroll-inner" :class="{ 'is-anim': deptRows.length >= 6 }">
                <div class="bs-feed" v-for="(d, i) in deptLoop" :key="'d'+i">
                  <span class="feed-rank" :class="'rank-' + ((i % deptRows.length) + 1)">{{ (i % deptRows.length) + 1 }}</span>
                  <span class="feed-txt">{{ d.department__name }}</span>
                  <span class="feed-bar"><span class="feed-bar-in"
                    :style="{ width: (d.pct || 0) + '%' }"></span></span>
                  <span class="feed-num">{{ d.n }}</span>
                  <span class="feed-pct">{{ d.pct }}%</span>
                </div>
              </div>
            </div>
          </div>
          <div v-else ref="deptChart" class="bs-chart"></div>
        </div>
        <div class="bs-panel">
          <h3>最近维修动态</h3>
          <div class="bs-scroll" v-if="recentRepairs.length">
            <div class="scroll-viewport">
              <div class="scroll-inner" :class="{ 'is-anim': recentRepairs.length >= 6 }">
                <div class="bs-feed" v-for="(rp, i) in repairLoop" :key="'r'+i">
                  <span class="feed-dot" :style="{ background: rp.status === 'done' ? 'var(--green)' : 'var(--yellow)' }"></span>
                  <span class="feed-tag">{{ rp.asset__asset_tag }}</span>
                  <span class="feed-txt ellipsis">{{ rp.fault_desc }}</span>
                  <span class="feed-time">{{ rp.report_date }}</span>
                </div>
              </div>
            </div>
          </div>
          <div v-else class="empty-hint">暂无维修记录</div>
        </div>
        <div class="bs-panel" v-if="stocktake.total">
          <h3>盘点进度 — {{ stocktakeProgress }}%</h3>
          <el-progress :percentage="stocktakeProgress" :stroke-width="18"
                       :color="stocktakeProgress >= 100 ? '#00d68f' : '#3d8bff'" />
          <div class="st-row">
            <span>已盘 {{ stocktake.found }}</span>
            <span>未盘 {{ stocktake.missing }}</span>
            <span>账外 {{ stocktake.unexpected }}</span>
          </div>
          <div class="bs-scroll st-scroll" v-if="stocktakeFound.length">
            <div class="scroll-viewport">
              <div class="scroll-inner" :class="{ 'is-anim': stocktakeFound.length >= 6 }">
                <div class="bs-feed" v-for="(it, i) in stocktakeLoop" :key="'s'+i">
                  <span class="feed-dot" style="background: var(--green)"></span>
                  <span class="feed-tag">{{ it.asset__asset_tag }}</span>
                  <span class="feed-txt ellipsis">{{ it.asset__brand }} {{ it.asset__model_spec }}</span>
                  <span class="feed-time">{{ fmtTime(it.found_at) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>        <div class="bs-panel" v-if="terminals.total">
          <h3>🏭 生产类终端 — {{ terminals.total }} 台 / ¥{{ fmt(terminals.value) }}</h3>
          <div class="bs-scroll" v-if="termDeptRows.length">
            <div class="scroll-viewport">
              <div class="scroll-inner" :class="{ 'is-anim': termDeptRows.length >= 6 }">
                <div class="bs-feed" v-for="(d, i) in termDeptLoop" :key="'t'+i">
                  <span class="feed-rank rank-1">{{ i % termDeptRows.length + 1 }}</span>
                  <span class="feed-txt">{{ d.department__name || '未分配' }}</span>
                  <span class="feed-bar"><span class="feed-bar-in"
                    :style="{ width: barWidth(d.n, termDeptMax) }"></span></span>
                  <span class="feed-num">{{ d.n }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import api from '../api'

const kpi = ref({}), risk = ref({}), riskItems = ref([]), recentRepairs = ref([])
const stocktake = ref({}), terminals = ref({}), deptRows = ref([]), termDeptRows = ref([])
const stocktakeFound = ref([])
const now = ref('')
const statusChart = ref(), ageChart = ref(), catChart = ref(), termChart = ref()
let timer = null, charts = []

const fmt = n => n == null ? '0' : Number(n).toLocaleString('zh-CN', { maximumFractionDigits: 0 })
const fmtTime = t => t ? String(t).slice(5, 16) : ''
const stocktakeProgress = computed(() => stocktake.value.progress || 0)

// 滚动列表：数据两倍拼接实现无缝循环
const deptMax = computed(() => Math.max(...deptRows.value.map(d => d.n), 1))
const termDeptMax = computed(() => Math.max(...termDeptRows.value.map(d => d.n), 1))
const deptLoop = computed(() => [...deptRows.value, ...deptRows.value])
const termDeptLoop = computed(() => [...termDeptRows.value, ...termDeptRows.value])
const repairLoop = computed(() => [...recentRepairs.value, ...recentRepairs.value])
const stocktakeLoop = computed(() => [...stocktakeFound.value, ...stocktakeFound.value])

function barWidth(n, max) {
  return Math.max(Math.round(n / max * 100), 4) + '%'
}

function mkChart(refEl, option) {
  const el = refEl
  if (!el) return
  const c = echarts.init(el)
  c.setOption(option)
  charts.push(c)
  return c
}

async function load() {
  now.value = new Date().toLocaleString('zh-CN', { hour12: false })
  const d = await api.get('/bigscreen/')
  kpi.value = d.kpi
  risk.value = d.risk
  riskItems.value = d.risk_items
  recentRepairs.value = d.recent_repairs
  stocktake.value = d.stocktake
  terminals.value = d.terminals || {}
  deptRows.value = d.by_dept || []
  termDeptRows.value = d.terminals?.by_dept || []
  stocktakeFound.value = d.stocktake_found || []

  // 状态饼图
  const stNames = { in_use: '在用', in_stock: '在库', repairing: '维修中', idle: '闲置' }
  mkChart(statusChart.value, {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item' },
    series: [{
      type: 'pie', radius: ['48%', '72%'],
      label: { color: '#8a97b8', fontSize: 12 },
      data: Object.entries(d.by_status || {}).map(([k, v]) => ({
        name: stNames[k] || k, value: v,
        itemStyle: { color: { in_use: '#3d8bff', in_stock: '#00d68f', repairing: '#f5a623', idle: '#8a97b8' }[k] },
      })).filter(x => x.value > 0),
    }],
  })

  // 年限柱图
  mkChart(ageChart.value, {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    grid: { left: 45, right: 15, top: 25, bottom: 28 },
    xAxis: { type: 'category', data: Object.keys(d.age_buckets || {}),
             axisLabel: { color: '#8a97b8' }, axisLine: { lineStyle: { color: '#263352' } } },
    yAxis: { type: 'value', axisLabel: { color: '#8a97b8' }, splitLine: { lineStyle: { color: '#1a2440' } } },
    series: [{ type: 'bar', barWidth: '45%', data: Object.values(d.age_buckets || {}),
               itemStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                 { offset: 0, color: '#3d8bff' }, { offset: 1, color: '#1a4bbf' }]) } }],
  })

  // 类别横向条形
  const cats = (d.by_cat || []).slice().reverse()
  mkChart(catChart.value, {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 110, right: 30, top: 10, bottom: 25 },
    xAxis: { type: 'value', axisLabel: { color: '#8a97b8' }, splitLine: { lineStyle: { color: '#1a2440' } } },
    yAxis: { type: 'category', data: cats.map(c => c.category__name),
             axisLabel: { color: '#c8d4f0', fontSize: 12 } },
    series: [{ type: 'bar', barWidth: '55%', data: cats.map(c => c.n),
               itemStyle: { color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                 { offset: 0, color: '#1a4bbf' }, { offset: 1, color: '#3d8bff' }]) } }],
  })

  // 部门横向条形
  const depts = (d.by_dept || []).slice().reverse()
  mkChart(deptChart.value, {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 110, right: 30, top: 10, bottom: 25 },
    xAxis: { type: 'value', axisLabel: { color: '#8a97b8' }, splitLine: { lineStyle: { color: '#1a2440' } } },
    yAxis: { type: 'category', data: depts.map(c => c.department__name || '未分配'),
             axisLabel: { color: '#c8d4f0', fontSize: 11, width: 95, overflow: 'truncate' } },
    series: [{ type: 'bar', barWidth: '55%', data: depts.map(c => c.n),
               itemStyle: { color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                 { offset: 0, color: '#0a7a5c' }, { offset: 1, color: '#00d68f' }]) } }],
  })
}

onMounted(() => {
  load()
  timer = setInterval(load, 30000)
  window.addEventListener('resize', () => charts.forEach(c => c.resize()))
})
onUnmounted(() => clearInterval(timer))
</script>

<style scoped>
.bigscreen {
  position: fixed;
  inset: 0;
  z-index: 2000;
  background: radial-gradient(ellipse at 50% 0%, #101a36 0%, #0b1020 65%);
  display: flex;
  flex-direction: column;
  padding: 16px 20px;
  overflow: auto;
}
.bs-header { position: relative; text-align: center; margin-bottom: 14px; }
.bs-header h1 {
  margin: 0; font-size: 30px; letter-spacing: 6px;
  background: linear-gradient(180deg, #fff, #7aa8ff);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.bs-sub { color: #4a5a80; font-size: 11px; letter-spacing: 4px; margin-top: 2px; }
.bs-time { position: absolute; left: 0; top: 8px; color: #8a97b8; font-size: 15px; }
.bs-exit {
  position: absolute; right: 0; top: 8px;
  background: transparent; border: 1px solid #263352; color: #8a97b8;
  border-radius: 4px; padding: 4px 12px; cursor: pointer;
}
.bs-kpis { display: flex; gap: 14px; margin-bottom: 14px; }
.bs-kpi {
  flex: 1; text-align: center; padding: 14px 8px;
  background: linear-gradient(180deg, rgba(61,139,255,.08), rgba(18,26,46,.6));
  border: 1px solid #263352; border-radius: 10px;
}
.bs-kpi .v { font-size: 30px; font-weight: 800; color: #e5ecff; }
.bs-kpi .l { color: #8a97b8; font-size: 13px; margin-top: 4px; }
.bs-grid { display: flex; gap: 14px; flex: 1; min-height: 0; }
.bs-col { flex: 1; display: flex; flex-direction: column; gap: 14px; min-width: 0; }
.bs-col-mid { flex: 1.3; }
.bs-panel {
  background: rgba(18, 26, 46, .8);
  border: 1px solid #263352; border-radius: 10px;
  padding: 12px 14px; flex: 1; display: flex; flex-direction: column; min-height: 0;
}
.bs-panel h3 {
  margin: 0 0 8px; font-size: 15px; color: #c8d4f0;
  padding-left: 8px; border-left: 3px solid var(--accent);
}
.bs-chart { flex: 1; min-height: 200px; }
.bs-table { flex: 1; overflow: auto; }
.bs-table table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.bs-table th { color: #8a97b8; text-align: left; padding: 6px 8px; border-bottom: 1px solid #263352; }
.bs-table td { padding: 7px 8px; border-bottom: 1px solid #1a2440; color: #c8d4f0; }
.ellipsis { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 140px; }
.bs-scroll { flex: 1; overflow: hidden; }
.empty-hint { color: #4a5a80; text-align: center; padding: 24px 0; font-size: 13px; }
/* 无缝滚动：内容两倍拼接 + translateY 上移一半 */
.scroll-viewport { height: 100%; overflow: hidden; }
.scroll-inner.is-anim { animation: bs-scroll-up 18s linear infinite; }
.scroll-inner.is-anim:hover { animation-play-state: paused; }
@keyframes bs-scroll-up {
  0% { transform: translateY(0); }
  100% { transform: translateY(-50%); }
}
/* 滚动行通用样式 */
.feed-rank {
  width: 20px; height: 20px; border-radius: 4px; flex-shrink: 0;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 700; color: #0b1020;
  background: #3d5a8f;
}
.feed-rank.rank-1 { background: #e8b004; }
.feed-rank.rank-2 { background: #5b8def; }
.feed-rank.rank-3 { background: #5b8def; }
.feed-bar {
  flex: 1; height: 8px; border-radius: 4px;
  background: #1a2440; overflow: hidden; margin: 0 4px;
}
.feed-bar-in {
  display: block; height: 100%; border-radius: 4px;
  background: linear-gradient(90deg, #2f6fed, #5b8def);
}
.feed-num { color: #e5ecff; font-weight: 700; flex-shrink: 0; min-width: 36px; text-align: right; }
.feed-pct { color: #8a97b8; font-size: 11px; flex-shrink: 0; width: 42px; text-align: right; }
.st-scroll { margin-top: 10px; max-height: 140px; }
.bs-feed { display: flex; align-items: center; gap: 8px; padding: 8px 0; border-bottom: 1px solid #1a2440; font-size: 12.5px; }
.feed-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.feed-tag { color: #7aa8ff; flex-shrink: 0; }
.feed-txt { color: #c8d4f0; flex: 1; }
.feed-time { color: #4a5a80; flex-shrink: 0; }
.st-row { display: flex; justify-content: space-between; margin-top: 10px; color: #8a97b8; font-size: 13px; }
</style>
