import { CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api/client'
import { useReplay } from '../api/replayContext'
import type { ForecastRow } from '../api/types'
import { useApi } from '../api/useApi'
import { BRAND, INK_2, RULE } from '../design/tokens'
import { fmtDate } from '../lib/dates'
import { fmt } from '../lib/format'
import { AsyncBlock } from './AsyncBlock'
import { Panel } from './Panel'
import { Value } from './Value'

/** One route's forecasts (spec 9.16.3 route-detail layout). Replay: today's predicted rides with its planned service
 *  and issue context, and the revealed rides drawn against the stored forecasts; today's actual is marked as not yet
 *  revealed. Historical analysis: a note that forecasts are shown in the replay. Every value comes from
 *  /api/forecasts for the current session (the backend decides what is revealed). */
export function ForecastPanel({ route }: { route: string }) {
  const r = useReplay()
  if (r.mode !== 'replay' || !r.state) {
    return (
      <Panel title="Forecast" purpose="Forecasts are shown in Historical replay.">
        <p className="text-sm">
          A forecast is only honest when it was made before its day. Switch to <span className="font-semibold">Historical replay</span> in
          the top bar to see this route's stored forecasts day by day, each issued before its actual rides were revealed.
        </p>
        <button type="button" className="btn-secondary mt-3" disabled={r.busy} onClick={r.resume}>Start or resume the replay</button>
      </Panel>
    )
  }
  return <ReplayForecast route={route} />
}

type Point = { date: string; actual: number | null; model: number | null; baseline: number | null }

function ReplayForecast({ route }: { route: string }) {
  const r = useReplay()
  const s = r.state!
  const f = useApi(o => api.forecasts({ route }, o), `forecasts:${route}`)
  return (
    <AsyncBlock state={f} retry={f.retry} label="Loading forecasts" isEmpty={d => d.forecasts.length === 0}
                emptyMessage={`Route ${route} has no scheduled service on any replay day reached so far.`}>
      {d => {
        const model = d.forecasts.filter(x => x.method === 'rf_demand')
        const base = new Map(d.forecasts.filter(x => x.method !== 'rf_demand').map(x => [x.target_date, x]))
        const today = s.virtual_date ? model.find(x => x.target_date === s.virtual_date) : undefined
        const points: Point[] = model.map(x => ({ date: x.target_date, actual: x.actual.revealed ? x.actual.rides : null,
                                                  model: x.prediction, baseline: base.get(x.target_date)?.prediction ?? null }))
        const scored = model.filter(x => x.actual.revealed && x.actual.rides != null && x.prediction != null)
        const mae = scored.length ? scored.reduce((a, x) => a + Math.abs(x.actual.rides! - x.prediction!), 0) / scored.length : null
        return (
          <Panel title={`Forecast, route ${route}`} purpose="Historical replay"
                 aside={!s.complete && <button type="button" className="btn-secondary" disabled={r.busy} onClick={() => void r.act('advance')}>Advance one day</button>}
                 howToRead="Solid: recorded rides, shown only once their day is revealed. Dashed: the model's stored forecast, issued at the start of each day. Dotted: the 4-week average. The marked day is today: its forecast is visible, its actual is not yet.">
            {today ? <TodayFacts t={today} /> : <p className="mb-3 text-sm">{s.complete ? 'The replay is complete.' : `No forecast for route ${route} today (no scheduled service).`}</p>}
            <div style={{ height: 240 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={points} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
                  <CartesianGrid stroke={RULE} vertical={false} />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: INK_2 }} tickFormatter={(x: string) => fmtDate(x).slice(0, -5)} minTickGap={36} />
                  <YAxis tick={{ fontSize: 11, fill: INK_2 }} width={56} tickFormatter={(x: number) => fmt(x)} />
                  <Tooltip isAnimationActive={false} labelFormatter={x => fmtDate(String(x))}
                           formatter={(x, name) => [x == null ? 'not revealed yet' : fmt(Number(x)), String(name)]} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  {s.virtual_date && <ReferenceLine x={s.virtual_date} stroke={INK_2} strokeDasharray="2 3"
                                                    label={{ value: 'today: actual not yet revealed', fontSize: 11, fill: INK_2, position: 'insideTopRight' }} />}
                  <Line dataKey="actual" name="Recorded rides" stroke={BRAND} strokeWidth={2} dot={false} connectNulls={false} isAnimationActive={false} />
                  <Line dataKey="model" name="Predicted rides (model)" stroke={BRAND} strokeWidth={1.5} strokeDasharray="6 4" dot={false} connectNulls={false} isAnimationActive={false} />
                  <Line dataKey="baseline" name="4-week average" stroke={INK_2} strokeWidth={1.5} strokeDasharray="2 3" dot={false} connectNulls={false} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <p className="mt-2 text-xs text-ink-2">
              {scored.length === 0
                ? 'No forecast for this route has been revealed and scored yet.'
                : <>On its {fmt(scored.length)} revealed, scored days the model missed by <span className="num">{fmt(mae, 0)}</span> rides on average.</>}
              {' '}Model {d.run.model_version}; {d.run.issue_time_rule}.
            </p>
          </Panel>
        )
      }}
    </AsyncBlock>
  )
}

function TodayFacts({ t }: { t: ForecastRow }) {
  const cell = 'border-l border-rule pl-3'
  return (
    <dl className="mb-3 grid grid-cols-2 gap-x-4 gap-y-2 text-sm md:grid-cols-4">
      <div className={cell}><dt className="text-xs text-ink-2">Predicted daily rides, {fmtDate(t.target_date)}</dt>
        <dd className="text-lg font-semibold"><Value value={t.prediction} unit={t.units} reason={t.unavailable_reason} /></dd></div>
      <div className={cell}><dt className="text-xs text-ink-2">Scheduled trips</dt><dd className="text-lg num">{fmt(t.scheduled_trips)}</dd></div>
      <div className={cell}><dt className="text-xs text-ink-2">Scheduled trip-hours</dt>
        <dd className="text-lg"><Value value={t.scheduled_hours} digits={1} reason="incomplete trip durations" /></dd></div>
      <div className={cell}><dt className="text-xs text-ink-2">Forecast rides per scheduled trip</dt>
        <dd className="text-lg"><Value value={t.forecast_rides_per_scheduled_trip} digits={1} reason={t.unavailable_reason ?? 'no forecast'} /></dd></div>
      <dd className="col-span-full text-xs text-ink-2">
        Issued at the start of {fmtDate(t.target_date)}, from rides up to {fmtDate(t.latest_available_ride_date)} and timetable {t.input_schedule_snapshot} ·
        status: {t.status === 'forecast' ? 'forecast' : `unavailable – ${t.unavailable_reason}`} · actual: {t.actual.revealed ? 'revealed' : 'not yet revealed'}
      </dd>
    </dl>
  )
}
