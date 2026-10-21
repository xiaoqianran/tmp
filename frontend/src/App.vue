<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import * as pdfjs from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl

const input = ref(null)
const viewer = ref(null)
const canvas = ref(null)
const docName = ref('')
const documentId = ref('')
const pageCount = ref(0)
const pageNum = ref(0)
const layout = ref(null)
const busy = ref(false)
const error = ref('')
const status = ref('本地运行 · Windows CPU · 文件不会上传至互联网')
const showLines = ref(true)
const showBoxes = ref(true)
const search = ref('')
const selected = ref('')
const zoom = ref(1)
const pageWidth = ref(0)
const pageHeight = ref(0)
const dragActive = ref(false)
const fitActive = ref(true)

let pdfDocument = null
let renderTask = null
let requestId = 0
let dragDepth = 0
let observer = null
const PDF_SCALE = 1.5

const allItems = computed(() => {
  if (!layout.value) return []
  return [
    ...layout.value.lines.map((entry, index) => ({ ...entry, type: 'lines', id: 'line-' + index })),
    ...layout.value.textboxes.map((entry, index) => ({ ...entry, type: 'textboxes', id: 'box-' + index })),
  ]
})
const filteredItems = computed(() => allItems.value.filter(item => {
  if (item.type === 'lines' && !showLines.value) return false
  if (item.type === 'textboxes' && !showBoxes.value) return false
  return item.text.toLowerCase().includes(search.value.trim().toLowerCase())
}))
const selectedItem = computed(() => allItems.value.find(i => i.id === selected.value))
const pageStyle = computed(() => ({
  width: pageWidth.value * zoom.value + 'px',
  height: pageHeight.value * zoom.value + 'px',
}))
const zoomText = computed(() => Math.round(zoom.value * 100) + '%')

function messageFromError(err) {
  return err?.message || String(err)
}

async function readResponse(response) {
  let data
  try { data = await response.json() } catch { throw new Error('服务器返回了无效响应') }
  if (!response.ok) {
    const detail = data?.detail
    throw new Error(typeof detail === 'string' ? detail : '请求失败 (' + response.status + ')')
  }
  return data
}

async function openPdf(file) {
  if (!file) return
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    error.value = '请选择 PDF 文件'
    return
  }
  busy.value = true
  error.value = ''
  status.value = '正在打开 ' + file.name
  let newPdf
  let newId
  try {
    const bytes = await file.arrayBuffer()
    newPdf = await pdfjs.getDocument({ data: new Uint8Array(bytes) }).promise
    const form = new FormData()
    form.append('file', file)
    const result = await readResponse(await fetch('/api/documents', { method: 'POST', body: form }))
    newId = result.id

    // 在完整验证新文档之后才替换旧文档。
    const oldId = documentId.value
    const oldPdf = pdfDocument
    documentId.value = newId
    pdfDocument = newPdf
    docName.value = result.filename
    pageCount.value = result.pages
    pageNum.value = 0
    layout.value = null
    selected.value = ''
    search.value = ''
    await loadPage(1, true)
    if (oldId) fetch('/api/documents/' + oldId, { method: 'DELETE' }).catch(() => {})
    if (oldPdf) oldPdf.destroy().catch(() => {})
    status.value = '已打开 ' + result.filename + ' · 共 ' + result.pages + ' 页'
  } catch (err) {
    error.value = messageFromError(err)
    status.value = '打开 PDF 失败'
    if (newPdf && newPdf !== pdfDocument) newPdf.destroy().catch(() => {})
    if (newId && newId !== documentId.value) fetch('/api/documents/' + newId, { method: 'DELETE' }).catch(() => {})
  } finally {
    busy.value = false
    if (input.value) input.value.value = ''
  }
}

