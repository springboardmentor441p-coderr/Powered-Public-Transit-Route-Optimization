// Stop-share strip: how many stops two routes have in common, as aligned bar segments.
// These are stop SETS (the database stores no stop order), so the strip shows "how many", never "where".

export type StopShare = {
  aOnly: number; shared: number; bOnly: number; union: number
  /** segment widths as fractions of the union, in drawing order */
  a: { only: number; shared: number }
  b: { shared: number; only: number }
}

export function stopShare(aStops: number, bStops: number, shared: number): StopShare {
  if (![aStops, bStops, shared].every(n => Number.isInteger(n) && n >= 0)) {
    throw new Error('stop counts must be whole numbers, 0 or more')
  }
  if (shared > Math.min(aStops, bStops)) throw new Error('shared stops cannot exceed either route\'s stops')
  const aOnly = aStops - shared
  const bOnly = bStops - shared
  const union = aOnly + shared + bOnly
  const f = (n: number) => (union ? n / union : 0)
  return { aOnly, shared, bOnly, union, a: { only: f(aOnly), shared: f(shared) }, b: { shared: f(shared), only: f(bOnly) } }
}
