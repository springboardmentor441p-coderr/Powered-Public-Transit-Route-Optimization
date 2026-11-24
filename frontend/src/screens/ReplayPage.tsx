// Replay (spec 9.16.2 "Forecast and evaluation" + "Replay controls"): how good the stored forecasts were, day by day,
// on revealed days only. Every number comes from /api/forecasts/review for the current replay session; the backend
// takes the cutoff from the session, so nothing after the revealed day can appear here (CLAUDE.md, spec 9.16.3).
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api/client'
import { useReplay } from '../api/replayContext'
import type { ReplayState, ReviewResponse } from '../api/types'
import { useApi } from '../api/useApi'
import { AsyncBlock } from '../components/AsyncBlock'
import { Panel, SectionHead } from '../components/Panel'
import { RouteSign } from '../components/RouteSign'
import { Empty } from '../components/States'
import { Value } from '../components/Value'
import { BRAND, INK_2, RULE } from '../design/tokens'
import { fmtDate } from '../lib/dates'
import { fmt } from '../lib/format'
import { daysModelBetter, runningComparison } from '../lib/replay'
import { compareRoutes } from '../lib/routeSort'

const PAGE = 20

export function ReplayPage() {
  const r = useReplay()
  return (
    <div>
      <div className="eyebrow">Replay</div>
      <h1 className="text-xl font-semibold tracking-tight">How good were the forecasts, day by day?</h1>
      {r.mode === 'replay' && r.state ? <ReplayBody s={r.state} /> : <StartReplay />}
    </div>
  )
}

function StartReplay() {
  const r = useReplay()
  const [start, setStart] = useState('2026-06-01')
  return (
    <div className="mt-4 max-w-[70ch] space-y-3 text-base">
      <p>
        A replay walks through June and July 2026 one day at a time. At the start of each day the frozen forecasting model
        has already stored its forecast for every route, using only rides recorded up to the day before. The day's actual
        rides appear only after the clock moves on. Every screen in the app then shows only what was known on that day.
      </p>
      <p className="text-sm text-ink-2">This proves the forecasts never used later information: they were stored before
        their outcome was revealed, and they are never changed afterwards.</p>
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor="replay-start" className="text-sm">Start on</label>
        <input id="replay-start" name="replay_start" type="date" min="2026-06-01" max="2026-07-31" value={start}
               onChange={e => setStart(e.target.value)} className="h-8 border border-rule-strong bg-panel px-1 text-sm" />
        <button type="button" className="btn-secondary" disabled={r.busy || !start} onClick={() => void r.enter(start)}>
          Start a replay</button>
      </div>
      {r.error && <p className="text-sm text-warn-ink" role="alert">{r.error}</p>}
    </div>
  )
}

function ReplayBody({ s }: { s: ReplayState }) {
  const review = useApi(o => api.review(o), 'review')
  const routes = useApi(o => api.routes({}, o), 'routes')
  const g: GroupOf = routes.status === 'ok' ? new Map(routes.data.routes.map(x => [x.route, x.group_id])) : new Map()
  return (
    <div className="mt-4 space-y-6">
      <AsyncBlock state={review} retry={review.retry} label="Loading the forecast review">
        {v => <>
          <Insight v={v} s={s} />
          <ModelFacts v={v} s={s} />
          <RunningChart v={v} />
          <div className="grid items-start gap-4 xl:grid-cols-2">
            <Today v={v} s={s} g={g} />
            <Yesterday v={v} g={g} />
          </div>
          <Misses v={v} g={g} />
        </>}
      </AsyncBlock>
    </div>
  )
}

function Insight({ v, s }: { v: ReviewResponse; s: ReplayState }) {
  const c = runningComparison(v.running)
  const days = daysModelBetter(v.running)
  return (
    <div className="space-y-2 border-l-[3px] border-brand pl-4 text-md leading-8">
      {c == null
        ? <p>Nothing has been revealed in this replay yet. Today's forecasts are stored; the first ones are scored when the
            clock moves to {s.virtual_date ? fmtDate(addDay(s.virtual_date)) : 'the next day'}.</p>
        : <>
            <p>Over <span className="num font-semibold">{fmt(c.rows)}</span> route-days revealed through {fmtDate(c.through)},
              the model's average miss is <span className="num font-semibold">{fmt(c.model, 1)}</span> rides per route-day,
              against <span className="num">{fmt(c.baseline, 1)}</span> for the 4-week average
              {c.direction === 'equal' ? ': the same.' : <>: <span className="font-semibold">{fmt(c.pct, 1)} % {c.direction}</span>.</>}</p>
            <p>The model had the smaller miss on <span className="num font-semibold">{fmt(days.better)}</span> of {fmt(days.days)} revealed days.
              {' '}{fmt(v.coverage.route_days_unavailable)} route-days had no forecast (missing recent rides) and{' '}
              {fmt(v.coverage.route_days_without_actual)} had no recorded rides; neither is scored.</p>
          </>}
    </div>
  )
}

