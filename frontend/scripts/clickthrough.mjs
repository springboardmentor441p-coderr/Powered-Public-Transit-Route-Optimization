// Click-through check: for every screen, open Start, click "Closer look", then click the screen's tab (client-side
// navigation, never a direct load) and wait until the screen's real content is there. Fails on a page error, on
// a block still loading after the timeout, or on missing content. Needs the API and Vite running. Dev-only.
//
//   node scripts/clickthrough.mjs            (APP_URL defaults to http://localhost:5173)
import { chromium } from 'playwright'

const BASE = process.env.APP_URL ?? 'http://localhost:5173'
const TIMEOUT = 30_000
// tab to click -> texts that must all appear (each proves one block rendered from API data)
const SCREENS = [
  ['Start', ['The network over time', 'on an average weekday', 'Route summary']],
  ['Closer look', ['Ranked routes:', 'Not ranked:']],
  ['One route', ['Choose one of']],
  ['Alike', ['How far each group spreads', 'grouped routes sit inside', 'Caveats (4)']],
  ['Shared stops', ['route pairs share at least one stop', 'Show all']],
  ['Compare', ['Choose at least 2 routes', 'Or start from an example']],
  ['Data', ['of scheduled route-days have a ridership record', 'Import checks:', 'methods were tried', 'Data version, code and files']],
]

const browser = await chromium.launch()
let failed = 0
for (const [tab, texts] of SCREENS) {
  const page = await browser.newPage({ viewport: { width: 1366, height: 900 } })
  const errors = []
  page.on('pageerror', e => errors.push(String(e)))
  await page.goto(BASE + '/')
  await page.getByText('The network over time').waitFor({ timeout: TIMEOUT })
  await page.getByRole('link', { name: 'Closer look', exact: true }).first().click()
  await page.getByText('Ranked routes:').waitFor({ timeout: TIMEOUT })
  if (tab !== 'Closer look') await page.getByRole('link', { name: tab, exact: true }).first().click()
  const missing = []
  for (const t of texts) {
    await page.getByText(t).first().waitFor({ timeout: TIMEOUT }).catch(() => missing.push(t))
  }
  await page.waitForFunction(() => !document.querySelector('[aria-busy]'), null, { timeout: TIMEOUT }).catch(() => {})
  const busy = await page.locator('[aria-busy]').count()
  const problems = [...errors.map(e => `page error: ${e}`), ...missing.map(t => `missing: "${t}"`),
                    ...(busy ? [`${busy} block(s) still loading`] : [])]
  failed += problems.length ? 1 : 0
  console.log(`${problems.length ? 'FAIL' : 'ok  '} Start → Closer look → ${tab}`)
  for (const p of problems) console.log(`       ${p}`)
  await page.close()
}
await browser.close()
process.exit(failed ? 1 : 0)
