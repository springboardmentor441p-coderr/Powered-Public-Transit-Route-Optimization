'use client';

import { useState, useEffect } from 'react';
import {
  Bell,
  AlertTriangle,
  X,
  Check,
  Filter,
  Loader2,
  Clock,
  MapPin,
  Train,
  Info,
} from 'lucide-react';
import { alertApi } from '@/lib/api';
import { useAuthStore } from '@/hooks/useAuthStore';
import { useSocket } from '@/hooks/useSocket';

interface Alert {
  id: string;
  type: string;
  severity: string;
  title: string;
  message: string;
  station_id: string | null;
  train_id: string | null;
  is_read: boolean;
  is_dismissed: boolean;
  created_at: string;
  station: { name: string; code: string } | null;
  train: { train_number: string } | null;
}

export default function AlertsPage() {
  const { isAuthenticated } = useAuthStore();
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedType, setSelectedType] = useState<string>('all');
  const [selectedSeverity, setSelectedSeverity] = useState<string>('all');
  const [showUnreadOnly, setShowUnreadOnly] = useState(false);
  const [summary, setSummary] = useState<any>(null);

  const alertTypes = ['overcrowding', 'delay', 'emergency', 'maintenance', 'schedule_change', 'system'];
  const severities = ['critical', 'warning', 'info'];

  useEffect(() => {
    fetchAlerts();
    fetchSummary();
    // Poll every 10 seconds
    const interval = setInterval(() => {
      fetchAlerts();
      fetchSummary();
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  // Real-time alerts
  const { subscribe, unsubscribe } = useSocket({
    channels: ['alerts'],
    onMessage: (message) => {
      if (message.type === 'alert') {
        fetchAlerts();
        fetchSummary();
      }
    },
  });

  useEffect(() => {
    subscribe('alerts');
    return () => unsubscribe('alerts');
  }, [subscribe, unsubscribe]);

  const fetchAlerts = async () => {
    try {
      const params: any = { limit: 100 };
      if (selectedType !== 'all') params.type = selectedType;
      if (selectedSeverity !== 'all') params.severity = selectedSeverity;
      if (showUnreadOnly) params.unread_only = true;

      const response = await alertApi.listAlerts(params);
      setAlerts(response.data);
    } catch (error) {
      console.error('Failed to fetch alerts:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchSummary = async () => {
    try {
      const response = await alertApi.getAlertSummary();
      setSummary(response.data);
    } catch (error) {
      console.error('Failed to fetch summary:', error);
    }
  };

  const handleMarkRead = async (alertId: string) => {
    try {
      await alertApi.markRead(alertId);
      fetchAlerts();
      fetchSummary();
    } catch (error) {
      console.error('Failed to mark read:', error);
    }
  };

  const handleDismiss = async (alertId: string) => {
    try {
      await alertApi.dismiss(alertId);
      fetchAlerts();
      fetchSummary();
    } catch (error) {
      console.error('Failed to dismiss:', error);
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await alertApi.markAllRead();
      fetchAlerts();
      fetchSummary();
    } catch (error) {
      console.error('Failed to mark all read:', error);
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'bg-danger-100 text-danger-800 border-danger-200';
      case 'warning': return 'bg-warning-100 text-warning-800 border-warning-200';
      case 'info': return 'bg-primary-100 text-primary-800 border-primary-200';
      default: return 'bg-secondary-100 text-secondary-800 border-secondary-200';
    }
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'critical': return <AlertTriangle className="w-5 h-5 text-danger-500" />;
      case 'warning': return <AlertTriangle className="w-5 h-5 text-warning-500" />;
      case 'info': return <Info className="w-5 h-5 text-primary-500" />;
      default: return <Bell className="w-5 h-5 text-secondary-500" />;
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'overcrowding': return <MapPin className="w-4 h-4" />;
      case 'delay': return <Train className="w-4 h-4" />;
      case 'emergency': return <AlertTriangle className="w-4 h-4" />;
      default: return <Bell className="w-4 h-4" />;
    }
  };

  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  };

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-secondary-50">
        <a href="/login" className="btn-primary">Please log in to view alerts</a>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-secondary-50 lg:ml-64">
      <header className="sticky top-0 z-40 bg-white border-b border-secondary-200">
        <div className="flex items-center justify-between h-16 px-6">
          <h1 className="text-2xl font-bold text-secondary-900">Alerts Center</h1>
          <div className="flex items-center gap-3">
            {summary && summary.unread > 0 && (
              <button
                onClick={handleMarkAllRead}
                className="btn-outline btn-sm"
              >
                <Check className="w-4 h-4 mr-2" />
                Mark All Read ({summary.unread})
              </button>
            )}
          </div>
        </div>
      </header>

      <div className="p-6">
        {/* Summary Cards */}
        {summary && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
            <div className="card p-4 border-l-4 border-secondary-400">
              <p className="text-sm text-secondary-500">Total Alerts</p>
              <p className="text-3xl font-bold text-secondary-900">{summary.total}</p>
            </div>
            <div className="card p-4 border-l-4 border-danger-500">
              <p className="text-sm text-secondary-500">Critical</p>
              <p className="text-3xl font-bold text-danger-600">{summary.critical}</p>
            </div>
            <div className="card p-4 border-l-4 border-warning-500">
              <p className="text-sm text-secondary-500">Warning</p>
              <p className="text-3xl font-bold text-warning-600">{summary.warning}</p>
            </div>
            <div className="card p-4 border-l-4 border-primary-500">
              <p className="text-sm text-secondary-500">Info</p>
              <p className="text-3xl font-bold text-primary-600">{summary.info}</p>
            </div>
            <div className="card p-4 border-l-4 border-success-500">
              <p className="text-sm text-secondary-500">Unread</p>
              <p className="text-3xl font-bold text-success-600">{summary.unread}</p>
            </div>
          </div>
        )}

        {/* Filters */}
        <div className="card p-4 mb-6">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex items-center gap-2">
              <Filter className="w-5 h-5 text-secondary-400" />
              <select
                value={selectedType}
                onChange={(e) => setSelectedType(e.target.value)}
                className="input w-40"
              >
                <option value="all">All Types</option>
                {alertTypes.map(type => (
                  <option key={type} value={type}>{type.replace('_', ' ')}</option>
                ))}
              </select>
              <select
                value={selectedSeverity}
                onChange={(e) => setSelectedSeverity(e.target.value)}
                className="input w-32"
              >
                <option value="all">All Severities</option>
                {severities.map(sev => (
                  <option key={sev} value={sev}>{sev.charAt(0).toUpperCase() + sev.slice(1)}</option>
                ))}
              </select>
              <label className="flex items-center gap-2 text-sm text-secondary-600">
                <input
                  type="checkbox"
                  checked={showUnreadOnly}
                  onChange={(e) => setShowUnreadOnly(e.target.checked)}
                  className="rounded border-secondary-300 text-primary-600 focus:ring-primary-500"
                />
                Unread only
              </label>
            </div>
          </div>
        </div>

        {/* Alerts List */}
        <div className="card overflow-hidden">
          {isLoading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="w-8 h-8 spinner" />
            </div>
          ) : alerts.length === 0 ? (
            <div className="text-center py-12">
              <Bell className="w-12 h-12 mx-auto text-secondary-300 mb-4" />
              <p className="text-secondary-500">No alerts found</p>
            </div>
          ) : (
            <div className="divide-y divide-secondary-100">
              {alerts.map(alert => (
                <div
                  key={alert.id}
                  className={`p-4 flex gap-4 transition-colors ${
                    alert.is_read ? '' : 'bg-primary-50'
                  } hover:bg-secondary-50`}
                >
                  <div className="flex-shrink-0 mt-1">
                    {getSeverityIcon(alert.severity)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-medium text-secondary-900">{alert.title}</span>
                          <span className={`px-2 py-0.5 text-xs font-medium rounded ${getSeverityColor(alert.severity)}`}>
                            {alert.severity.toUpperCase()}
                          </span>
                        </div>
                        <p className="text-secondary-600 text-sm">{alert.message}</p>
                        <div className="flex items-center gap-4 mt-2 text-xs text-secondary-400">
                          <span className="flex items-center gap-1">
                            {getTypeIcon(alert.type)}
                            {alert.type.replace('_', ' ')}
                          </span>
                          {alert.station && (
                            <span className="flex items-center gap-1">
                              <MapPin className="w-3 h-3" />
                              {alert.station.name} ({alert.station.code})
                            </span>
                          )}
                          {alert.train && (
                            <span className="flex items-center gap-1">
                              <Train className="w-3 h-3" />
                              {alert.train.train_number}
                            </span>
                          )}
                          <span>{formatTime(alert.created_at)}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-1 flex-shrink-0">
                        {!alert.is_read && (
                          <button
                            onClick={() => handleMarkRead(alert.id)}
                            className="btn-ghost btn-sm text-success-600 hover:bg-success-50"
                            title="Mark as read"
                          >
                            <Check className="w-4 h-4" />
                          </button>
                        )}
                        <button
                          onClick={() => handleDismiss(alert.id)}
                          className="btn-ghost btn-sm text-danger-600 hover:bg-danger-50"
                          title="Dismiss"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}