import { ref, markRaw } from 'vue'
import * as pdfjs from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { uploadDocument, getPageLayout, deleteDocument } from '../api'

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl

export function usePdf(renderPage) {
  const docName = ref('')
  const documentId = ref('')
  const pageCount = ref(0)
  const pageNum = ref(0)
  const layout = ref(null)
  const busy = ref(false)
  const error = ref('')
  const status = ref('本地运行 · Windows CPU · 文件不会上传至互联网')
  let pdfDocument = null
  let requestId = 0

  async function loadPage(number, first = false) {
    if (!pdfDocument || !documentId.value || number < 1 || number > pageCount.value) return
    const current = ++requestId
    const currentDocument = pdfDocument
    pageNum.value = number
    busy.value = true
    error.value = ''
    try {
      const [page, result] = await Promise.all([
        currentDocument.getPage(number), getPageLayout(documentId.value, number),
      ])
      if (current !== requestId) return
      layout.value = result
      await renderPage(page, first, () => current !== requestId)
    } catch (err) {
      if (current === requestId && err?.name !== 'RenderingCancelledException')
        error.value = '第 ' + number + ' 页解析失败：' + (err?.message || String(err))
    } finally {
      if (current === requestId) busy.value = false
    }
  }

  async function openPdf(file) {
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.pdf')) { error.value = '请选择 PDF 文件'; return }
    busy.value = true
    error.value = ''
    status.value = '正在打开 ' + file.name
    let nextPdf = null
    let nextId = ''
    try {
      const bytes = await file.arrayBuffer()
      nextPdf = markRaw(await pdfjs.getDocument({ data: new Uint8Array(bytes) }).promise)
      const uploaded = await uploadDocument(file)
      nextId = uploaded.id
      const oldId = documentId.value
      const oldPdf = pdfDocument
      pdfDocument = nextPdf
      documentId.value = nextId
      docName.value = uploaded.filename
      pageCount.value = uploaded.pages
      pageNum.value = 0
      layout.value = null
      await loadPage(1, true)
      if (oldId) deleteDocument(oldId).catch(() => {})
      if (oldPdf) oldPdf.destroy().catch(() => {})
      status.value = '已打开 ' + uploaded.filename + ' · 共 ' + uploaded.pages + ' 页'
    } catch (err) {
      error.value = err?.message || String(err)
      status.value = '打开 PDF 失败'
      if (nextPdf && nextPdf !== pdfDocument) nextPdf.destroy().catch(() => {})
      if (nextId && nextId !== documentId.value) deleteDocument(nextId).catch(() => {})
    } finally { busy.value = false }
  }

  function closePdf() {
    requestId++
    const oldId = documentId.value
    const oldPdf = pdfDocument
    pdfDocument = null
    documentId.value = ''
    layout.value = null
    pageNum.value = 0
    pageCount.value = 0
    if (oldId) deleteDocument(oldId).catch(() => {})
    if (oldPdf) oldPdf.destroy().catch(() => {})
  }

  return { docName, documentId, pageCount, pageNum, layout, busy, error, status, openPdf, loadPage, closePdf }
}
