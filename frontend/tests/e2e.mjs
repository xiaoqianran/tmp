import assert from 'node:assert/strict'
import { fileURLToPath } from 'node:url'
import { resolve, dirname } from 'node:path'
import { existsSync, readFileSync } from 'node:fs'
import { chromium } from 'playwright-core'

const root = dirname(fileURLToPath(import.meta.url))
const pdf = resolve(process.argv[2] || resolve(root, 'fixture.pdf'))
const url = process.env.TEST_URL || 'http://127.0.0.1:8767'
const chrome = process.env.CHROME_PATH || [
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
].find(existsSync)
if (!chrome) throw new Error('找不到 Chrome/Edge，请设置 CHROME_PATH')
const browser = await chromium.launch({
  headless: true,
  executablePath: chrome,
  args: ['--no-first-run'],
})
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, acceptDownloads: true })
const faults = []
page.on('pageerror', error => faults.push(error.message))
page.on('console', message => { if (message.type() === 'error') faults.push(message.text()) })

try {
  await page.goto(url, { waitUntil: 'networkidle' })
  await page.locator('input[type=file]').setInputFiles(pdf)
  await page.locator('.paper canvas').waitFor({ state: 'visible', timeout: 30000 })
  await page.waitForFunction(() => {
    const c = document.querySelector('.paper canvas')
    return c && c.width > 0 && !document.querySelector('.loading')
  }, null, { timeout: 30000 })
  assert.match(await page.locator('.inspector').innerText(), /Analyte/)
  assert.equal((await page.locator('.page-indicator strong').innerText()).trim(), '1')
  console.log('PASS: upload + PDF.js render + pdfplumber fields')
  await page.screenshot({ path: resolve(root, 'screenshot-test.png') })

  await page.locator('.viewer').hover()
  await page.keyboard.down('Control')
  await page.mouse.wheel(0, -190)
  await page.keyboard.up('Control')
  await page.waitForTimeout(300)
  const percent = Number((await page.locator('.zoom-number').innerText()).replace('%',''))
  assert(percent > 25, 'Ctrl+wheel should change zoom')
  console.log('PASS: Ctrl+wheel zoom', percent)

  await page.locator('.button.subtle').last().click()
  await page.locator('.zoom-btn').last().click({ clickCount: 4 })
  await page.waitForTimeout(150)
  await page.locator('.viewer').evaluate(node => { node.scrollLeft = 120; node.scrollTop = 120 })
  await page.keyboard.press('d')
  const h = await page.locator('.viewer').evaluate(node => node.scrollLeft)
  assert(h > 120, 'D should scroll right')
  await page.keyboard.press('s')
  const v = await page.locator('.viewer').evaluate(node => node.scrollTop)
  assert(v > 120, 'S should scroll down')
  console.log('PASS: WASD navigation', h, v)

  await page.keyboard.press('Alt+ArrowRight')
  await page.locator('.page-indicator strong').getByText('2').waitFor()
  console.log('PASS: Alt+Right page navigation')

  await page.locator('.search-wrap input').fill('Analyte')
  assert((await page.locator('.element-item').count()) > 0)
  await page.locator('.element-item').first().click()
  assert.match(await page.locator('.detail-content').innerText(), /Analyte/)
  console.log('PASS: text filter + selecting overlays')

  const pending = page.waitForEvent('download')
  await page.getByText('导出 JSON').click()
  const download = await pending
  assert(download.suggestedFilename().endsWith('.json'))
  console.log('PASS: export JSON')

  await page.locator('.search-wrap input').fill('')
  const payload = readFileSync(pdf).toString('base64')
  await page.evaluate(({ payload }) => {
    const binary = atob(payload)
    const bytes = Uint8Array.from(binary, c => c.charCodeAt(0))
    const file = new File([bytes], 'drag-test.pdf', { type: 'application/pdf' })
    const transfer = new DataTransfer()
    transfer.items.add(file)
    const destination = document.querySelector('.viewer')
    destination.dispatchEvent(new DragEvent('dragenter', { dataTransfer: transfer, bubbles: true, cancelable: true }))
    destination.dispatchEvent(new DragEvent('dragover', { dataTransfer: transfer, bubbles: true, cancelable: true }))
    destination.dispatchEvent(new DragEvent('drop', { dataTransfer: transfer, bubbles: true, cancelable: true }))
  }, { payload })
  await page.getByText('drag-test.pdf', { exact: false }).first().waitFor({ timeout: 30000 })
  await page.locator('.paper canvas').waitFor({ state: 'visible' })
  console.log('PASS: HTML5 drag-and-drop PDF')

  assert.equal(faults.length, 0, faults.join('\n'))
  console.log('ALL BROWSER TESTS PASSED')
} finally {
  await browser.close()
}
