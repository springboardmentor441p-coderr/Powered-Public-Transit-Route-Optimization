// Layout check: full-page screenshots of app pages at 1366 and 1920 px, plus three automatic checks per page:
// console errors, horizontal page overflow, and form fields whose text is clipped (e.g. "20" shown as "2").
// Needs the API (127.0.0.1:8000) and Vite (localhost:5173) running. Dev-only; nothing here ships.
//
//   node scripts/screens.mjs <out-dir> /route/22 /alike ...
import { mkdirSync } from 'node:fs'
import { join } from 'node:path'
import { chromium } from 'playwright'

const [outDir, ...paths] = process.argv.slice(2)
if (!outDir || paths.length === 0) {
  console.error('usage: node scripts/screens.mjs <out-dir> <path> [<path> ...]')
  process.exit(2)
}
mkdirSync(outDir, { recursive: true })
const BASE = process.env.APP_URL ?? 'http://localhost:5173'
const WIDTHS = [1366, 1920]

const browser = await chromium.launch()
let problems = 0
for (const width of WIDTHS) {
  const page = await browser.newPage({ viewport: { width, height: 900 } })
  for (const path of paths) {
    const errors = []
    page.removeAllListeners('console')
    page.on('console', m => { if (m.type() === 'error') errors.push(m.text()) })
    page.on('pageerror', e => errors.push(String(e)))
    await page.goto(BASE + path, { waitUntil: 'networkidle' })
    await page.waitForFunction(() => !document.querySelector('[aria-busy="true"], [aria-busy=""]'), null, { timeout: 60_000 })
      .catch(() => errors.push('still loading after 60 s'))
    await page.waitForTimeout(600)                       // map tiles / chart animation settle
    const report = await page.evaluate(() => {
      const doc = document.documentElement
      const clipped = [...document.querySelectorAll('input, select')]
        .filter(el => el.scrollWidth > el.clientWidth + 1)
        .map(el => `${el.tagName.toLowerCase()}[name=${el.getAttribute('name')}] value="${el.value}"`)
      return { overflowX: doc.scrollWidth > doc.clientWidth + 1 ? doc.scrollWidth - doc.clientWidth : 0, clipped }
    })
    const file = join(outDir, `${path.replace(/[^a-z0-9]+/gi, '_').replace(/^_|_$/g, '') || 'start'}_${width}.png`)
    await page.screenshot({ path: file, fullPage: true })
    const issues = [...errors.map(e => `console: ${e}`),
                    ...(report.overflowX ? [`page scrolls sideways by ${report.overflowX}px`] : []),
                    ...report.clipped.map(c => `clipped field: ${c}`)]
    problems += issues.length
    console.log(`${issues.length ? 'CHECK' : 'ok   '} ${width}px ${path} -> ${file}`)
    for (const i of issues) console.log(`        ${i}`)
  }
  await page.close()
}
await browser.close()
process.exit(problems ? 1 : 0)
