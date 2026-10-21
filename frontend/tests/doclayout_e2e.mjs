import assert from 'node:assert/strict'
import { existsSync } from 'node:fs'
import { chromium } from 'playwright-core'

const input = process.env.TEST_LAYOUT_PDF
if (!input || !existsSync(input)) throw new Error('Set TEST_LAYOUT_PDF to an existing multi-page table PDF')
const chrome = [
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
].find(existsSync)
const browser = await chromium.launch({ executablePath: chrome, headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, acceptDownloads: true })
const faults = []
page.on('pageerror', err => faults.push(err.message))
try {
  await page.goto(process.env.TEST_URL || 'http://127.0.0.1:8766')
  await page.locator('input[type=file]').setInputFiles(input)
  await page.waitForFunction(() => !document.querySelector('.loading') && document.querySelector('.paper canvas')?.width > 0, null, { timeout: 30000 })
  await page.getByRole('button', { name: 'PP-DocLayout-M' }).click()
  await page.waitForFunction(() => document.querySelector('.bbox.tables') || document.querySelector('[role=alert]'), null, { timeout: 60000 })
  assert.equal(await page.locator('.engine-note[role=alert]').count(), 0)
  assert((await page.locator('.bbox.tables').count()) > 0, 'Expected an ONNX table bbox')
  await page.locator('.element-item').first().click()
  assert.match(await page.locator('.detail-body').innerText(), /定位置信度/)
  await page.getByRole('button', { name: 'pdfplumber', exact: true }).click()
  await page.getByRole('button', { name: 'PP-DocLayout-M' }).click()
  assert((await page.locator('.bbox.tables').count()) > 0)
  assert.deepEqual(faults, [])
  console.log('PASS: ONNX table bbox + confidence + tab switching')
} finally { await browser.close() }
