// Data (spec 9.16.2 "Data and coverage"): coverage, missing data in both directions with reasons, the import checks,
// timetable archives, an honest model card and the sources. Every number and sentence is computed from
// /api/data/coverage and /api/models/summary at render time (CLAUDE.md, UI design principles).
import { api } from '../api/client'
import type { Coverage, MissingGroup, ModelsResponse } from '../api/types'
import { useApi } from '../api/useApi'
import { AsyncBlock } from '../components/AsyncBlock'
import { ApiLabel, Panel, SectionHead } from '../components/Panel'
import { SourcesPanel } from '../components/SourcesPanel'
import { Empty } from '../components/States'
import { Value } from '../components/Value'
import { fmtDate, fmtRange } from '../lib/dates'
import { fmt } from '../lib/format'
import { useState } from 'react'
import { gainWords, inSentence, networkSentence, sameRows, scoredShare, topAndRest } from '../lib/modelCard'
import { sortRoutes } from '../lib/routeSort'

type ModelsOk = Extract<ModelsResponse, { available: true }>

export function DataPage() {
  const coverage = useApi(o => api.coverage(o), 'coverage')
  const models = useApi(o => api.models(o), 'models')
  return (
    <div>
      <div className="eyebrow">Data</div>
      <h1 className="text-xl font-semibold tracking-tight">Can I trust these numbers?</h1>
      <div className="mt-4">
        <AsyncBlock state={coverage} retry={coverage.retry} label="Loading data coverage">
          {c => <CoverageBlock c={c} />}
        </AsyncBlock>
      </div>

      <SectionHead title="Forecast model card" note="What was tried, what serves predictions, and by how much it beats a simple rule." />
      <AsyncBlock state={models} retry={models.retry} label="Loading the model card">
        {m => m.available ? <ModelCard m={m} /> : <Empty message={`The model card is unavailable – ${m.reason}.`} />}
      </AsyncBlock>

      <SectionHead title="Sources" note="The same details as the Sources button in the top bar." />
      <AsyncBlock state={coverage} retry={coverage.retry} label="Loading sources">
        {c => <Panel title="Data version, code and files"><SourcesPanel c={c} /></Panel>}
      </AsyncBlock>
    </div>
  )
}

