// Scenarios (spec 9.16.2 "Scenarios"): "What if we changed the service?". A sentence builds the baseline and the
// service change; a separate, marked line adds a demand assumption. The API calculates (demand held fixed unless that
// line says otherwise), and the result can be saved: saved scenarios are never changed, only given new versions.
// Every number and sentence on this page comes from /api/scenarios (CLAUDE.md, UI principles).
import { useId, useState, type ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, scenarios } from '../api/client'
import { useRequestScope } from '../api/cutoff'
import { useReplay } from '../api/replayContext'
import type { DayType, PeriodName, Scenario, ScenarioRequest, ScenarioResponse, ScenarioRow, ScenarioSide, ScenarioTotals } from '../api/types'
import { useApi } from '../api/useApi'
import { AsyncBlock } from '../components/AsyncBlock'
import { ApiLabel, Panel, SectionHead } from '../components/Panel'
import { RouteSign } from '../components/RouteSign'
import { Choice, Sentence } from '../components/Sentence'
import { Empty } from '../components/States'
import { Value } from '../components/Value'
import { INK, INK_2, RULE, SLATE_RAMP } from '../design/tokens'
import { addDays, fmtDate, fmtTimestamp } from '../lib/dates'
import { fmt } from '../lib/format'
import { compareRoutes, sortByRoute } from '../lib/routeSort'
import {
  builderFromRequest, builderParams, DAYTYPE_TEXT, fmtChange, fmtRankMove, insights, MEASURE_TEXT, parseBuilder,
  PERIOD_TEXT, toRequest, type Builder, type Measure, type Verb,
} from '../lib/scenarios'

type GroupOf = Map<string, number | null>
const VERB_TEXT: Record<Verb, string> = { increase: 'Increase', decrease: 'Decrease', set: 'Set', keep: 'Keep' }
const AMOUNT_RANGE: Record<Exclude<Verb, 'keep'>, [number, number]> = { increase: [0, 200], decrease: [0, 100], set: [0, 2000] }

export function ScenariosPage() {
  const [params, setParams] = useSearchParams()
  const b = parseBuilder(params)
  const r = useReplay()
  const inReplay = r.mode === 'replay'
  const [revises, setRevises] = useState<{ id: string; name: string } | null>(null)
  const [openId, setOpenId] = useState<string | null>(null)
  const [listTick, setListTick] = useState(0)
  const update = (next: Builder) => setParams(() => {
    const n = new URLSearchParams()
    for (const [k, v] of Object.entries(builderParams(next))) if (v != null) n.set(k, v)
    return n
  }, { replace: true })
  const req = toRequest(inReplay || b.demand === 'recorded' ? b : { ...b, demand: 'recorded' })
  const reqKey = JSON.stringify(req)
  const calc = useApi(o => (req ? scenarios.calculate(req, o) : Promise.resolve(null)), `scenario:${reqKey}`)
  const routes = useApi(o => api.routes({}, o), 'routes')
  const groupOf: GroupOf = routes.status === 'ok' ? new Map(routes.data.routes.map(x => [x.route, x.group_id])) : new Map()

  return (
    <div>
      <div className="eyebrow">Scenarios</div>
      <h1 className="text-xl font-semibold tracking-tight">What if we changed the service?</h1>
      <p className="mt-2 max-w-[80ch] text-sm text-ink-2">
        A scenario starts from what was recorded, changes the timetable as you say, and recalculates the service
        ratios. Riders stay as recorded unless you add a demand assumption below: more buses do not create riders here.
      </p>
      <div className="mt-4">
        <Builder b={b} update={update} inReplay={inReplay} routes={routes.status === 'ok' ? routes.data : null} groupOf={groupOf} />
      </div>
      {revises && (
        <p className="mb-3 text-sm"><ApiLabel text={`Building a new version of “${revises.name}”. The saved version stays as it is.`} />
          <button type="button" className="ml-2 text-sm text-ink-2 underline" onClick={() => setRevises(null)}>Stop</button></p>
      )}
      {!req
        ? <Empty message={!b.routes.length && b.group == null ? 'Choose a route or a route group to start.'
                          : 'Choose a service change or add a demand assumption.'} />
        : <AsyncBlock state={calc} retry={calc.retry} label="Calculating the scenario" isEmpty={c => c == null}>
            {c => <>
              <SaveBar resp={c!} req={req} b={b} revises={revises}
                       onSaved={id => { setRevises(null); setOpenId(id); setListTick(t => t + 1) }} />
              <ResultView resp={c!} groupOf={groupOf} />
            </>}
          </AsyncBlock>}
      <SavedList tick={listTick} openId={openId} setOpenId={setOpenId} groupOf={groupOf} inReplay={inReplay}
                 onRevise={(s) => {
                   const rq = s.baseline.request
                   const next = builderFromRequest({ baseline: rq, service: s.inputs.service, demand_stress: s.inputs.demand_stress })
                   update(next); setRevises({ id: s.scenario_id!, name: s.name! }); window.scrollTo({ top: 0 })
                 }} />
    </div>
  )
}

