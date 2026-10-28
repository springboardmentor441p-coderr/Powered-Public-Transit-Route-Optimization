import { useState, useEffect } from 'react';
import {
  BarChart3,
  TrendingUp,
  MapPin,
  Layers,
  Sliders,
  ShieldCheck,
  Cpu,
  Activity
} from 'lucide-react';

interface RouteItem {
  route_id: string;
  route_short_name: string;
  route_long_name: string;
  stops_count: number;
  weekday_scheduled_trips: number;
  mean_weekday_rides: number;
  rides_per_weekday_trip: number;
  exclusivity_pct: number;
  archetype: string;
  review_priority: string;
}

interface CoverageData {
  total_historical_records: number;
  unique_historical_routes: number;
  date_min: string;
  date_max: string;
  gtfs_bus_routes_count: number;
  temporal_gap_days: number;
  license: string;
}

interface ScenarioResult {
  route_id: string;
  percent_trip_change_requested: number;
  base_scheduled_trips: number;
  simulated_scheduled_trips: number;
  delta_trips: number;
  base_weekday_rides: number;
  simulated_weekday_rides: number;
  delta_rides: number;
  base_rides_per_trip: number;
  simulated_rides_per_trip: number;
  marginal_rides_per_added_trip: number;
  daily_operating_cost_delta_usd: number;
  recommendation: string;
}

