import assert from 'node:assert/strict'
import { chromium } from 'playwright-core'
import { resolve } from 'node:path'
const browser=await chromium.launch({headless:true,executablePath:'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'})
const page=await browser.newPage({viewport:{width:1500,height:950}})
const failures=[]
page.on('pageerror',err=>failures.push(err.message))
page.on('console',msg=>{if(msg.type()==='error')failures.push(msg.text())})
try {
 await page.goto('http://127.0.0.1:8779',{waitUntil:'networkidle'})
 await page.locator('input[type=file]').setInputFiles(resolve('tests/fixture.pdf'))
 await page.locator('.paper').waitFor()
 await page.getByText('整页解析完成').waitFor({timeout:20000})
 const full=await page.locator('.layer-options label').filter({hasText:'Chars'}).innerText()
 console.log('before',full)
 await page.getByRole('button',{name:'框选解析'}).click()
 const picker=page.locator('.crop-picker')
 await picker.waitFor()
 const r=await picker.boundingBox()
 await page.mouse.move(r.x+r.width*.1,r.y+r.height*.1)
 await page.mouse.down()
 await page.mouse.move(r.x+r.width*.47,r.y+r.height*.47,{steps:12})
 await page.mouse.up()
 await page.getByText('局部解析完成').waitFor({timeout:20000})
 const local=await page.locator('.layer-options label').filter({hasText:'Chars'}).innerText()
 console.log('after',local,'cropbox',await page.locator('.crop-highlight').count())
 assert.notEqual(full,local)
 await page.getByRole('button',{name:'整页',exact:true}).click()
 await page.getByText('整页解析完成').waitFor({timeout:20000})
 console.log('restored',await page.locator('.layer-options label').filter({hasText:'Chars'}).innerText())
 assert.equal(failures.length,0,failures.join('\n'))
 console.log('BROWSER CROP PASS')
} finally {await browser.close()}
