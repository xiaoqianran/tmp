<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
const props = defineProps({ documentId: String, pageCount: Number, pageNum: Number, getPage: Function })
const emit = defineEmits(['navigate'])
const list = ref(null)
const previews = ref({})
const cache = new Map()
const MAX_CACHE = 80
let observer = null
let generation = 0
let queue = Promise.resolve()

function requestThumbnail(number) {
  if (cache.has(number)) {
    previews.value = { ...previews.value, [number]: cache.get(number) }
    return
  }
  const token = generation
  queue = queue.catch(() => {}).then(async () => {
    if (token !== generation || cache.has(number)) return
    let page
    try {
      page = await props.getPage(number)
      if (token !== generation) return
      const viewport = page.getViewport({ scale: 126 / page.getViewport({ scale: 1 }).width })
      const canvas = document.createElement('canvas')
      canvas.width = Math.ceil(viewport.width)
      canvas.height = Math.ceil(viewport.height)
      await page.render({ canvas, canvasContext: canvas.getContext('2d'), viewport }).promise
      if (token !== generation) return
      const url = canvas.toDataURL('image/jpeg', 0.72)
      cache.set(number, url)
      if (cache.size > MAX_CACHE) cache.delete(cache.keys().next().value)
      previews.value = Object.fromEntries(cache)
    } catch (error) {
      if (token === generation) console.warn('Thumbnail render failed:', number, error)
    } finally {
      // PDF.js page objects may be shared with the main viewer; do not cleanup here.
    }
  })
}
function observePages() {
  observer?.disconnect()
  observer = new IntersectionObserver(entries => {
    for (const entry of entries) {
      if (entry.isIntersecting) requestThumbnail(Number(entry.target.dataset.page))
    }
  }, { root: list.value, rootMargin: '400px 0px' })
  list.value?.querySelectorAll('[data-page]').forEach(item => observer.observe(item))
}
function focusCurrent() {
  list.value?.querySelector('[data-page="' + props.pageNum + '"]')?.scrollIntoView({ block: 'nearest' })
}
watch(() => props.documentId, async () => {
  generation++
  queue = Promise.resolve()
  cache.clear()
  previews.value = {}
  await nextTick()
  observePages()
  focusCurrent()
})
watch(() => props.pageNum, async () => { await nextTick(); focusCurrent() })
watch(() => props.pageCount, async () => { await nextTick(); observePages() })
onBeforeUnmount(() => { generation++; observer?.disconnect() })
</script>

<template>
  <aside class="thumbnail-sidebar" aria-label="PDF 页面缩略图">
    <div class="thumbnail-heading"><strong>页面预览</strong><span>{{ pageCount }} 页</span></div>
    <div ref="list" class="thumbnail-scroll">
      <button v-for="number in pageCount" :key="number" class="thumbnail-item"
        :class="{ active: pageNum === number }" :data-page="number"
        :aria-label="'跳转第 ' + number + ' 页'" @click="emit('navigate', number)">
        <div class="thumbnail-sheet">
          <img v-if="previews[number]" :src="previews[number]" :alt="'第 ' + number + ' 页预览'" loading="lazy">
          <div v-else class="thumbnail-placeholder"></div>
        </div>
        <span>{{ number }}</span>
      </button>
    </div>
  </aside>
</template>
