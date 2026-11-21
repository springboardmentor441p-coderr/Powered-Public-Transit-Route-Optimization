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
