// Alike (spec 9.16.2 "Route groups"): a scatter of two profile measures coloured by group, each group's spread on
// every measure, weekend service, members and the ungrouped routes with reasons, the method and all caveats.
// Every number and sentence is computed from /api/route-groups at render time (CLAUDE.md, UI design principles).
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api/client'
import type { GroupsResponse, RouteGroup } from '../api/types'
import { useApi } from '../api/useApi'
import { AsyncBlock } from '../components/AsyncBlock'
import { Panel, SectionHead } from '../components/Panel'
import { GroupLegend } from '../components/RouteMap'
import { RouteSign } from '../components/RouteSign'
import { Choice, Sentence } from '../components/Sentence'
import { Empty } from '../components/States'
import { groupColour, INK_2, RULE } from '../design/tokens'
import { fmtRange } from '../lib/dates'
import { fmt } from '../lib/format'
import { insideOtherGroup, scatterPoints, type ScatterPoint } from '../lib/scatter'
import { sortByRoute, sortRoutes } from '../lib/routeSort'

type Ok = Extract<GroupsResponse, { available: true }>
const DEFAULT_X = 'mean_weekday_rides', DEFAULT_Y = 'weekday_rides_per_scheduled_hour'

/** Digits that suit a measure's size: ratios and variability need decimals, rides do not. */
const digitsFor = (max: number) => (max < 2 ? 2 : max < 100 ? 1 : 0)

export function AlikePage() {
  const groups = useApi(o => api.groups(o), 'groups')
  return (
    <div>
      <div className="eyebrow">Alike</div>
      <h1 className="text-xl font-semibold tracking-tight">Which routes are alike?</h1>
      <div className="mt-4">
        <AsyncBlock state={groups} retry={groups.retry} label="Loading route groups">
          {g => g.available ? <AlikeBody g={g} /> : <Empty message={`Route groups are unavailable – ${g.reason}.`} />}
        </AsyncBlock>
      </div>
    </div>
  )
}

