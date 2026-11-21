// Style reference: RouteRanker's structure and building blocks on one page, for approval before any screen is
// built. EVERY number, line and label marked "specimen" here is made up to show the styling, not CTA data.
import { useState } from 'react'
import { MapContainer, Polyline, TileLayer, Tooltip as LTooltip } from 'react-leaflet'
import { CartesianGrid, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import 'leaflet/dist/leaflet.css'
import { Drawer } from '../components/Drawer'
import { EndsPreview } from '../components/EndsPreview'
import { MapCaption } from '../components/MapCaption'
import { ApiLabel, Panel, SectionHead } from '../components/Panel'
import { Num, ProvenanceBody, type ProvenanceInfo } from '../components/Provenance'
import { QuestionIndex } from '../components/QuestionIndex'
import { RankTrio } from '../components/RankTrio'
import { RhythmGrid } from '../components/RhythmGrid'
import { RouteSign } from '../components/RouteSign'
import { Choice, Sentence } from '../components/Sentence'
import { Empty, ErrorState, Loading } from '../components/States'
import { StopShareStrip } from '../components/StopShareStrip'
import { Value } from '../components/Value'
import { GROUP_COLOURS, INK_2, RULE, UNGROUPED, groupColour, groupDash } from '../design/tokens'
import { fmt } from '../lib/format'
import { stability } from '../lib/stability'

const DV = 'cta_ref__r20261113__gtfs8__to20260731'
const SPEC = '(specimen)'

// ---- specimen series -------------------------------------------------------------------------------------------
type Pt = { date: string; rides: number | null; reason: string | null }
const iso = (y: number, m: number, d: number) => new Date(Date.UTC(y, m, d)).toISOString().slice(0, 10)
function series(start: [number, number, number], n: number, gaps: Record<string, string>, zeros: string[] = []): Pt[] {
  return Array.from({ length: n }, (_, i) => {
    const date = iso(start[0], start[1], start[2] + i)
    if (gaps[date]) return { date, rides: null, reason: gaps[date]! }
    if (zeros.includes(date)) return { date, rides: 0, reason: null }
    const dow = new Date(`${date}T00:00:00Z`).getUTCDay()
    const base = dow === 0 ? 4200 : dow === 6 ? 5600 : 8400
    return { date, rides: base + ((i * 37) % 9) * 60 - (i > 40 && i < 50 ? 900 : 0), reason: null }
  })
}
const TREND = series([2025, 10, 9], 56, { '2025-11-27': 'service scheduled, no ridership record (specimen)' })
const RHYTHM = series([2025, 10, 24], 112, {
  '2025-11-27': 'service scheduled, no ridership record (specimen)',
  '2025-12-25': 'service scheduled, no ridership record (specimen)',
}, ['2026-01-25'])

function ChartTooltip({ active, payload }: { active?: boolean; payload?: { payload: Pt }[] }) {
  const p = payload?.[0]?.payload
  if (!active || !p) return null
  return (
    <div className="border border-rule-strong bg-panel px-3 py-2 text-sm">
      <div className="font-semibold">{p.date}</div>
      <div>Recorded rides: <Value value={p.rides} unit="rides/day" reason={p.reason} /></div>
    </div>
  )
}

// ---- specimen provenance -----------------------------------------------------------------------------------------
const TIMETABLES = [
  { id: '(specimen) archive A', start: '2025-11-23', end: '2026-01-07' },
  { id: '(specimen) archive B', start: '2026-01-08', end: '2026-03-25' },
  { id: '(specimen) archive C', start: '2026-03-26', end: '2026-07-31' },
]
const period = { name: 'Full matched window', start: '2025-11-23', end: '2026-07-31' }
const perHour: ProvenanceInfo = {
  title: 'Route 49 · rides per scheduled hour', value: 58.78, digits: 2, unit: 'rides per scheduled hour',
  formula: 'recorded rides ÷ scheduled trip-hours, summed over the observed days',
  numerator: { label: 'recorded rides', value: 1_234_567 }, denominator: { label: 'scheduled trip-hours', value: 21_003.9, digits: 1 },
  days: { observed: 171, gateLabel: 'reference gate: 20' }, period, daytype: 'Weekday (W)', timetables: TIMETABLES,
  dataVersion: DV, request: '/api/rankings?metric=rides_per_scheduled_hour&period=full_matched_window&daytype=W',
  specReference: 'spec 9.12',
}
const perTrip: ProvenanceInfo = {
  ...perHour, title: 'Route 49 · rides per scheduled trip', value: 41.06, unit: 'rides per scheduled trip',
  formula: 'recorded rides ÷ scheduled trips, summed over the observed days',
  denominator: { label: 'scheduled trips', value: 30_067 },
  request: '/api/rankings?metric=rides_per_scheduled_trip&period=full_matched_window&daytype=W',
}
const demand: ProvenanceInfo = {
  ...perHour, title: 'Route 49 · observed daily demand', value: 7_219.69, digits: 0, unit: 'rides/day',
  formula: 'recorded rides ÷ observed days', denominator: { label: 'observed days', value: 171 },
  request: '/api/rankings?metric=observed_daily_demand&period=full_matched_window&daytype=W',
}
const missingSat: ProvenanceInfo = {
  title: 'Route 10 · rides per scheduled hour, Saturday', value: null, unit: 'rides per scheduled hour',
  formula: 'recorded rides ÷ scheduled trip-hours, summed over the observed days',
  missing: { reason: 'no matched days of this day type in the period', side: 'no scheduled Saturday service' },
  period, daytype: 'Saturday (A)', dataVersion: DV,
  request: '/api/rankings?metric=rides_per_scheduled_hour&period=full_matched_window&daytype=A',
}

const TABLE = [
  { rank: 1, route: '79', g: 0, value: 61.42, days: 172, dev: 2 },
  { rank: 2, route: '9', g: 0, value: 58.07, days: 172, dev: 1 },
  { rank: 2, route: '49', g: 0, value: 58.07, days: 171, dev: 2 },
  { rank: 4, route: 'X49', g: 0, value: 0, days: 120, dev: null as number | null },
  { rank: null as number | null, route: '10', g: null as number | null, value: null as number | null, days: 14, dev: null as number | null },
]
const ENDS_SPECIMEN = [
  { route: '79', rank: 1, value: 61.4, groupId: 0 }, { route: '9', rank: 2, value: 58.1, groupId: 0 },
  { route: '49', rank: 3, value: 57.9, groupId: 0 }, { route: '22', rank: 4, value: 50.2, groupId: 0 },
  { route: '55A', rank: 121, value: 9.8, groupId: 1 }, { route: '125', rank: 122, value: 8.1, groupId: 1 },
  { route: 'J14', rank: 123, value: 6.4, groupId: 0 },
  { route: '10', rank: null, value: null, groupId: null }, { route: '1001', rank: null, value: null, groupId: null },
  { route: '19', rank: null, value: null, groupId: null },
]
// real Stage 5 memberships (group_names.json): 3, J14 in group 0; 55A, 125 in group 1; 1001 ungrouped
const SIGN_ROW: [string, number | null][] = [['3', 0], ['J14', 0], ['55A', 1], ['125', 1], ['1001', null]]
const LINES: { route: string; g: number | null; pts: [number, number][] }[] = [
  { route: 'A', g: 0, pts: [[41.85, -87.6313], [41.90, -87.6313], [41.93, -87.6365], [41.98, -87.668]] },
  { route: 'B', g: 1, pts: [[41.80, -87.6665], [41.97, -87.6665]] },
  { route: 'C', g: null, pts: [[41.80, -87.6866], [41.99, -87.6866]] },
]

function Swatch({ name, hex, note }: { name: string; hex: string; note: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="h-8 w-8 shrink-0 border border-rule" style={{ background: hex }} />
      <div className="min-w-0 break-words"><div className="text-sm font-semibold">{name}</div><div className="num text-xs text-ink-2">{hex} · {note}</div></div>
    </div>
  )
}

export function StylePage() {
  const [daytype, setDaytype] = useState<'W' | 'A' | 'U'>('W')
  const [per, setPer] = useState<'full' | 'dev'>('full')
  const [metric, setMetric] = useState<'hour' | 'trip' | 'demand'>('hour')
  const [gate, setGate] = useState<'20' | '8'>('20')

  return (
    <div>
      <div className="eyebrow">Development</div>
      <h1 className="text-xl font-semibold tracking-tight">Style reference</h1>
      <p className="mt-1 max-w-[80ch] text-base text-ink-2">
        RouteRanker's structure and building blocks, for approval before any screen is built. Values marked
        "specimen" are made up to show the styling; they are not CTA data.
      </p>

      {/* 1 ---------------------------------------------------------------------------------------------------- */}
      <SectionHead eyebrow="1 · Colour" title="Slate for the interface, bright colour for data" note="Bright colour is reserved for data: route groups and amber warnings. Every text pair passes WCAG AA." />
      <div className="flex flex-wrap items-center gap-4 border border-rule bg-panel p-4">
        <span className="flex h-12 w-24 shrink-0 items-center justify-center bg-brand text-sm font-semibold text-white">Aa</span>
        <div className="min-w-0">
          <div className="text-sm font-semibold">Brand slate #2B3440 (chosen)</div>
          <div className="num text-xs text-ink-2">Top bar, primary buttons, selected states · white text 12.6:1 · menu text #C9D1DA 8.2:1</div>
        </div>
      </div>
      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div className="grid grid-cols-2 gap-3 border border-rule bg-panel p-4 lg:grid-cols-3">
          <Swatch name="Page" hex="#F4F2EE" note="warm off-white" />
          <Swatch name="Panel" hex="#FFFFFF" note="data sits on white" />
          <Swatch name="Text" hex="#1C232B" note="12.6–15.9:1" />
          <Swatch name="Secondary text" hex="#4E5762" note="5.8–7.3:1" />
          <Swatch name="Hover" hex="#EDF0F3" note="light slate" />
          <Swatch name="Selected row" hex="#E1E6EC" note="light slate" />
        </div>
        <div className="space-y-3 border border-rule bg-panel p-4">
          <Swatch name="Group 0" hex={GROUP_COLOURS['0']!} note="solid line" />
          <Swatch name="Group 1" hex={GROUP_COLOURS['1']!} note="solid line" />
          <Swatch name="Ungrouped" hex={UNGROUPED} note="dashed, always labelled" />
          <Swatch name="Warning" hex="#7A5300" note="on #FFF3D1, 6.2:1" />
        </div>
      </div>

      {/* 2 ---------------------------------------------------------------------------------------------------- */}
      <SectionHead eyebrow="2 · Start page" title="The question index" note="The Start tab opens with planner questions, each with a live one-line answer. The network trend and dated map follow below them." />
      <div className="bg-panel px-5 pb-1 pt-2">
        <QuestionIndex rows={[
          { question: 'Which routes deserve a closer look?', to: '/closer-look',
            preview: <><EndsPreview lead="Weekdays, rides per scheduled hour" rows={ENDS_SPECIMEN} /> <span>{SPEC}</span></> },
          { question: 'How is one route doing?', to: '/route',
            preview: <>Pick a route to see its ranks, weekly rhythm, group and shared stops.</> },
          { question: 'Which routes are alike?', to: '/alike',
            preview: <>2 groups of 67 and 56 routes, 5 ungrouped · fitted on 23 Nov 2025 – 31 Mar 2026 {SPEC}</> },
          { question: 'Which routes share stops?', to: '/shared-stops',
            preview: <>Most shared: <RouteSign route="49" groupId={0} size="sm" /> and <RouteSign route="X49" groupId={0} size="sm" />, every stop of the smaller route shared {SPEC}</> },
          { question: 'Can I trust these numbers?', to: '/data', quiet: true,
            preview: <>99.915 % of scheduled route-days have a ride record · 9 of 9 import checks hold {SPEC}</> },
        ]} />
      </div>

      {/* 3 ---------------------------------------------------------------------------------------------------- */}
      <SectionHead eyebrow="3 · Every page" title="Sentence controls, an answer first, and numbers you can question" note="The sentence is the filter and the summary. Every number has a dotted underline: click it for how it was made." />
      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="bg-panel px-5 py-4">
          <Sentence>
            Showing <Choice label="Day type" value={daytype} onChange={setDaytype}
                            options={[{ value: 'W', text: 'weekdays' }, { value: 'A', text: 'Saturdays' }, { value: 'U', text: 'Sundays and holidays' }]} />{' '}
            in <Choice label="Period" value={per} onChange={setPer}
                       options={[{ value: 'full', text: 'the full matched window, 23 Nov 2025 – 31 Jul 2026' }, { value: 'dev', text: 'the development period, 23 Nov 2025 – 31 Mar 2026' }]} />,
            ranked by <Choice label="Metric" value={metric} onChange={setMetric}
                              options={[{ value: 'hour', text: 'rides per scheduled hour' }, { value: 'trip', text: 'rides per scheduled trip' }, { value: 'demand', text: 'observed daily demand' }]} />,
            counting routes with at least <Choice label="Minimum days" value={gate} onChange={setGate} warn={gate !== '20'}
                                                  options={[{ value: '20', text: '20 days (reference)' }, { value: '8', text: '8 days' }]} />.
            {gate !== '20' && <> <ApiLabel warn text="non-reference gate: 8 (reference: 20)" /></>}
          </Sentence>
          <p className="border-l-[3px] border-brand pl-4 text-lg leading-8">
            Route <RouteSign route="49" groupId={0} /> ranks <strong>3rd of 125</strong> by rides per scheduled hour on weekdays:{' '}
            <Num p={perHour} className="font-semibold" /> from <Num p={{ ...perHour, title: 'Route 49 · observed days', value: 171, digits: 0, unit: 'observed days', formula: 'matched days (rides and scheduled service on the same date) of this day type in the period' }} />.
          </p>
          <p className="mt-4 text-sm text-ink-2">
            A missing number in the same sentence stays quiet: Route <RouteSign route="10" size="sm" /> on Saturdays has{' '}
            <Num p={missingSat} />. {SPEC}
          </p>
        </div>
        <Drawer inline eyebrow="How was this number made? · open on click" title={perHour.title}>
          <ProvenanceBody p={perHour} />
        </Drawer>
      </div>

      {/* 4 ---------------------------------------------------------------------------------------------------- */}
      <SectionHead eyebrow="4 · One route" title="The route profile" note="Three ranks with their stability, the weekly rhythm, then group and shared stops." />
      <div className="bg-panel px-5 py-4">
        <div className="mb-4 flex items-center gap-4">
          <RouteSign route="49" groupId={0} groupName="Group 0" size="lg" />
          <div>
            <h3 className="text-xl font-semibold tracking-tight">Western</h3>
            <p className="text-sm text-ink-2">Group 0 · grouped on the development period · {SPEC}</p>
          </div>
        </div>
        <RankTrio cells={[
          { metricLabel: 'Rides per scheduled hour', value: perHour, rank: 3, of: 125, dev: { rank: 3 } },
          { metricLabel: 'Rides per scheduled trip', value: perTrip, rank: 7, of: 125, dev: { rank: 4 } },
          { metricLabel: 'Observed daily demand', value: demand, rank: 12, of: 125, dev: { rank: null, reason: 'fewer than 20 observed days (18)' } },
        ]} />
        <p className="mt-2 text-xs text-ink-2">
          <span className="font-semibold text-ink">How to read this: </span>each rank is among all routes for the same day type and
          period. Stability repeats the ranking on the development period; the full window contains it, so the two are not independent. {SPEC}
        </p>
        <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_280px]">
          <div>
            <h4 className="mb-2 text-base font-semibold">Weekly rhythm</h4>
            <RhythmGrid days={RHYTHM} unit="rides/day" />
            <p className="mt-2 text-xs text-ink-2"><span className="font-semibold text-ink">How to read this: </span>
              each column is a week, each row a weekday; darker means more recorded rides. Weekends and holidays show as
              lighter rows; dashed cells are days with no record. {SPEC}</p>
          </div>
          <div className="min-w-0 lg:border-l lg:border-rule lg:pl-6">
            <h4 className="mb-2 text-base font-semibold">Missing values stay quiet</h4>
            <div className="space-y-3">
              <div><div className="text-xs text-ink-2">A real figure</div><div className="text-xl font-semibold"><Value value={7219.69} unit="rides/day" /></div></div>
              <div><div className="text-xs text-ink-2">The same slot, missing</div><div className="text-xl font-semibold"><Value value={null} reason="no matched days of this day type" /></div></div>
              <div><div className="text-xs text-ink-2">A recorded zero is a value</div><div className="text-xl font-semibold"><Value value={0} unit="rides/day" /></div></div>
            </div>
          </div>
        </div>
      </div>

      {/* 5 ---------------------------------------------------------------------------------------------------- */}
      <SectionHead eyebrow="5 · Shared stops" title="Stop-share strip" note="How many stops two routes have in common. The database stores stop sets, not their order along the street." />
      <div className="bg-panel px-5 py-4">
        <StopShareStrip a={{ route: '49', groupId: 0, stops: 112 }} b={{ route: 'X49', groupId: 0, stops: 46 }}
                        shared={46} jaccard={46 / 112} smallerOverlap={1}
                        interpretation="corridor review only: shared stop IDs are not merge/split evidence (no direction, walking access, transfers or journeys)" />
        <p className="mt-2 text-xs text-ink-2">Stop counts are specimens; the caveat text is shown exactly as the API sends it.</p>
      </div>

      {/* 6 ---------------------------------------------------------------------------------------------------- */}
      <SectionHead eyebrow="6 · Tables" title="A ranking table with stability" note="Right-aligned tabular numbers. Ties keep the same rank. Unranked rows stay listed with their reason." />
      <div className="overflow-x-auto bg-panel">
        <table className="data-table">
          <thead><tr>
            <th className="n w-16">Rank</th><th>Route</th><th className="n">Rides per scheduled hour</th>
            <th className="n">Observed days</th><th>Stability (development → full window)</th>
          </tr></thead>
          <tbody>
            {TABLE.map(r => (
              <tr key={r.route} aria-selected={r.route === '49'}>
                <td className="n num">{r.rank ?? <span className="text-xs text-ink-2">–</span>}</td>
                <td><RouteSign route={r.route} groupId={r.g} size="sm" /></td>
                <td className="n"><Value value={r.value} digits={2} reason="unranked: fewer than 20 observed days (14)" /></td>
                <td className="n num">{fmt(r.days)}</td>
                <td className="text-xs">{r.rank == null ? <span className="text-ink-2">unranked – fewer than 20 observed days (14)</span>
                  : stability({ rank: r.dev, reason: 'fewer than 20 observed days (18)' }, { rank: r.rank }).text}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="border-t border-rule px-4 py-2 text-xs text-ink-2">The selected row (49) uses the light slate tint. X49's 0 is a recorded value, shown as 0. {SPEC}</p>
      </div>

      {/* 7 ---------------------------------------------------------------------------------------------------- */}
      <SectionHead eyebrow="7 · Charts and maps" title="Network over time, and the dated map" />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Panel title="Recorded rides, whole network" purpose="Daily total over routes that reported that day (specimen)."
               howToRead="Each point is one service day. A break is a day with no record; hover it for the reason. Shaded days come before dated schedules exist.">
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={TREND} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
                <CartesianGrid stroke={RULE} vertical={false} />
                <ReferenceArea x1={TREND[0]!.date} x2="2025-11-22" fill="#EDF0F3" fillOpacity={1}
                               label={{ value: 'Recorded rides only, no dated schedule', position: 'insideTopLeft', fontSize: 11, fill: INK_2 }} />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: INK_2 }} tickLine={false} axisLine={{ stroke: RULE }} minTickGap={40} tickFormatter={d => d.slice(5)} />
                <YAxis tick={{ fontSize: 11, fill: INK_2 }} tickLine={false} axisLine={false} width={56} tickFormatter={v => fmt(v)}
                       label={{ value: 'rides/day', angle: -90, position: 'insideLeft', fontSize: 11, fill: INK_2 }} />
                <Tooltip content={<ChartTooltip />} cursor={{ stroke: '#1C232B', strokeWidth: 1 }} />
                <Line dataKey="rides" stroke="#2B3440" strokeWidth={2} dot={false} connectNulls={false} isAnimationActive={false}
                      activeDot={{ r: 4, stroke: '#FFFFFF', strokeWidth: 2 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Panel>
        <Panel title="Dated map" purpose="OpenStreetMap tiles, greyed so the lines read first. No API key.">
          <div className="-mx-4 -my-3 h-64">
            <MapContainer center={[41.895, -87.66]} zoom={12} scrollWheelZoom={false} className="h-full w-full">
              <TileLayer url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" maxZoom={19}
                         attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' />
              {LINES.map(l => (
                <Polyline key={l.route} positions={l.pts} pathOptions={{ color: groupColour(l.g), weight: 3, dashArray: groupDash(l.g) }}>
                  <LTooltip sticky>Specimen line {l.route}{l.g == null ? ' · ungrouped' : ` · Group ${l.g}`}</LTooltip>
                </Polyline>
              ))}
            </MapContainer>
          </div>
          <div className="-mx-4 -mb-3 mt-3">
            <MapCaption geometryVersion={SPEC} appliedStart="2026-07-11" appliedEnd="2026-07-31" pathLabel="Most common path per direction"
                        displayNote="simplified for display: every stored point within 10 m of the drawn line" />
          </div>
        </Panel>
      </div>
      <p className="mt-2 text-xs text-ink-2">The network line is slate because it is not a group; a single route's line takes its group colour.</p>

      {/* 8 ---------------------------------------------------------------------------------------------------- */}
      <SectionHead eyebrow="8 · Parts" title="Type, route signs, controls and states" note="Press Tab to see the focus ring on every control." />
      <div className="grid gap-4 lg:grid-cols-3">
        <Panel title="Type scale" purpose="12 / 13 / 14 / 16 / 20 / 24">
          <div className="space-y-1">
            <div className="text-xl font-semibold">24 · Answer figures</div>
            <div className="text-lg font-semibold">20 · Questions, section titles</div>
            <div className="text-md">16 · Sentences</div>
            <div className="text-base">14 · Body, panel titles</div>
            <div className="text-sm">13 · Tables, controls</div>
            <div className="text-xs text-ink-2">12 · Notes, "how to read this", missing values</div>
          </div>
        </Panel>
        <Panel title="Route signs" purpose="The stripe is the route's group colour.">
          <div className="flex flex-wrap items-center gap-2">
            <RouteSign route="22" groupId={0} groupName="Group 0" size="lg" />
            <RouteSign route="X49" groupId={0} groupName="Group 0" size="lg" />
            <RouteSign route="1001" size="lg" />
          </div>
          <div className="mt-3 flex flex-wrap gap-2">{SIGN_ROW.map(([r, g]) => <RouteSign key={r} route={r} groupId={g} />)}</div>
          <div className="mt-2 flex flex-wrap gap-2">{SIGN_ROW.map(([r, g]) => <RouteSign key={r} route={r} groupId={g} size="sm" />)}</div>
          <p className="mt-3 text-xs text-ink-2">Groups shown are the real Stage 5 memberships.</p>
        </Panel>
        <Panel title="Controls and states">
          <div className="flex flex-wrap gap-2">
            <button type="button" className="btn-primary">Show full history since 2001</button>
            <button type="button" className="btn-secondary">Clear</button>
            <button type="button" className="btn-secondary" disabled title="not used on this screen">Disabled</button>
          </div>
          <div className="mt-3 space-y-3 border-t border-rule pt-3">
            <div><div className="field-label">Loading</div><Loading /></div>
            <div><div className="field-label">Empty</div><Empty message="No routes match these choices." /></div>
            <div><div className="field-label">Error</div><ErrorState message="compare needs 2 to 8 routes, got 1" onRetry={() => undefined} /></div>
          </div>
        </Panel>
      </div>
    </div>
  )
}
