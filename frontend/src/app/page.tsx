'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  LayoutDashboard,
  MapPin,
  Train,
  Calendar,
  Brain,
  Bell,
  BarChart3,
  Settings,
  Users,
  AlertTriangle,
  TrendingUp,
  Activity,
  RefreshCw,
} from 'lucide-react';
import { useAuthStore } from '@/hooks/useAuthStore';
import { useSocket } from '@/hooks/useSocket';

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Stations', href: '/stations', icon: MapPin },
  { name: 'Trains', href: '/trains', icon: Train },
  { name: 'Scheduling', href: '/scheduling', icon: Calendar },
  { name: 'Predictions', href: '/predictions', icon: Brain },
  { name: 'Alerts', href: '/alerts', icon: Bell },
  { name: 'Analytics', href: '/analytics', icon: BarChart3 },
  { name: 'Settings', href: '/settings', icon: Settings },
];

const stats = [
  {
    name: 'Active Trains',
    value: '24',
    change: '+2',
    icon: Train,
    color: 'text-primary-600',
    bgColor: 'bg-primary-100',
  },
  {
    name: 'Total Stations',
    value: '48',
    change: '0',
    icon: MapPin,
    color: 'text-success-600',
    bgColor: 'bg-success-100',
  },
  {
    name: 'Current Occupancy',
    value: '67%',
    change: '-3%',
    icon: Users,
    color: 'text-warning-600',
    bgColor: 'bg-warning-100',
  },
  {
    name: 'Active Alerts',
    value: '3',
    change: '+1',
    icon: AlertTriangle,
    color: 'text-danger-600',
    bgColor: 'bg-danger-100',
  },
];