function AlikeBody({ g }: { g: Ok }) {
  const features = g.groups[0]?.features ?? []
  const labelOf = Object.fromEntries(features.map(f => [f.feature, f.label]))
  const unitOf = Object.fromEntries(features.map(f => [f.feature, f.unit]))
  const [x, setX] = useState(labelOf[DEFAULT_X] ? DEFAULT_X : features[0]?.feature ?? '')
  const [y, setY] = useState(labelOf[DEFAULT_Y] ? DEFAULT_Y : features[1]?.feature ?? '')
  const { plotted, leftOff } = scatterPoints(g.route_values, x, y)
  const overlap = insideOtherGroup(plotted)
  const options = features.map(f => ({ value: f.feature, text: f.label.toLowerCase() }))
  const ungroupedPlotted = plotted.filter(p => p.groupId == null).length

  return (
    <div>
      <Sentence>
        {fmt(g.groups.reduce((s, x) => s + x.size, 0))} routes in {g.groups.length} groups, fitted on{' '}
        {fmtRange(g.profile_period.start, g.profile_period.end)}. Plotting{' '}
        <Choice label="Measure across" value={x} onChange={setX} options={options} /> across and{' '}
        <Choice label="Measure up" value={y} onChange={setY} options={options} /> up.
      </Sentence>

      <div className="space-y-2 border-l-[3px] border-brand pl-4 text-md leading-8">
        <p>
          {g.groups.map((gr, i) => <span key={gr.group_id}>{i > 0 && (i === g.groups.length - 1 ? ' and ' : ', ')}
            <span className="font-semibold">Group {gr.group_id}</span>, {gr.name.charAt(0).toLowerCase() + gr.name.slice(1)} ({fmt(gr.size)} routes)</span>)}.
        </p>
        <p>
          On these two measures, <span className="font-semibold num">{fmt(overlap.inside)}</span> of {fmt(overlap.grouped)} grouped routes
          sit inside another group's range
          {overlap.inside > 0 ? ': a group describes its typical member, not a hard boundary.' : ': here the groups do not overlap.'}
          {leftOff.length > 0 && <> {fmt(leftOff.length)} {leftOff.length === 1 ? 'route is' : 'routes are'} not plotted because a value is missing (listed under the chart).</>}
        </p>
      </div>

      <div className="mt-6 grid items-start gap-4 xl:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
        <Panel title={`${labelOf[y]} against ${labelOf[x]?.toLowerCase()}`} purpose={`${fmt(plotted.length)} routes plotted, development profile period.`}
               howToRead={`Across: ${unitOf[x]}; up: ${unitOf[y]}. Each dot is one route, coloured by its group (grey ring = ungrouped). A dot at 0 on a weekend measure is a route with no scheduled weekend service, not a missing value. Click a dot to open the route.`}>
          <GroupScatter points={plotted} x={{ label: labelOf[x] ?? x, unit: unitOf[x] ?? '' }} y={{ label: labelOf[y] ?? y, unit: unitOf[y] ?? '' }}
                        names={Object.fromEntries(g.groups.map(gr => [gr.group_id, gr.name]))} />
          <div className="mt-2"><GroupLegend groups={g.groups} showUngrouped={ungroupedPlotted > 0} /></div>
          {leftOff.length > 0 && (
            <ul className="mt-3 space-y-0.5 border-t border-rule pt-2 text-xs text-ink-2">
              {leftOff.map(l => <li key={l.route}>{l.note}</li>)}
            </ul>
          )}
        </Panel>
        <Panel title="Weekend service by group" purpose="Routes with scheduled Saturday and Sunday/holiday service in the profile period.">
          <WeekendTable groups={g.groups} />
        </Panel>
      </div>

      <SectionHead title="How far each group spreads" note="Each bar runs from a group's lowest to highest route; the tick is its median. Overlapping bars mean the groups share values on that measure." />
      <Panel title="Group spread on every measure" purpose={`Measures used to form the groups: ${g.method.selected_feature_labels.map(s => s.toLowerCase()).join(', ')}.`}
             howToRead="Read across: where two bars overlap, a route could look like either group on that measure alone. Bars use each measure's own scale.">
        <SpreadTable groups={g.groups} />
      </Panel>

      <SectionHead title="Members" />
      <div className="grid gap-4 xl:grid-cols-2">
        {g.groups.map(gr => (
          <Panel key={gr.group_id} title={`Group ${gr.group_id} · ${gr.name}`} purpose={`${fmt(gr.size)} routes`}>
            <ul className="flex flex-wrap gap-1.5">
              {sortRoutes(gr.routes).map(r => <li key={r}><Link to={`/route/${encodeURIComponent(r)}`} className="no-underline" aria-label={`Open route ${r}`}>
                <RouteSign route={r} groupId={gr.group_id} size="sm" /></Link></li>)}
            </ul>
          </Panel>
        ))}
      </div>
      {g.ungrouped.length > 0 && (
        <Panel className="mt-4" title={`Ungrouped: ${fmt(g.ungrouped.length)} routes`} purpose="Each with the reason it was not grouped.">
          <ul className="space-y-1 text-sm">
            {sortByRoute(g.ungrouped, u => u.route).map(u => <li key={u.route} className="flex items-center gap-2"><Link to={`/route/${encodeURIComponent(u.route)}`} className="no-underline" aria-label={`Open route ${u.route}`}>
              <RouteSign route={u.route} groupId={null} size="sm" /></Link> <span className="text-ink-2">{u.reason}</span></li>)}
          </ul>
        </Panel>
      )}

      <SectionHead title="How the groups were made, and their limits" />
      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Method">
          <dl className="space-y-1.5 text-sm">
            <div><dt className="inline text-ink-2">Method: </dt><dd className="inline">{g.method.algorithm}, {g.method.k} groups</dd></div>
            <div><dt className="inline text-ink-2">Measures used: </dt><dd className="inline">{g.method.selected_feature_labels.join(', ')}</dd></div>
            <div><dt className="inline text-ink-2">Choosing the number of groups: </dt><dd className="inline">{g.method.k_rule}</dd></div>
            <div><dt className="inline text-ink-2">Profile period: </dt><dd className="inline">{fmtRange(g.profile_period.start, g.profile_period.end)}: {g.profile_period.note}</dd></div>
            <div><dt className="inline text-ink-2">Values shown: </dt><dd className="inline">{g.route_values_note}</dd></div>
          </dl>
        </Panel>
        <Panel title={`Caveats (${g.caveats.length})`}>
          <ol className="list-decimal space-y-1.5 pl-5 text-sm">{g.caveats.map(c => <li key={c}>{c}</li>)}</ol>
        </Panel>
      </div>
    </div>
  )
}

function ScatterTip({ active, payload, x, y, names }: {
  active?: boolean; payload?: { payload: ScatterPoint }[]; x: { label: string; unit: string }; y: { label: string; unit: string }
  names: Record<number, string>
}) {
  const p = payload?.[0]?.payload
  if (!active || !p) return null
  const line = (axis: { label: string; unit: string }, v: number, status: ScatterPoint['xStatus']) =>
    <div>{axis.label}: <span className="num">{fmt(v, digitsFor(Math.abs(v) || 1))}</span>{' '}
      <span className="text-xs text-ink-2">{status === 'no_scheduled_service' ? '(no scheduled service, a real 0)' : axis.unit}</span></div>
  return (
    <div className="border border-rule-strong bg-panel px-3 py-2 text-sm">
      <div className="font-semibold">Route {p.route} <span className="font-normal text-ink-2">· {p.groupId == null ? 'ungrouped' : `Group ${p.groupId}, ${names[p.groupId]}`}</span></div>
      {line(x, p.x, p.xStatus)}{line(y, p.y, p.yStatus)}
    </div>
  )
}

