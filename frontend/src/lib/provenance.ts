// "How was this number made?" for a ranking value: every field comes from the /api/rankings response and its row.
import type { ProvenanceInfo } from '../components/Provenance'
import type { RankingMetric, RankingResponse, RankingRow } from '../api/types'
import { DIGITS } from './closerLook'

const DAYTYPE_WORDS = { W: 'weekdays', A: 'Saturdays', U: 'Sundays and holidays' } as const

export function rankingProvenance(d: RankingResponse, r: RankingRow | undefined, route: string, request: string): ProvenanceInfo {
  const m = d.metric.key as RankingMetric
  return {
    title: `Route ${route} · ${d.metric.label.toLowerCase()}`, value: r?.value ?? null, digits: DIGITS[m], unit: d.metric.unit,
    formula: `${d.metric.numerator_label} ÷ ${d.metric.denominator_label}, summed over the observed days`,
    numerator: { label: d.metric.numerator_label, value: r?.numerator ?? null },
    denominator: { label: d.metric.denominator_label, value: r?.denominator ?? null, digits: m === 'rides_per_scheduled_hour' ? 1 : 0 },
    days: r ? { observed: r.observed_days, gateLabel: d.configuration.gate_label } : undefined,
    period: { name: d.period.label, start: d.period.start, end: d.period.end }, daytype: DAYTYPE_WORDS[d.daytype],
    missing: r?.value == null ? { reason: r?.reason ?? 'not in this ranking' } : undefined,
    dataVersion: d.data_version, request, specReference: d.metric.spec_reference,
  }
}