function CoverageBlock({ c }: { c: Coverage }) {
  const m = c.matching
  const held = c.quality.import_checks.filter(k => k.violations === 0).length
  const missingDays = (g: MissingGroup[]) => g.reduce((s, x) => s + x.rows, 0)
  return (
    <div>
      <div className="space-y-2 border-l-[3px] border-brand pl-4 text-md leading-8">
        <p>
          Recorded rides run from {fmtDate(c.observations.first_date)} to {fmtDate(c.observations.last_date)}; dated schedules cover{' '}
          {fmtRange(c.analysis_window.start, c.analysis_window.end)}. In that window,{' '}
          <span className="font-semibold"><Value value={c.matching.schedule_conditioned_coverage_pct} digits={1} /> %</span> of scheduled
          route-days have a ridership record ({fmt(m.matched_rows)} of {fmt(m.schedule_rows)}).
        </p>
        <p>
          <span className="font-semibold num">{fmt(missingDays(m.ridership_without_schedule))}</span> route-days have rides but no schedule and{' '}
          <span className="font-semibold num">{fmt(missingDays(m.schedule_without_ridership))}</span> have a schedule but no rides; both are
          kept and shown as gaps, never as 0. <span className="font-semibold num">{fmt(held)}</span> of {fmt(c.quality.import_checks.length)} import
          checks hold.
        </p>
      </div>

      <div className="mt-6 grid items-start gap-4 xl:grid-cols-3">
        <Panel title="Coverage" purpose="Counts for the whole data version.">
          <dl className="space-y-1.5 text-sm">
            {([
              [c.observations.label, `${fmt(c.observations.rows)} route-days, ${fmt(c.observations.route_identifiers)} route numbers`],
              ['Recorded zero rides', `${fmt(c.observations.recorded_zero_rows)} route-days (real zeros, kept as 0)`],
              [c.schedule.label, `${fmt(c.schedule.rows)} route-days on ${fmt(c.schedule.dates)} dates, ${fmt(c.schedule.routes)} routes`],
              ['Matched', `${fmt(m.matched_rows)} route-days, ${fmt(m.matched_routes)} routes, ${fmt(m.matched_dates)} dates`],
              ['Trip times incomplete', `${fmt(c.schedule.incomplete_duration_rows)} scheduled route-days`],
            ] as [string, string][]).map(([k, v]) => (
              <div key={k} className="grid grid-cols-[11rem_minmax(0,1fr)] gap-2 border-b border-rule pb-1.5 last:border-b-0">
                <dt className="text-ink-2">{k}</dt><dd className="num">{v}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-2 text-xs text-ink-2">{c.schedule.note}</p>
        </Panel>
        <Panel title="Missing data, with reasons" purpose="Route-days present on one side only, in the analysis window."
               howToRead="Each row is one reason. A missing day stays missing: screens show it as a gap with this reason.">
          <MissingTable title="Rides recorded, no scheduled service" groups={m.ridership_without_schedule} />
          <div className="mt-3"><MissingTable title="Service scheduled, no ridership record" groups={m.schedule_without_ridership} /></div>
        </Panel>
        <Panel title={`Import checks: ${fmt(held)} of ${fmt(c.quality.import_checks.length)} hold`} purpose={c.quality.note}>
          <ul className="space-y-1 text-sm">
            {c.quality.import_checks.map(k => (
              <li key={k.check} className="flex items-baseline justify-between gap-3 border-b border-rule pb-1 last:border-b-0">
                <span>{k.label}</span>
                <span className={`num whitespace-nowrap text-xs ${k.violations === 0 ? 'text-ink-2' : 'font-semibold text-warn-ink'}`}>
                  {k.violations === 0 ? 'holds' : `${fmt(k.violations)} rows break it`}</span>
              </li>
            ))}
          </ul>
        </Panel>
      </div>

      <Panel className="mt-4" title={`Timetable archives: ${fmt(c.archives.length)}`} purpose="Each timetable applies from its first date until the next one starts."
             howToRead="Scheduled service for a date comes from the timetable that applies on that date. Map lines and shared stops are drawn from one named timetable.">
        <div className="-mx-4 overflow-x-auto">
          <table className="data-table">
            <thead><tr><th>Timetable</th><th>Captured</th><th>Applied</th><th className="n">Days</th><th className="n">Bus routes</th><th className="n">Scheduled routes</th><th className="n">Map lines</th></tr></thead>
            <tbody>{c.archives.map(a => (
              <tr key={a.geometry_version}>
                <td className="num text-sm">{a.geometry_version}</td><td className="text-sm">{fmtDate(a.captured_date)}</td>
                <td className="whitespace-nowrap text-sm">{fmtRange(a.applied_start, a.applied_end)}</td>
                <td className="n num">{fmt(a.applied_days)}</td><td className="n num">{fmt(a.bus_routes)}</td>
                <td className="n num">{fmt(a.scheduled_routes)}</td><td className="n num">{fmt(a.map_lines)}</td>
              </tr>))}</tbody>
          </table>
        </div>
      </Panel>
    </div>
  )
}

function MissingTable({ title, groups }: { title: string; groups: MissingGroup[] }) {
  return (
    <div>
      <h3 className="mb-1 text-sm font-semibold">{title}</h3>
      {groups.length === 0
        ? <p className="text-xs text-ink-2">None.</p>
        : <ul className="space-y-1.5 text-sm">
            {groups.map(g => (
              <li key={g.reason_code ?? g.reason}>
                <span className="num font-semibold">{fmt(g.rows)}</span> route-days, {fmt(g.routes)} {g.routes === 1 ? 'route' : 'routes'}: {g.reason}
                <span className="block text-xs text-ink-2">Routes {sortRoutes(g.route_list).join(', ')} · {fmtRange(g.first_date, g.last_date)}</span>
              </li>
            ))}
          </ul>}
    </div>
  )
}

function ModelCard({ m }: { m: ModelsOk }) {
  const v = gainWords(m.gain.validation), t = gainWords(m.gain.test)
  const sel = m.methods.find(x => x.method === m.selected.method)
  const nets = m.methods.filter(x => x.kind === 'neural').length
  const same = sameRows(m.methods)
  const baseShort = m.best_baseline.label.split(' (')[0]!.toLowerCase()
  const baseRow = m.methods.find(x => x.method === m.best_baseline.method)
  const share = sel ? scoredShare(sel.validation.scored_rows, sel.validation.withheld_rows) : null
  const pct = (g: { pct: number; direction: string } | null) => g == null ? 'unavailable'
    : g.direction === 'equal' ? 'the same as' : `${fmt(g.pct, 1)} % ${g.direction} than`
  return (
    <div className="space-y-4">
      <div className="space-y-2 border-l-[3px] border-brand pl-4 text-md leading-8">
        <p>
          {fmt(m.methods.length)} methods were tried to forecast {m.target_label}. The one serving predictions is{' '}
          <span className="font-semibold">{inSentence(m.selected.label)}</span>: its average error is{' '}
          <span className="font-semibold">{pct(v)}</span> the {m.best_baseline.label.split(' (')[0]!.toLowerCase()} on validation
          {m.gain.validation && <> ({fmt(m.gain.validation.model_mae, 1)} vs {fmt(m.gain.validation.baseline_mae, 1)} rides per route-day)</>},
          and <span className="font-semibold">{t == null ? 'unavailable' : t.direction === 'equal' ? 'the same' : `${fmt(t.pct, 1)} % ${t.direction}`}</span> on the test period
          {m.gain.test && <> ({fmt(m.gain.test.model_mae, 1)} vs {fmt(m.gain.test.baseline_mae, 1)})</>}.
        </p>
        <p>
          {m.best_network && sel && baseRow && <>
            {fmt(nets)} neural networks were tried as an extra experiment.{' '}
            {networkSentence({ label: m.best_network.label, mae: m.best_network.validation_mae },
                             { label: m.selected.label, mae: sel.validation.mae },
                             { label: baseShort, mae: baseRow.validation.mae }, x => fmt(x, 1))}
          </>}
          {' '}The {inSentence(m.selected.label)} forecasts <Value value={share == null ? null : share * 100} digits={1} /> % of
          validation route-days{sel && <> ({fmt(sel.validation.scored_rows)} of {fmt(sel.validation.scored_rows + sel.validation.withheld_rows)})</>};
          the rest lack the recent ride history it needs.
        </p>
      </div>
      <ApiLabel warn text={`Test period: ${m.test_status_label}.`} />

      <Panel title="All methods, best validation error first" purpose={`Error = ${m.metric_label}. ${m.selection_note[0]!.toUpperCase()}${m.selection_note.slice(1)}.`}
             howToRead={`MAE is the average miss in rides per route-day; WAPE is total miss as a share of total rides.${same
               ? ` All ${fmt(m.methods.length)} methods were scored on exactly the same route-days (${fmt(same.validation)} in validation${same.test != null ? `, ${fmt(same.test)} in the test period` : ''}), so the errors compare like with like.`
               : ''} The serving method and the best simple rule are named in the first column.`}>
        <div className="-mx-4 overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr><th rowSpan={2}>Method</th><th rowSpan={2}>Kind</th>
                <th colSpan={2} className="text-center">Validation {fmtRange(m.periods.validation[0], m.periods.validation[1])}</th>
                <th colSpan={2} className="text-center">Test {fmtRange(m.periods.test[0], m.periods.test[1])}</th></tr>
              <tr><th className="n">MAE</th><th className="n">WAPE</th><th className="n">MAE</th><th className="n">WAPE</th></tr>
            </thead>
            <tbody>{m.methods.map(x => (
              <tr key={x.method} className={x.method === m.selected.method ? 'bg-hover' : ''}>
                <td className="text-sm">{x.label}
                  {x.method === m.selected.method && <span className="block text-xs font-semibold">serves predictions</span>}
                  {x.method === m.best_baseline.method && <span className="block text-xs text-ink-2">best simple rule</span>}</td>
                <td className="text-xs text-ink-2">{x.kind_label}</td>
                <td className="n num">{fmt(x.validation.mae, 1)}</td><td className="n num">{fmt(x.validation.wape_percent, 2)} %</td>
                <td className="n"><Value value={x.test?.mae} digits={1} reason="not scored" /></td>
                <td className="n">{x.test ? <span className="num">{fmt(x.test.wape_percent, 2)} %</span> : <Value value={null} reason="not scored" />}</td>
              </tr>))}</tbody>
          </table>
        </div>
      </Panel>

      <div className="grid items-start gap-4 xl:grid-cols-2">
        <Panel title="Route-days not forecast" purpose={`${m.selected.label}: rows withheld because required ride history was missing.`}>
          {(['validation', 'test'] as const).map(split => (
            <div key={split} className="mb-2">
              <h3 className="text-sm font-semibold">{split === 'validation' ? 'Validation' : 'Test'}</h3>
              <WithheldList items={m.withheld[split]} />
            </div>
          ))}
        </Panel>
        <Panel title="Periods and versions">
          <dl className="space-y-1 text-sm">
            <div><dt className="inline text-ink-2">Training: </dt><dd className="inline">{fmtRange(m.periods.train[0], m.periods.train[1])}</dd></div>
            <div><dt className="inline text-ink-2">Validation (choosing the method): </dt><dd className="inline">{fmtRange(m.periods.validation[0], m.periods.validation[1])}</dd></div>
            <div><dt className="inline text-ink-2">Test (scored once): </dt><dd className="inline">{fmtRange(m.periods.test[0], m.periods.test[1])}</dd></div>
            <div><dt className="inline text-ink-2">Models: </dt><dd className="inline num">{m.artifact_version}, commit {m.git_commit}, built {m.created_at.slice(0, 10)}</dd></div>
            <div><dt className="inline text-ink-2">Neural network experiment: </dt><dd className="inline num">{m.extra_experiment.artifact_version}, commit {m.extra_experiment.git_commit}</dd></div>
          </dl>
        </Panel>
      </div>
    </div>
  )
}

/** The 3 most common reasons, then "+ N other combinations" that expands on click. */
function WithheldList({ items }: { items: { reason: string; rows: number }[] }) {
  const [open, setOpen] = useState(false)
  const sorted = [...items].sort((a, b) => b.rows - a.rows || a.reason.localeCompare(b.reason))
  const { top, rest } = topAndRest(sorted, 3)
  const line = (w: { reason: string; rows: number }) => <li key={w.reason}><span className="num">{fmt(w.rows)}</span> – {w.reason}</li>
  return (
    <ul className="text-xs text-ink-2">
      {top.map(line)}
      {open && rest.map(line)}
      {rest.length > 0 && (
        <li><button type="button" className="mt-0.5 underline" aria-expanded={open} onClick={() => setOpen(o => !o)}>
          {open ? 'Show fewer' : `+ ${fmt(rest.length)} other ${rest.length === 1 ? 'combination' : 'combinations'} (${fmt(rest.reduce((s, w) => s + w.rows, 0))} route-days)`}
        </button></li>
      )}
    </ul>
  )
}