// ------------------------------------------------------------------------------------------- the builder
function Builder({ b, update, inReplay, routes, groupOf }: {
  b: Builder; update: (b: Builder) => void; inReplay: boolean
  routes: { routes: { route: string; route_long_name: string | null; group_id: number | null; group_name: string | null }[] } | null
  groupOf: GroupOf
}) {
  const set = (patch: Partial<Builder>) => update({ ...b, ...patch })
  const groups = routes ? [...new Map(routes.routes.filter(x => x.group_id != null).map(x => [x.group_id!, x.group_name ?? `group ${x.group_id}`])).entries()].sort((x, y) => x[0] - y[0]) : []
  const addable = routes ? sortByRoute(routes.routes.filter(x => !b.routes.includes(x.route)), x => x.route) : []
  const predicted = inReplay && b.demand === 'predicted'
  const range = b.verb === 'keep' ? null : AMOUNT_RANGE[b.verb]
  const who = (
    <>
      {b.group != null
        ? <span className="mr-1 inline-flex items-center gap-0.5 align-middle font-semibold">
            the route group “{groups.find(g => g[0] === b.group)?.[1] ?? `group ${b.group}`}”
            <button type="button" className="px-1 text-sm font-normal text-ink-2 hover:text-ink" aria-label="Remove the route group"
                    onClick={() => set({ group: null })}>×</button></span>
        : b.routes.map(r => (
            <span key={r} className="mr-1 inline-flex items-center gap-0.5 align-middle">
              <RouteSign route={r} groupId={groupOf.get(r)} size="sm" />
              <button type="button" className="px-1 text-sm text-ink-2 hover:text-ink" aria-label={`Remove route ${r}`}
                      onClick={() => set({ routes: b.routes.filter(x => x !== r) })}>×</button>
            </span>
          ))}
      {routes && b.group == null && (
        <Choice label="Add a route or a group" value="" onChange={v => {
          if (!v) return
          if (v.startsWith('group:')) set({ group: Number(v.slice(6)), routes: [] })
          else set({ routes: [...b.routes, v] })
        }} options={[{ value: '', text: b.routes.length ? 'add a route' : 'choose routes or a group' },
                     ...(b.routes.length ? [] : groups.map(([id, name]) => ({ value: `group:${id}`, text: `the route group “${name}”` }))),
                     ...addable.map(x => ({ value: x.route, text: x.route_long_name ? `route ${x.route} ${x.route_long_name}` : `route ${x.route}` }))]} />
      )}
    </>
  )
  const when = predicted ? <> on the replay day</>
    : <> on <Choice label="Day type" value={b.daytype} onChange={v => set({ daytype: v as DayType })}
                    options={(Object.keys(DAYTYPE_TEXT) as DayType[]).map(d => ({ value: d, text: DAYTYPE_TEXT[d] }))} /> in{' '}
        <Choice label="Period" value={b.period} onChange={v => set({ period: v as PeriodName })}
                options={(Object.keys(PERIOD_TEXT) as PeriodName[]).map(p => ({ value: p, text: PERIOD_TEXT[p] }))} /></>
  const using = <>, using{' '}
    {inReplay
      ? <Choice label="Demand" value={b.demand} onChange={v => set({ demand: v as Builder['demand'] })}
                options={[{ value: 'recorded', text: 'recorded rides' }, { value: 'predicted', text: "the stored forecast for the replay day" }]} />
      : <span className="font-semibold">recorded rides</span>}.</>
  const verb = <Choice label="Change" value={b.verb} onChange={v => set({ verb: v as Verb })}
                       options={(Object.keys(VERB_TEXT) as Verb[]).map(v => ({ value: v, text: VERB_TEXT[v] }))} />
  const measure = <Choice label="What changes" value={b.measure} onChange={v => set({ measure: v as Measure })}
                          options={(Object.keys(MEASURE_TEXT) as Measure[]).map(m => ({ value: m, text: MEASURE_TEXT[m] }))} />
  const amount = range && <NumberField label="Amount" value={b.amount} min={range[0]} max={range[1]} onChange={v => set({ amount: v })} />
  return (
    <>
      <Sentence>
        {b.verb === 'keep' ? <>{verb} the service on {who} unchanged{when}{using}</>
          : b.verb === 'set' ? <>{verb} {measure} on {who} to {amount} per day{when}{using}</>
          : <>{verb} {measure} on {who} by {amount} %{when}{using}</>}
      </Sentence>
      <div className="mb-5 border-l-[3px] border-warn-ink bg-warn-bg px-3 py-2 text-base text-ink">
        <span className="mr-2 text-xs font-semibold uppercase tracking-wide text-warn-ink">Scenario assumption</span>
        {b.stress
          ? <>Assume rides{' '}
              <Choice label="Demand direction" value={b.stress.dir} onChange={v => set({ stress: { ...b.stress!, dir: v as 'fall' | 'rise' } })}
                      options={[{ value: 'fall', text: 'fall' }, { value: 'rise', text: 'rise' }]} /> by{' '}
              <NumberField label="Demand change" value={b.stress.percent} min={0} max={b.stress.dir === 'fall' ? 90 : 100}
                           onChange={v => set({ stress: { ...b.stress!, percent: v } })} /> % on{' '}
              <Choice label="Demand applies to" value={b.stress.scope} onChange={v => set({ stress: { ...b.stress!, scope: v as 'baseline_routes' | 'network' } })}
                      options={[{ value: 'baseline_routes', text: 'these routes' }, { value: 'network', text: 'every route in the network' }]} />.
              <span className="block text-xs text-ink-2">This is assumed demand, not a prediction. The recorded or forecast rides are kept alongside it.</span>
              <button type="button" className="mt-1 text-sm text-ink-2 underline" onClick={() => set({ stress: null })}>Remove the demand assumption</button></>
          : <>Demand is held fixed.{' '}
              <button type="button" className="text-sm underline" onClick={() => set({ stress: { dir: 'fall', percent: 15, scope: 'baseline_routes' } })}>
                Add a demand assumption</button></>}
      </div>
    </>
  )
}