async function loadPage(number, first = false) {
  if (!pdfDocument || !documentId.value || number < 1 || number > pageCount.value) return
  const current = ++requestId
  busy.value = true
  error.value = ''
  try {
    const [page, response] = await Promise.all([
      pdfDocument.getPage(number),
      fetch('/api/documents/' + documentId.value + '/pages/' + number),
    ])
    const result = await readResponse(response)
    if (current !== requestId) return
    const viewport = page.getViewport({ scale: PDF_SCALE })
    pageNum.value = number
    layout.value = result
    selected.value = ''
    pageWidth.value = viewport.width
    pageHeight.value = viewport.height
    await nextTick()

    if (renderTask) {
      renderTask.cancel()
      try { await renderTask.promise } catch { /* previous render canceled */ }
    }
    if (current !== requestId) return
    const element = canvas.value
    if (!element) return
    const ratio = Math.min(window.devicePixelRatio || 1, 2)
    element.width = Math.round(viewport.width * ratio)
    element.height = Math.round(viewport.height * ratio)
    renderTask = page.render({
      canvas: element,
      canvasContext: element.getContext('2d'),
      viewport,
      transform: ratio === 1 ? undefined : [ratio, 0, 0, ratio, 0, 0],
    })
    await renderTask.promise
    if (current !== requestId) return

    if (first) fitPage()
    await nextTick()
    if (viewer.value) {
      viewer.value.scrollLeft = 0
      viewer.value.scrollTop = 0
    }
  } catch (err) {
    if (current === requestId && err?.name !== 'RenderingCancelledException') {
      error.value = '第 ' + number + ' 页解析失败：' + messageFromError(err)
    }
  } finally {
    if (current === requestId) busy.value = false
  }
}

function fitPage() {
  if (!viewer.value || !pageWidth.value || !pageHeight.value) return
  fitActive.value = true
  const area = viewer.value
  zoom.value = Math.max(0.25, Math.min(1.6,
    (area.clientWidth - 86) / pageWidth.value,
    (area.clientHeight - 86) / pageHeight.value
  ))
}

function setZoom(scale, clientX, clientY) {
  if (!viewer.value || !pageWidth.value) return
  const next = Math.max(0.25, Math.min(4, scale))
  if (next === zoom.value) return
  const area = viewer.value
  const rect = area.getBoundingClientRect()
  const x = clientX ?? (rect.left + rect.width / 2)
  const y = clientY ?? (rect.top + rect.height / 2)
  const paper = area.querySelector('.paper')
  if (!paper) return
  const before = paper.getBoundingClientRect()
  const relativeX = (x - before.left) / zoom.value
  const relativeY = (y - before.top) / zoom.value
  fitActive.value = false
  zoom.value = next
  nextTick(() => {
    const after = paper.getBoundingClientRect()
    area.scrollLeft += after.left + relativeX * next - x
    area.scrollTop += after.top + relativeY * next - y
  })
}

function wheelZoom(event) {
  if (!event.ctrlKey || !layout.value) return
  event.preventDefault()
  setZoom(zoom.value * (event.deltaY < 0 ? 1.12 : 1 / 1.12), event.clientX, event.clientY)
}

function boxStyle(item) {
  if (!layout.value) return {}
  const [w, h] = layout.value.size
  const [x0, y0, x1, y1] = item.bbox
  return {
    left: x0 / w * 100 + '%',
    top: y0 / h * 100 + '%',
    width: Math.max(0, (x1 - x0) / w * 100) + '%',
    height: Math.max(0, (y1 - y0) / h * 100) + '%',
  }
}

function choose(item, center = false) {
  selected.value = item.id
  if (center && viewer.value && layout.value) {
    const [w, h] = layout.value.size
    const [x0, y0, x1, y1] = item.bbox
    viewer.value.scrollTo({
      left: ((x0 + x1) / 2) / w * pageWidth.value * zoom.value - viewer.value.clientWidth / 2,
      top: ((y0 + y1) / 2) / h * pageHeight.value * zoom.value - viewer.value.clientHeight / 2,
      behavior: 'smooth',
    })
  }
}

