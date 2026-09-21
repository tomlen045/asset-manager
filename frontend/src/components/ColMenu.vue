<template>
  <teleport to="body">
    <div v-if="visible" class="colmenu-mask" @click="close" @contextmenu.prevent="close">
      <div class="colmenu" :style="{ left: x + 'px', top: y + 'px' }" @click.stop>
        <div class="colmenu-title">显示列 <span class="hint">（勾选即生效，自动记住）</span></div>
        <div class="colmenu-item" v-for="c in cols" :key="c.prop">
          <el-checkbox :model-value="!hidden.includes(c.prop)"
                       @change="v => toggle(c.prop, v)">{{ c.label }}</el-checkbox>
        </div>
        <div class="colmenu-footer">
          <el-button link size="small" @click="reset">恢复默认</el-button>
          <el-button link size="small" type="primary" @click="close">关闭</el-button>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script setup>
import { ref } from 'vue'

const visible = ref(false), x = ref(0), y = ref(0)
const cols = ref([]), hidden = ref([])
let storeKey = '', onChange = null

function open(e, columns, key, currentHidden, cb) {
  cols.value = columns
  storeKey = key
  hidden.value = [...currentHidden]
  onChange = cb
  // 支持两种触发：鼠标事件（右键/按钮点击带坐标）或按钮元素（无坐标时定位其下方）
  if (e && typeof e.clientX === 'number') {
    x.value = Math.min(e.clientX, window.innerWidth - 240)
    y.value = Math.min(e.clientY, window.innerHeight - 320)
  } else if (e && e.getBoundingClientRect) {
    const r = e.getBoundingClientRect()
    x.value = Math.min(r.left, window.innerWidth - 240)
    y.value = Math.min(r.bottom + 6, window.innerHeight - 320)
  } else {
    x.value = window.innerWidth / 2 - 110
    y.value = window.innerHeight / 2 - 160
  }
  visible.value = true
}
function toggle(prop, show) {
  if (show) hidden.value = hidden.value.filter(p => p !== prop)
  else if (hidden.value.length < cols.value.length - 1) hidden.value.push(prop)
  localStorage.setItem(storeKey, JSON.stringify(hidden.value))
  if (onChange) onChange([...hidden.value])
}
function reset() {
  hidden.value = []
  localStorage.removeItem(storeKey)
  if (onChange) onChange([])
  close()
}
function close() { visible.value = false }
defineExpose({ open })
</script>

<style scoped>
.colmenu-mask { position: fixed; inset: 0; z-index: 3000; }
.colmenu { position: fixed; background: var(--bg-card); border: 1px solid var(--border);
           border-radius: 8px; box-shadow: 0 8px 28px rgba(30,40,70,.18);
           padding: 10px 6px; min-width: 220px; max-height: 70vh; overflow: auto; }
.colmenu-title { font-size: 13px; font-weight: 600; color: var(--text-main);
                 padding: 2px 10px 8px; border-bottom: 1px solid var(--border); }
.colmenu-title .hint { font-weight: 400; font-size: 11px; color: var(--text-dim); }
.colmenu-item { padding: 4px 10px; }
.colmenu-footer { display: flex; justify-content: space-between;
                  border-top: 1px solid var(--border); padding: 6px 10px 0; margin-top: 4px; }
</style>