/** A decimal number inside a sentence. An out-of-range value stays visible, says why, and is not used. */
function NumberField({ label, value, min, max, onChange }: { label: string; value: number; min: number; max: number; onChange: (v: number) => void }) {
  const id = useId()
  const [text, setText] = useState(String(value))
  const [seen, setSeen] = useState(value)
  if (value !== seen) { setSeen(value); setText(String(value)) }
  const n = text.trim() === '' ? NaN : Number(text)
  const ok = Number.isFinite(n) && n >= min && n <= max
  const name = label.toLowerCase().replace(/[^a-z0-9]+/g, '_')
  return (
    <>
      <label htmlFor={id} className="sr-only">{label}</label>
      <input id={id} name={name} type="number" inputMode="decimal" min={min} max={max} step="any" value={text}
             aria-invalid={!ok} aria-describedby={ok ? undefined : `${id}-err`}
             onChange={e => { setText(e.target.value); const v = Number(e.target.value); if (e.target.value.trim() !== '' && Number.isFinite(v) && v >= min && v <= max) onChange(v) }}
             style={{ width: `calc(${Math.max(text.length, 2) + 1}ch + 1.5rem)` }}
             className={`mx-0.5 border-0 border-b-2 px-1 py-0 text-center font-semibold num [appearance:textfield]
                         [&::-webkit-inner-spin-button]:appearance-none ${ok ? 'border-brand bg-transparent' : 'border-warn-ink bg-warn-bg text-warn-ink'}`} />
      {!ok && <span id={`${id}-err`} role="alert" className="ml-1 text-xs text-warn-ink">between {fmt(min)} and {fmt(max)}</span>}
    </>
  )
}

