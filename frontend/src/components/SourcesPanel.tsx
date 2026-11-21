import type { Coverage } from '../api/types'
import { fmtTimestamp } from '../lib/dates'

const short = (sha: string) => `${sha.slice(0, 12)}…`

/** Contents of the Sources drawer: which data version, which code, which files, each with its sha256.
 *  Everything comes from /api/data/coverage `details` and `archives`. */
export function SourcesPanel({ c }: { c: Coverage }) {
  const d = c.details
  const rows: [string, string, string?][] = [
    ['Data version', c.data_version],
    ['Built by commit', d.built_git_commit],
    ['Imported by commit', d.import_git_commit],
    ['Database schema sha256', d.schema_sha256],
  ]
  if (d.imported_at) rows.push(['Imported at', fmtTimestamp(d.imported_at), d.imported_at])
  if (c.cutoff.applied) rows.push(['Cutoff', `${c.cutoff.permitted_through} (dates after it are hidden by the API)`])
  return (
    <div className="space-y-5 text-sm">
      <dl>
        {rows.map(([k, v, full]) => (
          <div key={k} className="grid grid-cols-[150px_minmax(0,1fr)] gap-3 border-b border-rule py-1.5">
            <dt className="text-ink-2">{k}</dt><dd className="num break-all" title={full ?? v}>{v}</dd>
          </div>
        ))}
      </dl>
      <div>
        <h3 className="mb-1 text-sm font-semibold">Timetable archives (GTFS)</h3>
        <div className="overflow-x-auto">
        <table className="data-table">
          <thead><tr><th>Version</th><th>Applied</th><th>sha256</th></tr></thead>
          <tbody>
            {c.archives.map(a => (
              <tr key={a.geometry_version}>
                <td className="num">{a.geometry_version}</td>
                <td className="num whitespace-nowrap">{a.applied_start} to {a.applied_end}</td>
                <td className="num" title={d.archive_sha256[a.geometry_version]}>
                  {d.archive_sha256[a.geometry_version] ? short(d.archive_sha256[a.geometry_version]!) : <span className="text-xs text-ink-2">unavailable</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>
      <p className="text-xs text-ink-2">
        Hover a hash to see it in full. Every input was checked against these sha256 values when it was imported.
      </p>
    </div>
  )
}
