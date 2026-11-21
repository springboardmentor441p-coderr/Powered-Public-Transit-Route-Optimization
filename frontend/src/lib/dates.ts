// Dates are ISO strings from the API ("2026-07-31"), read as UTC calendar dates so no time zone can shift them.

const parse = (iso: string) => new Date(`${iso}T00:00:00Z`)

/** "23 Nov 2025". */
export function fmtDate(iso: string): string {
  return new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(parse(iso))
}

/** "23 Nov 2025 – 31 Jul 2026". */
export function fmtRange(start: string, end: string): string {
  return `${fmtDate(start)} – ${fmtDate(end)}`
}

/** The ISO date n days later (or earlier, for negative n). */
export function addDays(iso: string, n: number): string {
  const d = parse(iso)
  d.setUTCDate(d.getUTCDate() + n)
  return d.toISOString().slice(0, 10)
}
