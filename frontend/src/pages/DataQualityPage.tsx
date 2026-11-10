import { AlertTriangle, CheckCircle2, Database, FileCheck2, ShieldCheck } from 'lucide-react';
import { useApi } from '../hooks/useApi';
import { getDataQuality, getDataStatus } from '../services/api';
import { Badge, Card, EmptyState, ErrorAlert, LoadingSpinner, PageHeader, StatCard } from '../components/ui';

export default function DataQualityPage() {
  const quality = useApi(getDataQuality);
  const status = useApi(getDataStatus);

  if (quality.loading) return <LoadingSpinner text="Loading data quality audit…" />;
  if (quality.error) return <ErrorAlert message={quality.error} onRetry={quality.refetch} />;
  if (!quality.data) return <EmptyState title="No quality report available" />;
  const report = quality.data;
  const dataStatus = status.data;

  return (
    <div className="space-y-6">
      <PageHeader title="Data Quality & Provenance" subtitle="Validation, sanitization, and processing status reported by the backend." />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard title="Feed quality score" value={`${report.quality_score.toFixed(1)}%`} icon={ShieldCheck} color={report.passed_validation ? 'green' : 'amber'} subtitle={report.passed_validation ? 'Validation passed' : 'Review validation issues'} />
        <StatCard title="Routes" value={report.route_count} icon={Database} color="blue" />
        <StatCard title="Stops" value={report.stop_count} icon={FileCheck2} color="purple" />
        <StatCard title="Scheduled trips" value={report.trip_count} icon={CheckCircle2} color="indigo" />
      </div>

      <Card title="Pipeline status">
        {status.loading ? <LoadingSpinner text="Checking processed tables…" /> : status.error ? <ErrorAlert message={status.error} onRetry={status.refetch} /> : dataStatus ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-2 text-sm text-slate-600 dark:text-slate-300">
              <div className="flex items-center gap-2"><Badge color={dataStatus.status === 'ready' ? 'green' : 'amber'}>{dataStatus.status.replaceAll('_', ' ')}</Badge><span>{dataStatus.message}</span></div>
              <p>Last processed: {dataStatus.last_processed_at ? new Date(dataStatus.last_processed_at).toLocaleString() : 'Not reported'}</p>
              <p>Source files discovered: {dataStatus.raw_files_found}</p>
              <p>Quality score: {dataStatus.quality_score == null ? 'Not reported' : `${dataStatus.quality_score.toFixed(1)}%`}</p>
            </div>
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Registered processed tables</p>
              {dataStatus.processed_tables.length ? <div className="flex flex-wrap gap-2">{dataStatus.processed_tables.map(table => <Badge key={table} color="blue">{table}</Badge>)}</div> : <EmptyState title="No processed tables listed" />}
            </div>
          </div>
        ) : null}
      </Card>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card title="GTFS validation summary">
          <div className="grid grid-cols-2 gap-3 text-sm">
            <AuditValue label="Stop-time rows" value={report.stop_times_count} />
            <AuditValue label="Calendar services" value={report.calendar_count} />
            <AuditValue label="Times beyond 24:00" value={report.times_exceeding_24h_count} />
            <AuditValue label="Orphan trips" value={report.orphan_trips_count} />
            <AuditValue label="Invalid coordinates" value={report.invalid_coordinates_count} />
            <AuditValue label="Out-of-bounds stops" value={report.out_of_bounds_stops_count} />
          </div>
          {report.missing_files.length > 0 && <div className="mt-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-800 dark:bg-amber-950/30 dark:text-amber-200"><strong>Optional or missing source files:</strong> {report.missing_files.join(', ')}</div>}
        </Card>

        <Card title="Sanitization audit">
          {report.sanitization_events.length ? <div className="space-y-3">{report.sanitization_events.map((event, index) => <div key={`${event.table}-${event.column}-${index}`} className="rounded-lg border border-slate-200 p-3 dark:border-slate-700"><div className="flex flex-wrap items-center justify-between gap-2"><p className="font-medium text-slate-800 dark:text-slate-100">{event.issue_type}</p><Badge color="amber">{event.table}.{event.column}</Badge></div><p className="mt-2 break-all text-xs text-slate-500">Original: {event.original_value}</p><p className="mt-1 break-all text-xs text-slate-600 dark:text-slate-300">Sanitized: {event.sanitized_value}</p></div>)}</div> : <EmptyState title="No sanitization events recorded" description="The backend audit contains no sanitization events for the current feed." />}
          <p className="mt-4 text-xs text-slate-500">Raw GTFS content is retained separately; the frontend only displays audit metadata returned by the API.</p>
        </Card>
      </div>

      <Card title="Validation issues">
        {report.validation_issues.length ? <div className="space-y-3">{report.validation_issues.map((issue, index) => <div key={`${issue.table}-${index}`} className="flex gap-3 rounded-lg border border-slate-200 p-3 dark:border-slate-700"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" /><div className="text-sm"><div className="mb-1 flex flex-wrap items-center gap-2"><Badge color={issue.severity.toLowerCase() === 'error' ? 'red' : 'amber'}>{issue.severity}</Badge><span className="text-slate-500">{issue.table} · {issue.affected_rows} affected rows</span></div><p className="text-slate-700 dark:text-slate-300">{issue.message}</p></div></div>)}</div> : <EmptyState title="No validation issues reported" description="No issues were listed in the backend audit report." />}
      </Card>
      <p className="text-xs text-slate-500 dark:text-slate-400">All metrics on this page describe data quality and published GTFS schedules. They do not represent passenger counts, demand, occupancy, congestion, or live vehicle performance.</p>
    </div>
  );
}

function AuditValue({ label, value }: { label: string; value: number }) {
  return <div className="rounded-lg bg-slate-50 p-3 dark:bg-slate-800"><p className="text-xs text-slate-500">{label}</p><p className="mt-1 text-lg font-semibold text-slate-900 dark:text-white">{value.toLocaleString()}</p></div>;
}