// ------------------------------------------------------------------------------------------- saving
function defaultName(b: Builder, resp: ScenarioResponse): string {
  const s = resp.scenario.baseline
  const who = s.group ? s.group.group_name : s.routes.length === 1 ? `Route ${s.routes[0]}` : `${s.routes.length} routes`
  const change = b.verb === 'keep' ? 'service unchanged' : b.verb === 'set' ? `${MEASURE_TEXT[b.measure]} set to ${b.amount}/day`
    : `${b.verb === 'decrease' ? '−' : '+'}${b.amount} % ${MEASURE_TEXT[b.measure]}`
  const stress = b.stress ? `, rides ${b.stress.dir === 'fall' ? '−' : '+'}${b.stress.percent} % assumed` : ''
  return `${who}: ${change}, ${s.daytype_label}${stress}`.slice(0, 80)
}

function SaveBar({ resp, req, b, revises, onSaved }: {
  resp: ScenarioResponse; req: ScenarioRequest; b: Builder; revises: { id: string; name: string } | null; onSaved: (id: string) => void
}) {
  const scope = useRequestScope()
  const suggested = revises?.name ?? defaultName(b, resp)
  const [name, setName] = useState<string | null>(null)
  const [state, setState] = useState<{ busy: boolean; error: string | null; done: string | null }>({ busy: false, error: null, done: null })
  const value = name ?? suggested
  const save = async () => {
    setState({ busy: true, error: null, done: null })
    try {
      const r = await scenarios.save({ ...req, name: value, revises: revises?.id ?? null }, { session: scope.session })
      const s = r.scenario
      setState({ busy: false, error: null, done: `${r.created ? 'Saved' : 'Already saved'}: “${s.name}”, version ${s.version}.` })
      onSaved(s.scenario_id!)
    } catch (e) { setState({ busy: false, error: (e as Error).message, done: null }) }
  }
  return (
    <div className="mb-5 flex flex-wrap items-center gap-2">
      <label htmlFor="scenario-name" className="text-sm">Name</label>
      <input id="scenario-name" name="scenario_name" maxLength={80} value={value} onChange={e => setName(e.target.value)}
             className="h-8 w-[60ch] max-w-full border border-rule-strong bg-panel px-2 text-sm" />
      <button type="button" className="btn-secondary" disabled={state.busy || !value.trim()} onClick={() => void save()}>
        {revises ? 'Save as a new version' : 'Save scenario'}</button>
      {state.done && <span className="text-sm" role="status">{state.done}</span>}
      {state.error && <span className="text-sm text-warn-ink" role="alert">{state.error}</span>}
      <span className="basis-full text-xs text-ink-2">A saved scenario keeps its inputs, assumptions and results, and is never changed. Editing saves a new version.</span>
    </div>
  )
}

