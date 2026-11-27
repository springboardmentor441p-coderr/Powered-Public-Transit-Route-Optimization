// Replay click-through: switch to Historical replay (default start 1 Jun 2026), reveal a day, reveal a week, then visit
// every screen by clicking and check that no screen shows a date after the revealed day. Screenshots at 1366 and
// 1920 px; finally jump to the end and check the completion message. Needs an API and Vite running. Dev-only.
// The replay bar's own text (the supported range, e.g. "1 Jun 2026 – 31 Jul 2026") is not scanned: it is the
// session's configuration, not data.
//
// Each replay control waits for the server's answer and then for the exact new headline (scripts/checklib.mjs), so a
// slow answer is waited for and a wrong day is reported, instead of a timeout ending the run.
//
//   node scripts/replay_check.mjs <screenshot folder>        (APP_URL defaults to http://localhost:5173)
import { mkdirSync } from 'node:fs'
import { join } from 'node:path'
import { chromium } from 'playwright'
import { TIMEOUT, enterReplay, finish, replayControl, tally, waitIdle } from './checklib.mjs'

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

const t = tally()
let browser
try {
  browser = await chromium.launch()
  for (const width of [1366, 1920]) {
    const page = await browser.newPage({ viewport: { width, height: 900 } })
    const errors = []
    page.on('pageerror', e => errors.push(String(e)))
    console.log(`..   ${width}: opening Start and switching to Historical replay`)
    const ready = await t.step(`${width} start`, async () => {
      await page.goto(BASE + '/')
      await page.getByText('The network over time').waitFor({ timeout: TIMEOUT })
      await enterReplay(page, 'Replay day: 1 Jun 2026 · data revealed to 31 May 2026')
      t.ok(`${width} start headline: "Replay day: 1 Jun 2026 · data revealed to 31 May 2026"`)
      await replayControl(page, 'Next day', 'Replay day: 2 Jun 2026 · data revealed to 1 Jun 2026')
      t.ok(`${width} Next day → 2 Jun 2026`)
      await replayControl(page, 'Next week', 'Replay day: 9 Jun 2026 · data revealed to 8 Jun 2026')
      t.ok(`${width} Next week → 9 Jun 2026`)
      return true
    })
    if (!ready) { await page.close(); continue }          // later steps depend on the replay being on 9 Jun
    const limit = Date.UTC(2026, 5, 9)        // the replay day itself may appear (today's forecasts); nothing later
    for (const [tab, marker] of SCREENS) {
      await t.step(`${width} ${tab}`, async () => {
        await page.getByRole('link', { name: tab, exact: true }).first().click()
        await page.getByText(marker).first().waitFor({ timeout: TIMEOUT })
        await waitIdle(page)
        const later = (await pageDates(page)).filter(([, d]) => d > limit).map(([s]) => s)
        if (later.length) t.fail(`${width} ${tab}: dates after the revealed day: ${[...new Set(later)].slice(0, 6).join(', ')}`)
        else t.ok(`${width} ${tab}: no date after 9 Jun 2026`)
        await page.screenshot({ path: join(out, `replay_${tab.replace(/\s+/g, '_').toLowerCase()}_${width}.png`), fullPage: true })
      })
    }
    // One route with its forecast panel (route 22), reached by clicking a sign on the route picker
    await t.step(`${width} One route 22`, async () => {
      await page.getByRole('link', { name: 'One route', exact: true }).first().click()
      await page.getByRole('link', { name: 'Open route 22' }).first().click()
      await page.getByText('Forecast, route 22').first().waitFor({ timeout: TIMEOUT })
      await waitIdle(page)
      const later = (await pageDates(page)).filter(([, d]) => d > limit).map(([s]) => s)
      if (later.length) t.fail(`${width} route 22: dates after the revealed day: ${[...new Set(later)].slice(0, 6).join(', ')}`)
      else t.ok(`${width} route 22 with forecast panel: no date after 9 Jun 2026`)
      await page.screenshot({ path: join(out, `replay_route_22_${width}.png`), fullPage: true })
    })
    await t.step(`${width} jump to end`, async () => {
      await replayControl(page, 'Jump to end', 'Replay complete · data revealed to 31 Jul 2026')
      t.ok(`${width} jump to end: "Replay complete · data revealed to 31 Jul 2026"`)
    })
    for (const e of errors) t.fail(`${width} page error: ${e}`)
    await page.close()
  }
} catch (e) {
  t.fail(`unexpected: ${String(e?.message ?? e).split('\n')[0]}`)
} finally {
  await finish(browser, t)
}