function downloadJson() {
  if (!layout.value) return
  const blob = new Blob([JSON.stringify(layout.value, null, 2)], { type: 'application/json' })
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
    event.preventDefault()
    input.value?.click()
    return
  }
  if (event.ctrlKey && event.code === 'KeyS') {
    event.preventDefault()
    downloadJson()
    return
  }
  if (event.altKey && (event.code === 'ArrowLeft' || event.code === 'ArrowRight')) {
    event.preventDefault()
    loadPage(pageNum.value + (event.code === 'ArrowLeft' ? -1 : 1))
    return
  }
  if (event.altKey || event.ctrlKey || event.metaKey || !viewer.value || !layout.value) return
  const moves = {
    ArrowLeft: [-90, 0], KeyA: [-90, 0],
    ArrowRight: [90, 0], KeyD: [90, 0],
    ArrowUp: [0, -90], KeyW: [0, -90],
    ArrowDown: [0, 90], KeyS: [0, 90],
  }
  const delta = moves[event.code]
  if (delta) {
    event.preventDefault()
    viewer.value.scrollBy({ left: delta[0], top: delta[1], behavior: 'instant' })
  }
}

onMounted(() => {
  observer = new ResizeObserver(() => { if (fitActive.value) fitPage() })
  if (viewer.value) observer.observe(viewer.value)
  window.addEventListener('dragenter', onDragEnter)
  window.addEventListener('dragleave', onDragLeave)
  window.addEventListener('dragover', onDragOver)
  window.addEventListener('drop', onDrop)
  window.addEventListener('keydown', onKeyDown)
})
onUnmounted(() => {
  observer?.disconnect()
  window.removeEventListener('dragenter', onDragEnter)
  window.removeEventListener('dragleave', onDragLeave)
  window.removeEventListener('dragover', onDragOver)
  window.removeEventListener('drop', onDrop)
  window.removeEventListener('keydown', onKeyDown)
  if (renderTask) renderTask.cancel()
  if (pdfDocument) pdfDocument.destroy()
})
</script>