// ------------------------------------------------------------------------------------------- the result
function ResultView({ resp, groupOf, saved }: { resp: ScenarioResponse; groupOf: GroupOf; saved?: Scenario }) {
  const s = resp.scenario, res = s.result
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-2"><ApiLabel text={resp.note} /></div>
      <div className="border-l-[3px] border-brand pl-4 text-md leading-8">
        {insights(resp).map(t => <p key={t}>{t}</p>)}
      </div>
      <Panel title="Assumptions" purpose={saved ? `Saved with “${saved.name}”, version ${saved.version}.` : 'Saved with the scenario, word for word.'}>
        <ul className="space-y-1.5 text-sm">
          {s.assumptions.map(a => (
            <li key={a.kind + a.text} className={a.kind === 'demand_stress' ? 'border-l-[3px] border-warn-ink bg-warn-bg px-2 py-1' : ''}>
              {a.kind === 'demand_stress' && <span className="mr-2 text-xs font-semibold uppercase tracking-wide text-warn-ink">Scenario assumption</span>}
              {a.text}
            </li>
          ))}
        </ul>
        <p className="mt-3 text-xs text-ink-2">
          Data version {s.versions.data_version}{s.versions.group_version ? ` · route groups ${s.versions.group_version.split('/').at(-1)}` : ''}
          {s.versions.model_version ? ` · forecasts from model ${s.versions.model_version}` : ''} · data used to {fmtDate(s.cutoff)} ·
          result sha256 <span title={s.result_sha256} className="cursor-help border-b border-dotted border-ink-2">{s.result_sha256.slice(0, 12)}…</span>
        </p>
      </Panel>
      <ComparisonTable resp={resp} groupOf={groupOf} />
      <RatioChart rows={res.rows} />
    </div>
  )
}

function BeforeAfter({ b, s, digits = 1, rb, rs }: { b: number | null; s: number | null; digits?: number; rb?: string; rs?: string }) {
  const same = b != null && s != null && fmt(b, digits) === fmt(s, digits)
  if (b == null && s == null && rb === rs) return <Value value={null} reason={rb} />
  return (
    <span className="whitespace-nowrap">
      <Value value={b} digits={digits} reason={rb} />
      {!same && <><span className="mx-1 text-ink-2" aria-label="becomes">→</span><Value value={s} digits={digits} reason={rs} /></>}
    </span>
  )
}

const KEYS: [keyof ScenarioSide, 'rides_per_day' | 'trips_per_day' | 'hours_per_day' | 'rides_per_trip' | 'rides_per_hour', number][] = [
  ['rides_per_day', 'rides_per_day', 0], ['trips_per_day', 'trips_per_day', 1], ['hours_per_day', 'hours_per_day', 1],
  ['rides_per_scheduled_trip', 'rides_per_trip', 1], ['rides_per_scheduled_hour', 'rides_per_hour', 1],
]

