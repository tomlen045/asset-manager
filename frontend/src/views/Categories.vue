<template>
  <div>
    <h1 class="page-title">类别管理 · 自定义字段引擎</h1>
    <el-card>
      <div style="margin-bottom:14px">
        <el-button type="primary" @click="openEdit(null)">+ 新增类别</el-button>
        <span style="color:var(--text-dim);margin-left:14px;font-size:13px">
          每个类别可独立配置：默认报废年限、残值率、专属扩展字段（零改表）
        </span>
      </div>
      <el-table :data="list">
        <el-table-column prop="code" label="编码" width="90"  header-align="center" />
        <el-table-column prop="name" label="类别名称" width="130"  header-align="center" />
        <el-table-column prop="default_life" label="默认年限" width="90"  header-align="center" />
        <el-table-column prop="default_salvage_rate" label="残值率" width="80"  header-align="center" />
        <el-table-column prop="asset_count" label="资产数" width="80"  header-align="center" />
        <el-table-column label="扩展字段" header-align="center">
          <template #default="{ row }">
            <el-tag v-for="f in row.field_schema" :key="f.key" size="small" style="margin-right:6px"
                    type="info" effect="plain">{{ f.label }}</el-tag>
            <span v-if="!row.field_schema?.length" style="color:var(--text-dim)">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" header-align="center">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialog" :title="editing ? '编辑类别' : '新增类别'" width="600px" destroy-on-close>
      <el-form :model="form" label-width="100px">
        <el-row :gutter="12">
          <el-col :span="10"><el-form-item label="类别编码" required><el-input v-model="form.code" placeholder="SCN" /></el-form-item></el-col>
          <el-col :span="14"><el-form-item label="类别名称" required><el-input v-model="form.name" placeholder="扫描枪" /></el-form-item></el-col>
          <el-col :span="12">
            <el-form-item label="默认年限">
              <el-input-number v-model="form.default_life" :min="1" :max="30" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="残值率">
              <el-input-number v-model="form.default_salvage_rate" :min="0" :max="0.5" :step="0.01" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">扩展字段定义</el-divider>
        <div v-for="(f, i) in form.field_schema" :key="i"
             style="display:flex;gap:8px;margin-bottom:8px;align-items:center">
          <el-input v-model="f.key" placeholder="字段key(英文)" style="width:150px" size="small" />
          <el-input v-model="f.label" placeholder="显示名称" style="width:160px" size="small" />
          <el-select v-model="f.type" style="width:110px" size="small">
            <el-option label="文本" value="text" />
            <el-option label="数字" value="number" />
            <el-option label="日期" value="date" />
            <el-option label="开关" value="boolean" />
            <el-option label="下拉" value="select" />
          </el-select>
          <el-checkbox v-model="f.required" label="必填" />
          <el-button link type="danger" size="small" @click="form.field_schema.splice(i, 1)">删除</el-button>
        </div>
        <el-button size="small" @click="form.field_schema.push({ key: '', label: '', type: 'text', required: false })">
          + 添加字段
        </el-button>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import api from '../api'

const list = ref([]), dialog = ref(false), editing = ref(null)
const form = reactive({ code: '', name: '', default_life: 8, default_salvage_rate: 0.05, field_schema: [] })

async function load() { list.value = (await api.get('/categories/?page_size=100')).results }

function openEdit(row) {
  editing.value = row?.id || null
  Object.assign(form, row ? {
    ...row,
    field_schema: (row.field_schema || []).map(f => ({ ...f })),
  } : { code: '', name: '', default_life: 8, default_salvage_rate: 0.05, field_schema: [] })
  dialog.value = true
}

async function save() {
  const payload = { ...form, field_schema: form.field_schema.filter(f => f.key && f.label) }
  if (editing.value) await api.patch(`/categories/${editing.value}/`, payload)
  else await api.post('/categories/', payload)
  dialog.value = false
  load()
}

onMounted(load)
</script>
