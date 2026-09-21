<template>
  <div>
    <h1 class="page-title">
      <BackButton />
      资产台账
      <el-tag v-if="q.statuses?.includes('scrapped')" type="warning" size="small" style="margin-left:10px" closable
              @close="q.statuses = q.statuses.filter(s => s !== 'scrapped'); load()">当前包含已报废数据</el-tag>
    </h1>

    <el-card>
      <!-- 筛选区：基础 -->
      <div style="display:flex;gap:10px;margin-bottom:14px;flex-wrap:wrap">
        <el-input v-model="q.kw" placeholder="编号/序列号/品牌/型号（空格分隔多词）" style="width:260px" clearable
                  @keyup.enter="load" @clear="load" />
        <el-select v-model="q.categories" multiple collapse-tags collapse-tags-tooltip
                   placeholder="类别(可多选)" style="width:170px" clearable filterable @change="onFilterChange">
          <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
        </el-select>
        <el-select v-model="q.statuses" multiple collapse-tags collapse-tags-tooltip
                   placeholder="状态(可多选)" style="width:140px" clearable @change="onFilterChange">
          <el-option v-for="(t, k) in statusText" :key="k" :label="t" :value="k" />
        </el-select>
        <el-cascader v-model="deptPath" :options="deptTree" placeholder="部门(可多选/一二三级)"
                     style="width:260px" clearable filterable collapse-tags collapse-tags-tooltip
                     :props="{ multiple: true, checkStrictly: true, label: 'name', value: 'id', children: 'children' }"
                     @change="onDeptChange" />
        <el-input v-model="q.made_no" placeholder="出厂编号" style="width:130px" clearable
                  @keyup.enter="load" @clear="load" />
        <el-button :type="q.terminal_type === '生产类终端' ? 'primary' : ''"
                   @click="toggleTerminal">🏭 生产类终端</el-button>
        <el-button @click="advOpen = !advOpen">
          {{ advOpen ? '收起 ▲' : '更多筛选 ▼' }}
        </el-button>
        <el-button type="primary" @click="load">查询</el-button>
        <el-button @click="colMenu.open($event.target, COLS, 'am-cols-hidden-assets', hidden, h => { hidden = h })">⚙ 显示列</el-button>
        <div style="flex:1"></div>
        <el-button @click="resetFilters" v-if="hasActiveFilters">重置</el-button>
        <el-button @click="$router.push('/assets-import')">📥 批量导入</el-button>
        <el-button @click="exportCurrent" :loading="exporting">📤 批量导出</el-button>
        <el-button type="primary" @click="openCreate">+ 新增资产</el-button>
      </div>

      <!-- 筛选区：高级 -->
      <div v-if="advOpen" style="display:flex;gap:10px;margin-bottom:14px;flex-wrap:wrap;
                                padding:12px;background:var(--bg-page);border-radius:8px;
                                border:1px dashed var(--border)">
        <el-select v-model="q.custodian" placeholder="使用人" style="width:130px" clearable filterable @change="onFilterChange">
          <el-option v-for="u in users" :key="u.id" :label="u.username" :value="u.id" />
        </el-select>
        <el-input v-model="q.net_min" placeholder="净值≥" style="width:110px" clearable @keyup.enter="load" @clear="load" />
        <el-input v-model="q.net_max" placeholder="净值≤" style="width:110px" clearable @keyup.enter="load" @clear="load" />
        <el-input v-model="q.orig_min" placeholder="原值≥" style="width:110px" clearable @keyup.enter="load" @clear="load" />
        <el-input v-model="q.orig_max" placeholder="原值≤" style="width:110px" clearable @keyup.enter="load" @clear="load" />
        <el-date-picker v-model="pdateRange" type="daterange" range-separator="至"
                        start-placeholder="投产从" end-placeholder="投产到"
                        value-format="YYYY-MM-DD" style="width:260px" @change="onPdateChange" />
        <el-select v-model="ageRanges" multiple collapse-tags collapse-tags-tooltip
                   placeholder="已用年限(可多选)" style="width:170px" clearable @change="onAgeChange">
          <el-option label="0-2年" value="0-2" />
          <el-option label="3-5年" value="3-5" />
          <el-option label="6-8年" value="6-8" />
          <el-option label="8-9年" value="8-9" />
          <el-option label="9-10年" value="9-10" />
          <el-option label="10年以上" value="10+" />
        </el-select>
        <el-select v-model="q.ordering" placeholder="排序方式" style="width:150px" clearable @change="onFilterChange">
          <el-option label="净值从高到低" value="-current_value" />
          <el-option label="净值从低到高" value="current_value" />
          <el-option label="原值从高到低" value="-original_value" />
          <el-option label="投产日期最新" value="-purchase_date" />
          <el-option label="投产日期最早" value="purchase_date" />
          <el-option label="已用年限最长" value="-used_years" />
        </el-select>
      </div>

      <!-- 列表 -->
      <el-table :data="list" v-loading="loading" stripe border @header-contextmenu="onHeaderContextMenu" @header-dragend="onHeaderDragend">
        <el-table-column v-if="!hidden.includes('display_tag')" prop="display_tag" label="资产编号" width="130"  header-align="center" />
        <el-table-column v-if="!hidden.includes('category_name')" prop="category_name" label="类别" width="90"  header-align="center" />
        <el-table-column v-if="!hidden.includes('brand')" prop="brand" label="品牌(制造厂家)" min-width="130" show-overflow-tooltip  header-align="center" />
        <el-table-column v-if="!hidden.includes('asset_name')" prop="asset_name" label="型号(设备名称)" min-width="120" show-overflow-tooltip header-align="center">
          <template #default="{ row }">{{ row.asset_name || (row.model_spec || '').split(' / ')[0] }}</template>
        </el-table-column>
        <el-table-column v-if="!hidden.includes('model_spec')" prop="model_spec" label="型号规格" min-width="150" show-overflow-tooltip  header-align="center" />
        <el-table-column v-if="!hidden.includes('location_name')" prop="made_no" label="出厂编号" width="130" show-overflow-tooltip header-align="center">
          <template #default="{ row }">{{ (row.custom && row.custom.made_no) || '—' }}</template>
        </el-table-column>
        <el-table-column v-if="!hidden.includes('department_name')" prop="department_name" label="部门" width="95"  header-align="center" />
        <el-table-column v-if="!hidden.includes('custodian_name')" prop="remark_col" label="备注" min-width="120" show-overflow-tooltip header-align="center">
          <template #default="{ row }">{{ (row.custom && row.custom.remark) || '—' }}</template>
        </el-table-column>
        <el-table-column v-if="!hidden.includes('status')" label="状态" width="85" header-align="center">
          <template #default="{ row }">
            <el-tag :type="statusType[row.status]" size="small" effect="dark">
              {{ statusText[row.status] }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="!hidden.includes('purchase_date')" prop="purchase_date" label="投产日期" width="105"  header-align="center" />
        <el-table-column v-if="!hidden.includes('original_value')" label="原值" width="90" align="right" header-align="center">
          <template #default="{ row }">{{ fmt(row.original_value) }}</template>
        </el-table-column>
        <el-table-column v-if="!hidden.includes('current_value')" label="当前净值" width="100" align="right" header-align="center">
          <template #default="{ row }">
            <span style="color:var(--green)">{{ fmt(row.current_value) }}</span>
          </template>
        </el-table-column>
        <el-table-column v-if="!hidden.includes('used_years')" label="已用/年限" width="95" header-align="center">
          <template #default="{ row }">{{ row.used_years }}/{{ row.useful_life }}年</template>
        </el-table-column>
        <el-table-column label="操作" width="130" fixed="right" header-align="center">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="$router.push(`/assets/${row.id}`)">详情</el-button>
            <el-button link size="small" @click="openEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
      <ColMenu ref="colMenu" />

      <el-pagination style="margin-top:14px;justify-content:flex-end"
                     layout="total, prev, pager, next" :total="total" :page-size="20"
                     :current-page="q.page" @current-change="p => { q.page = p; load() }" />
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="dialog" :title="editing ? '编辑资产' : '新增资产'" width="640px" destroy-on-close>
      <el-form :model="form" label-width="110px">
        <el-row :gutter="12">
          <el-col :span="12"><el-form-item label="序列号" required><el-input v-model="form.sn" /></el-form-item></el-col>
          <el-col :span="12">
            <el-form-item label="资产类别" required>
              <el-select v-model="form.category" style="width:100%" @change="onCatChange">
                <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12"><el-form-item label="品牌"><el-input v-model="form.brand" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="型号规格"><el-input v-model="form.model_spec" /></el-form-item></el-col>
          <el-col :span="12">
            <el-form-item label="存放位置">
              <el-select v-model="form.location" style="width:100%" clearable>
                <el-option v-for="l in locations" :key="l.id" :label="l.name" :value="l.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属部门">
              <el-select v-model="form.department" style="width:100%" clearable>
                <el-option v-for="d in departments" :key="d.id" :label="d.name" :value="d.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="投产日期" required>
              <el-date-picker v-model="form.purchase_date" type="date" value-format="YYYY-MM-DD"
                              style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="原值(元)" required>
              <el-input-number v-model="form.original_value" :min="0" :precision="2" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="使用年限(年)">
              <el-input-number v-model="form.useful_life" :min="1" :max="30" style="width:100%"
                               :placeholder="`默认${currentCat?.default_life || 8}年`" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="残值率">
              <el-input-number v-model="form.salvage_rate" :min="0" :max="0.5" :step="0.01"
                               style="width:100%" :placeholder="`默认${currentCat?.default_salvage_rate ?? 0.05}`" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <el-select v-model="form.status" style="width:100%">
                <el-option v-for="(t, k) in statusText" :key="k" :label="t" :value="k" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 自定义字段（按类别schema动态渲染） -->
        <template v-if="currentCat?.field_schema?.length">
          <el-divider content-position="left">扩展字段 — {{ currentCat.name }}</el-divider>
          <el-row :gutter="12">
            <el-col :span="12" v-for="f in currentCat.field_schema" :key="f.key">
              <el-form-item :label="f.label" :required="f.required">
                <el-input-number v-if="f.type === 'number'" v-model="form.custom[f.key]"
                                 style="width:100%" />
                <el-date-picker v-else-if="f.type === 'date'" v-model="form.custom[f.key]"
                                type="date" value-format="YYYY-MM-DD" style="width:100%" />
                <el-switch v-else-if="f.type === 'boolean'" v-model="form.custom[f.key]" />
                <el-select v-else-if="f.type === 'select'" v-model="form.custom[f.key]" style="width:100%" clearable>
                  <el-option v-for="o in f.options || []" :key="o" :label="o" :value="o" />
                </el-select>
                <el-input v-else v-model="form.custom[f.key]" />
              </el-form-item>
            </el-col>
          </el-row>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import ColMenu from '../components/ColMenu.vue'
import { useTableCols } from '../composables/useTableCols'
import api from '../api'
import BackButton from '../components/BackButton.vue'

const statusText = { in_stock: '在库', in_use: '在用', repairing: '维修中', idle: '闲置', scrapped: '已报废' }
const statusType = { in_stock: 'success', in_use: 'primary', repairing: 'warning', idle: 'info', scrapped: 'danger' }
const fmt = n => n == null ? '-' : Number(n).toLocaleString('zh-CN', { maximumFractionDigits: 2 })

const list = ref([]), total = ref(0), loading = ref(false)
const exporting = ref(false)
const categories = ref([]), locations = ref([]), departments = ref([]), users = ref([])
const deptTree = ref([]), deptPath = ref(null)
const advOpen = ref(false), pdateRange = ref(null)
// 已用年限段（与工作台年限柱图分桶一致；age_gt/age_lte 传后端 SQL 过滤）
const ageRanges = ref([])
const AGE_MAP = { '0-2': { gt: null, lte: 2 }, '3-5': { gt: 2, lte: 5 },
                  '6-8': { gt: 5, lte: 8 }, '8-9': { gt: 8, lte: 9 },
                  '9-10': { gt: 9, lte: 10 }, '10+': { gt: 10, lte: null } }
const q = reactive({ kw: '', categories: [], statuses: [], terminal_type: null,
                     department: null, location: null, custodian: null,
                     net_min: '', net_max: '', orig_min: '', orig_max: '',
                     pdate_from: '', pdate_to: '', ordering: null, page: 1,
                     overdue: null, age_gt: null, age_lte: null,
                     made_no: '' })

const COLS = [
  { prop: 'display_tag', label: '资产编号' },
  { prop: 'category_name', label: '类别' },
  { prop: 'brand', label: '品牌(制造厂家)' },
  { prop: 'asset_name', label: '型号(设备名称)' },
  { prop: 'model_spec', label: '型号规格' },
  { prop: 'status', label: '状态' },
  { prop: 'department_name', label: '部门' },
  { prop: 'made_no', label: '出厂编号' },
  { prop: 'remark_col', label: '备注' },
  { prop: 'purchase_date', label: '投产日期' },
  { prop: 'original_value', label: '原值' },
  { prop: 'current_value', label: '净值' },
  { prop: 'sn', label: '序列号' },
]
const { hidden, colMenu, onHeaderContextMenu, onHeaderDragend, colWidth, visibleCols } = useTableCols('assets', COLS)

const dialog = ref(false), editing = ref(null), saving = ref(false)
const form = reactive({ sn: '', category: null, brand: '', model_spec: '', location: null,
                        department: null, status: 'in_stock', purchase_date: '',
                        original_value: null, useful_life: null, salvage_rate: null, custom: {} })

const currentCat = computed(() => categories.value.find(c => c.id === form.category))

const hasActiveFilters = computed(() =>
  !!(q.kw || q.categories?.length || q.statuses?.length || q.terminal_type || q.department || q.location ||
     q.custodian || q.net_min || q.net_max || q.orig_min || q.orig_max ||
     q.pdate_from || q.pdate_to || q.ordering || (ageRanges.value && ageRanges.value.length) || q.made_no ||
     (q.categories && q.categories.length)))

function resetFilters() {
  Object.assign(q, { kw: '', categories: [], statuses: [], terminal_type: null,
                     department: null, location: null, custodian: null, dept_node: null,
                     net_min: '', net_max: '', orig_min: '', orig_max: '',
                     pdate_from: '', pdate_to: '', ordering: null, page: 1, overdue: null,
                     age_gt: null, age_lte: null, made_no: '' })
  pdateRange.value = null
  deptPath.value = null
  ageRanges.value = []
  load()
}

// 年限段切换 → 写入 age_gt/age_lte 后查询（保留跳转带入的排除报废口径）
function onAgeChange(vals) {
  // 多选段：age_gt/age_lte 清空（互斥），由 age_segments 传后端
  q.age_gt = null
  q.age_lte = null
  q.page = 1
  load()
}

function onDeptChange(v) {
  // 多选：v = [[一级id,二级id,...], [一级id,...], ...]，取每条路径的末级节点 id
  if (v && v.length) {
    q.dept_node = v.map(path => path[path.length - 1]).join(',')
  } else {
    q.dept_node = null
  }
  q.page = 1
  load()
}

function onPdateChange(range) {
  if (range && range.length === 2) {
    q.pdate_from = range[0]
    q.pdate_to = range[1]
  } else {
    q.pdate_from = ''
    q.pdate_to = ''
  }
  load()
}

function onFilterChange() {
  q.page = 1
  load()
}

function toggleTerminal() {
  q.terminal_type = q.terminal_type ? null : '生产类终端'
  q.page = 1
  load()
}

async function exportCurrent() {
  exporting.value = true
  try {
    const wantsScrapped = q.statuses?.includes('scrapped')
    const params = {
      ...q,
      category: q.categories?.length ? q.categories.join(',') : undefined,
      status: q.statuses?.length ? q.statuses.join(',') : undefined,
      age_segments: ageRanges.value?.length ? ageRanges.value.join(',') : undefined,
      include_scrapped: wantsScrapped ? '1' : undefined,
      exclude_scrapped: undefined,
      page: undefined, page_size: undefined,
    }
    Object.keys(params).forEach(k => (params[k] === undefined || params[k] === '' || params[k] === null) && delete params[k])
    const qs = new URLSearchParams(params).toString()
    const resp = await api.get('/export/assets/?' + qs, { responseType: 'blob' })
    const url = URL.createObjectURL(resp)
    const a = document.createElement('a')
    a.href = url
    a.download = '资产台账导出-' + new Date().toISOString().slice(0, 10) + '.xlsx'
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('已导出当前筛选结果')
  } catch (e) {
    ElMessage.error('导出失败')
  } finally {
    exporting.value = false
  }
}

async function load() {
  loading.value = true
  try {
    const wantsScrapped = q.statuses?.includes('scrapped')
    const params = {
      ...q,
      category: q.categories?.length ? q.categories.join(',') : undefined,
      status: q.statuses?.length ? q.statuses.join(',') : undefined,
      age_segments: ageRanges.value?.length ? ageRanges.value.join(',') : undefined,
      // 默认不含报废；状态下拉显式勾选「已报废」时才包含
      include_scrapped: wantsScrapped ? '1' : undefined,
      exclude_scrapped: undefined,
    }
    delete params.page_size
    delete params.categories
    delete params.ageRanges
    try {
      const r = await api.get('/assets/', { params })
      list.value = r.results
      total.value = r.count
    } catch (e) {
      // 页码超出范围（筛选后总页数变少）→ 回第 1 页重试一次
      if (q.page > 1) {
        q.page = 1
        const r = await api.get('/assets/', { params })
        list.value = r.results
        total.value = r.count
      } else {
        throw e
      }
    }
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  Object.assign(form, { sn: '', category: null, brand: '', model_spec: '', location: null,
                        department: null, status: 'in_stock', purchase_date: '',
                        original_value: null, useful_life: null, salvage_rate: null, custom: {} })
  dialog.value = true
}

function openEdit(row) {
  editing.value = row.id
  Object.assign(form, { ...row, custom: { ...(row.custom || {}) } })
  dialog.value = true
}

function onCatChange() {
  form.custom = {}  // 切换类别清空扩展字段
}

async function save() {
  saving.value = true
  try {
    if (editing.value) {
      await api.patch(`/assets/${editing.value}/`, form)
    } else {
      await api.post('/assets/', form)
    }
    dialog.value = false
    load()
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  // 支持 URL 参数预置筛选（如 /assets?overdue=1&status=in_use，供工作台行动项跳转）
  const rq = useRoute().query
  if (rq.overdue === '1') q.overdue = '1'
  if (rq.status) q.statuses = [rq.status]
  if (rq.category) q.categories = String(rq.category).split(',').map(Number).filter(n => !isNaN(n))
  // 类别柱图跳转：categories=3（可多值逗号分隔）
  if (rq.categories) q.categories = String(rq.categories).split(',').map(Number).filter(n => !isNaN(n))
  if (rq.location) q.location = Number(rq.location)
  // 工作台「资产原值 TOP8 部门」行点击跳转：按部门筛选（单部门下拉选中态）
  if (rq.department) q.department = Number(rq.department)
  // 「未分配」部门行：部门为空的资产全量清单
  if (rq.no_dept === '1') q.no_dept = '1'
  // 还原部门 cascader 选中态：等树加载完后在 onMounted 尾部回填（见下方 deptTree 就位后）
  const pendingDeptId = rq.department ? Number(rq.department) : null
  // 报废数据已默认排除（后端口径），URL 里的 exclude_scrapped=1 不再需要单独处理
  // 工作台年限柱图跳转：age_gt/age_lte → 还原「已用年限」下拉选中态
  if (rq.age_gt != null || rq.age_lte != null) {
    q.age_gt = rq.age_gt != null ? Number(rq.age_gt) : null
    q.age_lte = rq.age_lte != null ? Number(rq.age_lte) : null
    for (const [key, r] of Object.entries(AGE_MAP)) {
      const gOk = r.gt == null ? q.age_gt == null : q.age_gt === r.gt
      const lOk = r.lte == null ? q.age_lte == null : q.age_lte === r.lte
      if (gOk && lOk) { ageRanges.value = [key]; break }
    }
    advOpen.value = true  // 年限筛选在高级区，跳转进来自动展开让用户看见筛选生效
  }
  load()
  const [c, l, d, u, t] = await Promise.all([
    api.get('/categories/?page_size=100'),
    api.get('/locations/?page_size=100'),
    api.get('/departments/?page_size=100'),
    api.get('/users/?page_size=100').catch(() => ({ results: [] })),
    api.get('/dept_tree/').catch(() => ({ tree: [] })),
  ])
  deptTree.value = t.tree || []
  categories.value = c.results || c
  locations.value = l.results || l
  departments.value = d.results || d
  users.value = u.results || u || []
  // 部门跳转回填：树就位后在 cascader 里还原选中路径（多选模式取单条路径）
  if (pendingDeptId != null) {
    const findPath = (nodes, path) => {
      for (const n of nodes || []) {
        const p = [...path, n.id]
        if (n.id === pendingDeptId) return p
        const r = findPath(n.children, p)
        if (r) return r
      }
      return null
    }
    const p = findPath(deptTree.value, [])
    if (p) deptPath.value = [p]
  }
})
</script>
