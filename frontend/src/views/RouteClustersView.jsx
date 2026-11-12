import React, { useState, useEffect } from 'react';
import { 
  Layers, 
  Award, 
  BarChart2, 
  Info, 
  CheckCircle2, 
  Search, 
  ArrowUpDown, 
  ShieldCheck 
} from 'lucide-react';
import { getRouteClusters, getRouteProductivityRankings } from '../api';
import DataSourceBadge from '../components/DataSourceBadge';
import LoadingSpinner from '../components/LoadingSpinner';

export default function RouteClustersView() {
  const [activeTab, setActiveTab] = useState('clusters'); // 'clusters' or 'rankings'
  const [clusterData, setClusterData] = useState(null);
  const [rankingData, setRankingData] = useState(null);
  const [dayType, setDayType] = useState('W');
  const [sortBy, setSortBy] = useState('rides_per_scheduled_hour');
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const [cRes, rRes] = await Promise.all([
          getRouteClusters(),
          getRouteProductivityRankings(dayType, sortBy)
        ]);
        setClusterData(cRes);
        setRankingData(rRes);
      } catch (err) {
        console.error('Failed to load cluster or ranking data:', err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [dayType, sortBy]);

  if (loading) return <LoadingSpinner message="Loading Route Clusters & Productivity Rankings..." />;

  const clusters = clusterData?.cluster_summaries || {};
  const members = (clusterData?.routes_membership || []).filter(r => 
    r.route_id.toLowerCase().includes(searchTerm.toLowerCase()) || 
    r.route_name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const rankings = (rankingData?.rankings || []).filter(r =>
    r.route_id.toLowerCase().includes(searchTerm.toLowerCase()) || 
    r.route_name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="space-y-6 max-w-7xl">
      {/* Top Banner */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-teal-950/40 to-slate-900 border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="w-2.5 h-2.5 rounded-full bg-teal-400"></span>
            <span className="text-xs uppercase tracking-wider font-semibold text-teal-400">
              Technical Specification v3.8 Sections 9 & 10
            </span>
          </div>
          <h2 className="text-2xl font-extrabold text-white tracking-tight flex items-center gap-3">
            <Layers className="w-6 h-6 text-teal-400" />
            Route Profiles, Clustering & Productivity Rankings
          </h2>
          <p className="text-sm text-slate-400 mt-1 max-w-3xl">
            Unsupervised K-Means clustering in original units and transparent, independent ranking indicators for all Chicago CTA bus corridors.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <DataSourceBadge source="HISTORICAL_ARCHIVE" />
          <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-teal-500/20 text-teal-300 border border-teal-500/30">
            K-Means (k=4) + GTFS Trips
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveTab('clusters')}
            className={`px-4 py-2 rounded-xl text-xs font-bold transition ${
              activeTab === 'clusters'
                ? 'bg-teal-600 text-white shadow-sm'
                : 'bg-slate-800 text-slate-400 hover:text-white'
            }`}
          >
            K-Means Route Profiles ({clusterData?.eligible_route_count} Corridors)
          </button>
          <button
            onClick={() => setActiveTab('rankings')}
            className={`px-4 py-2 rounded-xl text-xs font-bold transition ${
              activeTab === 'rankings'
                ? 'bg-teal-600 text-white shadow-sm'
                : 'bg-slate-800 text-slate-400 hover:text-white'
            }`}
          >
            Productivity Rankings (Ratio of Sums)
          </button>
        </div>

        {/* Search */}
        <div className="relative w-64">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search route (e.g. 79, Ashland)..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-slate-900 border border-slate-800 rounded-xl pl-9 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-teal-500"
          />
        </div>
      </div>

      {activeTab === 'clusters' ? (
        <div className="space-y-6">
          {/* Diagnostic Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {Object.values(clusters).map((c) => (
              <div key={c.cluster_id} className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-teal-400">
                    Group {c.cluster_id}
                  </span>
                  <span className="text-xs font-mono font-bold text-white bg-slate-800 px-2 py-0.5 rounded">
                    {c.route_count} routes
                  </span>
                </div>
                <h4 className="text-sm font-bold text-white leading-snug">{c.cluster_name}</h4>
                <p className="text-[11px] text-slate-400 leading-relaxed">{c.description}</p>
                <div className="pt-2 border-t border-slate-800/80 text-[11px] font-mono space-y-1 text-slate-300">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Mean Wkday:</span>
                    <span>{c.mean_weekday_rides?.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Sat/Wkday:</span>
                    <span>{c.mean_sat_ratio}x</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Sun/Wkday:</span>
                    <span>{c.mean_sun_ratio}x</span>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Membership Table */}
          <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-4">
            <h3 className="text-base font-bold text-white">Route Cluster Memberships</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead className="bg-slate-800/60 text-slate-400 font-semibold uppercase tracking-wider">
                  <tr>
                    <th className="px-4 py-3">Route ID</th>
                    <th className="px-4 py-3">Route Name</th>
                    <th className="px-4 py-3">Assigned Profile Group</th>
                    <th className="px-4 py-3 text-right">Mean Weekday Rides</th>
                    <th className="px-4 py-3 text-right">CV Variance</th>
                    <th className="px-4 py-3 text-right">Sat Ratio</th>
                    <th className="px-4 py-3 text-right">Sun Ratio</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {members.map((r) => (
                    <tr key={r.route_id} className="hover:bg-slate-800/30 transition">
                      <td className="px-4 py-3 font-mono font-bold text-sky-400">Route {r.route_id}</td>
                      <td className="px-4 py-3 text-slate-300">{r.route_name}</td>
                      <td className="px-4 py-3">
                        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-teal-500/10 text-teal-300 border border-teal-500/20">
                          {r.cluster_name}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right font-mono font-bold text-white">
                        {r.mean_weekday_rides?.toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-slate-400">{r.cv_weekday_rides}</td>
                      <td className="px-4 py-3 text-right font-mono text-slate-400">{r.sat_to_wkday_ratio}x</td>
                      <td className="px-4 py-3 text-right font-mono text-slate-400">{r.sun_to_wkday_ratio}x</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Controls Bar for Rankings */}
          <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 flex flex-wrap items-center justify-between gap-4 text-xs">
            <div className="flex items-center gap-3">
              <span className="text-slate-400 font-semibold uppercase tracking-wider">Day Type:</span>
              {[
                { id: 'W', label: 'Weekday' },
                { id: 'A', label: 'Saturday' },
                { id: 'U', label: 'Sunday/Holiday' }
              ].map(dt => (
                <button
                  key={dt.id}
                  onClick={() => setDayType(dt.id)}
                  className={`px-3 py-1.5 rounded-lg font-semibold transition ${
                    dayType === dt.id ? 'bg-sky-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-white'
                  }`}
                >
                  {dt.label}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-2">
              <span className="text-slate-400 font-semibold uppercase tracking-wider">Sort Indicator:</span>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="bg-slate-800 border border-slate-700 text-white rounded-lg px-3 py-1.5 focus:outline-none"
              >
                <option value="rides_per_scheduled_hour">Rides / Scheduled Hour</option>
                <option value="rides_per_scheduled_trip">Rides / Scheduled Trip</option>
                <option value="mean_daily_rides">Mean Daily Boardings</option>
              </select>
            </div>
          </div>

          {/* Ranking Table */}
          <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-white">Productivity Ranking Indicators</h3>
                <p className="text-xs text-slate-400">
                  Ratios computed as sum(rides)/sum(trips) over matched development observations.
                </p>
              </div>
              <div className="text-xs font-mono text-slate-400">
                Eligible: <strong className="text-emerald-400">{rankingData?.eligible_count}</strong> | Unranked: <strong className="text-amber-400">{rankingData?.unranked_count}</strong>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead className="bg-slate-800/60 text-slate-400 font-semibold uppercase tracking-wider">
                  <tr>
                    <th className="px-4 py-3">Rank</th>
                    <th className="px-4 py-3">Route ID</th>
                    <th className="px-4 py-3">Route Name</th>
                    <th className="px-4 py-3 text-right">Mean Daily Rides</th>
                    <th className="px-4 py-3 text-right">Sched. Trips/Day</th>
                    <th className="px-4 py-3 text-right">Rides / Trip</th>
                    <th className="px-4 py-3 text-right font-bold text-teal-400">Rides / Hour</th>
                    <th className="px-4 py-3 text-center">Eligibility / Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {rankings.map((r, idx) => (
                    <tr key={idx} className="hover:bg-slate-800/30 transition">
                      <td className="px-4 py-3 font-mono font-bold text-slate-300">
                        {r.productivity_rank ? `#${r.productivity_rank}` : '—'}
                      </td>
                      <td className="px-4 py-3 font-mono font-bold text-sky-400">Route {r.route_id}</td>
                      <td className="px-4 py-3 text-slate-300">{r.route_name}</td>
                      <td className="px-4 py-3 text-right font-mono font-bold text-white">
                        {r.mean_daily_rides?.toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-slate-400">{r.scheduled_trips_per_day}</td>
                      <td className="px-4 py-3 text-right font-mono text-slate-300">{r.rides_per_scheduled_trip ?? '—'}</td>
                      <td className="px-4 py-3 text-right font-mono font-bold text-teal-300">
                        {r.rides_per_scheduled_hour ?? '—'}
                      </td>
                      <td className="px-4 py-3 text-center">
                        {r.is_eligible ? (
                          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-400">
                            Eligible ({r.observed_days}d)
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-500/10 text-amber-400" title={r.unranked_reason}>
                            Unranked ({r.unranked_reason})
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

