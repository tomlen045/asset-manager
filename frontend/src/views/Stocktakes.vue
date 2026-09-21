<template>
  <div>
    <h1 class="page-title">资产盘点<el-button style="margin-left:12px" @click="exportStocktakes">📤 导出明细</el-button></h1>

    <!-- 任务列表 -->
    <el-card v-if="!current">
      <div style="display:flex;gap:10px;margin-bottom:14px">
        <el-button @click="colMenu.open($event.target, COLS, 'am-cols-hidden-stocktakes', hidden, h => { hidden = h })">⚙ 显示列</el-button>
        <el-button type="primary" @click="dialog = true">+ 新建盘点任务</el-button>
      </div>
      <el-table border :data="list" v-loading="loading" stripe
                @header-contextmenu="onHeaderContextMenu" @header-dragend="onHeaderDragend">
        <el-table-column v-if="!hidden.includes('name')" prop="name" label="任务名称" min-width="180"  header-align="center" />
        <el-table-column v-if="!hidden.includes('scope')" label="范围" width="100" header-align="center">
          <template #default="{ row }">{{ (row.stats && row.stats.total) ?? '-' }} 台</template>
        </el-table-column>
        <el-table-column v-if="!hidden.includes('status')" label="状态" width="90" header-align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'ongoing' ? 'warning' : 'success'" size="small">
              {{ row.status === 'ongoing' ? '进行中' : '已完成' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="!hidden.includes('found')" label="进度" width="130" header-align="center">
          <template #default="{ row }">
            <el-progress :percentage="(row.stats && row.stats.progress) || 0" :stroke-width="10" />
          </template>
        </el-table-column>
        <el-table-column v-if="!hidden.includes('created_at')" prop="created_at" label="创建时间" width="160" header-align="center">
          <template #default="{ row }">{{ (row.created_at || '').slice(0, 16).replace('T', ' ') }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right" header-align="center">
          <template #default="{ row }">
            <el-button v-if="row.status === 'ongoing'" link type="primary" size="small"
                       @click="openTask(row)">进入盘点</el-button>
            <el-button link size="small" @click="showDiff(row)">差异报表</el-button>
            <el-button v-if="row.status === 'ongoing'" link type="warning" size="small"
                       :disabled="true" @click="finishTask">结束盘点</el-button>
          </template>
        </el-table-column>
      </el-table>
      <ColMenu ref="colMenu" />
    </el-card>

    <!-- 扫码盘点 -->
    <el-card v-else>
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span>{{ current.name }} — 扫码盘点</span>
          <div>
            <el-button size="small" @click="current = null; load()">返回列表</el-button>
            <el-button size="small" type="warning" @click="finishTask">结束盘点</el-button>
          </div>
        </div>
      </template>
      <div style="display:flex;gap:16px;flex-wrap:wrap">
        <div style="flex:1;min-width:300px">
          <el-input v-model="scanCode" placeholder="扫描/输入 资产编号或序列号后回车"
                    size="large" @keyup.enter="doScan" clearable autofocus>
            <template #append><el-button @click="doScan">确认</el-button></template>
          </el-input>
          <el-alert v-if="lastScan" :title="lastScan.title" :type="lastScan.ok ? 'success' : 'error'"
                    :description="lastScan.desc" show-icon style="margin-top:14px" />
          <el-descriptions title="任务进度" :column="3" style="margin-top:14px">
            <el-descriptions-item label="已盘">{{ st.found ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="未盘">{{ st.missing ?? '?' }}</el-descriptions-item>
            <el-descriptions-item label="账外">{{ st.unexpected ?? 0 }}</el-descriptions-item>
          </el-descriptions>
        </div>
        <div style="flex:1;min-width:300px">
          <el-alert type="info" :closable="false"
                    title="账实核对规则"
                    description="扫描范围内资产→计入已盘；扫描范围外资产→记入账外清单；结束后生成差异报表。" />
        </div>
      </div>
    </el-card>

    <!-- 新建任务 -->
    <el-dialog v-model="dialog" title="新建盘点任务" width="520">
      <el-form label-width="100">
        <el-form-item label="任务名称">
          <el-input v-model="form.name" placeholder="如：2026年度生产终端盘点" />
        </el-form-item>
        <el-form-item label="部门">
          <el-select v-model="form.department" placeholder="全部部门" clearable filterable style="width:100%">
            <el-option v-for="d in departments" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="类别">
          <el-select v-model="form.category" placeholder="全部类别" clearable filterable style="width:100%">
            <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status" placeholder="默认在用" clearable style="width:100%">
            <el-option label="在用" value="in_use" />
            <el-option label="在库" value="in_stock" />
            <el-option label="闲置" value="idle" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" @click="createTask" :loading="saving">创建</el-button>
      </template>
    </el-dialog>

    <!-- 差异报表 -->
    <el-dialog v-model="diffVisible" :title="`差异报表 — ${diffName}`" width="760">
      <el-tabs>
        <el-tab-pane :label="`未盘到 (${diff.missing || 0})`">
          <el-table :data="diff.missing_list || []" size="small" max-height="320">
            <el-table-column prop="display_tag" label="资产编号" width="130"  header-align="center" />
            <el-table-column prop="sn" label="序列号" width="120"  header-align="center" />
            <el-table-column prop="brand" label="品牌" width="100"  header-align="center" />
            <el-table-column prop="model_spec" label="型号" min-width="140"  header-align="center" />
            <el-table-column label="状态" width="80" header-align="center">
            <template #default="{ row }">{{ { in_use: '在用', in_stock: '在库', repairing: '维修中', idle: '闲置', scrapped: '已报废' }[row.status] || row.status }}</template>
          </el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane :label="`账外 (${diff.unexpected || 0})`">
          <el-table :data="diff.unexpected_list || []" size="small" max-height="320">
            <el-table-column prop="display_tag" label="资产编号" width="130"  header-align="center" />
            <el-table-column prop="asset__sn" label="序列号" width="120"  header-align="center" />
            <el-table-column prop="asset__brand" label="品牌" width="100"  header-align="center" />
            <el-table-column prop="asset__model_spec" label="型号" min-width="140"  header-align="center" />
            <el-table-column prop="found_location" label="实盘位置" width="120"  header-align="center" />
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'
import ColMenu from '../components/ColMenu.vue'
import { useTableCols } from '../composables/useTableCols'

const list = ref([])

function exportStocktakes() {
  const headers = ['任务名称', '创建时间', '状态']
  const rows = list.value.map((x, i) => [
    i + 1, x.name || '', (x.created_at || '').slice(0, 19).replace('T', ' '), x.status_text || x.status || '',
  ])
  const csv = [headers, ...rows].map(r => r.map(v => '"' + String(v).replace(/"/g, '""') + '"').join(',')).join('\r\n')
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = '资产盘点-' + new Date().toISOString().slice(0, 10) + '.csv'
  a.click()
  URL.revokeObjectURL(url)
}
const loading = ref(false)
const current = ref(null), st = ref({})
const scanCode = ref(''), lastScan = ref(null)
const dialog = ref(false), saving = ref(false)
const departments = ref([]), categories = ref([])
const form = reactive({ name: '', department: null, category: null, status: null })
const diffVisible = ref(false), diffName = ref(''), diff = ref({})

const COLS = [{ prop: 'name', label: '任务名称' }, { prop: 'scope', label: '范围' }, { prop: 'status', label: '状态' }, { prop: 'found', label: '进度' }, { prop: 'created_at', label: '创建时间' }]
const { hidden, colMenu, onHeaderContextMenu, onHeaderDragend } = useTableCols('stocktakes', COLS)

async function load() {
  loading.value = true
  try {
    const r = await api.get('/stocktakes/')
    list.value = r.results || r
  } finally { loading.value = false }
}

async function createTask() {
  if (!form.name) return ElMessage.warning('请填写任务名称')
  saving.value = true
  try {
    const custom_filter = {}
    if (form.department) custom_filter.department = form.department
    if (form.category) custom_filter.category = form.category
    if (form.status) custom_filter.status = form.status
    await api.post('/stocktakes/', { name: form.name, custom_filter })
    ElMessage.success('已创建')
    dialog.value = false
    form.name = ''
    load()
  } finally { saving.value = false }
}

async function openTask(row) {
  current.value = row
  st.value = { found: row.stats?.found ?? 0, unexpected: row.stats?.unexpected ?? 0,
               total: row.stats?.total ?? 0 }
  lastScan.value = null
  scanCode.value = ''
}

async function doScan() {
  if (!scanCode.value || !current.value) return
  try {
    const r = await api.post(`/stocktakes/${current.value.id}/scan/`, { code: scanCode.value.trim() })
    if (r.result === 'unexpected') {
      lastScan.value = { ok: false, title: '⚠️ 账外资产',
        desc: `${r.asset_tag} ${r.name} 不在本任务范围内，已记入账外清单` }
    } else if (r.result === 'found') {
      lastScan.value = { ok: true, title: '✅ 盘点成功',
        desc: `${r.asset_tag} ${r.name}` }
    } else {
      lastScan.value = { ok: false, title: 'ℹ️ ' + (r.message || r.result), desc: '' }
    }
    // 扫码后刷新当前任务进度（从列表接口取最新 stats）
    const all = await api.get('/stocktakes/')
    const fresh = (all.results || all).find(x => x.id === current.value.id)
    if (fresh) { st.value = fresh; Object.assign(current.value, fresh) }
    const idx = list.value.findIndex(x => x.id === current.value.id)
    if (idx >= 0 && fresh) Object.assign(list.value[idx], fresh)
  } catch (e) {
    lastScan.value = { ok: false, title: '❌ 未找到该资产', desc: scanCode.value }
  }
  scanCode.value = ''
}

async function finishTask() {
  await ElMessageBox.confirm('确认结束盘点？结束后将生成差异报表，任务不再可扫。', '结束盘点')
  await api.post(`/stocktakes/${current.value.id}/finish/`)
  ElMessage.success('盘点已结束')
  current.value = null
  load()
}

async function showDiff(row) {
  diffName.value = row.name
  const r = await api.get(`/stocktakes/${row.id}/diff/`)
  diff.value = r
  diffVisible.value = true
}

onMounted(async () => {
  load()
  const [c, dp] = await Promise.all([
    api.get('/categories/?page_size=100'),
    api.get('/departments/?page_size=200'),
  ])
  categories.value = c.results || c
  departments.value = dp.results || dp
})
</script>
