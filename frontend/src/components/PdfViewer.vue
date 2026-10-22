<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
const props = defineProps(['layout', 'items', 'selected', 'status'])
const emit = defineEmits(['select', 'open'])
const viewer = ref(null)
const canvas = ref(null)
const zoom = ref(1)
const pageWidth = ref(0)
const pageHeight = ref(0)
const fitActive = ref(true)
let renderTask = null
let observer = null
let renderVersion = 0
const PDF_SCALE = 1.5
const zoomText = computed(() => Math.round(zoom.value * 100) + '%')
const pageStyle = computed(() => ({ width: pageWidth.value * zoom.value + 'px', height: pageHeight.value * zoom.value + 'px' }))
const segments = computed(() => props.items.filter(item => item.segment))
const boxes = computed(() => props.items.filter(item => !item.segment))

async function renderPage(page, first = false, stale = () => false) {
  const version = ++renderVersion
  const viewport = page.getViewport({ scale: PDF_SCALE })
  pageWidth.value = viewport.width
  pageHeight.value = viewport.height
  await nextTick()
  if (renderTask) {
    renderTask.cancel()
    try { await renderTask.promise } catch { /* canceled prior page */ }
    renderTask = null
  }
  if (version !== renderVersion || stale() || !canvas.value) return
  const ratio = Math.min(window.devicePixelRatio || 1, 2)
  const element = canvas.value
  element.width = Math.round(viewport.width * ratio)
  element.height = Math.round(viewport.height * ratio)
  renderTask = page.render({
    canvas: element, canvasContext: element.getContext('2d'), viewport,
    transform: ratio === 1 ? undefined : [ratio, 0, 0, ratio, 0, 0],
  })
  await renderTask.promise
  if (version !== renderVersion || stale()) return
  if (first) fitPage()
  await nextTick()
  if (viewer.value) { viewer.value.scrollLeft = 0; viewer.value.scrollTop = 0 }
}
function fitPage() {
  if (!viewer.value || !pageWidth.value || !pageHeight.value) return
  fitActive.value = true
  zoom.value = Math.max(0.25, Math.min(1.6,
    (viewer.value.clientWidth - 86) / pageWidth.value,
    (viewer.value.clientHeight - 86) / pageHeight.value))
}
function setZoom(scale, clientX, clientY) {
  if (!viewer.value || !pageWidth.value) return
  const next = Math.max(0.25, Math.min(4, scale))
  if (next === zoom.value) return
  const area = viewer.value
  const rect = area.getBoundingClientRect()
  const x = clientX ?? rect.left + rect.width / 2
  const y = clientY ?? rect.top + rect.height / 2
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
  if (!event.ctrlKey || !props.layout) return
  event.preventDefault()
  setZoom(zoom.value * (event.deltaY < 0 ? 1.12 : 1 / 1.12), event.clientX, event.clientY)
}
function boxStyle(item) {
  if (!props.layout) return {}
  const [w, h] = props.layout.size
  const [x0, y0, x1, y1] = item.bbox
  return {
    left: x0 / w * 100 + '%', top: y0 / h * 100 + '%',
    width: Math.max(0.15, (x1 - x0) / w * 100) + '%',
    height: Math.max(0.15, (y1 - y0) / h * 100) + '%',
  }
}
function centerOn(item) {
  if (!viewer.value || !props.layout) return
  const [w, h] = props.layout.size
  const [x0, y0, x1, y1] = item.bbox
  viewer.value.scrollTo({
    left: ((x0 + x1) / 2) / w * pageWidth.value * zoom.value - viewer.value.clientWidth / 2,
    top: ((y0 + y1) / 2) / h * pageHeight.value * zoom.value - viewer.value.clientHeight / 2,
    behavior: 'smooth',
  })
}
function scrollVertical(delta) { viewer.value?.scrollBy({ top: delta, behavior: 'instant' }) }
onMounted(() => {
  observer = new ResizeObserver(() => { if (fitActive.value) fitPage() })
  if (viewer.value) observer.observe(viewer.value)
})
onUnmounted(() => {
  observer?.disconnect()
  if (renderTask) renderTask.cancel()
})
defineExpose({ renderPage, fitPage, setZoom, centerOn, scrollVertical, zoomText })
</script>

<template>
  <div ref="viewer" class="viewer" @wheel="wheelZoom">
    <div v-if="!layout" class="empty-state">
      <div class="empty-illustration"><div class="empty-paper"><div></div><div></div><div></div><div></div></div><span class="empty-spark">✦</span></div>
      <h2>从这里开始检查 PDF 布局</h2>
      <p>拖入一份 PDF，或点击顶部打开文件</p>
      <button class="button primary big" @click="emit('open')">选择本地 PDF <span>↗</span></button>
      <div class="empty-meta">无须 GPU · 本地解析 · 无需联网使用</div>
    </div>
    <div v-else class="page-holder">
      <div class="paper" :style="pageStyle">
        <canvas ref="canvas" class="pdf-canvas"></canvas>
        <div class="overlay">
          <svg v-if="segments.length" class="geometry-overlay" :viewBox="'0 0 ' + layout.size[0] + ' ' + layout.size[1]" preserveAspectRatio="none">
            <line v-for="item in segments" :key="item.id" :x1="item.segment[0]" :y1="item.segment[1]" :x2="item.segment[2]" :y2="item.segment[3]" :class="['geometry-line', item.type, { selected: selected === item.id }]" />
          </svg>
          <button v-for="item in boxes" :key="item.id" class="bbox" :class="[item.type, { selected: selected === item.id }]"
            :style="boxStyle(item)" :aria-label="item.text" :title="item.text" @click="emit('select', item)"></button>
          <button v-for="item in segments" :key="item.id" class="geometry-hit" :style="boxStyle(item)" :aria-label="item.type" :title="item.type" @click="emit('select', item)"></button>
        </div>
      </div>
    </div>
  </div>
</template>
