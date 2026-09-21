<template>
  <el-button class="back-btn" link @click="goBack">← 返回</el-button>
</template>

<script setup>
import { useRouter } from 'vue-router'
const router = useRouter()
function goBack() {
  router.push('/dashboard')
}
</script>

<style scoped>
.back-btn { font-size: 14px; margin-right: 10px; color: var(--text-dim); }
.back-btn:hover { color: var(--accent); }
</style>
