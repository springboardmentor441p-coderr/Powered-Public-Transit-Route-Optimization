// Click-through check: for every screen, open Start, click "Closer look", then click the screen's tab (client-side
// navigation, never a direct load) and wait until the screen's real content is there. Fails on a page error, on
// a block still loading after the timeout, or on missing content. Needs the API and Vite running. Dev-only.
// A progress line is printed before each screen, and an error inside one screen is reported as that screen's FAIL,
// so a run never ends without saying how far it got (scripts/checklib.mjs).
//
//   node scripts/clickthrough.mjs            (APP_URL defaults to http://localhost:5173)
import { chromium } from 'playwright'
import { finish, tally } from './checklib.mjs'

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
  ['Scenarios', ['Choose a route or a route group to start.', 'Saved scenarios']],
  ['Data', ['of scheduled route-days have a ridership record', 'Import checks:', 'methods were tried', 'Data version, code and files']],
]

const t = tally()
let browser
try {
  const api = await fetch(`${BASE}/api/health/database`).then(r => r.ok, () => false)
  if (!api) throw new Error(`no API answers behind ${BASE} (is Vite running, and the API it forwards to?)`)
  browser = await chromium.launch()
  for (const [tab, texts] of SCREENS) {
    console.log(`..   Start → Closer look → ${tab}`)
    const page = await browser.newPage({ viewport: { width: 1366, height: 900 } })
    const errors = []
    page.on('pageerror', e => errors.push(String(e)))
    await t.step(`Start → Closer look → ${tab}`, async () => {
      await page.goto(BASE + '/')
      await page.getByText('The network over time').waitFor({ timeout: TIMEOUT })
      await page.getByRole('link', { name: 'Closer look', exact: true }).first().click()
      await page.getByText('Ranked routes:').waitFor({ timeout: TIMEOUT })
      if (tab !== 'Closer look') await page.getByRole('link', { name: tab, exact: true }).first().click()
      const missing = []
      for (const x of texts) await page.getByText(x).first().waitFor({ timeout: TIMEOUT }).catch(() => missing.push(x))
      await page.waitForFunction(() => !document.querySelector('[aria-busy]'), null, { timeout: TIMEOUT }).catch(() => {})
      const busy = await page.locator('[aria-busy]').count()
      const problems = [...errors.map(e => `page error: ${e}`), ...missing.map(x => `missing: "${x}"`),
                        ...(busy ? [`${busy} block(s) still loading`] : [])]
      if (problems.length) t.fail(`Start → Closer look → ${tab}\n       ${problems.join('\n       ')}`)
      else t.ok(`Start → Closer look → ${tab}`)
    })
    await page.close()
  }
} catch (e) {
  t.fail(`unexpected: ${String(e?.message ?? e).split('\n')[0]}`)
} finally {
  await finish(browser, t)
}
