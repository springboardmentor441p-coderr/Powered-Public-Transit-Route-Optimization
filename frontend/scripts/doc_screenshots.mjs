// README screenshots: the main screens at 1600 × 1000 px (the browser window, not the full page). Dev-only.
//
// Read-only except for the replay: it starts ONE replay session (1 Jun 2026), reveals a week (8 Jun), jumps to the end,
// then presses Reset, which makes a second, clean session on 1 Jun and leaves it paused. Replay sessions are kept as
// audit evidence and never deleted, so these two stay in the database the API reads. Nothing is saved on Scenarios:
// the route 49 example is only opened from the saved list.
//
//   node scripts/doc_screenshots.mjs <raw png folder> [shot ...]    (APP_URL defaults to http://localhost:5180)
// Name shots (e.g. `scenarios data`) to retake only those; `replay` is the only shot that creates sessions.
// The PNGs are then reduced to 256 colours for the README (see docs/SETUP.md, "Screenshots").
import { mkdirSync } from 'node:fs'
import { join } from 'node:path'
import { chromium } from 'playwright'
import { TIMEOUT, enterReplay, finish, headline, replayControl, tally, waitIdle } from './checklib.mjs'

const [out, ...only] = process.argv.slice(2)
const want = name => only.length === 0 || only.includes(name)
if (!out) { console.error('usage: node scripts/doc_screenshots.mjs <raw png folder>'); process.exit(2) }
const BASE = process.env.APP_URL ?? 'http://localhost:5180'
const ROUTE49 = 'Route 49: 20 % more weekday trips, demand held fixed'
mkdirSync(out, { recursive: true })

const t = tally()
let browser
async function shot(page, name, { scrollTo, settle = 1200 } = {}) {
  await waitIdle(page, settle)                        // charts finish drawing, map tiles arrive
  if (scrollTo) {
    await scrollTo.evaluate(el => { el.scrollIntoView({ block: 'start' }); window.scrollBy(0, -64) })   // below the sticky top bar
    await page.waitForTimeout(400)
  }
  await page.screenshot({ path: join(out, `${name}.png`) })
  t.ok(`${name}.png`)
}
async function open(page, path, marker) {
  await page.goto(BASE + path)
  await page.getByText(marker).first().waitFor({ timeout: TIMEOUT })
}

try {
  const db = await fetch(`${BASE}/api/health/database`).then(r => r.json()).catch(() => null)
  if (!db?.database) throw new Error(`no API answers behind ${BASE}`)
  console.log(`..   the API behind ${BASE} reads ${db.database}`)
  browser = await chromium.launch()
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } })
  const errors = []
  page.on('pageerror', e => errors.push(String(e)))

  // ------------------------------------------------------------ historical analysis (the default mode)
  if (want('start')) await t.step('start', async () => { await open(page, '/', 'The network over time'); await shot(page, 'start') })
  if (want('closer_look')) await t.step('closer look', async () => { await open(page, '/closer-look', 'Ranked routes:'); await shot(page, 'closer_look') })
  if (want('one_route')) await t.step('one route', async () => { await open(page, '/route/22', 'Recorded rides per day'); await shot(page, 'one_route_22', { settle: 2500 }) })
  if (want('alike')) await t.step('alike', async () => { await open(page, '/alike', 'How far each group spreads'); await shot(page, 'alike', { settle: 2500 }) })
  if (want('shared_stops')) await t.step('shared stops', async () => {
    await open(page, '/shared-stops', 'route pairs share at least one stop'); await shot(page, 'shared_stops', { settle: 2500 })
  })
  if (want('compare')) await t.step('compare', async () => { await open(page, '/compare?routes=49,X49', 'Scheduled trips per day'); await shot(page, 'compare', { settle: 2500 }) })
  if (want('scenarios')) await t.step('scenarios', async () => {
    await open(page, '/scenarios', 'Saved scenarios')
    const title = page.getByRole('button', { name: ROUTE49, exact: true })
    await title.waitFor({ timeout: TIMEOUT })
    if ((await title.getAttribute('aria-expanded')) !== 'true') await title.click()   // open, never Save
    await page.getByText('Stored result').first().waitFor({ timeout: TIMEOUT })
    await shot(page, 'scenarios_route49', { scrollTo: title })
  })
  if (want('data')) await t.step('data', async () => {
    await open(page, '/data', 'methods were tried')
    await shot(page, 'data_model_card', { scrollTo: page.getByRole('heading', { name: 'Forecast model card' }) })
  })

  // ------------------------------------------------------------ historical replay
  if (want('replay')) await t.step('replay', async () => {
    await open(page, '/', 'The network over time')
    await enterReplay(page, 'Replay day: 1 Jun 2026 · data revealed to 31 May 2026')
    await replayControl(page, 'Next week', 'Replay day: 8 Jun 2026 · data revealed to 7 Jun 2026')
    await page.getByRole('link', { name: 'Replay', exact: true }).first().click()
    await page.getByText('Running error').first().waitFor({ timeout: TIMEOUT })
    await shot(page, 'replay_8_jun', { settle: 2000 })
    await replayControl(page, 'Jump to end', 'Replay complete · data revealed to 31 Jul 2026')
    await shot(page, 'replay_end', { settle: 2000 })
    // leave it clean: Reset makes a new session on the same start day, paused
    await replayControl(page, 'Reset', 'Replay day: 1 Jun 2026 · data revealed to 31 May 2026')
    const play = page.locator('[aria-label="Replay controls"]').getByRole('button', { name: 'Play', exact: true })
    if (await play.count()) t.ok(`after Reset: "${await headline(page).textContent()}", paused (Play is offered)`)
    else t.fail('after Reset: the replay is not paused')
  })
  for (const e of errors) t.fail(`page error: ${e}`)
} catch (e) {
  t.fail(`unexpected: ${String(e?.message ?? e).split('\n')[0]}`)
} finally {
  await finish(browser, t)
}
