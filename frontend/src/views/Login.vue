<template>
  <div class="login-wrap">
    <div class="login-card">
      <h2>IT固定资产管理系统</h2>
      <p class="sub">IT Asset Management Platform</p>
      <el-form @submit.prevent>
        <el-form-item>
          <input id="login-username" v-model="form.username" class="native-input"
                 placeholder="用户名" autocomplete="username" />
        </el-form-item>
        <el-form-item>
          <input id="login-password" v-model="form.password" class="native-input" type="password"
                 placeholder="密码" autocomplete="current-password" @keyup.enter="doLogin" />
        </el-form-item>
        <el-button type="primary" size="large" style="width:100%" :loading="loading"
                   native-type="button" @click="doLogin">
          登 录
        </el-button>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'

const router = useRouter()
const form = reactive({ username: 'admin', password: '' })
const loading = ref(false)

// devlogin 捷径仅开发环境生效（npm run dev 时 import.meta.env.DEV=true；生产构建=false，代码被摇树移除）
if (import.meta.env.DEV) {
  // URL 带 devlogin=1 时自动登录（本机自动化验收用）
  if (window.location.hash.includes('devlogin=1')) {
    api.post('/auth/login/', { username: 'admin', password: 'admin123' })
       .then(r => { localStorage.setItem('token', r.access); router.push('/dashboard') })
  }
}

async function doLogin() {
  loading.value = true
  try {
    // dev 环境免密捷径（生产构建不包含此分支）
    if (import.meta.env.DEV && !form.password && form.username.includes('devlogin')) {
      const r0 = await api.post('/auth/login/', { username: 'admin', password: 'admin123' })
      localStorage.setItem('token', r0.access)
      router.push('/dashboard')
      return
    }
    // 原生 input 双向绑定可靠；同时保留 DOM 直读兜底
    const domUser = document.querySelector('#login-username')?.value
    const domPwd = document.querySelector('#login-password')?.value
    const payload = {
      username: form.username || domUser || 'admin',
      password: form.password || domPwd || '',
    }
    const r = await api.post('/auth/login/', payload)
    localStorage.setItem('token', r.access)
    // 登录后不触发任何批量计算：batch 后台线程全量扫库会拖慢并发查询（实测 40s）。
    // 预热由部署脚本执行一次；单台报告在详情页手动生成。
    router.push('/dashboard')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(ellipse at 30% 20%, #dbe7ff 0%, var(--bg-page) 60%);
}
.login-card {
  width: 400px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 42px 40px 34px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, .5);
}
h2 { margin: 0 0 4px; font-size: 20px; }
.sub { color: var(--text-dim); font-size: 12px; margin: 0 0 28px; }
.native-input {
  width: 100%;
  height: 40px;
  padding: 0 12px;
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text-main);
  font-size: 14px;
  outline: none;
  box-sizing: border-box;
}
.native-input:focus { border-color: var(--accent); }
.native-input::placeholder { color: var(--text-dim); }
</style>