export default function DashboardPage() {
  const { user, isAuthenticated } = useAuthStore();
  const { isConnected } = useSocket();

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-secondary-50">
        <div className="text-center">
          <h1 className="text-4xl font-bold text-secondary-900 mb-4">AI MetroFlow</h1>
          <p className="text-secondary-600 mb-8">Please log in to access the dashboard</p>
          <Link href="/login" className="btn-primary">
            Sign In
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-secondary-50">
      {/* Sidebar */}
      <aside className="fixed inset-y-0 left-0 z-50 w-64 bg-white border-r border-secondary-200 hidden lg:block">
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="flex items-center justify-center h-16 border-b border-secondary-200">
            <Link href="/" className="flex items-center gap-2">
              <Train className="w-8 h-8 text-primary-600" />
              <span className="text-xl font-bold text-secondary-900">MetroFlow</span>
            </Link>
          </div>

          {/* Navigation */}
          <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
            {navigation.map((item) => (
              <Link
                key={item.name}
                href={item.href}
                className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-secondary-600 hover:bg-secondary-100 hover:text-secondary-900 transition-colors"
              >
                <item.icon className="w-5 h-5" />
                <span>{item.name}</span>
              </Link>
            ))}
          </nav>

          {/* User & Connection Status */}
          <div className="p-4 border-t border-secondary-200">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center">
                  <span className="text-sm font-medium text-primary-700">
                    {user?.full_name?.charAt(0) || 'U'}
                  </span>
                </div>
                <div>
                  <p className="text-sm font-medium text-secondary-900">{user?.full_name}</p>
                  <p className="text-xs text-secondary-500 capitalize">{user?.role}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span
                  className={`w-2 h-2 rounded-full ${isConnected ? 'bg-success-500' : 'bg-danger-500'}`}
                />
                <span className="text-xs text-secondary-500">
                  {isConnected ? 'Connected' : 'Disconnected'}
                </span>
              </div>
            </div>
            <Link href="/settings" className="btn-outline w-full btn-sm">
              <Settings className="w-4 h-4 mr-2" />
              Settings
            </Link>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="lg:ml-64 min-h-screen">
        {/* Top Bar */}
        <header className="sticky top-0 z-40 bg-white border-b border-secondary-200">
          <div className="flex items-center justify-between h-16 px-6">
            <h1 className="text-2xl font-bold text-secondary-900">Dashboard</h1>
            <div className="flex items-center gap-4">
              <button className="btn-ghost btn-sm">
                <RefreshCw className="w-4 h-4" />
              </button>
              <div className="flex items-center gap-2">
                <Activity className="w-5 h-5 text-primary-600" />
                <span className="text-sm text-secondary-600">Live</span>
              </div>
            </div>
          </div>
        </header>

        {/* Dashboard Content */}
        <div className="p-6">
          {/* Stats Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            {stats.map((stat) => (
              <div key={stat.name} className="card p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-secondary-500">{stat.name}</p>
                    <p className="text-3xl font-bold text-secondary-900 mt-1">{stat.value}</p>
                    <p className={`text-xs font-medium mt-1 ${stat.change.startsWith('-') ? 'text-danger-600' : 'text-success-600'}`}>
                      {stat.change} vs last hour
                    </p>
                  </div>
                  <div className={`${stat.bgColor} p-3 rounded-xl`}>
                    <stat.icon className={`w-6 h-6 ${stat.color}`} />
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Charts & Maps Row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            {/* System Occupancy Chart */}
            <div className="card p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-secondary-900">System Occupancy (24h)</h2>
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-primary-500" />
                  <span className="text-sm text-secondary-500">Live</span>
                </div>
              </div>
              <div className="h-64">
                <OccupancyChart />
              </div>
            </div>

            {/* Congestion Heatmap */}
            <div className="card p-6">
              <h2 className="text-lg font-semibold text-secondary-900 mb-4">Station Congestion Map</h2>
              <div className="h-64 rounded-lg bg-secondary-100 flex items-center justify-center">
                <CongestionMap />
              </div>
            </div>
          </div>

          {/* Recent Alerts & Quick Actions */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Recent Alerts */}
            <div className="lg:col-span-2 card p-6">
              <h2 className="text-lg font-semibold text-secondary-900 mb-4">Recent Alerts</h2>
              <div className="space-y-3">
                {[
                  { type: 'overcrowding', severity: 'critical', message: 'Central Station at 95% capacity', time: '2 min ago' },
                  { type: 'delay', severity: 'warning', message: 'Train RED-001 delayed by 8 minutes', time: '15 min ago' },
                  { type: 'maintenance', severity: 'info', message: 'Scheduled maintenance on Blue Line tonight', time: '1 hour ago' },
                ].map((alert, i) => (
                  <div key={i} className="flex items-start gap-3 p-3 bg-secondary-50 rounded-lg">
                    <div className={`w-2 h-2 rounded-full mt-2 flex-shrink-0 ${
                      alert.severity === 'critical' ? 'bg-danger-500' :
                      alert.severity === 'warning' ? 'bg-warning-500' : 'bg-primary-500'
                    }`} />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-secondary-900">{alert.message}</p>
                      <p className="text-xs text-secondary-500">{alert.time}</p>
                    </div>
                    <span className={`badge-sm ${alert.severity === 'critical' ? 'badge-danger' : alert.severity === 'warning' ? 'badge-warning' : 'badge-info'}`}>
                      {alert.type}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Quick Actions */}
            <div className="card p-6">
              <h2 className="text-lg font-semibold text-secondary-900 mb-4">Quick Actions</h2>
              <div className="space-y-3">
                <Link href="/scheduling" className="btn-outline w-full justify-start gap-3">
                  <Calendar className="w-5 h-5" />
                  <span>Optimize Schedule</span>
                </Link>
                <Link href="/predictions" className="btn-outline w-full justify-start gap-3">
                  <Brain className="w-5 h-5" />
                  <span>View Predictions</span>
                </Link>
                <Link href="/stations" className="btn-outline w-full justify-start gap-3">
                  <MapPin className="w-5 h-5" />
                  <span>Monitor Stations</span>
                </Link>
                <Link href="/trains" className="btn-outline w-full justify-start gap-3">
                  <Train className="w-5 h-5" />
                  <span>Track Trains</span>
                </Link>
                <Link href="/analytics" className="btn-outline w-full justify-start gap-3">
                  <BarChart3 className="w-5 h-5" />
                  <span>View Analytics</span>
                </Link>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

// Simple chart components (would use recharts in production)
function OccupancyChart() {
  return (
    <div className="flex items-end justify-between h-full">
      {Array.from({ length: 24 }).map((_, i) => (
        <div key={i} className="flex-1 flex items-end justify-center px-1">
          <div
            className="w-full bg-primary-500 rounded-t transition-all hover:bg-primary-600"
            style={{ height: `${Math.random() * 80 + 10}%` }}
          />
        </div>
      ))}
    </div>
  );
}

function CongestionMap() {
  return (
    <div className="w-full h-full relative">
      {/* Simplified map representation */}
      <div className="absolute inset-0 bg-gradient-to-br from-secondary-100 to-secondary-200" />
      <div className="relative z-10 flex items-center justify-center h-full">
        <div className="text-center text-secondary-500">
          <MapPin className="w-12 h-12 mx-auto mb-2 opacity-50" />
          <p>Interactive Map</p>
          <p className="text-sm">(Leaflet integration)</p>
        </div>
      </div>
      {/* Sample congestion points */}
      <div className="absolute top-1/4 left-1/4">
        <div className="w-4 h-4 rounded-full bg-danger-500 animate-pulse" title="Critical" />
      </div>
      <div className="absolute top-1/2 left-1/2">
        <div className="w-4 h-4 rounded-full bg-warning-500" title="Warning" />
      </div>
      <div className="absolute top-3/4 right-1/4">
        <div className="w-3 h-3 rounded-full bg-primary-500" title="Normal" />
      </div>
    </div>
  );
}