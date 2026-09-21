<template>
  <div>
    <h1 class="page-title">
      <BackButton />
      未分配部门资产清单
      <el-tag type="warning" size="small" style="margin-left:10px">{{ total }} 台待补录归属</el-tag>
    </h1>
    <el-alert type="info" :closable="false" style="margin-bottom:14px"
              title="这些资产在原始台账表格中「使用部门」列为空，无法归属到部门。点击「编辑」可补录部门，补录后自动从本清单消失。列表不受统计口径限制（全量排查）。" />

    <el-card>
      <div style="display:flex;gap:10px;margin-bottom:14px;flex-wrap:wrap">
        <el-input v-model="q.kw" placeholder="编号/序列号/品牌/型号" style="width:230px" clearable
                  @keyup.enter="load" @clear="load" />
        <el-select v-model="q.category" placeholder="类别" style="width:170px" clearable filterable @change="onFilter">
          <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
        </el-select>
        <el-select v-model="q.status" placeholder="状态" style="width:110px" clearable @change="onFilter">
          <el-option v-for="(t, k) in statusText" :key="k" :label="t" :value="k" />
        </el-select>
        <el-select v-model="q.ordering" placeholder="排序" style="width:150px" clearable @change="onFilter">
          <el-option label="原值从高到低" value="-original_value" />
          <el-option label="投产日期最新" value="-purchase_date" />
          <el-option label="已用年限最长" value="-used_years" />
        </el-select>
        <div style="flex:1"></div>
        <el-button @click="exportCsv" :loading="exporting">📤 导出 Excel(CSV)</el-button>
        <el-button type="primary" @click="load">查询</el-button>
      </div>

      <el-table :data="list" v-loading="loading" stripe border>
        <el-table-column prop="display_tag" label="资产编号" width="130"  header-align="center" />
        <el-table-column prop="category_name" label="类别" width="150"  header-align="center" />
        <el-table-column label="品牌/型号" min-width="160" show-overflow-tooltip header-align="center">
          <template #default="{ row }">{{ row.brand }} {{ row.asset_name || row.model_spec }}</template>
        </el-table-column>
        <el-table-column prop="location_name" label="位置" width="110" show-overflow-tooltip  header-align="center" />
        <el-table-column prop="custodian_name" label="使用人" width="90"  header-align="center" />
        <el-table-column prop="status" label="状态" width="85" header-align="center">
          <template #default="{ row }">
            <el-tag :type="statusType[row.status]" size="small" effect="dark">{{ statusText[row.status] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="purchase_date" label="投产日期" width="105"  header-align="center" />
        <el-table-column label="原值(元)" width="110" align="right" header-align="center">
          <template #default="{ row }">{{ fmt(row.original_value) }}</template>
        </el-table-column>
        <el-table-column label="当前净值(元)" width="115" align="right" header-align="center">
          <template #default="{ row }"><span style="color:var(--green)">{{ fmt(row.current_value) }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="130" fixed="right" header-align="center">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="editDept(row)">补录部门</el-button>
            <el-button link size="small" @click="$router.push(`/assets/${row.id}`)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination style="margin-top:14px;justify-content:flex-end" layout="total, prev, pager, next"
                     :total="total" :page-size="20" :current-page="q.page"
                     @current-change="p => { q.page = p; load() }" />
    </el-card>

    <!-- 补录部门对话框 -->
    <el-dialog v-model="dlg" title="补录部门" width="440px" destroy-on-close>
      <div v-if="editing" style="margin-bottom:14px;color:var(--text-dim);font-size:13px">
        {{ editing.display_tag }} · {{ editing.brand }} {{ editing.asset_name || editing.model_spec }}
      </div>
      <el-cascader v-model="deptPath" :options="deptTree" placeholder="选择部门(到末级)"
                   style="width:100%" clearable filterable
                   :props="{ checkStrictly: false, label: 'name', value: 'id', children: 'children' }" />
      <template #footer>
        <el-button @click="dlg = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveDept">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'
import BackButton from '../components/BackButton.vue'

const statusText = { in_stock: '在库', in_use: '在用', repairing: '维修中', idle: '闲置', scrapped: '已报废' }
const statusType = { in_stock: 'success', in_use: 'primary', repairing: 'warning', idle: 'info', scrapped: 'info' }
const fmt = n => n == null ? '-' : Number(n).toLocaleString('zh-CN', { maximumFractionDigits: 2 })

const list = ref([]), total = ref(0), loading = ref(false), exporting = ref(false)
const categories = ref([]), deptTree = ref([])
const q = reactive({ kw: '', category: null, status: null, ordering: null, page: 1 })

const dlg = ref(false), editing = ref(null), saving = ref(false), deptPath = ref(null)

async function load() {
  loading.value = true
  try {
    const r = await api.get('/assets/', { params: {
      no_dept: '1', all_categories: '1', include_scrapped: '1', page: q.page,
      kw: q.kw || undefined, category: q.category || undefined,
      status: q.status || undefined, ordering: q.ordering || undefined,
    } })
    list.value = r.results
    total.value = r.count
  } finally {
    loading.value = false
  }
}

function onFilter() { q.page = 1; load() }

function editDept(row) {
  editing.value = row
  deptPath.value = null
  dlg.value = true
}

async function saveDept() {
  if (!deptPath.value || !deptPath.value.length) {
    ElMessage.warning('请选择部门')
    return
  }
  saving.value = true
  try {
    const last = deptPath.value[deptPath.value.length - 1]
    await api.patch(`/assets/${editing.value.id}/`, { department: last })
    ElMessage.success(`已把 ${editing.value.display_tag} 归入部门，清单已刷新`)
    dlg.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function exportCsv() {
  exporting.value = true
  try {
    // 全量拉取当前筛选（最多 5000 台）导出
    const r = await api.get('/assets/', { params: {
      no_dept: '1', all_categories: '1', page_size: 500, page: 1,
      kw: q.kw || undefined, category: q.category || undefined,
      status: q.status || undefined, ordering: q.ordering || undefined,
    } })
    const header = ['资产编号', '类别', '品牌', '型号/设备名称', '位置', '使用人', '状态', '投产日期', '原值(元)', '当前净值(元)']
    const lines = [header.join(',')]
    for (const row of r.results) {
      lines.push([row.display_tag, row.category_name, row.brand,
                  row.asset_name || row.model_spec, row.location_name, row.custodian_name,
                  statusText[row.status] || row.status, row.purchase_date,
                  row.original_value, row.current_value]
                 .map(v => `"${String(v ?? '').replace(/"/g, '""')}"`).join(','))
    }
    const blob = new Blob(['\ufeff' + lines.join('\n')], { type: 'text/csv;charset=utf-8' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `未分配部门资产清单_${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(a.href)
    ElMessage.success(`已导出前 ${r.results.length} 台（当前筛选）`)
  } finally {
    exporting.value = false
  }
}

onMounted(async () => {
  load()
  const [c, t] = await Promise.all([
    api.get('/categories/?page_size=100'),
    api.get('/dept_tree/').catch(() => ({ tree: [] })),
  ])
  categories.value = c.results || c
  deptTree.value = t.tree || []
})
</script>
