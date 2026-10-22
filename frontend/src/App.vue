<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { usePdf } from './composables/usePdf'
import PdfViewer from './components/PdfViewer.vue'
import ElementPanel from './components/ElementPanel.vue'
import DetailPanel from './components/DetailPanel.vue'
import ThumbnailSidebar from './components/ThumbnailSidebar.vue'
import { getCamelotTables, getDocLayoutTables } from './api'

const input = ref(null)
const pdfViewer = ref(null)
const { docName, documentId, pageCount, pageNum, layout, busy, error, status, openPdf: openDocument, loadPage, closePdf, getPdfPage } =
  usePdf((page, first, stale) => pdfViewer.value.renderPage(page, first, stale))
const showLines = ref(true)
const showBoxes = ref(true)
const showTables = ref(true)
const extraLayers = ref({ words: false, chars: false, strokes: false, rects: false, curves: false, edges: false, images: false, intersections: false, cells: false, tableEdges: false })
const extraTypes = ['words', 'chars', 'strokes', 'rects', 'curves', 'edges', 'images']
const activeTab = ref('pdfplumber')
const tableStrategy = ref('text')
const camelotStrategy = ref('stream')
const camelotResults = ref({})
const camelotBusy = ref(false)
const camelotError = ref('')
const doclayoutThreshold = ref(0.5)
const doclayoutResults = ref({})
const doclayoutBusy = ref(false)
const doclayoutError = ref('')
let doclayoutRequest = 0
watch([activeTab, documentId, pageNum, doclayoutThreshold], async () => {
  const request = ++doclayoutRequest
  doclayoutError.value = ''
  if (activeTab.value !== 'doclayout' || !documentId.value || !pageNum.value) return
  const key = documentId.value + ':' + pageNum.value + ':' + doclayoutThreshold.value
  if (doclayoutResults.value[key]) return
  doclayoutBusy.value = true
  try {
    const result = await getDocLayoutTables(documentId.value, pageNum.value, doclayoutThreshold.value)
    if (request === doclayoutRequest) doclayoutResults.value = { ...doclayoutResults.value, [key]: result.tables }
  } catch (err) {
    if (request === doclayoutRequest) doclayoutError.value = err.message || String(err)
  } finally { if (request === doclayoutRequest) doclayoutBusy.value = false }
})
const doclayoutTables = computed(() => doclayoutResults.value[documentId.value + ':' + pageNum.value + ':' + doclayoutThreshold.value] || [])
const currentStrategy = computed({
  get: () => activeTab.value === 'doclayout' ? 'PP-DocLayout-M' : activeTab.value === 'camelot' ? camelotStrategy.value : tableStrategy.value,
  set: value => { if (activeTab.value === 'camelot') camelotStrategy.value = value; else tableStrategy.value = value },
})
let camelotRequest = 0
watch([activeTab, camelotStrategy, documentId, pageNum], async () => {
  const request = ++camelotRequest
  camelotError.value = ''
  if (activeTab.value !== 'camelot' || !documentId.value || !pageNum.value) return
  const key = documentId.value + ':' + pageNum.value + ':' + camelotStrategy.value
  if (camelotResults.value[key]) return
  camelotBusy.value = true
  try {
    const result = await getCamelotTables(documentId.value, pageNum.value, camelotStrategy.value)
    if (request === camelotRequest) camelotResults.value = { ...camelotResults.value, [key]: result.tables }
  } catch (err) {
    if (request === camelotRequest) camelotError.value = err.message || String(err)
  } finally { if (request === camelotRequest) camelotBusy.value = false }
})
const camelotTables = computed(() => camelotResults.value[documentId.value + ':' + pageNum.value + ':' + camelotStrategy.value] || [])
const search = ref('')
watch([activeTab, currentStrategy], () => {
  search.value = ''
  selected.value = ''
  showTables.value = true
})
const selected = ref('')
const dragActive = ref(false)
const leftOpen = ref(true)
const rightOpen = ref(true)
const thumbnailsOpen = ref(true)
const pageInput = ref('1')
const pageInputError = ref(false)
watch(pageNum, number => { pageInput.value = String(number || 1); pageInputError.value = false })
function jumpToPage() {
  const value = Number(pageInput.value)
  if (!Number.isInteger(value) || value < 1 || value > pageCount.value) {
    pageInputError.value = true
    return
  }
  pageInputError.value = false
  loadPage(value)
}
function resetPageInput() {
  pageInput.value = String(pageNum.value || 1)
  pageInputError.value = false
}
const leftWidth = ref(290)
const rightWidth = ref(320)
const workspaceStyle = computed(() => ({
  gridTemplateColumns: [
    ...(leftOpen.value ? [leftWidth.value + 'px', '6px'] : []),
    'minmax(0, 1fr)',
    ...(rightOpen.value ? ['6px', rightWidth.value + 'px'] : []),
  ].join(' '),
}))
const allItems = computed(() => layout.value ? [
  ...layout.value.lines.map((entry, index) => ({ ...entry, type: 'lines', id: 'line-' + index })),
  ...layout.value.textboxes.map((entry, index) => ({ ...entry, type: 'textboxes', id: 'box-' + index })),
  ...extraTypes.flatMap(type => (['words', 'chars', 'images'].includes(type) ? (layout.value[type] || []) : (layout.value.strokes?.[type === 'strokes' ? 'lines' : type] || [])).map((entry, index) => ({ ...entry, type, id: type + '-' + index }))),
  ...['intersections', 'cells', 'tableEdges'].flatMap(type => (layout.value.table_debug?.[tableStrategy.value]?.[type === 'tableEdges' ? 'edges' : type] || []).map((entry, index) => ({ ...entry, type, id: type + '-' + index }))),
  ...(activeTab.value === 'doclayout' ? doclayoutTables.value : activeTab.value === 'camelot' ? camelotTables.value : layout.value.tables?.[tableStrategy.value] || []).map((entry, index) => ({
    ...entry, type: 'tables', id: 'table-' + currentStrategy.value + '-' + index,
  })),
] : [])
const visibleItems = computed(() => allItems.value.filter(item =>
  activeTab.value !== 'pdfplumber' ? item.type === 'tables' && showTables.value :
  (item.type === 'lines' && showLines.value) ||
  (item.type === 'textboxes' && showBoxes.value) ||
  (extraLayers.value[item.type] === true) ||
  (item.type === 'tables' && showTables.value)
))
const filteredItems = computed(() => visibleItems.value.filter(item =>
  item.text.toLowerCase().includes(search.value.trim().toLowerCase())))