function addDay(iso: string) { const d = new Date(`${iso}T00:00:00Z`); d.setUTCDate(d.getUTCDate() + 1); return d.toISOString().slice(0, 10) }

function ModelFacts({ v, s }: { v: ReviewResponse; s: ReplayState }) {
  return (
    <p className="text-xs text-ink-2">
      Forecasts: {v.model.label}, model {v.model.model_version} (sha256 <span title={v.model.model_sha256} className="cursor-help border-b border-dotted border-ink-2">{v.model.model_sha256.slice(0, 12)}…</span>),
      trained on data to {fmtDate(s.model.trained_through)}, chosen on {fmtDate(s.model.chosen_on[0])} – {fmtDate(s.model.chosen_on[1])},
      {' '}{s.model.frozen_note}. Each forecast is issued at the start of its day.
    </p>
  )
}

function RunningChart({ v }: { v: ReviewResponse }) {
  if (v.running.length === 0) return <Panel title="Running error"><Empty message="No day has been revealed yet." /></Panel>
  return (
    <Panel title="Running error: model against the 4-week average" purpose="Average miss so far, on the same route-days for both."
           howToRead="Each point is the average miss (rides per route-day) over every revealed day up to that date. Solid: the model; dashed: the 4-week average. Lower is better.">
      <div style={{ height: 260 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={v.running} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
            <CartesianGrid stroke={RULE} vertical={false} />
            <XAxis dataKey="date" tick={{ fontSize: 11, fill: INK_2 }} tickFormatter={(d: string) => fmtDate(d).slice(0, -5)} minTickGap={40} />
            <YAxis tick={{ fontSize: 11, fill: INK_2 }} width={56} tickFormatter={(x: number) => fmt(x)}
                   label={{ value: 'average miss, rides', angle: -90, position: 'insideLeft', fontSize: 11, fill: INK_2, style: { textAnchor: 'middle' } }} />
            <Tooltip isAnimationActive={false} labelFormatter={d => fmtDate(String(d))} formatter={x => fmt(Number(x), 1)} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Line dataKey="model_mae" name="Model (random forest)" stroke={BRAND} strokeWidth={2} dot={false} isAnimationActive={false} />
            <Line dataKey="baseline_mae" name="4-week average" stroke={INK_2} strokeWidth={2} strokeDasharray="6 4" dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  )
}

function Today({ v, s, g }: { v: ReviewResponse; s: ReplayState; g: GroupOf }) {
  const [all, setAll] = useState(false)
  if (!v.review.date) return <Panel title="Today's forecasts"><Empty message="The replay is complete: there is no next day to forecast." /></Panel>
  const rows = v.review.rows
  const shown = all ? rows : rows.slice(0, PAGE)
  return (
    <Panel title={`Today's forecasts, ${fmtDate(v.review.date)}`}
           purpose={`Predicted rides against planned service, issued at the start of the day; actuals appear after ${fmtDate(v.review.date)} is revealed.`}
           howToRead={`${v.review.meaning}. #n ranks predicted rides per scheduled hour (ties share a rank). A route without a forecast shows why.`}>
      <div className="-mx-4 overflow-x-auto">
        <table className="data-table">
          <thead><tr><th>Route</th><th className="n">Predicted rides</th><th className="n">Scheduled trips</th><th className="n">Per scheduled hour</th></tr></thead>
          <tbody>{shown.map(r => (
            <tr key={r.route}>
              <td><RouteLink route={r.route} g={g} /></td>
              <td className="n"><Value value={r.predicted_rides} reason={r.reason} /></td>
              <td className="n num">{fmt(r.scheduled_trips)}</td>
              <td className="n"><Value value={r.predicted_rides_per_scheduled_hour} digits={1} reason={r.status === 'forecast' ? r.reason : 'no forecast'} />
                {r.rank_per_hour != null && <span className="ml-1.5 text-xs text-ink-2">#{r.rank_per_hour}</span>}</td>
            </tr>))}</tbody>
        </table>
      </div>
      {rows.length > PAGE && <button type="button" className="btn-secondary mt-3" onClick={() => setAll(a => !a)}>
        {all ? `Show the first ${PAGE}` : `Show all ${rows.length} routes`}</button>}
      <p className="mt-2 text-xs text-ink-2">{fmt(rows.filter(r => r.status === 'forecast').length)} of {fmt(rows.length)} scheduled routes have a forecast today · replay day {s.virtual_date ? fmtDate(s.virtual_date) : ''}.</p>
    </Panel>
  )
}

function Yesterday({ v, g }: { v: ReviewResponse; g: GroupOf }) {
  const [all, setAll] = useState(false)
  const day = v.running.at(-1)?.date
  if (!day || v.yesterday.length === 0) return <Panel title="Yesterday"><Empty message="No day has been revealed yet." /></Panel>
  const rows = [...v.yesterday].sort((a, b) => Math.abs(b.error ?? -1) - Math.abs(a.error ?? -1) || compareRoutes(a.route, b.route))
  const shown = all ? rows : rows.slice(0, PAGE)
  return (
    <Panel title={`Yesterday, ${fmtDate(day)}: forecast against actual`} purpose="Largest misses first. Both forecasts were stored before the day's rides were revealed."
           howToRead="Miss = actual minus forecast: positive means more riders than forecast. A route with no forecast or no recorded rides shows why.">
      <div className="-mx-4 overflow-x-auto">
        <table className="data-table">
          <thead><tr><th>Route</th><th className="n">Forecast</th><th className="n">4-week average</th><th className="n">Actual</th><th className="n">Miss</th></tr></thead>
          <tbody>{shown.map(r => (
            <tr key={r.route}>
              <td><RouteLink route={r.route} g={g} /></td>
              <td className="n"><Value value={r.prediction} reason="no forecast" /></td>
              <td className="n"><Value value={r.baseline} reason="no forecast" /></td>
              <td className="n"><Value value={r.rides} reason="no ridership record" /></td>
              <td className="n">{r.error == null ? <Value value={null} reason="not scored" /> : <span className="num">{r.error > 0 ? '+' : ''}{fmt(r.error)}</span>}</td>
            </tr>))}</tbody>
        </table>
      </div>
      {rows.length > PAGE && <button type="button" className="btn-secondary mt-3" onClick={() => setAll(a => !a)}>
        {all ? `Show the first ${PAGE}` : `Show all ${rows.length} routes`}</button>}
    </Panel>
  )
}

function Misses({ v, g }: { v: ReviewResponse; g: GroupOf }) {
  const [all, setAll] = useState(false)
  const ranked = v.misses.rows.filter(m => m.rank != null)
  const unranked = v.misses.rows.length - ranked.length
  const shown = all ? ranked : ranked.slice(0, PAGE)
  return (
    <>
      <SectionHead title="Largest misses so far" note={`Ranked only with ${v.misses.gate_label}, the same gate as the other rankings.`} />
      <Panel title={`${fmt(ranked.length)} routes ranked, ${fmt(unranked)} not yet`} purpose={`${v.misses.meaning[0]!.toUpperCase()}${v.misses.meaning.slice(1)}.`}
             howToRead="Average miss per route over its revealed, scored days, for the model and the 4-week average. A large miss is a prompt to look at the route, not a verdict on it.">
        {ranked.length === 0
          ? <p className="text-sm">No route has {v.misses.gate_label} yet{v.misses.rows[0] ? ` (the most so far: ${fmt(Math.max(...v.misses.rows.map(m => m.scored_days)))})` : ''}. Routes are ranked once they reach the gate.</p>
          : <div className="-mx-4 overflow-x-auto">
              <table className="data-table">
                <thead><tr><th className="n">Rank</th><th>Route</th><th className="n">Scored days</th><th className="n">Model miss</th><th className="n">4-week average miss</th></tr></thead>
                <tbody>{shown.map(m => (
                  <tr key={m.route}>
                    <td className="n num">#{m.rank}</td><td><RouteLink route={m.route} g={g} /></td>
                    <td className="n num">{fmt(m.scored_days)}</td>
                    <td className="n"><Value value={m.model_mae} digits={1} /></td>
                    <td className="n"><Value value={m.baseline_mae} digits={1} /></td>
                  </tr>))}</tbody>
              </table>
            </div>}
        {ranked.length > PAGE && <button type="button" className="btn-secondary mt-3" onClick={() => setAll(a => !a)}>
          {all ? `Show the first ${PAGE}` : `Show all ${ranked.length} ranked routes`}</button>}
      </Panel>
    </>
  )
}

type GroupOf = Map<string, number | null>

function RouteLink({ route, g }: { route: string; g: GroupOf }) {
  return <Link to={`/route/${encodeURIComponent(route)}`} className="no-underline" aria-label={`Open route ${route}`}>
    <RouteSign route={route} groupId={g.get(route)} size="sm" /></Link>
}