function ComparisonTable({ resp, groupOf }: { resp: ScenarioResponse; groupOf: GroupOf }) {
  const s = resp.scenario, res = s.result
  const sorted = [...res.rows].sort((a, b) => Number(a.status === 'unchanged') - Number(b.status === 'unchanged') || compareRoutes(a.route, b.route))
  // Routes with nothing to compare on either side are listed once, by reason, instead of a row of "unavailable" cells
  const rows = sorted.filter(r => !nothingToCompare(r))
  const blank = new Map<string, string[]>()
  for (const r of sorted.filter(nothingToCompare)) {
    const why = r.baseline.reasons.trips_per_day ?? r.baseline.reasons.rides_per_day ?? 'no values'
    blank.set(why, [...(blank.get(why) ?? []), r.route])
  }
  const of = res.ranked_routes.rides_per_scheduled_hour
  const demandWord = s.baseline.demand === 'predicted' ? 'Predicted rides/day' : 'Recorded rides/day'
  const totals = (label: string, t: ScenarioTotals) => (
    <tr className="border-t-2 border-rule-strong font-semibold">
      <th scope="row" className="text-left">{label}<span className="block text-xs font-normal text-ink-2">{t.rides_per_scheduled_hour.routes_included} of {t.routes} routes with values on both sides</span></th>
      {(['rides_per_day', 'trips_per_day', 'hours_per_day'] as const).map(k => (
        <td key={k} className="n"><BeforeAfter b={t[k].baseline} s={t[k].scenario} digits={k === 'rides_per_day' ? 0 : 1} rb="no route has a value" rs="no route has a value" /></td>
      ))}
      <td className="n" />
      {(['rides_per_scheduled_trip', 'rides_per_scheduled_hour'] as const).map(k => (
        <td key={k} className="n"><BeforeAfter b={t[k].baseline} s={t[k].scenario} rb="no route has a value" rs="no route has a value" />
          <span className="block text-xs font-normal text-ink-2">{fmtChange(t[k].change_percent)}</span></td>
      ))}
      <td />
    </tr>
  )
  return (
    <Panel title="Baseline and scenario, route by route"
           purpose={s.baseline.demand === 'predicted'
             ? `The replay day, ${fmtDate(s.baseline.period.start)} · predicted rides from the stored forecast, with that day's timetable.`
             : `${s.baseline.period.label} · ${s.baseline.daytype_label} · per-day values are means over each route's observed days; ratios are sums over the same days.`}
           howToRead={`Each cell shows the baseline, then → the scenario. "Assumed" marks rides changed by the demand assumption. Rank is the position on rides per scheduled hour among ${of.scenario} ranked routes (1 = highest), with ties sharing a rank. Unavailable values say why and are never shown as 0.`}>
      <div className="-mx-4 overflow-x-auto">
        <table className="data-table">
          <thead><tr>
            <th>Route</th><th className="n">{demandWord}</th><th className="n">Scheduled trips/day</th><th className="n">Scheduled trip-hours/day</th>
            <th className="n">Minutes per trip</th><th className="n">Rides per scheduled trip</th><th className="n">Rides per scheduled hour</th><th className="n">Rank</th>
          </tr></thead>
          <tbody>
            {rows.map(r => <RouteRow key={r.route} r={r} groupOf={groupOf} />)}
            {res.rows.length > 1 && totals(s.baseline.group ? 'The group' : 'These routes', res.totals.selected)}
            {totals('Whole network', res.totals.network)}
          </tbody>
        </table>
      </div>
      {[...blank.entries()].map(([why, rs]) => (
        <p key={why} className="mt-3 text-sm">
          <span className="font-semibold">{rs.length} route{rs.length === 1 ? '' : 's'} not in the table</span>
          <span className="text-ink-2"> – unavailable on both sides: {why}. </span>
          {rs.map((r, i) => <span key={r}>{i > 0 && ' '}<Link to={`/route/${encodeURIComponent(r)}`} className="no-underline" aria-label={`Open route ${r}`}>
            <RouteSign route={r} groupId={groupOf.get(r)} size="sm" /></Link></span>)}
        </p>
      ))}
      {res.other_rank_changes.length > 0 && (
        <p className="mt-3 text-sm">Other routes that change rank as a result: {res.other_rank_changes.slice(0, 12).map((o, i) => (
          <span key={o.route}>{i > 0 && ', '}<Link to={`/route/${encodeURIComponent(o.route)}`} aria-label={`Open route ${o.route}`}>{o.route}</Link> ({o.rank_before} → {o.rank_after})</span>
        ))}{res.other_rank_changes.length > 12 && ` and ${res.other_rank_changes.length - 12} more`}.</p>
      )}
    </Panel>
  )
}

/** No value on either side (a structural zero, or no timetable match), and nothing applied to it. */
function nothingToCompare(r: ScenarioRow): boolean {
  if (r.status !== 'unchanged' || r.note) return false
  return KEYS.every(([k]) => r.baseline[k] == null && r.scenario[k] == null)
}