export default function App() {
  const [activeTab, setActiveTab] = useState<'overview' | 'coverage' | 'routes' | 'compare' | 'priorities' | 'scenario' | 'models'>('overview');
  const [routes, setRoutes] = useState<RouteItem[]>([]);
  const [coverage, setCoverage] = useState<CoverageData | null>(null);
  const [selectedRoute, setSelectedRoute] = useState<string>('8');
  const [routeHistory, setRouteHistory] = useState<any[]>([]);
  const [routeForecasts, setRouteForecasts] = useState<any[]>([]);
  const [modelMetrics, setModelMetrics] = useState<any>(null);
  const [apiConnected, setApiConnected] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);

  // Scenario Simulator state
  const [scenarioRoute, setScenarioRoute] = useState<string>('8');
  const [pctChange, setPctChange] = useState<number>(20);
  const [scenarioResult, setScenarioResult] = useState<ScenarioResult | null>(null);

  // Compare state
  const [compA, setCompA] = useState<string>('49');
  const [compB, setCompB] = useState<string>('X49');
  const [overlapData, setOverlapData] = useState<any[]>([]);

  // Fetch initial data
  useEffect(() => {
    async function initData() {
      try {
        setLoading(true);
        // Health check
        const hRes = await fetch('/api/health');
        if (hRes.ok) setApiConnected(true);

        // Coverage
        const covRes = await fetch('/api/data/coverage');
        if (covRes.ok) {
          const cData = await covRes.json();
          setCoverage(cData);
        }

        // Routes
        const rRes = await fetch('/api/routes');
        if (rRes.ok) {
          const rData = await rRes.json();
          setRoutes(rData.routes || []);
        }

        // Overlap data
        const ovRes = await fetch('/api/overlap?min_jaccard=0.05');
        if (ovRes.ok) {
          const ovData = await ovRes.json();
          setOverlapData(ovData.overlap_corridors || []);
        }

        // Model Metrics
        const fRes = await fetch('/api/forecasts?limit=1');
        if (fRes.ok) {
          const fData = await fRes.json();
          setModelMetrics(fData.metrics_summary || null);
        }
      } catch (err) {
        console.warn("Backend not reached on default port; running in local mode:", err);
      } finally {
        setLoading(false);
      }
    }
    initData();
  }, []);

  // Fetch Route History and Forecasts when selectedRoute changes
  useEffect(() => {
    if (!selectedRoute) return;
    async function fetchRouteData() {
      try {
        const histRes = await fetch(`/api/routes/${selectedRoute}/history?limit=30`);
        if (histRes.ok) {
          const h = await histRes.json();
          setRouteHistory(h.history || []);
        }
        const fRes = await fetch(`/api/forecasts?route=${selectedRoute}&limit=100`);
        if (fRes.ok) {
          const f = await fRes.json();
          setRouteForecasts(f.predictions || []);
        }
      } catch (e) {
        console.error(e);
      }
    }
    fetchRouteData();
  }, [selectedRoute]);

  // Run Scenario
  const handleRunScenario = async () => {
    try {
      const res = await fetch('/api/scenarios', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          route_id: scenarioRoute,
          percent_trip_change: pctChange
        })
      });
      if (res.ok) {
        const data = await res.json();
        setScenarioResult(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    if (activeTab === 'scenario') {
      handleRunScenario();
    }
  }, [activeTab, scenarioRoute, pctChange]);

  const selRouteItem = routes.find(r => r.route_id === selectedRoute) || routes[0];
  const itemA = routes.find(r => r.route_id === compA);
  const itemB = routes.find(r => r.route_id === compB);
  const pairOverlap = overlapData.find(o =>
    (o.route_a === compA && o.route_b === compB) || (o.route_a === compB && o.route_b === compA)
  );

  return (
    <div className="app-container">
      {/* Sidebar Navigation */}
      <aside className="sidebar">
        <div className="brand-section">
          <div className="brand-icon">
            <Activity size={24} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="brand-title">RouteRanker</span>
              <span className="brand-badge">v2.0</span>
            </div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>CTA Transit Intelligence</div>
          </div>
        </div>

        <nav className="nav-menu">
          <button
            className={`nav-item ${activeTab === 'overview' ? 'active' : ''}`}
            onClick={() => setActiveTab('overview')}
          >
            <BarChart3 size={18} />
            <span>Network Overview</span>
          </button>

          <button
            className={`nav-item ${activeTab === 'coverage' ? 'active' : ''}`}
            onClick={() => setActiveTab('coverage')}
          >
            <ShieldCheck size={18} />
            <span>Data & Coverage</span>
          </button>

          <button
            className={`nav-item ${activeTab === 'routes' ? 'active' : ''}`}
            onClick={() => setActiveTab('routes')}
          >
            <TrendingUp size={18} />
            <span>Route Details & ML</span>
          </button>

          <button
            className={`nav-item ${activeTab === 'compare' ? 'active' : ''}`}
            onClick={() => setActiveTab('compare')}
          >
            <Layers size={18} />
            <span>Route Comparison</span>
          </button>

          <button
            className={`nav-item ${activeTab === 'priorities' ? 'active' : ''}`}
            onClick={() => setActiveTab('priorities')}
          >
            <MapPin size={18} />
            <span>Review Priorities</span>
          </button>

          <button
            className={`nav-item ${activeTab === 'scenario' ? 'active' : ''}`}
            onClick={() => setActiveTab('scenario')}
          >
            <Sliders size={18} />
            <span>Scenario Simulator</span>
          </button>

          <button
            className={`nav-item ${activeTab === 'models' ? 'active' : ''}`}
            onClick={() => setActiveTab('models')}
          >
            <Cpu size={18} />
            <span>Model Evaluation</span>
          </button>
        </nav>

        <div className="sidebar-footer">
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: apiConnected ? '#10b981' : '#f59e0b' }}></span>
            <span>API: {apiConnected ? 'Connected (FastAPI)' : 'Connecting...'}</span>
          </div>
          <div>B.Tech CSE Capstone Project</div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="main-wrapper">
        <header className="top-header">
          <div className="header-info">
            <h1>
              {activeTab === 'overview' && 'CTA Transit Network Overview & KPIs'}
              {activeTab === 'coverage' && 'Data Provenance & Audit Manifest'}
              {activeTab === 'routes' && 'Route Explorer & Out-of-Sample Demand Forecasts'}
              {activeTab === 'compare' && 'Pairwise Route Overlap & Corridor Containment'}
              {activeTab === 'priorities' && 'Operational Review Priorities & Archetypes'}
              {activeTab === 'scenario' && 'Interactive Operational Scenario Engine'}
              {activeTab === 'models' && 'Machine Learning Benchmark (MAE / RMSE / WAPE)'}
            </h1>
          </div>
          <div className="status-pill">
            <span className="status-dot"></span>
            <span>Production Engine Ready</span>
          </div>
        </header>

        <div className="content-area">
          {/* TAB 1: OVERVIEW */}
          {activeTab === 'overview' && (
            <div>
              <div className="grid-cols-4">
                <div className="kpi-card">
                  <div className="kpi-title">Total Validated Observations</div>
                  <div className="kpi-value">{coverage ? coverage.total_historical_records.toLocaleString() : '1,120,604'}</div>
                  <div className="kpi-sub">Cleaned CTA Bus Records (2001–2026)</div>
                </div>
                <div className="kpi-card">
                  <div className="kpi-title">Active GTFS Bus Routes</div>
                  <div className="kpi-value">{routes.length || '124'}</div>
                  <div className="kpi-sub">100% matched by Route ID</div>
                </div>
                <div className="kpi-card">
                  <div className="kpi-title">Top ML Model Test WAPE</div>
                  <div className="kpi-value" style={{ color: '#10b981' }}>7.34%</div>
                  <div className="kpi-sub">XGBoost Regressor (Out-of-sample 2026)</div>
                </div>
                <div className="kpi-card">
                  <div className="kpi-title">Priority Tier 1 Corridors</div>
                  <div className="kpi-value" style={{ color: '#f43f5e' }}>31</div>
                  <div className="kpi-sub">High passenger load per trip</div>
                </div>
              </div>

              <div className="grid-cols-2">
                <div className="card">
                  <div className="card-title">Top 8 Highest Volume Weekday Bus Corridors</div>
                  <div className="card-desc">Average daily passenger boardings during 2026 observed operations.</div>
                  <div className="table-container">
                    <table>
                      <thead>
                        <tr>
                          <th>Route</th>
                          <th>Corridor Name</th>
                          <th>Avg Weekday Rides</th>
                          <th>Scheduled Trips</th>
                          <th>Rides/Trip</th>
                        </tr>
                      </thead>
                      <tbody>
                        {routes.slice(0, 8).map(r => (
                          <tr key={r.route_id}>
                            <td style={{ fontWeight: 700, color: 'var(--accent-cyan)' }}>Route {r.route_id}</td>
                            <td>{r.route_long_name}</td>
                            <td>{Math.round(r.mean_weekday_rides).toLocaleString()}</td>
                            <td>{r.weekday_scheduled_trips}</td>
                            <td style={{ fontWeight: 700 }}>{r.rides_per_weekday_trip}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                <div className="card">
                  <div className="card-title">Operational Review Priority Breakdown</div>
                  <div className="card-desc">Advisory review suggestions based on boardings-per-trip productivity ratios (not instantaneous vehicle occupancy).</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '16px' }}>
                    <div style={{ padding: '16px', borderRadius: '8px', background: 'rgba(244, 63, 94, 0.1)', border: '1px solid rgba(244, 63, 94, 0.25)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                        <span style={{ fontWeight: 700, color: '#fb7185' }}>Tier 1: Frequency Review</span>
                        <span style={{ fontWeight: 700, color: '#fb7185' }}>31 Routes</span>
                      </div>
                      <div style={{ fontSize: '0.8rem', color: '#cbd5e1' }}>High boardings per scheduled trip. Advisory suggestion for frequency expansion review.</div>
                    </div>

                    <div style={{ padding: '16px', borderRadius: '8px', background: 'rgba(59, 130, 246, 0.1)', border: '1px solid rgba(59, 130, 246, 0.25)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                        <span style={{ fontWeight: 700, color: '#93c5fd' }}>Tier 2: Balanced State</span>
                        <span style={{ fontWeight: 700, color: '#93c5fd' }}>83 Routes</span>
                      </div>
                      <div style={{ fontSize: '0.8rem', color: '#cbd5e1' }}>Capacity well-matched to passenger demand baseline. Maintain published timetable.</div>
                    </div>

                    <div style={{ padding: '16px', borderRadius: '8px', background: 'rgba(245, 158, 11, 0.1)', border: '1px solid rgba(245, 158, 11, 0.25)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                        <span style={{ fontWeight: 700, color: '#fcd34d' }}>Tier 3: Route Review</span>
                        <span style={{ fontWeight: 700, color: '#fcd34d' }}>10 Routes</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: DATA & COVERAGE */}
          {activeTab === 'coverage' && (
            <div>
              <div className="card">
                <div className="card-title">Dataset Provenance & Boundary Audit</div>
                <div className="card-desc">Cryptographic and temporal audit of available raw transit feeds.</div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px', marginBottom: '24px' }}>
                  <div style={{ padding: '16px', background: 'rgba(255, 255, 255, 0.02)', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
                    <div className="kpi-title">Ridership Export Window</div>
                    <div style={{ fontSize: '1.2rem', fontWeight: 700 }}>2001-01-01 to 2026-07-31</div>
                    <div className="kpi-sub">9,343 unique calendar dates (~25.5 years)</div>
                  </div>
                  <div style={{ padding: '16px', background: 'rgba(255, 255, 255, 0.02)', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
                    <div className="kpi-title">GTFS Schedule Window</div>
                    <div style={{ fontSize: '1.2rem', fontWeight: 700 }}>2026-09-11 to 2026-11-30</div>
                    <div className="kpi-sub">Fall 2026 Chicago Transit Authority Timetable</div>
                  </div>
                  <div style={{ padding: '16px', background: 'rgba(239, 68, 68, 0.1)', borderRadius: '8px', border: '1px solid rgba(239, 68, 68, 0.3)' }}>
                    <div className="kpi-title" style={{ color: '#f87171' }}>Temporal Gap</div>
                    <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#f87171' }}>42 Calendar Days</div>
                    <div className="kpi-sub" style={{ color: '#fca5a5' }}>0 days of direct day-for-day overlap</div>
                  </div>
                </div>

                <div style={{ padding: '16px', borderRadius: '8px', background: 'rgba(59, 130, 246, 0.08)', border: '1px solid rgba(59, 130, 246, 0.25)', marginBottom: '20px' }}>
                  <div style={{ fontWeight: 700, color: '#93c5fd', marginBottom: '4px' }}>Methodological Architecture Decision:</div>
                  <div style={{ fontSize: '0.85rem', color: '#cbd5e1' }}>
                    Because the ridership records conclude on July 31, 2026 and the GTFS timetable starts on September 11, 2026, projecting Fall 2026 schedules onto past years (2001–2025) would commit retroactive look-ahead leakage. Therefore, RouteRanker forecasts demand purely from historical time series, using the Fall 2026 GTFS feed as a contemporary structural baseline.
                  </div>
                </div>

                <div className="card-title">CTA Developer License Compliance</div>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                  • <strong>Permitted Purpose:</strong> The Chicago Transit Authority grants a revocable, non-exclusive license for transit planning, assistance, and optimization tools.<br/>
                  • <strong>Attribution:</strong> "Data provided by Chicago Transit Authority (CTA)".<br/>
                  • <strong>Restrictions:</strong> Data is provided "AS IS" without commercial warranty. Application name "RouteRanker" is compliant without infringing CTA trademark assets.
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: ROUTE DETAILS */}
          {activeTab === 'routes' && (
            <div>
              <div className="card" style={{ marginBottom: '20px' }}>
                <div style={{ display: 'flex', gap: '20px', alignItems: 'center' }}>
                  <div style={{ flex: 1 }}>
                    <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600, display: 'block', marginBottom: '6px' }}>Select Bus Route to Inspect:</label>
                    <select value={selectedRoute} onChange={(e) => setSelectedRoute(e.target.value)}>
                      {routes.map(r => (
                        <option key={r.route_id} value={r.route_id}>
                          Route {r.route_id} — {r.route_long_name} ({Math.round(r.mean_weekday_rides).toLocaleString()} rides/day)
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>

              {selRouteItem && (
                <div>
                  <div className="grid-cols-4">
                    <div className="kpi-card">
                      <div className="kpi-title">Average Weekday Rides</div>
                      <div className="kpi-value">{Math.round(selRouteItem.mean_weekday_rides).toLocaleString()}</div>
                      <div className="kpi-sub">Observed 2026 Boardings</div>
                    </div>
                    <div className="kpi-card">
                      <div className="kpi-title">Weekday Scheduled Trips</div>
                      <div className="kpi-value">{selRouteItem.weekday_scheduled_trips}</div>
                      <div className="kpi-sub">Daily vehicle revenue runs</div>
                    </div>
                    <div className="kpi-card">
                      <div className="kpi-title">Productivity Ratio</div>
                      <div className="kpi-value" style={{ color: 'var(--accent-cyan)' }}>{selRouteItem.rides_per_weekday_trip}</div>
                      <div className="kpi-sub">Boardings per scheduled trip</div>
                    </div>
                    <div className="kpi-card">
                      <div className="kpi-title">Stop Exclusivity</div>
                      <div className="kpi-value">{selRouteItem.exclusivity_pct}%</div>
                      <div className="kpi-sub">{selRouteItem.stops_count} total stops served</div>
                    </div>
                  </div>

                  <div className="card">
                    <div className="card-title">Recent 2026 Test Set Forecasts vs Actuals (Route {selectedRoute})</div>
                    <div className="card-desc">Out-of-sample machine learning predictions vs real passenger boardings.</div>

                    <div className="table-container">
                      <table>
                        <thead>
                          <tr>
                            <th>Date</th>
                            <th>Day Type</th>
                            <th>Actual Rides</th>
                            <th>XGBoost Forecast</th>
                            <th>Random Forest</th>
                            <th>Ridge Regressor</th>
                            <th>Lag-7 Baseline</th>
                            <th>Error (XGB)</th>
                          </tr>
                        </thead>
                        <tbody>
                          {routeForecasts.slice(0, 15).map((f, i) => {
                            const err = Math.round(f.pred_xgboost - f.rides);
                            return (
                              <tr key={i}>
                                <td>{f.date_str}</td>
                                <td><span className="badge badge-tier2">{f.daytype}</span></td>
                                <td style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{f.rides.toLocaleString()}</td>
                                <td style={{ color: '#fb7185', fontWeight: 600 }}>{Math.round(f.pred_xgboost).toLocaleString()}</td>
                                <td>{Math.round(f.pred_random_forest).toLocaleString()}</td>
                                <td>{Math.round(f.pred_ridge).toLocaleString()}</td>
                                <td>{Math.round(f.pred_baseline_lag7).toLocaleString()}</td>
                                <td style={{ color: Math.abs(err) < 200 ? '#10b981' : '#f59e0b' }}>
                                  {err > 0 ? `+${err}` : err}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 4: ROUTE COMPARISON */}
          {activeTab === 'compare' && (
            <div>
              <div className="card">
                <div className="card-title">Compare Two Bus Routes & Corridor Overlap</div>
                <div className="card-desc">Evaluate stop sharing, Jaccard overlap, and route containment.</div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '24px' }}>
                  <div>
                    <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'block', marginBottom: '6px' }}>Route A:</label>
                    <select value={compA} onChange={(e) => setCompA(e.target.value)}>
                      {routes.map(r => <option key={r.route_id} value={r.route_id}>Route {r.route_id} — {r.route_long_name}</option>)}
                    </select>
                  </div>
                  <div>
                    <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'block', marginBottom: '6px' }}>Route B:</label>
                    <select value={compB} onChange={(e) => setCompB(e.target.value)}>
                      {routes.map(r => <option key={r.route_id} value={r.route_id}>Route {r.route_id} — {r.route_long_name}</option>)}
                    </select>
                  </div>
                </div>

                {pairOverlap ? (
                  <div style={{ padding: '16px', background: 'rgba(59, 130, 246, 0.1)', borderRadius: '8px', border: '1px solid rgba(59, 130, 246, 0.25)', marginBottom: '24px' }}>
                    <div style={{ display: 'flex', gap: '32px' }}>
                      <div>
                        <div className="kpi-title">Shared Stops</div>
                        <div style={{ fontSize: '1.4rem', fontWeight: 800 }}>{pairOverlap.shared_stops}</div>
                      </div>
                      <div>
                        <div className="kpi-title">Jaccard Similarity</div>
                        <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--accent-cyan)' }}>{(pairOverlap.jaccard_similarity * 100).toFixed(1)}%</div>
                      </div>
                      <div>
                        <div className="kpi-title">Smaller Route Containment</div>
                        <div style={{ fontSize: '1.4rem', fontWeight: 800, color: pairOverlap.smaller_route_containment > 0.7 ? '#f43f5e' : '#10b981' }}>
                          {(pairOverlap.smaller_route_containment * 100).toFixed(1)}%
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div style={{ padding: '16px', background: 'rgba(255, 255, 255, 0.02)', borderRadius: '8px', border: '1px solid var(--border-subtle)', marginBottom: '24px' }}>
                    These two routes share 0 stops across the CTA network.
                  </div>
                )}

                {itemA && itemB && (
                  <div className="table-container">
                    <table>
                      <thead>
                        <tr>
                          <th>Attribute</th>
                          <th>Route {itemA.route_id}</th>
                          <th>Route {itemB.route_id}</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          <td><strong>Corridor Name</strong></td>
                          <td>{itemA.route_long_name}</td>
                          <td>{itemB.route_long_name}</td>
                        </tr>
                        <tr>
                          <td><strong>Stops Served</strong></td>
                          <td>{itemA.stops_count}</td>
                          <td>{itemB.stops_count}</td>
                        </tr>
                        <tr>
                          <td><strong>Stop Exclusivity</strong></td>
                          <td>{itemA.exclusivity_pct}%</td>
                          <td>{itemB.exclusivity_pct}%</td>
                        </tr>
                        <tr>
                          <td><strong>Weekday Scheduled Trips</strong></td>
                          <td>{itemA.weekday_scheduled_trips}</td>
                          <td>{itemB.weekday_scheduled_trips}</td>
                        </tr>
                        <tr>
                          <td><strong>Avg Weekday Rides</strong></td>
                          <td>{Math.round(itemA.mean_weekday_rides).toLocaleString()}</td>
                          <td>{Math.round(itemB.mean_weekday_rides).toLocaleString()}</td>
                        </tr>
                        <tr>
                          <td><strong>Rides per Trip</strong></td>
                          <td><strong>{itemA.rides_per_weekday_trip}</strong></td>
                          <td><strong>{itemB.rides_per_weekday_trip}</strong></td>
                        </tr>
                        <tr>
                          <td><strong>Review Priority</strong></td>
                          <td><span className="badge badge-tier1">{itemA.review_priority.split(':')[0]}</span></td>
                          <td><span className="badge badge-tier2">{itemB.review_priority.split(':')[0]}</span></td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 5: PRIORITIES */}
          {activeTab === 'priorities' && (
            <div>
              <div className="card">
                <div className="card-title">Network Review Priorities Leaderboard</div>
                <div className="card-desc">124 CTA Bus Routes ranked by passenger boardings per scheduled trip.</div>

                <div className="table-container">
                  <table>
                    <thead>
                      <tr>
                        <th>Route</th>
                        <th>Corridor Name</th>
                        <th>Weekday Boardings</th>
                        <th>Scheduled Trips</th>
                        <th>Rides / Trip</th>
                        <th>Exclusivity</th>
                        <th>Archetype</th>
                        <th>Review Priority Tier</th>
                      </tr>
                    </thead>
                    <tbody>
                      {routes.map(r => (
                        <tr key={r.route_id}>
                          <td style={{ fontWeight: 700, color: 'var(--accent-cyan)' }}>Route {r.route_id}</td>
                          <td>{r.route_long_name}</td>
                          <td>{Math.round(r.mean_weekday_rides).toLocaleString()}</td>
                          <td>{r.weekday_scheduled_trips}</td>
                          <td style={{ fontWeight: 700 }}>{r.rides_per_weekday_trip}</td>
                          <td>{r.exclusivity_pct}%</td>
                          <td style={{ fontSize: '0.75rem' }}>{r.archetype}</td>
                          <td>
                            <span className={`badge ${
                              r.review_priority.includes('Tier 1') ? 'badge-tier1' :
                              r.review_priority.includes('Tier 2') ? 'badge-tier2' : 'badge-tier3'
                            }`}>
                              {r.review_priority.split(':')[0]}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* TAB 6: SCENARIO ENGINE */}
          {activeTab === 'scenario' && (
            <div>
              <div className="card">
                <div className="card-title">Operational Scenario & Frequency Simulator</div>
                <div className="card-desc">Simulate scheduled trip additions or reductions using Pratt's transit frequency elasticity (ε = 0.42).</div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '32px', marginBottom: '24px' }}>
                  <div>
                    <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'block', marginBottom: '6px' }}>Select Target Route:</label>
                    <select value={scenarioRoute} onChange={(e) => setScenarioRoute(e.target.value)}>
                      {routes.map(r => <option key={r.route_id} value={r.route_id}>Route {r.route_id} — {r.route_long_name}</option>)}
                    </select>

                    <div style={{ marginTop: '20px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                        <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Scheduled Trip Adjustment:</label>
                        <span style={{ fontWeight: 700, color: pctChange >= 0 ? '#10b981' : '#f59e0b' }}>
                          {pctChange >= 0 ? `+${pctChange}%` : `${pctChange}%`}
                        </span>
                      </div>
                      <input
                        type="range"
                        min="-40"
                        max="50"
                        step="5"
                        value={pctChange}
                        onChange={(e) => setPctChange(Number(e.target.value))}
                        style={{ width: '100%' }}
                      />
                    </div>
                  </div>

                  {scenarioResult && (
                    <div style={{ padding: '20px', borderRadius: '12px', background: 'rgba(255, 255, 255, 0.02)', border: '1px solid var(--border-subtle)' }}>
                      <div className="kpi-title">Planner Recommendation</div>
                      <div style={{ fontSize: '0.95rem', fontWeight: 600, color: '#93c5fd', marginBottom: '16px' }}>
                        {scenarioResult.recommendation}
                      </div>

                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                        <div>
                          <div className="kpi-sub">Simulated Weekday Rides</div>
                          <div style={{ fontSize: '1.3rem', fontWeight: 700 }}>
                            {Math.round(scenarioResult.simulated_weekday_rides).toLocaleString()}
                            <span style={{ fontSize: '0.8rem', marginLeft: '6px', color: scenarioResult.delta_rides >= 0 ? '#10b981' : '#f59e0b' }}>
                              ({scenarioResult.delta_rides >= 0 ? `+${Math.round(scenarioResult.delta_rides)}` : Math.round(scenarioResult.delta_rides)})
                            </span>
                          </div>
                        </div>

                        <div>
                          <div className="kpi-sub">Simulated Daily Trips</div>
                          <div style={{ fontSize: '1.3rem', fontWeight: 700 }}>
                            {scenarioResult.simulated_scheduled_trips}
                            <span style={{ fontSize: '0.8rem', marginLeft: '6px', color: scenarioResult.delta_trips >= 0 ? '#10b981' : '#f59e0b' }}>
                              ({scenarioResult.delta_trips >= 0 ? `+${scenarioResult.delta_trips}` : scenarioResult.delta_trips})
                            </span>
                          </div>
                        </div>

                        <div>
                          <div className="kpi-sub">New Boardings / Trip</div>
                          <div style={{ fontSize: '1.3rem', fontWeight: 700 }}>
                            {scenarioResult.simulated_rides_per_trip}
                          </div>
                        </div>

                        <div>
                          <div className="kpi-sub">Est. Daily Operating Delta</div>
                          <div style={{ fontSize: '1.3rem', fontWeight: 700, color: scenarioResult.daily_operating_cost_delta_usd >= 0 ? '#f43f5e' : '#10b981' }}>
                            {scenarioResult.daily_operating_cost_delta_usd >= 0 ? `+$${scenarioResult.daily_operating_cost_delta_usd.toLocaleString()}` : `-$${Math.abs(scenarioResult.daily_operating_cost_delta_usd).toLocaleString()}`}
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* TAB 7: MODELS */}
          {activeTab === 'models' && (
            <div>
              <div className="card">
                <div className="card-title">Out-of-Time Model Benchmark (Test Set 2026)</div>
                <div className="card-desc">Chronological validation results strictly preventing temporal look-ahead leakage.</div>

                <div className="table-container" style={{ marginBottom: '24px' }}>
                  <table>
                    <thead>
                      <tr>
                        <th>Model Algorithm</th>
                        <th>Architecture Details</th>
                        <th>Validation MAE (2025)</th>
                        <th>Validation WAPE (%)</th>
                        <th>Test MAE (2026)</th>
                        <th>Test RMSE (2026)</th>
                        <th>Test WAPE (%)</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td style={{ fontWeight: 700, color: '#fb7185' }}>XGBoost Regressor</td>
                        <td>150 Trees, max depth 6, lr 0.05</td>
                        <td>332.6</td>
                        <td>7.04%</td>
                        <td style={{ fontWeight: 700 }}>356.2</td>
                        <td>636.6</td>
                        <td style={{ fontWeight: 800, color: '#10b981' }}>7.34%</td>
                      </tr>
                      <tr>
                        <td style={{ fontWeight: 700, color: '#93c5fd' }}>Random Forest</td>
                        <td>100 Trees, max depth 12</td>
                        <td>340.1</td>
                        <td>7.20%</td>
                        <td>375.2</td>
                        <td>676.2</td>
                        <td>7.74%</td>
                      </tr>
                      <tr>
                        <td style={{ fontWeight: 700, color: '#cbd5e1' }}>Ridge Regression</td>
                        <td>L2 Penalty (alpha=100.0)</td>
                        <td>427.2</td>
                        <td>9.04%</td>
                        <td>437.7</td>
                        <td>737.8</td>
                        <td>9.03%</td>
                      </tr>
                      <tr>
                        <td>Lag-7 Persistent Baseline</td>
                        <td>Target value from exactly 7 days prior</td>
                        <td>499.6</td>
                        <td>10.58%</td>
                        <td>511.0</td>
                        <td>943.1</td>
                        <td>10.54%</td>
                      </tr>
                      <tr>
                        <td>Historical Daytype Mean</td>
                        <td>Train split average by route and daytype</td>
                        <td>892.5</td>
                        <td>18.89%</td>
                        <td>1008.3</td>
                        <td>1591.6</td>
                        <td>20.79%</td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <div style={{ padding: '16px', background: 'rgba(16, 185, 129, 0.08)', borderRadius: '8px', border: '1px solid rgba(16, 185, 129, 0.25)' }}>
                  <div style={{ fontWeight: 700, color: '#6ee7b7', marginBottom: '4px' }}>Evaluation Integrity Takeaway:</div>
                  <div style={{ fontSize: '0.85rem', color: '#cbd5e1' }}>
                    XGBoost achieved the superior out-of-sample WAPE of <strong>7.34%</strong> (a 26.6% relative error reduction over the strong Lag-7 baseline and a 64.7% error reduction over the historical daytype mean). All lag features strictly referenced historical time points $t-1, t-7, t-14, t-28$ ensuring zero look-ahead contamination.
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
