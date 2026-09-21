# asset-manager 主题规则（永久遵守）

> 写入时间：2026-09-01，用户要求"记住这个，以后都按照这个规则"

## 主题铁律

1. **后台页面一律浅色主题**。当前 style.css 内置 4 套方案，通过 `html[data-theme]` 切换：
   - `a` 蓝白商务（默认）：底 #f5f7fa / 卡片 #fff / 主色 #3477f6
   - `b` 青瓷冷灰：底 #f2f6f6 / 主色 #0f9488
   - `c` 暖米雅致：底 #faf7f2 / 主色 #c47f17
   - `d` 紫灰现代：底 #f6f5fa / 主色 #6f5bd4
2. **切换入口**：Layout.vue 侧边栏底部 🎨 色板，点击即换，localStorage key=`am-theme` 记忆。
3. **新建页面/组件禁止硬编码 hex 色值**，必须引用 `var(--bg-page)` `var(--accent)` 等变量，否则切主题时该处不跟随。
4. **数据大屏 BigScreen.vue 是唯一例外**：保持暗色（投屏惯例），不引用主题变量。
5. **禁止 Element Plus dark class**：main.js 不得出现 `document.documentElement.classList.add('dark')`（曾导致下拉/日期弹层冒暗色）。
6. ECharts 轴标签用 `#6b7a99`（var(--text-dim) 同值），网格线 `#dfe5f1`，禁止再使用暗色系的 #8a97b8/#263352。

## 修改主题的入口

- 全部变量集中在一个文件：`frontend/src/style.css`（4 组 `:root`/`html[data-theme]` 变量块）
- 切换逻辑：`frontend/src/views/Layout.vue`（setTheme 函数）
