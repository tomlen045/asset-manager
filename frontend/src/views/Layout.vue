<template>
  <el-container class="layout">
    <el-aside width="210px" class="aside">
      <div class="logo">
        <span class="logo-main">IT资产管理</span>
        <span class="logo-sub">Asset Manager</span>
      </div>
      <el-menu :default-active="$route.path" router background-color="transparent"
               text-color="#7a869c" active-text-color="var(--accent)">
        <el-menu-item index="/dashboard">📊 工作台</el-menu-item>
        <el-menu-item index="/assets">💻 资产台账</el-menu-item>
        <el-menu-item index="/assets-import">📥 批量导入</el-menu-item>
        <el-menu-item index="/categories">🏷️ 类别管理</el-menu-item>
        <el-menu-item index="/repairs">🔧 维修管理</el-menu-item>
        <el-menu-item index="/flows">📋 资产流程</el-menu-item>
        <el-menu-item index="/stocktakes">📱 资产盘点</el-menu-item>
        <el-menu-item index="/economy">♻️ 报废预测</el-menu-item>
        <el-menu-item index="/unassigned-dept">⚠️ 未分配部门</el-menu-item>
        <el-menu-item index="/pda">📱 移动设备定位</el-menu-item>
        <el-menu-item index="/pda-bigscreen">🖥 定位大屏</el-menu-item>
        <el-menu-item index="/bigscreen" @click.stop>🖥️ 数据大屏</el-menu-item>
      </el-menu>
      <div class="aside-footer">
        <div class="theme-picker">
          <span class="tp-label">🎨 主题</span>
          <div class="tp-dots">
            <button v-for="t in themes" :key="t.key"
                    class="tp-dot" :class="{ active: cur === t.key }"
                    :style="{ background: themeDotColor[t.key] }"
                    :title="t.name"
                    @click="setTheme(t.key)" />
          </div>
        </div>
        <el-button link type="danger" @click="logout">退出登录</el-button>
      </div>
    </el-aside>
    <el-main class="main">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { ref } from 'vue'

const router = useRouter()

// 主题切换：4 套浅色方案，选择存 localStorage
const themes = [
  { key: 'a', name: 'A 蓝白商务' },
  { key: 'b', name: 'B 青瓷冷灰' },
  { key: 'c', name: 'C 暖米雅致' },
  { key: 'd', name: 'D 紫灰现代' },
]
const themeDotColor = { a: '#3477f6', b: '#0f9488', c: '#c47f17', d: '#6f5bd4' }
const cur = ref(localStorage.getItem('am-theme') || 'a')

function setTheme(k) {
  cur.value = k
  document.documentElement.setAttribute('data-theme', k)
  localStorage.setItem('am-theme', k)
}
// 初始化
setTheme(cur.value)

function logout() {
  localStorage.removeItem('token')
  router.push('/login')
}
</script>

<style scoped>
.layout { min-height: 100vh; }
.aside {
  background: var(--bg-card);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
}
.logo {
  padding: 22px 20px 18px;
  border-bottom: 1px solid var(--border);
}
.logo-main { display: block; font-size: 17px; font-weight: 700; color: var(--accent); }
.logo-sub { display: block; font-size: 11px; color: var(--text-dim); margin-top: 3px; letter-spacing: 1px; }
.el-menu { border-right: none; flex: 1; }
.aside-footer { padding: 16px 20px; border-top: 1px solid var(--border); }
.theme-picker {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 10px;
}
.tp-label { font-size: 12px; color: var(--text-dim); }
.tp-dots { display: flex; gap: 8px; }
.tp-dot {
  width: 18px; height: 18px; border-radius: 50%;
  border: 2px solid transparent; cursor: pointer; padding: 0;
  outline: 2px solid transparent; outline-offset: 2px;
  transition: all .15s;
}
.tp-dot.active { outline-color: var(--text-dim); transform: scale(1.15); }
.main { background: var(--bg-page); padding: 24px 28px; }
</style>
