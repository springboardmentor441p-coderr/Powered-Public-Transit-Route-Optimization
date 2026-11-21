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

const ZONE_NAMES: Record<string, string> = { '+05:30': 'IST', '+00:00': 'UTC', 'Z': 'UTC' }

/** "2026-11-20T14:43:01.623976+05:30" -> "20 Nov 2026, 14:43 IST": the clock time as recorded, in the timestamp's
 *  own offset (never converted to the viewer's zone), named when known, else "UTC+hh:mm". Unparseable -> as given. */
export function fmtTimestamp(ts: string): string {
  const m = /^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})(?::[\d.]+)?(Z|[+-]\d{2}:\d{2})$/.exec(ts)
  if (!m) return ts
  const zone = ZONE_NAMES[m[4]!] ?? `UTC${m[4]}`
  return `${fmtDate(m[1]!)}, ${m[2]}:${m[3]} ${zone}`
}