<template>
  <div class="app">
    <header class="topbar">
      <div class="identity">
        <div class="brand-icon"><span>▧</span></div>
        <div>
          <div class="brand-name">PDF Layout <span>Inspector</span></div>
          <div class="brand-sub">NATIVE PDF · STRUCTURE WORKSPACE</div>
        </div>
      </div>
      <div class="top-actions">
        <div class="local-label"><span class="online-dot"></span> LOCAL / CPU</div>
        <span class="top-divider"></span>
        <span class="file-name" :title="docName">{{ docName || '尚未打开文件' }}</span>
        <input ref="input" class="sr-only" type="file" accept=".pdf,application/pdf" @change="openPdf($event.target.files?.[0])">
        <button class="button primary" @click="input.click()"><span class="plus">＋</span> 打开 PDF</button>
      </div>
    </header>

    <div class="workspace">
      <section class="main-area">
        <nav class="toolbar">
          <div class="tools-left">
            <div class="page-controls">
              <button class="icon-button" title="上一页 (Alt+←)" :disabled="pageNum <= 1 || busy" @click="loadPage(pageNum-1)">‹</button>
              <span class="page-indicator"><strong>{{ pageNum || '—' }}</strong><i>/</i>{{ pageCount || '—' }}</span>
              <button class="icon-button" title="下一页 (Alt+→)" :disabled="pageNum >= pageCount || busy" @click="loadPage(pageNum+1)">›</button>
            </div>
            <div class="bar-divider"></div>
            <label class="toggle-toggle"><input type="checkbox" v-model="showLines"><span class="legend-dot red"></span>Text Lines</label>
            <label class="toggle-toggle"><input type="checkbox" v-model="showBoxes"><span class="legend-dot blue"></span>LTTextBox</label>
          </div>
          <div class="tools-right">
            <button class="icon-button zoom-btn" :disabled="!layout" title="缩小" @click="setZoom(zoom / 1.15)">−</button>
            <span class="zoom-number">{{ zoomText }}</span>
            <button class="icon-button zoom-btn" :disabled="!layout" title="放大" @click="setZoom(zoom * 1.15)">+</button>
            <button class="button subtle" :disabled="!layout" @click="fitPage">适应窗口</button>
            <button class="button subtle" :disabled="!layout" @click="setZoom(1)">100%</button>
          </div>
        </nav>

        <div ref="viewer" class="viewer" @wheel="wheelZoom">
          <div v-if="!layout" class="empty-state">
            <div class="empty-illustration">
              <div class="empty-paper"><div></div><div></div><div></div><div></div></div>
              <span class="empty-spark">✦</span>
            </div>
            <h2>从这里开始检查 PDF 布局</h2>
            <p>拖入一份 PDF，或点击顶部打开文件</p>
            <button class="button primary big" @click="input.click()">选择本地 PDF <span>↗</span></button>
            <div class="empty-meta">无须 GPU · 本地解析 · 无需联网使用</div>
          </div>
          <div v-else class="page-holder">
            <div class="paper" :style="pageStyle">
              <canvas ref="canvas" class="pdf-canvas"></canvas>
              <div class="overlay">
                <template v-for="item in allItems" :key="item.id">
                  <button
                    v-if="(item.type === 'lines' && showLines) || (item.type === 'textboxes' && showBoxes)"
                    class="bbox"
                    :class="[item.type, { selected: selected === item.id }]"
                    :style="boxStyle(item)"
                    :aria-label="item.text"
                    :title="item.text"
                    @click="choose(item)"
                  ></button>
                </template>
              </div>
            </div>
          </div>
        </div>
        <div class="viewer-footer">
          <span><span class="footer-dot"></span>{{ status }}</span>
          <span class="shortcuts">Ctrl + 滚轮缩放 <i>·</i> WASD / 方向键移动 <i>·</i> Alt + ← → 翻页</span>
        </div>
      </section>

      <aside class="inspector">
        <div class="inspector-head">
          <div class="inspector-kicker">DOCUMENT ANALYSIS</div>
          <div class="inspector-title-row"><h2>布局元素</h2><span class="count-badge">{{ filteredItems.length }}</span></div>
          <p>比较 pdfplumber 与 pdfminer.six 的文本分组</p>
          <div class="stats">
            <div><span class="stat-number">{{ layout?.lines.length ?? 0 }}</span><span>Text Lines</span></div>
            <div><span class="stat-number">{{ layout?.textboxes.length ?? 0 }}</span><span>LTTextBox</span></div>
          </div>
          <div class="search-wrap">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"></circle><path d="m16 16 5 5"></path></svg>
            <input v-model="search" aria-label="搜索文字内容" placeholder="搜索文字内容…" :disabled="!layout">
            <kbd v-if="!search">TEXT</kbd>
            <button v-else class="clear-search" aria-label="清除搜索" @click="search=''">×</button>
          </div>
        </div>

        <div class="element-list">
          <template v-if="filteredItems.length">
            <button v-for="item in filteredItems" :key="item.id" class="element-item"
              :class="{ active: selected === item.id }" @click="choose(item, true)">
              <span class="element-bar" :class="item.type"></span>
              <span class="element-text">
                <span class="element-type">{{ item.type === 'lines' ? 'TEXT LINE' : 'LT TEXT BOX' }}</span>
                <span class="element-preview">{{ item.text }}</span>
              </span>
              <span class="element-chevron">›</span>
            </button>
          </template>
          <div v-else class="list-empty">{{ layout ? '没有匹配的文字元素' : '打开 PDF 后显示布局候选' }}</div>
        </div>
        <div class="detail-panel">
          <div class="detail-title">
            <strong>元素详情</strong>
            <button class="export-link" :disabled="!layout" @click="downloadJson()">导出 JSON ↗</button>
          </div>
          <template v-if="selectedItem">
            <div class="detail-chip" :class="selectedItem.type">{{ selectedItem.type === 'lines' ? 'Text Line' : 'LTTextBox' }}</div>
            <div class="detail-content">{{ selectedItem.text }}</div>
            <div class="bbox-info">BBox <code>{{ selectedItem.bbox.map(n => n.toFixed(1)).join(' , ') }}</code></div>
          </template>
          <div v-else class="detail-placeholder">点击页面标注或右侧文字，查看完整内容与坐标。</div>
        </div>
      </aside>
    </div>

    <div v-if="busy" class="loading"><span class="spinner"></span> 正在解析 PDF…</div>
    <div v-if="error" class="error-toast" role="alert"><span>{{ error }}</span><button @click="error=''">×</button></div>
    <div v-if="dragActive" class="drop-overlay"><div class="drop-frame"><span class="drop-icon">⇧</span><strong>松开以打开 PDF</strong><small>本地读取并解析，不会上传到互联网</small></div></div>
  </div>
</template>
