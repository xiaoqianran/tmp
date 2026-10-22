<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps(['layout', 'item', 'tableStrategy'])
const emit = defineEmits(['export', 'copy'])
const expanded = ref(false)
const showJson = ref(false)

const isWiredTable = computed(() =>
  props.item?.type === 'tables' &&
  ['lines', 'text'].includes(props.tableStrategy) &&
  Array.isArray(props.item.data)
)
const tableRows = computed(() => isWiredTable.value
  ? props.item.data.map(row => Array.isArray(row) ? row.map(cell => String(cell ?? '')) : [])
  : []
)
const columnCount = computed(() => Math.max(0, ...tableRows.value.map(row => row.length)))
const displayRows = computed(() => {
  if (!isWiredTable.value) return []
  if (!Array.isArray(props.item.cells)) {
    return tableRows.value.map(row => row.map(text => ({ text, rowspan: 1, colspan: 1 })))
  }
  const rows = Array.from({ length: tableRows.value.length }, () => [])
  for (const cell of props.item.cells) {
    if (rows[cell.row]) rows[cell.row].push(cell)
  }
  return rows
})
const tableText = computed(() => tableRows.value.map(row =>
  Array.from({ length: columnCount.value }, (_, index) => row[index] ?? '').join('\t')
).join('\n'))

watch(() => props.item, () => {
  expanded.value = false
  showJson.value = false
})

async function copyTable() {
  try {
    await navigator.clipboard.writeText(tableText.value)
  } catch {
    const field = document.createElement('textarea')
    field.value = tableText.value
    document.body.appendChild(field)
    field.select()
    document.execCommand('copy')
    field.remove()
  }
}
</script>

<template>
  <aside class="inspector detail-sidebar">
    <div class="detail-title">
      <div><h2>元素详情</h2><p class="panel-subtitle">选中标注后显示完整内容和坐标</p></div>
      <button class="export-link" :disabled="!layout" @click="emit('export')">导出 JSON ↗</button>
    </div>
    <div v-if="item" class="detail-body">
      <div class="detail-chip" :class="item.type">{{ item.type === 'lines' ? 'Text Line' : item.type === 'tables' ? 'Table · ' + tableStrategy : item.type === 'textboxes' ? 'LTTextBox' : item.type.toUpperCase() }}</div>
      <template v-if="item.score !== undefined"><div class="section-label">表格定位置信度</div><div class="detail-content">{{ (item.score * 100).toFixed(1) }}%</div></template>
      <div class="section-label">{{ item.score !== undefined ? '检测结果' : '完整文字' }}</div>
      <div class="detail-content">{{ item.text }}</div>

      <template v-if="isWiredTable">
        <div class="table-preview-heading">
          <span class="section-label">pdfplumber 表格预览</span>
          <span class="table-dimensions">{{ tableRows.length }} 行 × {{ columnCount }} 列</span>
        </div>
        <template v-if="tableRows.length && columnCount">
          <div class="table-preview-actions">
            <button class="button subtle" @click="showJson = !showJson">{{ showJson ? '表格视图' : 'JSON 视图' }}</button>
            <button class="button subtle" @click="copyTable">复制表格</button>
            <button class="button subtle" @click="expanded = true">放大预览 ⤢</button>
          </div>
          <pre v-if="showJson" class="detail-content table-data">{{ JSON.stringify(item.data, null, 2) }}</pre>
          <div v-else class="table-scroll" role="region" aria-label="识别表格预览" tabindex="0">
            <table class="preview-grid">
              <tbody>
                <tr v-for="(row, rowIndex) in displayRows" :key="rowIndex">
                  <td v-for="(cell, index) in row" :key="index" :rowspan="cell.rowspan" :colspan="cell.colspan" :class="{ 'first-row': rowIndex === 0 }">{{ cell.text ?? '' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
        <div v-else class="detail-content">已定位表格，但未识别出单元格内容。</div>
      </template>
      <div v-else-if="item.type === 'tables' && item.score === undefined" class="detail-content">当前支持 pdfplumber lines / text 的表格预览。</div>

      <div class="section-label">边界坐标 · BBox</div>
      <div class="bbox-grid">
        <div v-for="(axis, index) in ['x0','top','x1','bottom']" :key="axis"><span>{{ axis }}</span><strong>{{ item.bbox[index].toFixed(2) }}</strong></div>
      </div>
      <button class="button subtle copy-detail" @click="emit('copy')">复制文字</button>
    </div>
    <div v-else class="detail-placeholder">点击中间 PDF 标注框，或在左侧元素列表中选取条目。</div>
  </aside>

  <Teleport to="body">
    <div v-if="expanded && isWiredTable" class="table-modal-backdrop" @click.self="expanded = false" @keydown.esc="expanded = false">
      <section class="table-modal" role="dialog" aria-modal="true" aria-label="表格放大预览">
        <div class="table-modal-header">
          <div><h2>pdfplumber 表格 · 放大预览</h2><p>{{ tableStrategy }} · {{ tableRows.length }} 行 × {{ columnCount }} 列</p></div>
          <div class="table-preview-actions">
            <button class="button subtle" @click="copyTable">复制表格</button>
            <button class="button subtle" @click="expanded = false">关闭 ×</button>
          </div>
        </div>
        <div class="table-scroll table-modal-scroll" role="region" aria-label="放大表格" tabindex="0">
          <table class="preview-grid">
            <tbody>
              <tr v-for="(row, rowIndex) in displayRows" :key="rowIndex">
                <td v-for="(cell, index) in row" :key="index" :rowspan="cell.rowspan" :colspan="cell.colspan" :class="{ 'first-row': rowIndex === 0 }">{{ cell.text ?? '' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  </Teleport>
</template>
