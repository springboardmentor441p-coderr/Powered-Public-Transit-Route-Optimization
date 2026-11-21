import { END_WORDS, rankingEnds, type RankedRow } from '../lib/ends'
import { RouteSign } from './RouteSign'

/** One-line preview of both ends of a ranking: "highest … · lowest … · N unranked". Neutral words only. */
export function EndsPreview({ lead, rows, n = 3 }: {
  lead: string; rows: (RankedRow & { groupId?: number | null })[]; n?: number
}) {
  const e = rankingEnds(rows, n)
  const signs = (list: typeof e.high) => list.map(r => <RouteSign key={r.route} route={r.route} groupId={r.groupId} size="sm" />)
  return (
    <>
      <span>{lead}:</span>
      <span className="font-semibold text-ink">{END_WORDS.high}</span> {signs(e.high)}
      <span aria-hidden>·</span>
      <span className="font-semibold text-ink">{END_WORDS.low}</span> {signs(e.low)}
      {e.unranked > 0 && <><span aria-hidden>·</span><span>{e.unranked} unranked</span></>}
    </>
  )
}
