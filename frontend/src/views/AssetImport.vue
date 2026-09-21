<template>
  <div>
    <h1 class="page-title">批量导入资产</h1>
    <el-card>
      <el-steps :active="step" align-center style="margin-bottom:26px">
        <el-step title="下载模板" />
        <el-step title="上传校验" />
        <el-step title="确认导入" />
      </el-steps>

      <div style="text-align:center;padding:20px 0" v-if="step === 0">
        <p style="color:var(--text-dim);margin-bottom:18px">
          第一步：下载标准模板，按列填写资产清单（支持必填校验/日期校验/重复序列号检测）
        </p>
        <el-button type="primary" size="large" @click="downloadTpl">📥 下载导入模板</el-button>
        <div style="margin-top:26px">
          <el-button @click="step = 1">已有模板，下一步 →</el-button>
        </div>
      </div>

      <div v-if="step === 1" style="text-align:center;padding:20px 0">
        <el-upload drag :auto-upload="false" :limit="1" accept=".xlsx" :on-change="onFile" :on-exceed="() => {}">
          <div style="padding:24px">
            <div style="font-size:34px">📄</div>
            <p>将填写好的 .xlsx 文件拖到此处，或点击选择</p>
          </div>
        </el-upload>
        <el-button type="primary" style="margin-top:18px" :disabled="!file" :loading="checking" @click="doCheck">
          🔍 开始校验
        </el-button>
      </div>

      <div v-if="step === 2">
        <el-result v-if="checkResult && !checkResult.errors.length" icon="success"
                   :title="`校验通过：${checkResult.valid} 条资产可导入`" />
        <el-alert v-else-if="checkResult" type="error" :closable="false"
                  :title="`发现 ${checkResult.errors.length} 个错误行`" style="margin-bottom:14px" />
        <el-table v-if="checkResult?.errors?.length" :data="checkResult.errors" size="small" style="margin-bottom:16px">
          <el-table-column prop="row" label="行号" width="80"  header-align="center" />
          <el-table-column prop="sn" label="序列号" width="160"  header-align="center" />
          <el-table-column label="错误" header-align="center">
            <template #default="{ row }">
              <el-tag v-for="e in row.errors" :key="e" type="danger" size="small" style="margin-right:6px">{{ e }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
        <div style="text-align:center">
          <el-button v-if="checkResult?.errors?.length" @click="step = 1">← 返回修正后重新上传</el-button>
          <el-button v-else @click="step = 1">← 重新上传</el-button>
          <el-button v-if="!checkResult?.errors?.length" type="primary" :loading="importing" @click="doImport">
            ✅ 确认正式导入 {{ checkResult?.valid }} 条
          </el-button>
        </div>
      </div>

      <el-result v-if="imported" icon="success" title="导入完成"
                 :sub-title="`成功导入 ${imported} 条资产，已自动生成编号并计算折旧`">
        <template #extra>
          <el-button type="primary" @click="$router.push('/assets')">查看资产台账</el-button>
          <el-button @click="reset">继续导入</el-button>
        </template>
      </el-result>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import api from '../api'

const step = ref(0), file = ref(null), checkResult = ref(null)
const checking = ref(false), importing = ref(false), imported = ref(0)

async function downloadTpl() {
  // JWT 需要放在请求头里，window.open 不带 token → 401；改用 blob 下载
  const resp = await api.get('/assets/import_template/', { responseType: 'blob' })
  const url = URL.createObjectURL(resp)
  const a = document.createElement('a')
  a.href = url
  a.download = 'asset_import_template.xlsx'
  a.click()
  URL.revokeObjectURL(url)
}
function onFile(f) { file.value = f.raw }
function reset() { step.value = 0; file.value = null; checkResult.value = null; imported.value = 0 }

async function doCheck() {
  checking.value = true
  try {
    const fd = new FormData()
    fd.append('file', file.value)
    checkResult.value = await api.post('/assets/batch_import/?dry_run=1', fd)
    step.value = 2
  } finally {
    checking.value = false
  }
}

async function doImport() {
  importing.value = true
  try {
    const fd = new FormData()
    fd.append('file', file.value)
    const r = await api.post('/assets/batch_import/', fd)
    imported.value = r.imported
  } finally {
    importing.value = false
  }
}
</script>
