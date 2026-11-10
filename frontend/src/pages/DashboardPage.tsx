import { useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { Route, MapPin, Bus, CalendarDays, Hash, TrendingUp } from 'lucide-react';
import { useApi } from '../hooks/useApi';
import { getDashboardSummary } from '../services/api';
import { LoadingSpinner, ErrorAlert, StatCard, Card, PageHeader } from '../components/ui';

const COLORS = ['#2563eb', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16'];

export default function DashboardPage() {
  const { data, loading, error, refetch } = useApi(getDashboardSummary);

  if (loading) return <LoadingSpinner text="Loading dashboard data..." />;
  if (error) return <ErrorAlert message={error} onRetry={refetch} />;
  if (!data) return null;

  return (
    <div>
      <PageHeader title="Dashboard Overview" subtitle="Chennai MTC Bus Transportation Analytics — All values derived from GTFS schedule data" />

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4 mb-6">
        <StatCard title="Total Routes" value={data.total_routes} icon={Route} color="blue" />
        <StatCard title="Total Stops" value={data.total_stops} icon={MapPin} color="green" />
        <StatCard title="Scheduled Trips" value={data.total_trips} icon={Bus} color="amber" />
        <StatCard title="Service IDs" value={data.total_service_ids} icon={CalendarDays} color="purple" />
        <StatCard title="Avg Stops/Route" value={data.avg_stops_per_route.toFixed(1)} icon={Hash} color="rose" />
        <StatCard title="Avg Trips/Route" value={data.avg_trips_per_route.toFixed(1)} icon={TrendingUp} color="indigo" />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <Card title="Top Routes by Scheduled Trip Count">
          <TopRoutesChart data={data.top_routes_by_trips} dataKey="trip_count" label="Trips" />
        </Card>
        <Card title="Top Routes by Stop Coverage">
          <TopRoutesChart data={data.top_routes_by_stops} dataKey="stop_count" label="Stops" />
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="Service Distribution by Calendar">
          <ServicePieChart data={data.service_distribution} />
        </Card>
        <Card title="Stops Served by Multiple Routes">
          <MultiRouteStopsChart data={data.multi_route_stops} />
        </Card>
      </div>
    </div>
  );
}

function TopRoutesChart({ data, dataKey, label }: { data: { route_short_name: string; [k: string]: unknown }[]; dataKey: string; label: string }) {
  const chartData = useMemo(() => data.slice(0, 15).map(d => ({
    name: d.route_short_name,
    value: d[dataKey] as number,
  })), [data, dataKey]);

  return (
    <div className="h-72">
      <ResponsiveContainer>
        <BarChart data={chartData} layout="vertical" margin={{ left: 60, right: 20, top: 5, bottom: 5 }}>
          <XAxis type="number" tick={{ fontSize: 12 }} />
          <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={55} />
          <Tooltip formatter={v => [Number(v ?? 0).toLocaleString(), label]} />
          <Bar dataKey="value" fill="#2563eb" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function ServicePieChart({ data }: { data: { service_id: string; trip_count: number }[] }) {
  const safeData = useMemo(() =>
    data.filter(d => d.service_id && !d.service_id.includes('<') && d.service_id.trim().length > 0),
  [data]);

  return (
    <div className="h-72 flex items-center">
      <ResponsiveContainer>
        <PieChart>
          <Pie data={safeData} dataKey="trip_count" nameKey="service_id" cx="50%" cy="50%" outerRadius={100} label={({ name, percent }) => `${String(name ?? '')} (${((percent ?? 0) * 100).toFixed(0)}%)`}>
            {safeData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
          </Pie>
          <Tooltip formatter={v => [Number(v ?? 0).toLocaleString(), 'Trips']} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

function MultiRouteStopsChart({ data }: { data: { stop_count: number; num_stops: number }[] }) {
  const chartData = useMemo(() => data.map(d => ({
    name: `${d.stop_count} route${d.stop_count > 1 ? 's' : ''}`,
    stops: d.num_stops,
  })), [data]);

  return (
    <div className="h-72">
      <ResponsiveContainer>
        <BarChart data={chartData} margin={{ left: 10, right: 20, top: 5, bottom: 5 }}>
          <XAxis dataKey="name" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip formatter={v => [Number(v ?? 0).toLocaleString(), 'Stops']} />
          <Bar dataKey="stops" fill="#10b981" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

