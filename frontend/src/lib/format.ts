// One rule for every number on screen: a missing value is "unavailable – reason", never 0.
export const UNAVAILABLE = 'unavailable'

const nf = (digits: number) =>
  new Intl.NumberFormat('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })

/** Format a number with fixed decimals; null/undefined/NaN becomes "unavailable – {reason}". 0 stays "0". */
export function fmt(value: number | null | undefined, digits = 0, reason?: string | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return reason ? `${UNAVAILABLE} – ${reason}` : UNAVAILABLE
  }
  return nf(digits).format(value)
}

/** "rank 3 of 125" or "unranked – {reason}". */
export function fmtRank(rank: number | null | undefined, of: number, reason?: string | null): string {
  return rank == null ? `unranked – ${reason ?? 'no reason given'}` : `rank ${rank} of ${of}`
}

/** A number field's width: one `ch` per character typed (at least 2) plus room for the padding and the list
 *  arrow, so the whole value is always visible ("20" never shows as "2"). */
export const fieldWidth = (text: string) => `calc(${Math.max(text.length, 2) + 1}ch + 1.5rem)`

/** A 0-1 share as a whole percent, except that a share just below 1 is never rounded up to "100": it shows one
 *  decimal ("99.6"), so "100 %" always means every one. Missing stays "unavailable". */
export function fmtPct(share: number | null | undefined, reason?: string | null): string {
  if (share == null || Number.isNaN(share)) return fmt(share, 0, reason)
  const p = share * 100
  return share < 1 && Math.round(p) >= 100 ? fmt(Math.floor(p * 10) / 10, 1) : fmt(p, 0)
}
