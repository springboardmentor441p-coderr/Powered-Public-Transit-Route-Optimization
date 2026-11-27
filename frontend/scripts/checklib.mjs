// Shared helpers for the browser checks (dev-only). They make the checks wait for the right thing:
//   - a replay control is "done" when its request has answered AND the headline shows the expected day,
//     not when some matching text happens to appear somewhere on the page;
//   - a timeout inside one step is reported as a FAIL line for that step, never a silent crash;
//   - the exit code is set with process.exitCode, so every line already printed reaches the terminal.

export const TIMEOUT = 60_000

/** The replay headline, e.g. "Replay day: 8 Jun 2026 · data revealed to 7 Jun 2026". */
export const headline = page => page.locator('[aria-label="Replay controls"] [aria-live]')

/** Wait until the headline starts with `expected`. On a timeout, the error names what the headline said instead. */
export async function waitHeadline(page, expected, timeout = TIMEOUT) {
  const ok = await page.waitForFunction(
    exp => document.querySelector('[aria-label="Replay controls"] [aria-live]')?.textContent?.startsWith(exp),
    expected, { timeout }).then(() => true, () => false)
  if (!ok) {
    const now = await headline(page).textContent({ timeout: 1_000 }).catch(() => null)
    const alert = await page.locator('[aria-label="Replay controls"] [role="alert"]').textContent({ timeout: 1_000 }).catch(() => null)
    throw new Error(`replay headline is "${now ?? '(no replay bar)'}", expected "${expected}…"${alert ? `; error shown: ${alert}` : ''}`)
  }
}

/** Switch to Historical replay from a fresh browser (no stored session) and wait for the new session's headline. */
export async function enterReplay(page, expected) {
  const button = page.getByRole('button', { name: 'Historical replay' })
  await button.waitFor({ timeout: TIMEOUT })
  const created = page.waitForResponse(r => r.request().method() === 'POST' && /\/api\/replays$/.test(new URL(r.url()).pathname),
                                       { timeout: TIMEOUT })
  await button.click()
  const res = await created
  if (!res.ok()) throw new Error(`creating the replay session answered ${res.status()}`)
  await waitHeadline(page, expected)
}

/** Click one replay control (e.g. "Next week"), wait for the server's answer to that click, then for the new day. */
export async function replayControl(page, name, expected) {
  const button = page.locator('[aria-label="Replay controls"]').getByRole('button', { name, exact: true })
  await button.waitFor({ timeout: TIMEOUT })
  await page.waitForFunction(n => [...document.querySelectorAll('[aria-label="Replay controls"] button')]
    .some(b => b.textContent === n && !b.disabled), name, { timeout: TIMEOUT })   // not busy with an earlier control
  const answered = page.waitForResponse(r => r.request().method() === 'POST' && /\/api\/replays\/[^/]+\/control$/.test(new URL(r.url()).pathname),
                                        { timeout: TIMEOUT })
  await button.click()
  const res = await answered
  if (!res.ok()) throw new Error(`"${name}" answered ${res.status()}: ${(await res.text()).slice(0, 200)}`)
  await waitHeadline(page, expected)
}

/** Wait until no block is still loading, then a short settle for charts and map tiles. */
export async function waitIdle(page, settle = 500) {
  await page.waitForFunction(() => !document.querySelector('[aria-busy]'), null, { timeout: TIMEOUT }).catch(() => {})
  await page.waitForTimeout(settle)
}

/** A pass/fail counter. step() runs one part of a check; any error inside it becomes one FAIL line. */
export function tally() {
  const t = {
    failed: 0,
    fail(msg) { t.failed++; console.log('FAIL', msg) },
    ok(msg) { console.log('ok  ', msg) },
    async step(label, fn) {
      try { return await fn() } catch (e) { t.fail(`${label}: ${String(e?.message ?? e).split('\n')[0]}`); return undefined }
    },
  }
  return t
}

/** Close the browser whatever happened and set the exit code (1 on any failure) without cutting off the output. */
export async function finish(browser, t) {
  await browser?.close().catch(() => {})
  console.log(t.failed ? `${t.failed} check(s) failed` : 'all checks passed')
  process.exitCode = t.failed ? 1 : 0
}
