import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5180,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8089',
        changeOrigin: true,
      },
    },
  },
  build: {
    // 依赖库独立分包（rolldown-vite 要求函数形式）：echarts/element-plus 改动少，
    // 可长期走浏览器缓存；业务代码更新不使大库缓存失效
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/echarts') || id.includes('node_modules/zrender'))
            return 'echarts'
          if (id.includes('node_modules/element-plus') ||
              id.includes('node_modules/@element-plus'))
            return 'element-plus'
        },
      },
    },
    assetsInlineLimit: 4096,
  },
})
