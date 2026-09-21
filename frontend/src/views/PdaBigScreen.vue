<template>
  <div class="bs-wrap">
    <header class="bs-header">
      <div class="bs-title">📱 车间移动设备定位监控大屏</div>
      <div class="bs-time">{{ data.server_time }}</div>
    </header>

    <!-- 顶部指标 -->
    <section class="bs-kpis">
      <div class="kpi" style="border-color: var(--accent)">
        <div class="kpi-num" style="color: var(--accent)">{{ data.summary.total }}</div>
        <div class="kpi-label">终端总数</div>
      </div>
      <div class="kpi" style="border-color: var(--green)">
        <div class="kpi-num" style="color: var(--green)">{{ data.summary.online }}</div>
        <div class="kpi-label">当前在线</div>
      </div>
      <div class="kpi" style="border-color: var(--text-dim)">
        <div class="kpi-num">{{ data.summary.offline }}</div>
        <div class="kpi-label">离线</div>
      </div>
      <div class="kpi" style="border-color: var(--yellow)">
        <div class="kpi-num" style="color: var(--yellow)">{{ data.summary.lowbat }}</div>
        <div class="kpi-label">低电量</div>
      </div>
      <div class="kpi" style="border-color: #e74c3c">
        <div class="kpi-num" style="color: #e74c3c">{{ data.summary.stale }}</div>
        <div class="kpi-label">失联超3天</div>
      </div>
      <div class="kpi" style="border-color: #9b59b6">
        <div class="kpi-num" style="color: #9b59b6">{{ data.summary.ap_online }} / {{ data.summary.ap_total }}</div>
        <div class="kpi-label">AP 在线</div>
      </div>
    </section>

    <section class="bs-main">
      <!-- 左：区域在线率 -->
      <div class="bs-panel">
        <div class="bs-panel-title">各区域在线率</div>
        <div class="bs-zone-list">
          <div class="bz" v-for="z in data.zones" :key="z.zone">
            <span class="bz-name">{{ z.zone }}</span>
            <div class="bz-bar"><div class="bz-bar-in" :style="{width: z.rate + '%'}"></div></div>
            <span class="bz-val">{{ z.online }}/{{ z.total }}</span>
          </div>
        </div>
      </div>

      <!-- 中：类型分布 + 告警 -->
      <div class="bs-panel">
        <div class="bs-panel-title">终端类型分布</div>
        <div class="bs-types">
          <div class="bt" v-for="t in data.types" :key="t.type">
            <span class="bt-name">{{ t.type }}</span>
            <span class="bt-num">{{ t.total }}</span>
          </div>
        </div>
        <div class="bs-panel-title" style="margin-top:18px">🚨 区域围栏告警（未读）</div>
        <div class="bs-alarms" v-if="data.alarms.length">
          <div class="ba" v-for="(a, i) in data.alarms" :key="i">
            <span class="ba-dev">{{ a.device }}</span>
            <span class="ba-route">{{ a.from || '—' }} → <b>{{ a.to }}</b></span>
            <span class="ba-time">{{ a.time }}</span>
          </div>
        </div>
        <div v-else class="bs-empty">✓ 暂无围栏告警，全部终端在允许区域</div>
      </div>

      <!-- 右：最近接入 -->
      <div class="bs-panel">
        <div class="bs-panel-title">最近接入动态</div>
        <div class="bs-recent">
          <div class="br" v-for="(r, i) in data.recent" :key="i">
            <span class="br-time">{{ r.time }}</span>
            <span class="br-name">{{ r.name }}</span>
            <span class="br-zone">{{ r.zone }}</span>
          </div>
        </div>
      </div>
    </section>

    <footer class="bs-footer">数据来源：信锐 NAC/AC · 每 5 分钟自动同步 · 3s 后自动刷新</footer>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted } from 'vue'
import api from '../api'

export default {
  name: 'PdaBigScreen',
  setup() {
    const data = ref({
      summary: { total: 0, online: 0, offline: 0, lowbat: 0, stale: 0, ap_total: 0, ap_online: 0, server_time: '' },
      zones: [], types: [], alarms: [], recent: []
    })
    let timer = null
    async function load() {
      try {
        data.value = await api.get('/pda/bigscreen/')
      } catch (e) { /* silent */ }
    }
    onMounted(() => { load(); timer = setInterval(load, 3000) })
    onUnmounted(() => clearInterval(timer))
    return { data }
  }
}
</script>

<style scoped>
.bs-wrap { min-height: 100vh; background: #0b1220; color: #dfe7f3; padding: 14px 18px; box-sizing: border-box; }
.bs-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.bs-title { font-size: 22px; font-weight: 700; letter-spacing: 2px; color: #fff; }
.bs-time { font-size: 14px; color: #8fa3c0; font-variant-numeric: tabular-nums; }
.bs-kpis { display: flex; gap: 12px; margin-bottom: 14px; }
.kpi { flex: 1; background: rgba(255,255,255,.04); border: 1px solid; border-top-width: 3px; border-radius: 8px; padding: 12px 8px; text-align: center; }
.kpi-num { font-size: 34px; font-weight: 700; font-variant-numeric: tabular-nums; }
.kpi-label { font-size: 13px; color: #8fa3c0; margin-top: 2px; }
.bs-main { display: flex; gap: 12px; }
.bs-panel { flex: 1; background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.08); border-radius: 10px; padding: 12px 14px; min-height: 380px; }
.bs-panel-title { font-size: 15px; font-weight: 600; color: #fff; margin-bottom: 10px; }
.bz { display: flex; align-items: center; gap: 8px; margin-bottom: 9px; }
.bz-name { width: 100px; font-size: 13px; color: #b9c8de; text-align: right; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.bz-bar { flex: 1; height: 14px; background: rgba(255,255,255,.07); border-radius: 7px; overflow: hidden; }
.bz-bar-in { height: 100%; background: linear-gradient(90deg, #2f6fed, #43c6ac); border-radius: 7px; }
.bz-val { width: 80px; font-size: 12px; color: #8fa3c0; font-variant-numeric: tabular-nums; }
.bs-types { display: flex; flex-direction: column; gap: 8px; }
.bt { display: flex; justify-content: space-between; padding: 8px 12px; background: rgba(255,255,255,.05); border-radius: 6px; }
.bt-name { color: #b9c8de; }
.bt-num { font-weight: 700; color: #fff; }
.bs-empty { color: #43c6ac; font-size: 14px; padding: 20px 0; text-align: center; }
.ba { display: flex; gap: 8px; padding: 7px 10px; background: rgba(231, 76, 60, .12); border-left: 3px solid #e74c3c; border-radius: 4px; margin-bottom: 7px; font-size: 13px; }
.ba-dev { color: #fff; min-width: 110px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.ba-route { color: #f0b27a; flex: 1; }
.ba-time { color: #8fa3c0; font-variant-numeric: tabular-nums; }
.br { display: flex; gap: 8px; padding: 6px 8px; border-bottom: 1px dashed rgba(255,255,255,.07); font-size: 13px; }
.br-time { color: #43c6ac; font-variant-numeric: tabular-nums; width: 44px; }
.br-name { flex: 1; color: #dfe7f3; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.br-zone { color: #8fa3c0; }
.bs-footer { margin-top: 14px; text-align: center; font-size: 12px; color: #5d7290; }
</style>
