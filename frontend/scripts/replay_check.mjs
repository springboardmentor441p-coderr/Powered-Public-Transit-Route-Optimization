// Replay click-through: switch to Historical replay (default start 1 Jun 2026), reveal a day, reveal a week, then visit
// every screen by clicking and check that no screen shows a date after the revealed day. Screenshots at 1366 and
// 1920 px; finally jump to the end and check the completion message. Needs an API and Vite running. Dev-only.
// The replay bar's own text (the supported range, e.g. "1 Jun 2026 – 31 Jul 2026") is not scanned: it is the
// session's configuration, not data.
//
//   node scripts/replay_check.mjs <screenshot folder>        (APP_URL defaults to http://localhost:5173)
import { mkdirSync } from 'node:fs'
import { join } from 'node:path'
import { chromium } from 'playwright'

const out = process.argv[2]
if (!out) { console.error('usage: node scripts/replay_check.mjs <screenshot folder>'); process.exit(2) }
const BASE = process.env.APP_URL ?? 'http://localhost:5173'
// Replay sessions are never deleted, so this check only runs against an API on the test database.
const db = await fetch(`${BASE}/api/health/database`).then(r => r.json()).catch(() => null)
if (db?.database !== 'routeranker_test') {
  console.error(`REFUSED: the API behind ${BASE} reads ${db?.database ?? 'an unknown database'}, not routeranker_test.`)
  process.exit(2)
}
mkdirSync(out, { recursive: true })
const TIMEOUT = 60_000
const MONTHS = { Jan: 0, Feb: 1, Mar: 2, Apr: 3, May: 4, Jun: 5, Jul: 6, Aug: 7, Sep: 8, Oct: 9, Nov: 10, Dec: 11 }
const SCREENS = [
  ['Start', 'The network over time'], ['Closer look', 'Ranked routes:'], ['One route', 'Choose one of'],
  ['Alike', 'How far each group spreads'], ['Shared stops', 'route pairs share at least one stop'],
  ['Compare', 'Choose at least 2 routes'], ['Scenarios', 'Saved scenarios'], ['Replay', 'Running error'], ['Data', 'Import checks:'],
]

/** Every date on the page outside the replay bar, as UTC ms. "D Mon YYYY", ISO dates, and year-less June/July ticks. */
async function pageDates(page) {
  const text = await page.evaluate(() => {
    const clone = document.body.cloneNode(true)
    clone.querySelectorAll('[aria-label="Replay controls"]').forEach(n => n.remove())
    return clone.innerText + ' ' + [...clone.querySelectorAll('svg text')].map(t => t.textContent).join(' ')
  })
  const found = []
  for (const m of text.matchAll(/\b(\d{1,2}) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (\d{4})\b/g))
    found.push([m[0], Date.UTC(+m[3], MONTHS[m[2]], +m[1])])
  for (const m of text.matchAll(/\b(\d{4})-(\d{2})-(\d{2})\b/g)) found.push([m[0], Date.UTC(+m[1], +m[2] - 1, +m[3])])
  for (const m of text.matchAll(/\b(\d{1,2}) (Jun|Jul)\b(?! \d{4})/g)) found.push([m[0] + ' (2026 assumed)', Date.UTC(2026, MONTHS[m[2]], +m[1])])
  return found
}

async function waitIdle(page) {
  await page.waitForFunction(() => !document.querySelector('[aria-busy]'), null, { timeout: TIMEOUT }).catch(() => {})
  await page.waitForTimeout(500)
}

const browser = await chromium.launch()
let failed = 0
const fail = msg => { failed++; console.log('FAIL', msg) }
for (const width of [1366, 1920]) {
  const page = await browser.newPage({ viewport: { width, height: 900 } })
  const errors = []
  page.on('pageerror', e => errors.push(String(e)))
  await page.goto(BASE + '/')
  await page.getByText('The network over time').waitFor({ timeout: TIMEOUT })
  await page.getByRole('button', { name: 'Historical replay' }).click()
  const head = page.locator('[aria-label="Replay controls"] [aria-live]')
  await head.waitFor({ timeout: TIMEOUT })
  const h0 = await head.textContent()
  if (h0 !== 'Replay day: 1 Jun 2026 · data revealed to 31 May 2026') fail(`${width}: start headline "${h0}"`)
  await page.getByRole('button', { name: 'Next day' }).click()
  await page.getByText('Replay day: 2 Jun 2026').waitFor({ timeout: TIMEOUT })
  await page.getByRole('button', { name: 'Next week' }).click()
  await page.getByText('Replay day: 9 Jun 2026 · data revealed to 8 Jun 2026').waitFor({ timeout: TIMEOUT })
  const limit = Date.UTC(2026, 5, 9)        // the replay day itself may appear (today's forecasts); nothing later
  for (const [tab, marker] of SCREENS) {
    await page.getByRole('link', { name: tab, exact: true }).first().click()
    const ok = await page.getByText(marker).first().waitFor({ timeout: TIMEOUT }).then(() => true, () => false)
    if (!ok) { fail(`${width} ${tab}: "${marker}" did not appear`); continue }
    await waitIdle(page)
    const later = (await pageDates(page)).filter(([, t]) => t > limit).map(([s]) => s)
    if (later.length) fail(`${width} ${tab}: dates after the revealed day: ${[...new Set(later)].slice(0, 6).join(', ')}`)
    else console.log(`ok   ${width} ${tab}: no date after 9 Jun 2026`)
    await page.screenshot({ path: join(out, `replay_${tab.replace(/\s+/g, '_').toLowerCase()}_${width}.png`), fullPage: true })
  }
  // One route with its forecast panel (route 22), reached by clicking a sign on the route picker
  await page.getByRole('link', { name: 'One route', exact: true }).first().click()
  await page.getByRole('link', { name: 'Open route 22' }).first().click()
  const panel = await page.getByText('Forecast, route 22').first().waitFor({ timeout: TIMEOUT }).then(() => true, () => false)
  if (!panel) fail(`${width} One route 22: forecast panel did not appear`)
  else {
    await waitIdle(page)
    const later = (await pageDates(page)).filter(([, t]) => t > limit).map(([s]) => s)
    if (later.length) fail(`${width} route 22: dates after the revealed day: ${[...new Set(later)].slice(0, 6).join(', ')}`)
    else console.log(`ok   ${width} route 22 with forecast panel: no date after 9 Jun 2026`)
    await page.screenshot({ path: join(out, `replay_route_22_${width}.png`), fullPage: true })
  }
  await page.getByRole('button', { name: 'Jump to end' }).click()
  const done = await page.getByText('Replay complete · data revealed to 31 Jul 2026').waitFor({ timeout: TIMEOUT }).then(() => true, () => false)
  if (!done) fail(`${width}: completion message did not appear`)
  else console.log(`ok   ${width} jump to end: "Replay complete · data revealed to 31 Jul 2026"`)
  for (const e of errors) fail(`${width} page error: ${e}`)
  await page.close()
}
await browser.close()
process.exit(failed ? 1 : 0)
