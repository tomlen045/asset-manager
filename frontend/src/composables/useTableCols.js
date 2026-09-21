import { ref, watch } from 'vue'

/**
 * 表格列管理：显隐（右键菜单）+ 列宽拖拽 + localStorage 持久化
 * @param key    存储键（每页唯一，如 'assets'）
 * @param columns [{prop,label,width?}]
 */
export function useTableCols(key, columns) {
  const HKEY = `am-cols-hidden-${key}`
  const WKEY = `am-cols-width-${key}`

  const hidden = ref(JSON.parse(localStorage.getItem(HKEY) || '[]'))
  const widths = ref(JSON.parse(localStorage.getItem(WKEY) || '{}'))

  function saveHidden() { localStorage.setItem(HKEY, JSON.stringify(hidden.value)) }
  function saveWidths() { localStorage.setItem(WKEY, JSON.stringify(widths.value)) }

  // 右键菜单打开回调（配合 ColMenu 组件）
  const colMenu = ref(null)
  function onHeaderContextMenu(col, e) {
    if (colMenu.value && col.columnKey !== undefined) {
      colMenu.value.open(e, columns, HKEY, hidden.value, (h) => { hidden.value = h; saveHidden() })
    } else if (colMenu.value) {
      colMenu.value.open(e, columns, HKEY, hidden.value, (h) => { hidden.value = h; saveHidden() })
    }
  }

  // 拖拽列宽结束
  function onHeaderDragend(newW, _oldW, col) {
    if (col.property) {
      widths.value[col.property] = Math.round(newW)
      saveWidths()
    }
  }

  // 计算列实际宽度：用户拖过用拖的，否则默认
  function colWidth(col) {
    return widths.value[col.prop] || col.width || null
  }

  // 过滤可见列
  function visibleCols(list) {
    return list.filter(c => !hidden.value.includes(c.prop))
  }

  return { hidden, widths, colMenu, onHeaderContextMenu, onHeaderDragend, colWidth, visibleCols }
}
