import React, { useState } from 'react';
import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';
import DashboardView from './views/DashboardView';
import LiveMonitoringView from './views/LiveMonitoringView';
import RoutePlannerView from './views/RoutePlannerView';
import ForecastingView from './views/ForecastingView';
import RecommendationsView from './views/RecommendationsView';
import AnalyticsView from './views/AnalyticsView';
import HistoricalReplayView from './views/HistoricalReplayView';
import RouteClustersView from './views/RouteClustersView';
import AboutView from './views/AboutView';

export default function App() {
  const [currentTab, setTab] = useState('dashboard');

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100">
      {/* Top Application Navbar */}
      <Navbar />

      {/* Main Body with Sidebar + View Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Navigation Sidebar */}
        <Sidebar currentTab={currentTab} setTab={setTab} />

        {/* Dynamic View Panel */}
        <main className="flex-1 overflow-y-auto p-6 md:p-8">
          {currentTab === 'dashboard' && <DashboardView setTab={setTab} />}
          {currentTab === 'live' && <LiveMonitoringView />}
          {currentTab === 'planner' && <RoutePlannerView />}
          {currentTab === 'forecasting' && <ForecastingView />}
          {currentTab === 'replay' && <HistoricalReplayView />}
          {currentTab === 'clustering' && <RouteClustersView />}
          {currentTab === 'recommendations' && <RecommendationsView />}
          {currentTab === 'analytics' && <AnalyticsView />}
          {currentTab === 'about' && <AboutView />}
        </main>
      </div>
    </div>
  );
}