function RouteRow({ r, groupOf }: { r: ScenarioRow; groupOf: GroupOf }) {
  const b = r.baseline, s = r.scenario
  const cells: ReactNode[] = KEYS.map(([k, reasonKey, d]) => (
    <td key={k} className="n">
      <BeforeAfter b={b[k] as number | null} s={s[k] as number | null} digits={d} rb={b.reasons[reasonKey]} rs={s.reasons[reasonKey]} />
      {k === 'rides_per_day' && r.demand_assumed && <span className="ml-1 text-xs font-semibold text-warn-ink">assumed</span>}
      {(k === 'rides_per_scheduled_trip' || k === 'rides_per_scheduled_hour') && b[k] != null && s[k] != null &&
        <span className="block text-xs text-ink-2">{fmtChange(r.change_percent[k])}</span>}
    </td>
  ))
  cells.splice(3, 0, <td key="minutes" className="n"><BeforeAfter b={b.mean_trip_minutes} s={s.mean_trip_minutes} rb="no duration" rs="no duration" /></td>)
  return (
    <tr>
      <th scope="row" className="text-left font-normal">
        <Link to={`/route/${encodeURIComponent(r.route)}`} className="no-underline" aria-label={`Open route ${r.route}`}>
          <RouteSign route={r.route} groupId={r.group_id ?? groupOf.get(r.route)} size="sm" /></Link>
        {r.note && <span className="mt-0.5 block max-w-[28ch] text-xs text-ink-2">{r.status === 'unchanged' ? 'Not changed: ' : ''}{r.note}</span>}
      </th>
      {cells}
      <td className="n whitespace-nowrap">
        {fmtRankMove(b.rank_rides_per_scheduled_hour, s.rank_rides_per_scheduled_hour)}
        {s.rank_rides_per_scheduled_hour == null && <span className="block max-w-[24ch] text-xs text-ink-2">{s.rank_rides_per_scheduled_hour_reason}</span>}
      </td>
    </tr>
  )
}

function RatioChart({ rows }: { rows: ScenarioRow[] }) {
  const data = rows.filter(r => r.baseline.rides_per_scheduled_hour != null && r.scenario.rides_per_scheduled_hour != null)
    .sort((a, b) => b.baseline.rides_per_scheduled_hour! - a.baseline.rides_per_scheduled_hour!).slice(0, 24)
    .map(r => ({ route: r.route, baseline: r.baseline.rides_per_scheduled_hour, scenario: r.scenario.rides_per_scheduled_hour }))
  const left = rows.length - rows.filter(r => r.baseline.rides_per_scheduled_hour != null && r.scenario.rides_per_scheduled_hour != null).length
  if (!data.length) return <Panel title="Rides per scheduled hour"><Empty message="No route has rides per scheduled hour on both sides to draw." /></Panel>
  return (
    <Panel title="Rides per scheduled hour, baseline and scenario"
           purpose={`${data.length} route${data.length === 1 ? '' : 's'}${rows.length > 24 ? ', the highest 24 at baseline' : ''}${left ? `; ${left} without a value on both sides are left out, not drawn as 0` : ''}.`}
           howToRead="For each route, the solid bar is the baseline and the outlined bar is the scenario. A shorter outlined bar means fewer rides for each scheduled hour of service.">
      <div style={{ height: 260 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 4 }} barGap={2}>
            <CartesianGrid stroke={RULE} vertical={false} />
            <XAxis dataKey="route" tick={{ fontSize: 11, fill: INK_2 }} interval={0} />
            <YAxis tick={{ fontSize: 11, fill: INK_2 }} width={44} tickFormatter={(x: number) => fmt(x)} />
            <Tooltip formatter={(v) => fmt(Number(v), 1)} isAnimationActive={false} />
            <Bar dataKey="baseline" name="Baseline" fill={SLATE_RAMP[3]} maxBarSize={48} isAnimationActive={false} />
            <Bar dataKey="scenario" name="Scenario" fill="#FFFFFF" stroke={INK} strokeWidth={1.5} maxBarSize={48} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-1 flex flex-wrap justify-center gap-x-5 text-xs text-ink-2" aria-label="Chart key">
        <span><span className="mr-1.5 inline-block h-2.5 w-3.5 align-middle" style={{ background: SLATE_RAMP[3] }} />Baseline</span>
        <span><span className="mr-1.5 inline-block h-2.5 w-3.5 border-[1.5px] align-middle" style={{ borderColor: INK, background: '#FFFFFF' }} />Scenario</span>
      </p>
    </Panel>
  )
}

