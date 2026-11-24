// Scenarios click-through, in both modes, at 1366 and 1920 px. Needs an API and Vite running. Dev-only.
//
// Saved scenarios and replay sessions can never be deleted, so this check REFUSES to run unless the API it talks to
// reads the test database (routeranker_test): start a temporary API with ROUTERANKER_URL_VAR=TEST_DATABASE_URL.
//
//   historical: build "+20 % trips on route 49, weekdays, full window", save, open it from the saved list,
//               recalculate (identical), open the route by clicking it; a group under a -15 % demand assumption.
//   replay:     start a replay, advance a week, build and save a group demand assumption and a +20 % trip change on
//               the replay day's forecast, check no visible date is after the replay day, advance a day, and check
//               the saved scenario is still there and recalculates identically.
//
//   node scripts/scenario_check.mjs <screenshot folder>        (APP_URL, e.g. http://localhost:5180)
import { mkdirSync } from 'node:fs'
import { join } from 'node:path'
import { chromium } from 'playwright'

const out = process.argv[2]
if (!out) { console.error('usage: node scripts/scenario_check.mjs <screenshot folder>'); process.exit(2) }
const BASE = process.env.APP_URL ?? 'http://localhost:5173'
const TIMEOUT = 60_000
const MONTHS = { Jan: 0, Feb: 1, Mar: 2, Apr: 3, May: 4, Jun: 5, Jul: 6, Aug: 7, Sep: 8, Oct: 9, Nov: 10, Dec: 11 }

const db = await fetch(`${BASE}/api/health/database`).then(r => r.json()).catch(() => null)
if (db?.database !== 'routeranker_test') {
  console.error(`REFUSED: the API behind ${BASE} reads ${db?.database ?? 'an unknown database'}, not routeranker_test.`)
  process.exit(2)
}
mkdirSync(out, { recursive: true })

let failed = 0
const fail = msg => { failed++; console.log('FAIL', msg) }
const ok = msg => console.log('ok  ', msg)
const seen = (page, text) => page.getByText(text).first().waitFor({ timeout: TIMEOUT }).then(() => true, () => false)
async function waitIdle(page) {
  await page.waitForFunction(() => !document.querySelector('[aria-busy]'), null, { timeout: TIMEOUT }).catch(() => {})
  await page.waitForTimeout(400)
}
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
  return found
}
async function expect(page, text, label) {
  if (await seen(page, text)) ok(label)
  else fail(`${label}: "${text}" did not appear`)
}
async function save(page, label) {
  await page.getByRole('button', { name: /^Save (scenario|as a new version)$/ }).click()
  const status = page.getByRole('status').filter({ hasText: /Saved:|Already saved:/ })
  const done = await status.first().waitFor({ timeout: TIMEOUT }).then(() => true, () => false)
  if (!done) { fail(`${label}: no "Saved" status`); return null }
  const text = await status.first().textContent()
  ok(`${label}: ${text}`)
  return text
}
async function openSavedAndRecheck(page, name, label) {
  const listed = await page.getByRole('button', { name, exact: true }).first().waitFor({ timeout: TIMEOUT }).then(() => true, () => false)
  if (!listed) { fail(`${label}: "${name}" is not in the saved list`); return }
  const item = page.locator('li', { has: page.getByRole('button', { name, exact: true }) }).first()
  const title = item.getByRole('button', { name, exact: true })
  if ((await title.getAttribute('aria-expanded')) !== 'true') await title.click()
  await expect(page, 'Stored result', `${label}: saved scenario opens with its stored result`)
  await item.getByRole('button', { name: 'Recalculate and compare' }).click()
  await expect(page, 'identical result', `${label}: recalculated from the stored inputs, identical`)
}

