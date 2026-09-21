<template>
  <div style="max-width:420px;margin:40px auto;padding:0 16px">
    <h2 style="margin-bottom:4px">📷 设备领用 / 归还登记</h2>
    <p style="color:var(--text-dim);font-size:13px;margin:0 0 18px">
      扫描设备背面二维码自动识别设备，输入姓名完成登记。</p>

    <template v-if="dev">
      <el-card style="margin-bottom:14px">
        <div style="font-size:16px;font-weight:600">{{ dev.name || dev.mac }}</div>
        <div style="font-size:13px;color:var(--text-dim);margin-top:4px">
          {{ dev.device_no }} · {{ dev.zone || '未分区' }} · {{ dev.owner || '未指定责任人' }}</div>
        <div style="margin-top:8px;font-size:13px">
          状态: <el-tag size="small" :type="dev.online ? 'success' : 'info'">{{ dev.online ? '在线' : '离线' }}</el-tag>
          <span v-if="dev.battery != null" style="margin-left:10px">🔋 {{ dev.battery }}%</span>
        </div>
      </el-card>
      <el-form label-width="80px" size="large">
        <el-form-item label="动作">
          <el-radio-group v-model="action" size="large">
            <el-radio-button value="take">📤 领用</el-radio-button>
            <el-radio-button value="return">📥 归还</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="我的姓名" required>
          <el-input v-model="person" placeholder="姓名 / 班组" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" size="large" style="width:100%" :loading="saving"
                     :disabled="!person.trim()" @click="submit">完成登记</el-button>
        </el-form-item>
      </el-form>
    </template>
    <el-empty v-else-if="checked" description="未找到该设备，请确认二维码是否属于本系统登记的设备" />
    <div v-else style="text-align:center;color:var(--text-dim)">正在识别设备...</div>

    <el-card v-if="done" style="margin-top:16px">
      <el-result icon="success" :title="done.title" :sub-title="done.sub" />
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import axios from 'axios'

const mac = new URLSearchParams(location.search).get('mac') ||
            (location.hash.match(/mac=([\w:.-]+)/) || [])[1] || ''
const dev = ref(null), checked = ref(false)
const action = ref('take'), person = ref(''), saving = ref(false)
const done = ref(null)

const api = axios.create({ baseURL: location.origin + '/api', timeout: 15000 })

async function lookup() {
  if (!mac) { checked.value = true; return }
  try {
    const r = await api.get('/pda/scan/lookup/?mac=' + encodeURIComponent(mac))
    if (r.data.found) dev.value = r.data
  } catch (e) { /* ignore */ }
  checked.value = true
}
lookup()

async function submit() {
  saving.value = true
  try {
    const r = await api.post('/pda/scan/log/', { mac, action: action.value, person: person.value })
    done.value = { title: `${r.data.device} ${r.data.action_text}成功`,
                   sub: `${r.data.person} · ${r.data.time}` }
  } catch (e) {
    done.value = { title: '登记失败', sub: (e.response && e.response.data && e.response.data.error) || '请重试' }
  } finally { saving.value = false }
}
</script>
