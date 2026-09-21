<template>
  <div>
    <h1 class="page-title">资产流程</h1>

    <el-card>
      <div style="display:flex;gap:10px;margin-bottom:14px;flex-wrap:wrap">
        <el-select v-model="q.type" placeholder="类型" style="width:130px" clearable @change="load">
          <el-option label="领用" value="receive" />
          <el-option label="归还" value="return" />
          <el-option label="调拨" value="transfer" />
          <el-option label="报废申请" value="scrap" />
        </el-select>
        <el-select v-model="q.status" placeholder="状态" style="width:130px" clearable @change="load">
          <el-option label="待审批" value="pending" />
          <el-option label="已批准" value="approved" />
          <el-option label="已驳回" value="rejected" />
        </el-select>
        <el-button @click="colMenu.open($event.target, COLS, 'am-cols-hidden-flows', hidden, h => { hidden = h })">⚙ 显示列</el-button>
        <el-button type="primary" @click="dialog = true">+ 发起申请</el-button>
      </div>

      <el-table border :data="list" v-loading="loading" stripe
                @header-contextmenu="onHeaderContextMenu" @header-dragend="onHeaderDragend">
        <el-table-column v-if="!hidden.includes('display_tag')" prop="display_tag" label="资产编号" width="130" header-align="center">
          <template #default="{ row }">{{ row.asset_display || row.asset_tag }}</template>
        </el-table-column>
        <el-table-column v-if="!hidden.includes('type')" label="类型" width="90" header-align="center">
          <template #default="{ row }">{{ typeText(row.type) }}</template>
        </el-table-column>
        <el-table-column v-if="!hidden.includes('reason')" prop="reason" label="事由" min-width="180" show-overflow-tooltip  header-align="center" />
        <el-table-column v-if="!hidden.includes('applicant_name')" prop="applicant_name" label="申请人" width="100"  header-align="center" />
        <el-table-column v-if="!hidden.includes('status')" label="状态" width="90" header-align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'approved' ? 'success' : row.status === 'rejected' ? 'danger' : 'warning'" size="small">
              {{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="!hidden.includes('created_at')" prop="created_at" label="时间" width="160" header-align="center">
          <template #default="{ row }">{{ (row.created_at || '').slice(0, 16).replace('T', ' ') }}</template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right" header-align="center">
          <template #default="{ row }">
            <template v-if="row.status === 'pending'">
              <el-button link type="success" size="small" @click="act(row, 'approve')">批准</el-button>
              <el-button link type="danger" size="small" @click="act(row, 'reject')">驳回</el-button>
            </template>
            <span v-else style="color:var(--text-dim)">已处理</span>
          </template>
        </el-table-column>
      </el-table>
      <ColMenu ref="colMenu" />

      <el-pagination style="margin-top:14px;justify-content:flex-end" layout="total, prev, pager, next"
                     :total="total" :page-size="20" :current-page="q.page"
                     @current-change="p => { q.page = p; load() }" />
    </el-card>

    <!-- 发起申请 -->
    <el-dialog v-model="dialog" title="发起资产申请" width="480">
      <el-form label-width="80">
        <el-form-item label="资产">
          <el-select v-model="form.asset" filterable remote :remote-method="searchAsset"
                     :loading="searching" placeholder="输入编号/品牌/型号搜索" style="width:100%">
            <el-option v-for="a in assetOptions" :key="a.id"
                       :label="`${a.display_tag} ${a.brand} ${a.model_spec}`" :value="a.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.type" style="width:100%">
            <el-option label="领用" value="receive" />
            <el-option label="归还" value="return" />
            <el-option label="调拨" value="transfer" />
            <el-option label="报废申请" value="scrap" />
          </el-select>
        </el-form-item>
        <el-form-item label="事由">
          <el-input v-model="form.reason" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" @click="save" :loading="saving">提交申请</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'
import ColMenu from '../components/ColMenu.vue'
import { useTableCols } from '../composables/useTableCols'

const list = ref([]), total = ref(0), loading = ref(false)
const dialog = ref(false), saving = ref(false), searching = ref(false)
const assetOptions = ref([])
const q = reactive({ type: null, status: null, page: 1 })
const form = reactive({ asset: null, type: 'receive', reason: '' })

const COLS = [{ prop: 'display_tag', label: '资产编号' }, { prop: 'type', label: '类型' }, { prop: 'reason', label: '事由' }, { prop: 'applicant_name', label: '申请人' }, { prop: 'status', label: '状态' }, { prop: 'created_at', label: '时间' }]
const { hidden, colMenu, onHeaderContextMenu, onHeaderDragend } = useTableCols('flows', COLS)

const typeText = t => ({ receive: '领用', return: '归还', transfer: '调拨', scrap: '报废申请' }[t] || t)
const statusText = s => ({ pending: '待审批', approved: '已批准', rejected: '已驳回' }[s] || s)

async function load() {
  loading.value = true
  try {
    const r = await api.get('/flows/', { params: { ...q, page_size: 20 } })
    list.value = r.results
    total.value = r.count
  } finally { loading.value = false }
}

async function searchAsset(kw) {
  if (!kw) return
  searching.value = true
  try {
    const r = await api.get('/assets/', { params: { kw, page_size: 20 } })
    assetOptions.value = r.results
  } finally { searching.value = false }
}

async function act(row, action) {
  const tips = { approve: '批准', reject: '驳回' }
  await ElMessageBox.confirm(`确认${tips[action]}这笔申请？`, '确认')
  await api.post(`/flows/${row.id}/${action}/`)
  ElMessage.success(`已${tips[action]}`)
  load()
}

async function save() {
  if (!form.asset) return ElMessage.warning('请选择资产')
  saving.value = true
  try {
    await api.post('/flows/', { ...form })
    ElMessage.success('已提交')
    dialog.value = false
    Object.assign(form, { asset: null, type: 'receive', reason: '' })
    load()
  } finally { saving.value = false }
}

onMounted(load)
</script>