/** No comparison table on the page may scroll sideways. */
async function tablesFit(page, label) {
  const wide = await page.evaluate(() => [...document.querySelectorAll('.overflow-x-auto')]
    .filter(d => d.querySelector('table') && d.scrollWidth > d.clientWidth + 1).map(d => `${d.scrollWidth} > ${d.clientWidth}`))
  if (wide.length) fail(`${label}: a table scrolls sideways (${wide.join(', ')})`)
  else ok(`${label}: tables fit without sideways scrolling`)
  // every reason number shown in the table is explained once under it
  const { shown, listed } = await page.evaluate(() => ({
    shown: Math.max(0, ...[...document.querySelectorAll('table sup')].flatMap(x => x.textContent.split(',').map(Number))),
    listed: document.querySelectorAll('ol[aria-label="Why values are unavailable"] li').length,
  }))
  if (shown > listed) fail(`${label}: the table shows reason ${shown} but only ${listed} are listed`)
  else ok(`${label}: all ${listed} reason(s) listed once under the table`)
}

/** The saved examples (if the database holds them): each opens, its table fits, the chart tooltip shows both values. */
async function examples(page, width) {
  const list = await fetch(`${BASE}/api/scenarios`).then(r => r.json())
  const ex = list.scenarios.filter(s => s.origin === 'example')
  if (!ex.length) { console.log(`skip ${width}: no saved examples in this database`); return }
  for (const [i, s] of ex.entries()) {
    await page.goto(BASE + '/scenarios')
    const title = page.getByRole('button', { name: s.name, exact: true })
    await title.waitFor({ timeout: TIMEOUT })
    await title.click()
    await expect(page, 'Stored result', `${width} example "${s.name}" opens`)
    await waitIdle(page)
    await tablesFit(page, `${width} example ${i + 1}`)
    const bar = page.locator('.recharts-bar-rectangle').first()
    if (await bar.count()) {
      await bar.hover()
      const tip = page.locator('.recharts-tooltip-wrapper')
      const text = (await tip.textContent().catch(() => '')) ?? ''
      if (/Baseline: [\d,.]+/.test(text) && /Scenario: [\d,.]+/.test(text)) ok(`${width} example ${i + 1}: tooltip shows both values`)
      else fail(`${width} example ${i + 1}: tooltip shows "${text}"`)
    }
    await page.screenshot({ path: join(out, `example_${i + 1}_${width}.png`), fullPage: true })
  }
}