// ------------------------------------------------------------------------------------------- saved scenarios
function SavedList({ tick, openId, setOpenId, groupOf, inReplay, onRevise }: {
  tick: number; openId: string | null; setOpenId: (id: string | null) => void; groupOf: GroupOf; inReplay: boolean
  onRevise: (s: Scenario) => void
}) {
  const list = useApi(o => scenarios.list(o), `scenarios:list:${tick}`)
  return (
    <>
      <SectionHead eyebrow="Saved" title="Saved scenarios"
                   note={inReplay ? 'In replay, only scenarios saved on or before this replay day are shown.' : 'Saved scenarios are never changed; a new version sits beside the old one.'} />
      <AsyncBlock state={list} retry={list.retry} label="Loading saved scenarios" isEmpty={l => l.scenarios.length === 0}
                  emptyMessage={inReplay ? 'No scenario has been saved in a replay up to this day.' : 'No scenario has been saved yet.'}>
        {l => (
          <ul className="divide-y divide-rule border border-rule bg-panel">
            {l.scenarios.map(s => (
              <li key={s.scenario_id} className="px-4 py-2.5">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <button type="button" className="text-left font-semibold underline-offset-2 hover:underline" aria-expanded={openId === s.scenario_id}
                          onClick={() => setOpenId(openId === s.scenario_id ? null : s.scenario_id!)}>{s.name}</button>
                  <span className="text-xs text-ink-2">version {s.version}{s.origin === 'example' ? ' · saved example' : ''} ·{' '}
                    {s.mode === 'historical_replay' ? `saved on replay day ${fmtDate(s.virtual_date ?? addDays(s.cutoff, 1))}` : `saved ${s.saved_at ? fmtTimestamp(s.saved_at) : ''}`}</span>
                  <button type="button" className="btn-secondary ml-auto" onClick={() => onRevise(s)}>Make a new version</button>
                </div>
                <p className="text-sm text-ink-2">{s.assumptions.find(a => a.kind === 'baseline')?.text}</p>
                {openId === s.scenario_id && <SavedView id={s.scenario_id!} groupOf={groupOf} />}
              </li>
            ))}
          </ul>
        )}
      </AsyncBlock>
    </>
  )
}

function SavedView({ id, groupOf }: { id: string; groupOf: GroupOf }) {
  const got = useApi(o => scenarios.get(id, o), `scenario:get:${id}`)
  const [check, setCheck] = useState<string | null>(null)
  const scope = useRequestScope()
  const recheck = async () => {
    setCheck('Recalculating…')
    try {
      const r = await scenarios.recompute(id, { session: scope.session })
      setCheck(r.check.identical ? `Recalculated from the stored inputs: identical result (sha256 ${r.check.recomputed_sha256.slice(0, 12)}…).`
        : `Recalculated: the result differs from the stored one (stored ${r.check.stored_sha256.slice(0, 12)}…, now ${r.check.recomputed_sha256.slice(0, 12)}…).`)
    } catch (e) { setCheck((e as Error).message) }
  }
  return (
    <div className="mt-3">
      <AsyncBlock state={got} retry={got.retry} label="Loading the saved scenario">
        {g => <>
          <div className="mb-3 flex flex-wrap items-center gap-2 text-sm">
            <span>Stored result{g.lineage && g.lineage.length > 1 ? ` · versions: ${g.lineage.map(v => v.version).join(', ')}` : ''}.</span>
            <button type="button" className="btn-secondary" onClick={() => void recheck()}>Recalculate and compare</button>
            {check && <span role="status">{check}</span>}
          </div>
          <ResultView resp={g} groupOf={groupOf} saved={g.scenario} />
        </>}
      </AsyncBlock>
    </div>
  )
}