function GroupScatter({ points, x, y, names }: {
  points: ScatterPoint[]; x: { label: string; unit: string }; y: { label: string; unit: string }; names: Record<number, string>
}) {
  const navigate = useNavigate()
  const ids = [...new Set(points.map(p => p.groupId))]
  const xd = digitsFor(Math.max(...points.map(p => Math.abs(p.x)), 0)), yd = digitsFor(Math.max(...points.map(p => Math.abs(p.y)), 0))
  return (
    <div style={{ height: 380 }}>
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 8, right: 16, bottom: 28, left: 8 }}>
          <CartesianGrid stroke={RULE} />
          <XAxis type="number" dataKey="x" name={x.label} tick={{ fontSize: 11, fill: INK_2 }} tickFormatter={(v: number) => fmt(v, xd)}
                 label={{ value: x.label, position: 'insideBottom', offset: -16, fontSize: 11, fill: INK_2 }} />
          <YAxis type="number" dataKey="y" name={y.label} tick={{ fontSize: 11, fill: INK_2 }} width={64} tickFormatter={(v: number) => fmt(v, yd)}
                 label={{ value: y.label, angle: -90, position: 'insideLeft', fontSize: 11, fill: INK_2, style: { textAnchor: 'middle' } }} />
          <Tooltip content={<ScatterTip x={x} y={y} names={names} />} isAnimationActive={false} />
          {ids.map(id => (
            <Scatter key={String(id)} data={points.filter(p => p.groupId === id)} isAnimationActive={false}
                     fill={id == null ? '#FFFFFF' : groupColour(id)} stroke={id == null ? groupColour(null) : '#FFFFFF'} strokeWidth={1}
                     cursor="pointer" onClick={(d: { payload?: ScatterPoint }) => { if (d?.payload) navigate(`/route/${encodeURIComponent(d.payload.route)}`) }} />
          ))}
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  )
}

function WeekendTable({ groups }: { groups: RouteGroup[] }) {
  const ws = (g: RouteGroup, day: 'saturday' | 'sunday_holiday', s: string) => g.weekend_service[`${day}_${s}`] ?? null
  return (
    <div className="-mx-4 overflow-x-auto">
      <table className="data-table">
        <thead><tr><th>Group</th><th className="n">Saturday service</th><th className="n">Sunday/holiday service</th></tr></thead>
        <tbody>
          {groups.map(g => (
            <tr key={g.group_id}>
              <td className="whitespace-nowrap"><span className="mr-1.5 inline-block h-2.5 w-2.5" style={{ background: groupColour(g.group_id) }} />Group {g.group_id}</td>
              {(['saturday', 'sunday_holiday'] as const).map(d => (
                <td key={d} className="n text-sm">
                  <span className="num font-semibold">{fmt(ws(g, d, 'available'))}</span> of {fmt(g.size)}
                  {(ws(g, d, 'no_scheduled_service') ?? 0) > 0 && <span className="block text-xs text-ink-2">{fmt(ws(g, d, 'no_scheduled_service'))} with none scheduled</span>}
                  {(ws(g, d, 'insufficient_observations') ?? 0) > 0 && <span className="block text-xs text-ink-2">{fmt(ws(g, d, 'insufficient_observations'))} with too few days</span>}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function SpreadTable({ groups }: { groups: RouteGroup[] }) {
  const features = groups[0]?.features ?? []
  return (
    <div className="-mx-4 overflow-x-auto">
      <table className="data-table">
        <thead><tr><th>Measure</th><th>Spread by group</th>{groups.map(g => <th key={g.group_id} className="n">Group {g.group_id} median</th>)}</tr></thead>
        <tbody>
          {features.map(f => {
            const all = groups.map(g => g.features.find(x => x.feature === f.feature)!)
            const lo = Math.min(...all.map(a => a.min)), hi = Math.max(...all.map(a => a.max))
            const pos = (v: number) => (hi > lo ? ((v - lo) / (hi - lo)) * 100 : 50)
            const d = digitsFor(hi)
            return (
              <tr key={f.feature}>
                <td className="text-sm">{f.label}<span className="block text-xs text-ink-2">{f.unit}{f.selected_for_clustering ? ' · used to form groups' : ''}</span></td>
                <td className="min-w-[16rem]">
                  <svg viewBox="0 0 100 24" preserveAspectRatio="none" className="h-7 w-full" role="img"
                       aria-label={all.map((a, i) => `Group ${groups[i]!.group_id}: ${fmt(a.min, d)} to ${fmt(a.max, d)}, median ${fmt(a.median, d)}`).join('; ')}>
                    {all.map((a, i) => {
                      const yy = 6 + i * 12
                      return <g key={i}>
                        <line x1={pos(a.min)} x2={pos(a.max)} y1={yy} y2={yy} stroke={groupColour(groups[i]!.group_id)} strokeWidth={4} vectorEffect="non-scaling-stroke" />
                        <line x1={pos(a.median)} x2={pos(a.median)} y1={yy - 5} y2={yy + 5} stroke="#1C232B" strokeWidth={2} vectorEffect="non-scaling-stroke" />
                      </g>
                    })}
                  </svg>
                  <div className="flex justify-between text-[11px] text-ink-2"><span className="num">{fmt(lo, d)}</span><span className="num">{fmt(hi, d)}</span></div>
                </td>
                {all.map((a, i) => <td key={i} className="n num">{fmt(a.median, d)}</td>)}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