const browser = await chromium.launch()
for (const width of [1366, 1920]) {
  const page = await browser.newPage({ viewport: { width, height: 900 } })
  const errors = []
  page.on('pageerror', e => errors.push(String(e)))
  await examples(page, width)
  await page.goto(BASE + '/scenarios?routes=1&daytype=U&verb=set&amount=40')
  await expect(page, 'Route 1 gets 40.0 scheduled trips per day on Sundays and holidays', `${width} route 1 Sunday builder`)
  await waitIdle(page)
  await tablesFit(page, `${width} route 1 Sunday builder`)
  const said = (await page.locator('[data-insight]').first().textContent()) ?? ''
  if ((said.match(/no recorded rides on days without service/g) ?? []).length === 1) ok(`${width} route 1: the reason is said once above the table`)
  else fail(`${width} route 1: the reason appears ${(said.match(/no recorded rides on days without service/g) ?? []).length} times in the insight`)

  // ---------------------------------------------------------------- historical analysis
  await page.goto(BASE + '/')
  await page.getByText('The network over time').waitFor({ timeout: TIMEOUT })
  if (await page.getByRole('button', { name: 'Historical analysis' }).getAttribute('aria-pressed') === 'false')
    await page.getByRole('button', { name: 'Historical analysis' }).click()
  await page.getByRole('link', { name: 'Scenarios', exact: true }).first().click()
  await expect(page, 'Choose a route or a route group to start.', `${width} historical: empty builder`)
  await page.getByLabel('Add a route or a group').selectOption('49')
  await expect(page, 'On route 49, rides per scheduled hour falls from', `${width} historical: route 49 +20 % insight`)
  await expect(page, 'because demand is held fixed', `${width} historical: demand held fixed is said`)
  await waitIdle(page)
  await page.screenshot({ path: join(out, `scenarios_route49_${width}.png`), fullPage: true })
  const name = `Route 49 check ${width}`
  await page.getByLabel('Name').fill(name)
  await save(page, `${width} historical save`)
  await openSavedAndRecheck(page, name, `${width} historical`)
  // clicking a route opens it
  await page.getByRole('link', { name: 'Open route 49' }).first().click()
  if (await page.waitForURL(/\/route\/49$/, { timeout: TIMEOUT }).then(() => true, () => false)) ok(`${width} clicking route 49 opens it`)
  else fail(`${width} clicking route 49 did not open it`)
  await page.getByRole('link', { name: 'Create a scenario for route 49' }).click()
  await expect(page, 'On route 49, rides per scheduled hour', `${width} One route → Create scenario`)

  await page.goto(BASE + '/scenarios?group=1&daytype=U&verb=keep&stress=-15')
  await expect(page, 'Across the group', `${width} historical: group −15 % demand assumption insight`)
  await expect(page, 'because rides are assumed to fall by 15.0 %', `${width} historical: the stress is named as an assumption`)
  await expect(page, 'shown as unavailable rather than 0', `${width} historical: structural zeros shown as unavailable`)
  await waitIdle(page)
  await page.screenshot({ path: join(out, `scenarios_group_stress_${width}.png`), fullPage: true })

  // ---------------------------------------------------------------- historical replay
  await page.goto(BASE + '/')
  await page.getByText('The network over time').waitFor({ timeout: TIMEOUT })
  await page.getByRole('button', { name: 'Historical replay' }).click()
  await page.getByText('Replay day: 1 Jun 2026').waitFor({ timeout: TIMEOUT })
  await page.getByRole('button', { name: 'Next week' }).click()
  await page.getByText('Replay day: 8 Jun 2026 · data revealed to 7 Jun 2026').waitFor({ timeout: TIMEOUT })
  const limit = Date.UTC(2026, 5, 8)
  await page.goto(BASE + '/scenarios?group=1&verb=keep&stress=-15')
  await expect(page, 'Across the group', `${width} replay: group demand assumption`)
  await waitIdle(page)
  const rName = `Replay group check ${width}`
  await page.getByLabel('Name').fill(rName)
  await save(page, `${width} replay save`)
  await expect(page, 'saved on replay day 8 Jun 2026', `${width} replay: saved on the replay day`)
  await waitIdle(page)
  let later = (await pageDates(page)).filter(([, t]) => t > limit).map(([s]) => s)
  if (later.length) fail(`${width} replay: dates after the replay day: ${[...new Set(later)].slice(0, 6).join(', ')}`)
  else ok(`${width} replay: no visible date after 8 Jun 2026`)
  if (await page.getByText(`Route 49 check ${width}`).count()) fail(`${width} replay: a historical scenario is listed in replay`)
  else ok(`${width} replay: historical scenarios are not listed`)
  await page.screenshot({ path: join(out, `scenarios_replay_group_${width}.png`), fullPage: true })

  await page.goto(BASE + '/scenarios?routes=22&demand=predicted')
  await expect(page, 'On route 22, rides per scheduled hour', `${width} replay: +20 % trips on the replay day's forecast`)
  await waitIdle(page)
  later = (await pageDates(page)).filter(([, t]) => t > limit).map(([s]) => s)
  if (later.length) fail(`${width} replay predicted: dates after the replay day: ${[...new Set(later)].slice(0, 6).join(', ')}`)
  else ok(`${width} replay predicted: no visible date after 8 Jun 2026`)
  await page.screenshot({ path: join(out, `scenarios_replay_predicted_${width}.png`), fullPage: true })

  await page.getByRole('button', { name: 'Next day' }).click()
  await page.getByText('Replay day: 9 Jun 2026').waitFor({ timeout: TIMEOUT })
  await waitIdle(page)
  await openSavedAndRecheck(page, rName, `${width} replay after Next day`)
  await page.getByRole('button', { name: 'Historical analysis' }).click()
  await page.getByText('The network over time').first().waitFor({ timeout: 5_000 }).catch(() => {})

  for (const e of errors) fail(`${width} page error: ${e}`)
  await page.close()
}
await browser.close()
process.exit(failed ? 1 : 0)
