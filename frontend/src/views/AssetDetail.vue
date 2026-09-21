<template>
  <div v-if="asset">
    <h1 class="page-title">
      <BackButton />
      {{ asset.display_tag }} · {{ asset.brand }} {{ asset.model_spec }}
      <el-button type="warning" size="small" style="margin-left:16px" :loading="aiLoading"
                 @click="genAiReport">{{ aiLoading ? '🤖 AI 生成中，约需1-2分钟…' : (aiReady ? '🤖 查看AI报告' : '🤖 AI 分析报告') }}</el-button>
    </h1>

    <!-- AI 报告弹窗 -->
    <el-dialog v-model="aiDialog" title="🤖 AI 资产处置分析报告" width="680px" destroy-on-close>
      <div v-if="aiEngine" style="margin-bottom:10px">
        <el-tag :type="aiEngine === 'ollama' ? 'success' : 'info'" size="small">
          {{ aiEngine === 'ollama' ? '大模型生成（内网 Ollama）' : '规则引擎模板（LLM 不可用自动降级）' }}
        </el-tag>
      </div>
      <pre style="white-space:pre-wrap;font-family:inherit;line-height:1.8;font-size:14px;margin:0">{{ aiReport }}</pre>
      <template #footer>
        <el-button @click="copyReport">复制报告</el-button>
        <el-button type="primary" @click="aiDialog = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-row :gutter="16">
      <!-- 左：基本信息+财务 -->
      <el-col :span="9">
        <el-card style="margin-bottom:16px">
          <template #header>基本信息</template>
          <el-descriptions :column="1" size="small">
            <el-descriptions-item label="资产编号">{{ asset.display_tag }}</el-descriptions-item>
              <el-descriptions-item label="系统编号">{{ asset.asset_tag }}</el-descriptions-item>
            <el-descriptions-item label="序列号">{{ asset.sn || '—' }}</el-descriptions-item>
            <el-descriptions-item label="类别">{{ asset.category_name }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag size="small" effect="dark">{{ { in_use: '在用', in_stock: '在库', repairing: '维修中', idle: '闲置', scrapped: '已报废' }[asset.status] || asset.status }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="位置">{{ asset.location_name || '—' }}</el-descriptions-item>
            <el-descriptions-item label="部门">{{ asset.department_name || '—' }}</el-descriptions-item>
          </el-descriptions>
        </el-card>

        <el-card>
          <template #header>财务信息（折旧引擎）</template>
          <el-descriptions :column="2" size="small">
            <el-descriptions-item label="投产日期">{{ asset.purchase_date }}</el-descriptions-item>
            <el-descriptions-item label="原值">¥{{ asset.original_value }}</el-descriptions-item>
            <el-descriptions-item label="年折旧">¥{{ eco.annual_depreciation }}</el-descriptions-item>
            <el-descriptions-item label="当前净值">
              <span style="color:var(--green);font-weight:700">¥{{ eco.current_value }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="已使用">{{ asset.used_years }} 年</el-descriptions-item>
            <el-descriptions-item label="折旧年限">{{ asset.useful_life }} 年</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>

      <!-- 中：经济寿命曲线 -->
      <el-col :span="9">
        <el-card style="margin-bottom:16px">
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span>经济寿命分析</span>
              <el-tag :type="healthType" effect="dark" size="small">{{ healthText }}</el-tag>
            </div>
          </template>
          <div ref="ecoChart" style="height:260px"></div>
          <el-alert v-if="eco.suggestion" :type="alertType" :title="eco.suggestion" :closable="false"
                    style="margin-top:8px" />
        </el-card>
        <el-card>
          <template #header>命中决策规则</template>
          <el-empty v-if="!eco.rules_hit?.length" description="无风险规则命中" :image-size="48" />
          <div v-for="h in eco.rules_hit" :key="h.rule" style="margin-bottom:8px">
            <el-tag :type="h.level === 'red' ? 'danger' : 'warning'" size="small">{{ h.rule }}</el-tag>
            <span style="margin-left:8px;font-size:13px">{{ h.msg }}</span>
          </div>
        </el-card>
      </el-col>

      <!-- 右：生命周期 -->
      <el-col :span="6">
        <el-card>
          <template #header>生命周期留痕</template>
          <el-timeline style="padding-left:4px">
            <el-timeline-item v-for="log in lifecycle" :key="log.id"
                              :timestamp="log.created_at" :type="log.action === 'create' ? 'primary' : undefined">
              <b>{{ actionText[log.action] || log.action }}</b>
              <div v-if="log.detail?.cost" style="color:var(--yellow);font-size:12px">
                维修费 ¥{{ log.detail.cost }}
              </div>
            </el-timeline-item>
          </el-timeline>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import BackButton from '../components/BackButton.vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import api from '../api'

const route = useRoute()
const asset = ref(null), eco = ref({}), lifecycle = ref([])
const ecoChart = ref()
const aiDialog = ref(false), aiLoading = ref(false), aiReport = ref(''), aiEngine = ref('')

// 进入详情页即触发 AI 报告：接口秒回模板版（数字完整），LLM 润色后台进行，
// 前端轮询 status，润色完成后自动替换为 LLM 版（engine=ollama）
const aiReady = ref(false)
let aiPollTimer = null

function applyReport(r) {
  aiReport.value = r.report
  aiEngine.value = r.engine
  aiReady.value = true
}

function pollAiStatus() {
  let n = 0
  clearInterval(aiPollTimer)
  aiPollTimer = setInterval(async () => {
    n++
    if (n > 90) { clearInterval(aiPollTimer); return }  // 最多轮询 4.5 分钟
    try {
      const s = await api.get(`/assets/${route.params.id}/ai_report_status/`)
      if (s.status === 'done') {
        aiReport.value = s.report
        aiEngine.value = s.engine
        clearInterval(aiPollTimer)
        ElMessage.success('AI 润色完成，报告已更新')
      } else if (s.status === 'none') {
        clearInterval(aiPollTimer)
      }
    } catch (e) { /* 轮询失败静默重试 */ }
  }, 3000)
}

async function prefetchAi() {
  try {
    const r = await api.post(`/assets/${route.params.id}/ai_report/`, { use_llm: true },
                             { timeout: 30000 })
    applyReport(r)
    if (r.engine === 'template') pollAiStatus()   // LLM 润色中，轮询替换
  } catch (e) { /* 预生成失败静默，点击时再试 */ }
}

async function genAiReport() {
  if (aiReady.value && aiReport.value) {   // 已生成：秒开
    aiDialog.value = true
    return
  }
  aiLoading.value = true
  try {
    const r = await api.post(`/assets/${route.params.id}/ai_report/`, { use_llm: true },
                             { timeout: 30000 })   // 接口已后台化，秒回模板版
    applyReport(r)
    aiDialog.value = true
    if (r.engine === 'template') pollAiStatus()
  } finally {
    aiLoading.value = false
  }
}

function copyReport() {
  navigator.clipboard.writeText(aiReport.value)
  ElMessage.success('已复制到剪贴板')
}

const actionText = { create: '入库', assign: '领用', return: '归还', transfer: '调拨',
                     repair: '维修', stocktake: '盘点', scrap: '报废', update: '信息变更' }
const healthType = computed(() => ({ red: 'danger', yellow: 'warning', green: 'success' }[eco.value.health_level]))
const healthText = computed(() => ({ red: '报废风险', yellow: '预警', green: '健康' }[eco.value.health_level]))
const alertType = computed(() => ({ red: 'error', yellow: 'warning', green: 'success' }[eco.value.health_level]))

onMounted(async () => {
  prefetchAi()
  const id = route.params.id
  asset.value = await api.get(`/assets/${id}/`)
  eco.value = await api.get(`/assets/${id}/economy/`)
  lifecycle.value = await api.get(`/assets/${id}/lifecycle/`)

  // 成本交叉曲线：累计维修费(升) vs 净值(降)
  const yearly = eco.value.repair_yearly || {}
  const years = eco.value.useful_life
  const total = eco.value.original_value
  const annual = eco.value.annual_depreciation
  const xs = [], repair = [], value = []
  let cum = 0
  const byY = Object.fromEntries(Object.entries(yearly).map(([y, c]) => [+y, c]))
  for (let t = 0; t <= years; t++) {
    xs.push(`第${t}年`)
    cum += byY[t] || 0
    repair.push(+cum.toFixed(0))
    value.push(+Math.max(total - annual * t, total * 0.05).toFixed(0))
  }
  const chart = echarts.init(ecoChart.value)
  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: { textStyle: { color: '#6b7a99' } },
    grid: { left: 50, right: 20, top: 35, bottom: 25 },
    xAxis: { type: 'category', data: xs, axisLabel: { color: '#6b7a99', interval: 1 } },
    yAxis: { type: 'value', axisLabel: { color: '#6b7a99' }, splitLine: { lineStyle: { color: '#dfe5f1' } } },
    series: [
      { name: '累计维修费', type: 'line', smooth: true, data: repair,
        lineStyle: { color: '#ff4d6a' }, itemStyle: { color: '#ff4d6a' }, areaStyle: { opacity: .15 } },
      { name: '资产净值', type: 'line', smooth: true, data: value,
        lineStyle: { color: '#00d68f' }, itemStyle: { color: '#00d68f' }, areaStyle: { opacity: .1 } },
    ],
  })
})
onUnmounted(() => { if (aiPollTimer) clearInterval(aiPollTimer) })
</script>
