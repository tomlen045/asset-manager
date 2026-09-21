<template>
  <div>
    <h1 class="page-title"><BackButton />报废预测 · 经济寿命分析</h1>

    <el-row :gutter="16" style="margin-bottom:16px">
      <el-col :span="6">
        <div class="stat-card" style="border-top:3px solid var(--red)">
          <div class="label">🔴 建议报废</div>
          <div class="value" style="color:var(--red)">{{ stat.red ?? '-' }}</div>
          <div class="sub">继续维修不经济</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card" style="border-top:3px solid var(--yellow)">
          <div class="label">🟡 维修预警</div>
          <div class="value" style="color:var(--yellow)">{{ stat.yellow ?? '-' }}</div>
          <div class="sub">维修成本偏高，加强监控</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card" style="border-top:3px solid var(--green)">
          <div class="label">🟢 健康在用</div>
          <div class="value" style="color:var(--green)">{{ stat.green ?? '-' }}</div>
          <div class="sub">经济性正常</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card" style="border-top:3px solid var(--accent);cursor:pointer"
             @click="openCmDrawer">
          <div class="label">📋 预警处置对策</div>
          <div class="value" style="color:var(--accent)">{{ cmSummary.replace_total ?? '-' }}</div>
          <div class="sub">分批更换建议 · 点击查看对策方案 →</div>
        </div>
      </el-col>
    </el-row>

    <!-- 预警处置对策报告抽屉 -->
    <el-drawer v-model="cmDrawer" title="📋 预警资产处置对策建议（财务经济师口径）" size="46%" @opened="renderCmCharts">
      <template v-if="cm">
        <el-alert type="info" :closable="false" style="margin-bottom:14px">
          处置对象共 <b>{{ cm.replace_total }}</b> 台（建议报废 {{ cm.total_red }} + 维修预警 {{ cm.total_yellow }}），
          按经济性分级给出对策，红色资产按残值由低到高分三批处置以平滑预算。
        </el-alert>

        <h4 style="margin:10px 0 8px">① 分批更换计划</h4>
        <div style="display:flex;gap:14px;flex-wrap:wrap">
          <div ref="cmPie" style="flex:1;min-width:200px;height:220px"></div>
          <div ref="cmBar" style="flex:1.4;min-width:260px;height:220px"></div>
        </div>
        <el-table :data="cm.batches" size="small" border style="margin-top:10px">
          <el-table-column prop="label" label="批次" min-width="140" header-align="center" />
          <el-table-column prop="count" label="台数" width="70" align="right" header-align="center" />
          <el-table-column label="净值合计" min-width="110" align="right" header-align="center">
            <template #default="{ row }">¥{{ (row.net_value / 10000).toFixed(1) }} 万</template>
          </el-table-column>
          <el-table-column label="原值合计" min-width="110" align="right" header-align="center">
            <template #default="{ row }">¥{{ (row.orig_value / 10000).toFixed(1) }} 万</template>
          </el-table-column>
          <el-table-column prop="window" label="处置窗口" min-width="110" header-align="center" />
          <el-table-column label="清单" width="96" header-align="center">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="showBatch(row)">查看清单</el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 批次全量清单对话框 -->
        <el-dialog v-model="batchDialog" :title="batchRow ? batchRow.label + ' · 处置清单（' + batchRow.count + ' 台 · ' + batchRow.window + '）' : ''"
                   width="78%" top="6vh" append-to-body>
          <template #header="{ close }">
            <div style="display:flex;align-items:center;justify-content:space-between;padding-right:40px">
              <span role="heading" style="font-size:16px;font-weight:600">
                {{ batchRow ? batchRow.label + ' · 处置清单（' + batchRow.count + ' 台 · ' + batchRow.window + '）' : '' }}
              </span>
              <el-button type="primary" size="small" @click="exportBatch(batchRow)">📤 导出明细</el-button>
            </div>
          </template>
          <el-table v-if="batchRow" :data="batchRow.items" size="small" border max-height="520">
            <el-table-column type="index" label="#" width="50" header-align="center" />
            <el-table-column prop="display_tag" label="资产编号" min-width="110" header-align="center" />
            <el-table-column prop="name" label="名称" min-width="140" show-overflow-tooltip header-align="center" />
            <el-table-column prop="category" label="类别" min-width="120" show-overflow-tooltip header-align="center" />
            <el-table-column prop="department" label="部门" min-width="130" show-overflow-tooltip header-align="center" />
            <el-table-column label="已用年限" width="90" align="right" header-align="center">
              <template #default="{ row }">{{ row.used_years ? Number(row.used_years).toFixed(1) + '年' : '—' }}</template>
            </el-table-column>
            <el-table-column label="净值" min-width="100" align="right" header-align="center">
              <template #default="{ row }">¥{{ Number(row.current_value || 0).toLocaleString() }}</template>
            </el-table-column>
            <el-table-column label="原值" min-width="100" align="right" header-align="center">
              <template #default="{ row }">¥{{ Number(row.original_value || 0).toLocaleString() }}</template>
            </el-table-column>
          </el-table>
        </el-dialog>

        <h4 style="margin:18px 0 8px">② 按已用年限分布（处置对象）</h4>
        <el-table :data="cm.by_age" size="small" border>
          <el-table-column prop="bucket" label="年限段" min-width="90" header-align="center" />
          <el-table-column prop="red" label="🔴 建议报废" width="100" align="right" header-align="center" />
          <el-table-column prop="yellow" label="🟡 维修预警" width="100" align="right" header-align="center" />
          <el-table-column prop="total" label="小计" width="70" align="right" header-align="center" />
          <el-table-column label="原值合计" min-width="110" align="right" header-align="center">
            <template #default="{ row }">¥{{ (row.orig_value / 10000).toFixed(1) }} 万</template>
          </el-table-column>
        </el-table>

        <h4 style="margin:18px 0 8px">③ 对策类型分布（按首条对策归类）</h4>
        <el-table :data="cm.by_action" size="small" border>
          <el-table-column prop="action" label="对策类型" min-width="240" show-overflow-tooltip />
          <el-table-column prop="count" label="台数" width="80" align="right" header-align="center" />
        </el-table>

        <h4 style="margin:18px 0 8px">④ 第一批处置清单（净值最低、损失最小优先）</h4>
        <div style="line-height:2;font-size:13px;color:var(--text-2)">
          <template v-for="b in cm.batches" :key="b.label">
            <div v-if="b.samples && b.samples.length">
              <b>{{ b.label }}（{{ b.window }}）示例：</b>{{ b.samples.join('、') }}<span v-if="b.count > 5"> 等 {{ b.count }} 台</span>
            </div>
          </template>
        </div>
      </template>
      <el-empty v-else description="对策数据计算中，约 8 分钟后自动就绪（首次访问触发全量分析）" />
    </el-drawer>

    <el-card>
      <!-- 筛选区 -->
      <div style="display:flex;gap:10px;margin-bottom:14px;flex-wrap:wrap">
        <el-input v-model="q.kw" placeholder="编号/序列号/品牌/型号" style="width:230px" clearable
                  @keyup.enter="onFilter" @clear="onFilter" />
        <el-select v-model="q.health" placeholder="健康度" style="width:110px" clearable @change="onFilter">
          <el-option label="🔴 报废" value="red" />
          <el-option label="🟡 预警" value="yellow" />
          <el-option label="🟢 正常" value="green" />
        </el-select>
        <el-select v-model="q.category" placeholder="类别" style="width:130px" clearable filterable @change="onFilter">
          <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
        </el-select>
        <el-cascader v-model="deptPath" :options="deptTree" placeholder="部门(可多选/一二三级)"
                     style="width:280px" clearable filterable collapse-tags collapse-tags-tooltip
                     :props="{ multiple: true, checkStrictly: true, label: 'name', value: 'id', children: 'children' }"
                     @change="onDeptChange" />
        <el-button @click="advOpen = !advOpen">{{ advOpen ? '收起 ▲' : '更多筛选 ▼' }}</el-button>
        <el-button type="primary" @click="onFilter">查询</el-button>
        <el-button @click="colMenu.open($event.target, COLS, 'am-cols-hidden-economy', hidden, h => { hidden = h })">⚙ 显示列</el-button>
        <div style="flex:1"></div>
        <el-button @click="resetFilters" v-if="hasActiveFilters">重置</el-button>
        <el-button @click="exportExcel" :loading="exporting">📤 导出Excel</el-button>
      </div>

      <!-- 更多筛选（折叠区） -->
      <div v-if="advOpen" style="display:flex;gap:10px;margin-bottom:14px;flex-wrap:wrap;
                                padding:12px;background:var(--bg-page);border-radius:8px;
                                border:1px dashed var(--border)">
        <el-input v-model="q.net_min" placeholder="净值≥" style="width:110px" clearable @keyup.enter="onFilter" @clear="onFilter" />
        <el-input v-model="q.net_max" placeholder="净值≤" style="width:110px" clearable @keyup.enter="onFilter" @clear="onFilter" />
        <el-input v-model="q.orig_min" placeholder="原值≥" style="width:110px" clearable @keyup.enter="onFilter" @clear="onFilter" />
        <el-input v-model="q.orig_max" placeholder="原值≤" style="width:110px" clearable @keyup.enter="onFilter" @clear="onFilter" />
        <el-input v-model="q.used_min" placeholder="已用年限≥" style="width:110px" clearable @keyup.enter="onFilter" @clear="onFilter" />
        <el-select v-model="q.ordering" placeholder="排序方式" style="width:150px" clearable @change="onFilter">
          <el-option label="净值高→低" value="-current_value" />
          <el-option label="净值低→高" value="current_value" />
          <el-option label="原值高→低" value="-original_value" />
          <el-option label="已用年限最长" value="-used_years" />
          <el-option label="经济寿命最短" value="econ_life" />
        </el-select>
      </div>

      <el-table border :data="pageItems" v-loading="loading" stripe
                @header-contextmenu="onHeaderContextMenu" @header-dragend="onHeaderDragend">
        <el-table-column v-if="!hidden.includes('health_level')" label="健康度" width="90" header-align="center">
          <template #default="{ row }">
            <span :style="{ color: color(row.health_level), fontSize: '18px' }">●</span>
            {{ text(row.health_level) }}
          </template>
        </el-table-column>
        <el-table-column v-if="!hidden.includes('display_tag')" prop="display_tag" label="资产编号" width="130"  header-align="center" />
        <el-table-column v-if="!hidden.includes('category')" prop="category" label="类别" width="90"  header-align="center" />
        <el-table-column v-if="!hidden.includes('name')" prop="name" label="名称" min-width="140"  header-align="center" />
        <el-table-column v-if="!hidden.includes('original_value')" label="原值" width="90" align="right" header-align="center">
          <template #default="{ row }">¥{{ fmt(row.original_value) }}</template>
        </el-table-column>
        <el-table-column v-if="!hidden.includes('current_value')" label="净值" width="95" align="right" header-align="center">
          <template #default="{ row }">¥{{ fmt(row.current_value) }}</template>
        </el-table-column>
        <el-table-column v-if="!hidden.includes('repair_total')" label="累计维修" width="100" align="right" header-align="center">
          <template #default="{ row }">
            <span :style="{ color: row.repair_total > row.original_value * 0.5 ? 'var(--yellow)' : '' }">
              ¥{{ fmt(row.repair_total) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column v-if="!hidden.includes('used_years')" label="已用/年限" width="95" header-align="center">
          <template #default="{ row }">{{ row.used_years }}/{{ row.useful_life }}</template>
        </el-table-column>
        <el-table-column v-if="!hidden.includes('econ_life')" label="经济寿命" width="90" header-align="center">
          <template #default="{ row }">
            {{ row.econ_life ? row.econ_life + '年' : '—' }}
          </template>
        </el-table-column>
        <el-table-column v-if="!hidden.includes('suggestion')" prop="suggestion" label="系统建议" min-width="200" show-overflow-tooltip  header-align="center" />
        <el-table-column label="操作" width="80" fixed="right" header-align="center">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="$router.push(`/assets/${row.id}`)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
      <ColMenu ref="colMenu" />

      <el-pagination style="margin-top:14px;justify-content:flex-end"
                     layout="total, prev, pager, next, sizes"
                     :total="filtered.length" :page-size="pageSize"
                     :current-page="page" :page-sizes="[20, 50, 100]"
                     @current-change="p => page = p"
                     @size-change="s => { pageSize = s; page = 1 }" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import BackButton from '../components/BackButton.vue'
import { ElMessage } from 'element-plus'
import api from '../api'
import ColMenu from '../components/ColMenu.vue'
import { useTableCols } from '../composables/useTableCols'

const stat = ref({})
const allItems = ref([])
const cmDrawer = ref(false)
import * as echarts from 'echarts'
function openCmDrawer() {
  cmDrawer.value = true
  nextTick(() => {
    // 抽屉展开动画 ~300ms，容器有尺寸后重试渲染（最多 2.4s）
    let tries = 0
    const t = setInterval(() => {
      tries++
      const el = cmPie.value && cmBar.value
      const ready = el && cmPie.value.offsetWidth > 50 && cmBar.value.offsetWidth > 50
      if (ready || tries > 12) {
        clearInterval(t)
        renderCmCharts()
      }
    }, 200)
  })
}
const cmSummaryFull = ref(null)
// 对策汇总【跟随筛选联动】：基于当前筛选后的 filtered 即时计算，筛选变 → 卡片/图表/清单全变
const batchDialog = ref(false)
const batchRow = ref(null)
const cmPie = ref(), cmBar = ref()
let cmChartsInited = false

function showBatch(row) {
  batchRow.value = row
  batchDialog.value = true
}

function exportBatch(row) {
  if (!row || !row.items || !row.items.length) return
  const headers = ['序号', '资产编号', '名称', '类别', '部门', '已用年限', '净值(元)', '原值(元)', '处置窗口']
  const rows = row.items.map((x, i) => [
    i + 1, x.display_tag || '', x.name || '', x.category || '', x.department || '',
    x.used_years != null ? Number(x.used_years).toFixed(2) : '',
    Number(x.current_value || 0).toFixed(2), Number(x.original_value || 0).toFixed(2),
    row.window || '',
  ])
  const csv = [headers, ...rows]
    .map(r => r.map(v => '"' + String(v).replace(/"/g, '""') + '"').join(','))
    .join('\r\n')
  // UTF-8 BOM 防止 Excel 打开乱码
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = row.label.replace(/（.*）/, '') + '-处置清单-' + row.count + '台.csv'
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success('已导出 ' + row.count + ' 条明细')
}

let _cmChartInsts = []
function disposeCmCharts() { _cmChartInsts.forEach(c => c.dispose()); _cmChartInsts = [] }
function renderCmCharts() {
  try {
    if (!cmDrawer.value) throw new Error('drawer closed')
    if (!cm.value || !cm.value.batches || !cm.value.batches.length) throw new Error('batches empty')
    if (!cmPie.value || !cmBar.value) throw new Error('refs null')
    if (cmPie.value.offsetWidth < 50 || cmBar.value.offsetWidth < 50) {
      throw new Error('width=' + cmPie.value.offsetWidth + '/' + cmBar.value.offsetWidth)
    }
    const ec = echarts
    if (_cmChartInsts.length === 2) {
      _cmChartInsts[0].setOption({
        tooltip: { trigger: 'item', formatter: '{b}<br/>{c} 台（{d}%）' },
        legend: { bottom: 0, itemWidth: 12, itemHeight: 12, textStyle: { fontSize: 11 } },
        series: [{
          type: 'pie', radius: ['38%', '64%'], center: ['50%', '44%'],
          label: { formatter: '{c}台' },
          data: cm.value.batches.map(b => ({
            name: b.label.replace(/（.*）/, ''),
            value: b.count,
            itemStyle: { color: ['#e5455e', '#d98f1f', '#3477f6'][cm.value.batches.indexOf(b) % 3] }
          }))
        }]
      })
      _cmChartInsts[1].setOption({
        tooltip: { trigger: 'axis' },
        legend: { bottom: 0, itemWidth: 12, itemHeight: 12, textStyle: { fontSize: 11 } },
        xAxis: { type: 'category', data: cm.value.batches.map(b => b.label.replace(/（.*）/, '')) },
        series: [
          { name: '净值合计', type: 'bar', barWidth: 26, itemStyle: { color: '#e5455e' },
            data: cm.value.batches.map(b => +(b.net_value / 10000).toFixed(1)) },
          { name: '原值合计', type: 'bar', barWidth: 26, itemStyle: { color: '#b8bcc4' },
            data: cm.value.batches.map(b => +(b.orig_value / 10000).toFixed(1)) },
        ]
      })
      return
    }
    const pie = ec.init(cmPie.value); _cmChartInsts.push(pie)
    pie.setOption({
      tooltip: { trigger: 'item', formatter: '{b}<br/>{c} 台（{d}%）' },
      legend: { bottom: 0, itemWidth: 12, itemHeight: 12, textStyle: { fontSize: 11 } },
      series: [{
        type: 'pie', radius: ['38%', '64%'], center: ['50%', '44%'],
        label: { formatter: '{c}台' },
        data: cm.value.batches.map(b => ({
          name: b.label.replace(/（.*）/, ''),
          value: b.count,
          itemStyle: { color: ['#e5455e', '#d98f1f', '#3477f6'][cm.value.batches.indexOf(b) % 3] }
        }))
      }]
    })
    const bar = ec.init(cmBar.value); _cmChartInsts.push(bar)
    bar.setOption({
      tooltip: { trigger: 'axis' },
      legend: { bottom: 0, itemWidth: 12, itemHeight: 12, textStyle: { fontSize: 11 } },
      grid: { left: 60, right: 10, top: 24, bottom: 42 },
      xAxis: { type: 'category', data: cm.value.batches.map(b => b.label.replace(/（.*）/, '')),
               axisLabel: { fontSize: 11 } },
      yAxis: { type: 'value', name: '万元', axisLabel: { fontSize: 11 } },
      series: [
        { name: '净值合计', type: 'bar', barWidth: 26, itemStyle: { color: '#e5455e' },
          data: cm.value.batches.map(b => +(b.net_value / 10000).toFixed(1)) },
        { name: '原值合计', type: 'bar', barWidth: 26, itemStyle: { color: '#b8bcc4' },
          data: cm.value.batches.map(b => +(b.orig_value / 10000).toFixed(1)) },
      ]
    })
    cmChartsInited = true
  } catch (e) {
    console.warn('[cm-charts]', e.message)
    if (cmPie.value) cmPie.value.innerText = '⚠ 图表: ' + e.message
  }
}
const cmSummary = computed(() => cm.value || { replace_total: 0 })
const loading = ref(false)
const categories = ref([]), departments = ref([])
const deptTree = ref([]), deptPath = ref([])
// 节点id → 子树覆盖的部门全名集合（从 dept_tree 接口构建）
const deptNodeMap = ref({})
const q = ref({ kw: '', health: null, category: null, department: null,
                net_min: '', net_max: '', orig_min: '', orig_max: '',
                used_min: '', ordering: null })
const advOpen = ref(false)
const hasActiveFilters = computed(() =>
  !!(q.value.kw || q.value.health || q.value.category || q.value.department ||
     q.value.net_min || q.value.net_max || q.value.orig_min || q.value.orig_max ||
     q.value.used_min || q.value.ordering))
const page = ref(1), pageSize = ref(20)
const exporting = ref(false)

const COLS = [{ prop: 'health_level', label: '健康度' }, { prop: 'display_tag', label: '资产编号' }, { prop: 'category', label: '类别' }, { prop: 'name', label: '名称' }, { prop: 'original_value', label: '原值' }, { prop: 'current_value', label: '净值' }, { prop: 'repair_total', label: '累计维修' }, { prop: 'used_years', label: '已用/年限' }, { prop: 'econ_life', label: '经济寿命' }, { prop: 'suggestion', label: '系统建议' }, { prop: 'countermeasures', label: '处置对策' }]
const { hidden, colMenu, onHeaderContextMenu, onHeaderDragend } = useTableCols('economy', COLS)

const fmt = n => n == null ? '-' : Number(n).toLocaleString('zh-CN', { maximumFractionDigits: 0 })
const color = l => ({ red: 'var(--red)', yellow: 'var(--yellow)', green: 'var(--green)' }[l])
const text = l => ({ red: '报废', yellow: '预警', green: '正常' }[l] || l)

const filtered = computed(() => {
  const { kw, health, category } = q.value
  const catName = (categories.value.find(c => c.id === category) || {}).name
  // 多选部门：选中节点子树 = 部门名以节点完整路径为前缀（含相等）的并集
  let deptPrefixes = null
  if (deptPath.value && deptPath.value.length) {
    deptPrefixes = (deptPath.value || [])
      .map(path => deptNodeMap.value[path[path.length - 1]])
      .filter(Boolean)
  }
  let out = allItems.value.filter(it => {
    if (health && it.health_level !== health) return false
    if (catName && it.category !== catName) return false
    if (deptPrefixes && !deptPrefixes.some(pfx => (it.department || '').startsWith(pfx))) return false
    if (kw) {
      const s = `${it.display_tag} ${it.asset_tag} ${it.name}`.toLowerCase()
      if (!s.includes(kw.toLowerCase())) return false
    }
    if (q.value.net_min && !(it.current_value >= Number(q.value.net_min))) return false
    if (q.value.net_max && !(it.current_value <= Number(q.value.net_max))) return false
    if (q.value.orig_min && !(it.original_value >= Number(q.value.orig_min))) return false
    if (q.value.orig_max && !(it.original_value <= Number(q.value.orig_max))) return false
    if (q.value.used_min && !((it.used_years || 0) >= Number(q.value.used_min))) return false
    return true
  })
  const ord = q.value.ordering
  if (ord) {
    const key = ord.replace('-', '')
    out = out.slice().sort((a, b) => {
      const va = a[key] ?? -Infinity, vb = b[key] ?? -Infinity
      return ord.startsWith('-') ? vb - va : va - vb
    })
  }
  return out
})

const cm = computed(() => {
  const rows = filtered.value.filter(x => x.health_level !== 'green')
  const bucketOf = u => u <= 5 ? '0-5年' : u <= 8 ? '5-8年' : u <= 10 ? '8-10年' : '10年以上'
  const bucketOrder = ['0-5年', '5-8年', '8-10年', '10年以上']
  const byAgeMap = {}
  const cmCounter = {}
  for (const x of rows) {
    const b = bucketOf(x.used_years || 0)
    const d = byAgeMap[b] || (byAgeMap[b] = { red: 0, yellow: 0, value: 0 })
    d[x.health_level === 'red' ? 'red' : 'yellow']++
    d.value += Number(x.original_value || 0)
    const key = (x.countermeasures && x.countermeasures[0] || '常规监控').slice(0, 14)
    cmCounter[key] = (cmCounter[key] || 0) + 1
  }
  const by_age = bucketOrder.filter(b => byAgeMap[b]).map(b => ({
    bucket: b, red: byAgeMap[b].red, yellow: byAgeMap[b].yellow,
    total: byAgeMap[b].red + byAgeMap[b].yellow,
    orig_value: +byAgeMap[b].value.toFixed(2),
  }))
  const by_action = Object.entries(cmCounter).sort((a, b) => b[1] - a[1])
    .map(([action, count]) => ({ action, count }))
  const reds = [...rows.filter(x => x.health_level === 'red')]
    .sort((a, b) => Number(a.current_value || 0) - Number(b.current_value || 0))
  const mk = (lst, label, window2) => lst.length ? ({
    label, count: lst.length, window: window2,
    net_value: +lst.reduce((s, x) => s + Number(x.current_value || 0), 0).toFixed(2),
    orig_value: +lst.reduce((s, x) => s + Number(x.original_value || 0), 0).toFixed(2),
    samples: lst.slice(0, 5).map(x => x.display_tag),
    items: lst.map(x => ({
      display_tag: x.display_tag, name: (x.name || '').slice(0, 24),
      category: x.category || '', department: x.department || '',
      used_years: x.used_years, current_value: x.current_value,
      original_value: x.original_value,
    })),
  }) : null
  const n = reds.length
  const batches = [
    mk(reds.slice(0, Math.ceil(n / 3)), '第一批（立即处置）', '0-3个月'),
    mk(reds.slice(Math.ceil(n / 3), Math.ceil(n * 2 / 3)), '第二批（纳入季度计划）', '3-6个月'),
    mk(reds.slice(Math.ceil(n * 2 / 3)), '第三批（年度预算安排）', '6-12个月'),
  ].filter(Boolean)
  return {
    total_red: reds.length,
    total_yellow: rows.length - reds.length,
    replace_total: rows.length,
    by_age, by_action, batches,
  }
})

watch(cm, () => {
  if (!cmDrawer.value) return
  if (_cmChartInsts.length === 2) { nextTick(renderCmCharts); return }   // 已有实例：直接更新
  openCmDrawer()                                                          // 首次：走重试挂载
})

const pageItems = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filtered.value.slice(start, start + pageSize.value)
})

function onFilter() { page.value = 1 }

function onDeptChange() { page.value = 1 }

function resetFilters() {
  q.value = { kw: '', health: null, category: null, department: null,
              net_min: '', net_max: '', orig_min: '', orig_max: '',
              used_min: '', ordering: null }
  deptPath.value = []
  page.value = 1
}

async function exportExcel() {
  exporting.value = true
  try {
    const resp = await api.get('/export/scrappage/', { responseType: 'blob' })
    const url = URL.createObjectURL(resp)
    const a = document.createElement('a')
    a.href = url
    a.download = '报废预测.xlsx'
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('已导出')
  } finally {
    exporting.value = false
  }
}

onUnmounted(() => disposeCmCharts())
onMounted(async () => {
  loading.value = true
  try {
    const [d, c, dt] = await Promise.all([
      api.get('/dashboard/scrappage/'),
      api.get('/categories/?page_size=100'),
      api.get('/dept_tree/'),
    ])
    stat.value = { red: d.red, yellow: d.yellow, green: d.green }
    allItems.value = d.items
    cmSummaryFull.value = d.countermeasure_summary || null
    categories.value = c.results || c
    deptTree.value = dt.tree || []
    // 构建 节点id → 该节点的完整路径（用于前缀匹配子树部门）
    const nodeMap = {}
    function collect(node, prefix) {
      nodeMap[node.id] = prefix ? `${prefix} ${node.name}` : node.name
      for (const ch of (node.children || [])) collect(ch, nodeMap[node.id])
    }
    for (const root of deptTree.value) collect(root, '')
    deptNodeMap.value = nodeMap
  } finally {
    loading.value = false
  }
})
</script>
