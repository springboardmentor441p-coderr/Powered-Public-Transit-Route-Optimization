import { fmt } from '../lib/format'

/** A number with its unit. A missing value is deliberately QUIETER than a real one: 12 px, normal weight,
 *  secondary colour, with its reason, whatever size or weight its parent uses. Never 0, never bold. */
export function Value({ value, digits = 0, unit, reason }: {
  value: number | null | undefined; digits?: number; unit?: string; reason?: string | null
}) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return <span className="align-middle text-xs font-normal tracking-normal text-ink-2">{fmt(value, digits, reason)}</span>
  }
  return (
    <span className="num">
      {fmt(value, digits)}
      {unit && <span className="ml-1 text-[0.75em] font-normal text-ink-2">{unit}</span>}
    </span>
  )
}
