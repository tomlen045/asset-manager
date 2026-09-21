<template>
  <div>
    <h1 class="page-title">维修管理
      <el-button style="margin-left:12px" @click="exportRepairs">📤 导出明细</el-button></h1>
    <el-card>
      <div style="margin-bottom:14px;display:flex;gap:10px">
        <el-select v-model="status" placeholder="全部状态" style="width:130px" clearable @change="load">
          <el-option label="待维修" value="pending" />
          <el-option label="已完成" value="done" />
        </el-select>
        <el-button @click="colMenu.open($event.target, COLS, 'am-cols-hidden-repairs', hidden, h => { hidden = h })">⚙ 显示列</el-button>
        <el-button type="primary" @click="dialog = true">+ 新建维修工单</el-button>
      </div>
      <el-table border @header-contextmenu="onHeaderContextMenu" @header-dragend="onHeaderDragend" :data="list" stripe>
        <el-table-column v-if="!hidden.includes('display_tag')" prop="display_tag" label="资产编号" width="130" header-align="center">
          <template #default="{ row }">{{ row.display_tag || row.asset_tag }}</template>
        </el-table-column>
        <el-table-column v-if="!hidden.includes('report_date')" prop="report_date" label="报修日期" width="105"  header-align="center" />
        <el-table-column v-if="!hidden.includes('fault_desc')" prop="fault_desc" label="故障描述" min-width="180" show-overflow-tooltip  header-align="center" />
        <el-table-column v-if="!hidden.includes('parts')" label="配件" min-width="150" header-align="center">
          <template #default="{ row }">
            <el-tag v-for="p in row.parts_replaced" :key="p.name" size="small" style="margin-right:4px"
                    type="info" effect="plain">{{ p.name }} ¥{{ p.cost }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="!hidden.includes('labor_cost')" label="人工费" width="90" align="right" header-align="center">
          <template #default="{ row }">¥{{ row.labor_cost }}</template>
        </el-table-column>
        <el-table-column v-if="!hidden.includes('total')" label="总费用" width="100" align="right" header-align="center">
          <template #default="{ row }">
            <span style="color:var(--yellow)">¥{{ row.total_cost }}</span>
          </template>
        </el-table-column>
        <el-table-column v-if="!hidden.includes('vendor')" prop="vendor" label="维修商" width="110"  header-align="center" />
        <el-table-column label="状态" width="90" header-align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'done' ? 'success' : 'warning'" size="small">
              {{ row.status === 'done' ? '已完成' : '待维修' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right" header-align="center">
          <template #default="{ row }">
            <el-button v-if="row.status === 'pending'" link type="success" size="small"
                       @click="finish(row)">完成维修</el-button>
          </template>
        </el-table-column>
      </el-table>
      <ColMenu ref="colMenu" />
    </el-card>

    <el-dialog v-model="dialog" title="新建维修工单" width="560px" destroy-on-close>
      <el-form :model="form" label-width="100px">
        <el-form-item label="资产" required>
          <el-select v-model="form.asset" filterable style="width:100%" placeholder="按编号/品牌搜索">
            <el-option v-for="a in assetOptions" :key="a.id" :value="a.id"
                       :label="`${a.display_tag || a.asset_tag} ${a.brand} ${a.model_spec}`" />
          </el-select>
        </el-form-item>
        <el-form-item label="报修日期" required>
          <el-date-picker v-model="form.report_date" type="date" value-format="YYYY-MM-DD" style="width:100%" />
        </el-form-item>
        <el-form-item label="故障描述" required>
          <el-input v-model="form.fault_desc" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="更换配件">
          <div style="width:100%">
            <div v-for="(p, i) in form.parts_replaced" :key="i" style="display:flex;gap:8px;margin-bottom:6px">
              <el-input v-model="p.name" placeholder="配件名称" style="flex:1" size="small" />
              <el-input-number v-model="p.cost" :min="0" :precision="2" placeholder="费用" size="small" style="width:140px" />
              <el-button link type="danger" size="small" @click="form.parts_replaced.splice(i, 1)">删</el-button>
            </div>
            <el-button size="small" @click="form.parts_replaced.push({ name: '', cost: 0 })">+ 添加配件</el-button>
          </div>
        </el-form-item>
        <el-form-item label="人工/服务费">
          <el-input-number v-model="form.labor_cost" :min="0" :precision="2" style="width:100%" />
        </el-form-item>
        <el-form-item label="维修商"><el-input v-model="form.vendor" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" @click="save">创建工单</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'
import ColMenu from '../components/ColMenu.vue'
import { useTableCols } from '../composables/useTableCols'

const COLS = [{ prop: 'display_tag', label: '资产编号' }, { prop: 'report_date', label: '报修日期' }, { prop: 'fault_desc', label: '故障描述' }, { prop: 'parts', label: '配件' }, { prop: 'labor_cost', label: '人工费' }, { prop: 'total', label: '总费用' }, { prop: 'vendor', label: '维修商' }, { prop: 'status', label: '状态' }]
const { hidden, colMenu, onHeaderContextMenu, onHeaderDragend } = useTableCols('repairs', COLS)


const list = ref([])

function exportRepairs() {
  const headers = ['资产编号', '报修日期', '故障描述', '维修商', '状态', '配件费(元)', '人工费(元)', '总费用(元)']
  const rows = list.value.map((x, i) => [
    i + 1, x.display_tag || x.asset_tag || '', x.report_date || '', x.fault_desc || '',
    x.vendor || '', x.status_text || x.status || '',
    Number(x.parts_cost || 0).toFixed(2), Number(x.labor_cost || 0).toFixed(2),
    Number(x.total_cost || 0).toFixed(2),
  ])
  const csv = [headers, ...rows].map(r => r.map(v => '"' + String(v).replace(/"/g, '""') + '"').join(',')).join('\r\n')
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = '维修工单-' + new Date().toISOString().slice(0, 10) + '.csv'
  a.click()
  URL.revokeObjectURL(url)
}
const status = ref(null), dialog = ref(false), assetOptions = ref([])
const form = reactive({ asset: null, report_date: '', fault_desc: '', parts_replaced: [], labor_cost: 0, vendor: '' })

async function load() {
  list.value = (await api.get('/repairs/', { params: status.value ? { status: status.value } : {} })).results
}

async function finish(row) {
  await api.patch(`/repairs/${row.id}/`, {
    status: 'done',
    finish_date: new Date().toISOString().slice(0, 10),
  })
  ElMessage.success('已登记完成，维修费用已计入经济寿命分析')
  load()
}

async function save() {
  await api.post('/repairs/', { ...form, status: 'pending' })
  dialog.value = false
  load()
}

onMounted(async () => {
  load()
  const r = await api.get('/assets/?page_size=200')
  assetOptions.value = r.results
})
</script>