const selectedItem = computed(() => visibleItems.value.find(item => item.id === selected.value))
const zoomText = computed(() => pdfViewer.value?.zoomText || '100%')
watch([layout, tableStrategy, camelotStrategy, activeTab], () => { selected.value = '' })

let dragging = null
let dragDepth = 0
function startResize(side, event) {
  event.preventDefault()
  dragging = { side, x: event.clientX, width: side === 'left' ? leftWidth.value : rightWidth.value }
  window.addEventListener('pointermove', resizeMove)
  window.addEventListener('pointerup', stopResize, { once: true })
}
function resizeMove(event) {
  if (!dragging) return
  const delta = event.clientX - dragging.x
  const width = Math.max(210, Math.min(540, dragging.width + (dragging.side === 'left' ? delta : -delta)))
  if (dragging.side === 'left') leftWidth.value = width
  else rightWidth.value = width
}
function stopResize() { dragging = null; window.removeEventListener('pointermove', resizeMove) }

async function openPdf(file) {
  if (!file) return
  search.value = ''
  selected.value = ''
  await openDocument(file)
  if (input.value) input.value.value = ''
}
function choose(item, center = false) {
  selected.value = item.id
  if (center) pdfViewer.value?.centerOn(item)
}
async function copySelectedText() {
  if (!selectedItem.value) return
  try {
    await navigator.clipboard.writeText(selectedItem.value.text)
    status.value = '已复制元素文字'
  } catch { error.value = '复制失败，请检查浏览器剪贴板权限' }
}
function downloadJson() {
  if (!layout.value) return
  const blob = new Blob([JSON.stringify({ ...layout.value, ...(activeTab.value === 'camelot' ? { camelot: { strategy: camelotStrategy.value, tables: camelotTables.value } } : {}), ...(activeTab.value === 'doclayout' ? { doclayout: { model: 'PP-DocLayout-M ONNX', threshold: doclayoutThreshold.value, tables: doclayoutTables.value } } : {}) }, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = docName.value.replace(/\.pdf$/i, '') + '_page_' + pageNum.value + '.json'
  link.click()
  URL.revokeObjectURL(url)
}
function onDragEnter(event) {
  if (!event.dataTransfer?.types?.includes('Files')) return
  event.preventDefault()
  dragDepth++
  dragActive.value = true
}
function onDragLeave(event) {
  if (!event.dataTransfer?.types?.includes('Files')) return
  event.preventDefault()
  dragDepth = Math.max(0, dragDepth - 1)
  if (!dragDepth) dragActive.value = false
}
function onDragOver(event) {
  if (event.dataTransfer?.types?.includes('Files')) event.preventDefault()
}
function onDrop(event) {
  event.preventDefault()
  dragDepth = 0
  dragActive.value = false
  const file = Array.from(event.dataTransfer?.files || []).find(f => f.name.toLowerCase().endsWith('.pdf'))
  if (file) openPdf(file)
  else if (event.dataTransfer?.files?.length) error.value = '请拖入 PDF 文件'
}
function onKeyDown(event) {
  const element = event.target
  if (element instanceof HTMLElement && (element.matches('input,textarea,select') || element.isContentEditable)) return
  if (event.ctrlKey && event.code === 'KeyO') {
    event.preventDefault(); input.value?.click(); return
  }
  if (event.ctrlKey && event.code === 'KeyS') {
    event.preventDefault(); downloadJson(); return
  }
  if (event.altKey || event.ctrlKey || event.metaKey || !documentId.value) return
  if (event.code === 'ArrowLeft' || event.code === 'KeyA') {
    event.preventDefault(); loadPage(pageNum.value - 1); return
  }
  if (event.code === 'ArrowRight' || event.code === 'KeyD') {
    event.preventDefault(); loadPage(pageNum.value + 1); return
  }
  const vertical = { ArrowUp: -90, KeyW: -90, ArrowDown: 90, KeyS: 90 }[event.code]
  if (vertical !== undefined) {
    event.preventDefault(); pdfViewer.value?.scrollVertical(vertical)
  }
}
onMounted(() => {
  window.addEventListener('dragenter', onDragEnter)
  window.addEventListener('dragleave', onDragLeave)
  window.addEventListener('dragover', onDragOver)
  window.addEventListener('drop', onDrop)
  window.addEventListener('keydown', onKeyDown, true)
})
onUnmounted(() => {
  for (const [type, handler] of [['dragenter', onDragEnter], ['dragleave', onDragLeave], ['dragover', onDragOver], ['drop', onDrop], ['keydown', onKeyDown]]) window.removeEventListener(type, handler, true)
  stopResize()
  closePdf()
})
</script>

<template>
  <div class="app">
    <header class="topbar">
      <div class="identity">
        <div class="brand-icon"><span>▧</span></div>
        <div><div class="brand-name">PDF Layout <span>Inspector</span></div><div class="brand-sub">NATIVE PDF · STRUCTURE WORKSPACE</div></div>
      </div>
      <div class="top-actions">
        <div class="local-label"><span class="online-dot"></span> LOCAL / CPU</div>
        <span class="top-divider"></span>
        <span class="file-name" :title="docName">{{ docName || '尚未打开文件' }}</span>
        <input ref="input" class="sr-only" type="file" accept=".pdf,application/pdf" @change="openPdf($event.target.files?.[0])">
        <button class="button primary" @click="input.click()"><span class="plus">＋</span> 打开 PDF</button>
      </div>
    </header>

    <div class="workspace" :style="workspaceStyle">
      <ElementPanel v-show="leftOpen" :layout="layout" :items="filteredItems" :selected="selected"
        v-model:activeTab="activeTab" v-model:tableStrategy="currentStrategy"
        v-model:showLines="showLines" v-model:showBoxes="showBoxes" v-model:showTables="showTables"
        v-model:search="search" v-model:extraLayers="extraLayers" :camelotCount="camelotTables.length" :camelotBusy="camelotBusy" :camelotError="camelotError"
        :doclayoutCount="doclayoutTables.length" :doclayoutBusy="doclayoutBusy" :doclayoutError="doclayoutError"
        v-model:doclayoutThreshold="doclayoutThreshold" @select="choose($event, true)" />
      <div v-if="leftOpen" class="splitter" role="separator" aria-label="调整左侧宽度" @pointerdown="startResize('left', $event)"></div>
      <section class="main-area">
        <nav class="toolbar">
          <div class="tools-left">
            <button class="icon-button panel-toggle" title="切换元素列表" @click="leftOpen = !leftOpen">☷</button>
            <button class="icon-button panel-toggle thumbnail-toggle" title="切换页面预览" :aria-pressed="thumbnailsOpen" @click="thumbnailsOpen = !thumbnailsOpen">▤</button>
            <div class="page-controls">
              <button class="icon-button" title="上一页 (A / ←)" :disabled="pageNum <= 1 || !documentId" @click="loadPage(pageNum - 1)">‹</button>
              <span class="page-indicator"><input class="page-number-input" :class="{ invalid: pageInputError }" type="number" min="1" :max="pageCount" :disabled="!documentId" aria-label="页码输入" v-model="pageInput" @keydown.enter="jumpToPage" @keydown.esc="resetPageInput"><strong class="sr-only">{{ pageNum || '—' }}</strong><i>/</i>{{ pageCount || '—' }}</span>
              <button class="icon-button" title="下一页 (D / →)" :disabled="pageNum >= pageCount || !documentId" @click="loadPage(pageNum + 1)">›</button>
              <button class="button subtle page-jump" :disabled="!documentId" @click="jumpToPage">跳转</button>
            </div>
            <div class="bar-divider"></div>
            <label class="toggle-toggle"><input type="checkbox" v-model="showLines"><span class="legend-dot red"></span>Text Lines</label>
            <label class="toggle-toggle"><input type="checkbox" v-model="showBoxes"><span class="legend-dot blue"></span>LTTextBox</label>
            <label class="toggle-toggle"><input type="checkbox" v-model="showTables"><span class="legend-dot green"></span>Tables ({{ tableStrategy }})</label>
          </div>
          <div class="tools-right">
            <button class="icon-button panel-toggle" title="切换详情面板" @click="rightOpen = !rightOpen">☷</button>
            <button class="icon-button zoom-btn" :disabled="!layout" title="缩小" @click="pdfViewer?.setZoom((parseInt(zoomText) / 100) / 1.15)">−</button>
            <span class="zoom-number">{{ zoomText }}</span>
            <button class="icon-button zoom-btn" :disabled="!layout" title="放大" @click="pdfViewer?.setZoom((parseInt(zoomText) / 100) * 1.15)">+</button>
            <button class="button subtle" :disabled="!layout" @click="pdfViewer?.fitPage()">适应窗口</button>
            <button class="button subtle" :disabled="!layout" @click="pdfViewer?.setZoom(1)">100%</button>
          </div>
        </nav>
        <div class="pdf-reading-space">
          <ThumbnailSidebar v-if="thumbnailsOpen" :documentId="documentId" :pageCount="pageCount"
            :pageNum="pageNum" :getPage="getPdfPage" @navigate="loadPage" />
          <PdfViewer ref="pdfViewer" :layout="layout" :items="visibleItems" :selected="selected"
            :status="status" @select="choose" @open="input?.click()" />
        </div>
        <div class="viewer-footer"><span><span class="footer-dot"></span>{{ status }}</span><span class="shortcuts">Ctrl + 滚轮缩放 <i>·</i> A/D / ← → 翻页 <i>·</i> W/S / ↑ ↓ 竖向滚动</span></div>
      </section>
      <div v-if="rightOpen" class="splitter" role="separator" aria-label="调整右侧宽度" @pointerdown="startResize('right', $event)"></div>
      <DetailPanel v-show="rightOpen" :layout="layout" :item="selectedItem" :tableStrategy="currentStrategy"
        @export="downloadJson" @copy="copySelectedText" />
    </div>
    <div v-if="busy" class="loading"><span class="spinner"></span> 正在解析 PDF…</div>
    <div v-if="error" class="error-toast" role="alert"><span>{{ error }}</span><button @click="error=''">×</button></div>
    <div v-if="dragActive" class="drop-overlay"><div class="drop-frame"><span class="drop-icon">⇧</span><strong>松开以打开 PDF</strong><small>本地读取并解析，不会上传到互联网</small></div></div>
  </div>
</template>
