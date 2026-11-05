'use client';

import { useState } from 'react';
import {
  User,
  Bell,
  Shield,
  Palette,
  Globe,
  Save,
  Loader2,
  Eye,
  EyeOff,
} from 'lucide-react';
import { useAuthStore } from '@/hooks/useAuthStore';
import { authApi } from '@/lib/api';

export default function SettingsPage() {
  const { user, updateUser, isAuthenticated } = useAuthStore();
  const [activeTab, setActiveTab] = useState<'profile' | 'notifications' | 'security' | 'appearance'>('profile');
  const [isLoading, setIsLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  // Profile form state
  const [profileForm, setProfileForm] = useState({
    full_name: user?.full_name || '',
    email: user?.email || '',
    current_password: '',
    new_password: '',
    confirm_password: '',
  });

  // Notification preferences
  const [notifications, setNotifications] = useState({
    email_alerts: true,
    push_alerts: true,
    daily_summary: false,
    weekly_report: true,
    critical_only: false,
  });

  // Appearance preferences
  const [appearance, setAppearance] = useState({
    theme: 'system', // 'light', 'dark', 'system'
    compact_mode: false,
    animations: true,
  });

  const handleProfileSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      await updateUser({
        full_name: profileForm.full_name,
        email: profileForm.email,
      });
      // If password change requested
      if (profileForm.new_password) {
        // Would call password change API
      }
      alert('Profile updated successfully!');
    } catch (error) {
      console.error('Failed to update profile:', error);
      alert('Failed to update profile');
    } finally {
      setIsLoading(false);
    }
  };

  const handleNotificationChange = (key: string, value: boolean) => {
    setNotifications(prev => ({ ...prev, [key]: value }));
  };

  const handleAppearanceChange = (key: string, value: any) => {
    setAppearance(prev => ({ ...prev, [key]: value }));
  };

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-secondary-50">
        <a href="/login" className="btn-primary">Please log in to access settings</a>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-secondary-50 lg:ml-64">
      <header className="sticky top-0 z-40 bg-white border-b border-secondary-200">
        <div className="flex items-center justify-between h-16 px-6">
          <h1 className="text-2xl font-bold text-secondary-900">Settings</h1>
        </div>
      </header>

      <div className="p-6">
        <div className="max-w-4xl mx-auto">
          {/* Tab Navigation */}
          <div className="card mb-6">
            <div className="flex border-b border-secondary-200">
              {[
                { id: 'profile', label: 'Profile', icon: User },
                { id: 'notifications', label: 'Notifications', icon: Bell },
                { id: 'security', label: 'Security', icon: Shield },
                { id: 'appearance', label: 'Appearance', icon: Palette },
              ].map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as any)}
                  className={`flex items-center gap-2 px-6 py-4 text-sm font-medium border-b-2 transition-colors ${
                    activeTab === tab.id
                      ? 'border-primary-500 text-primary-600'
                      : 'border-transparent text-secondary-500 hover:text-secondary-700'
                  }`}
                >
                  <tab.icon className="w-4 h-4" />
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          {/* Profile Tab */}
          {activeTab === 'profile' && (
            <form onSubmit={handleProfileSubmit} className="card p-6 space-y-6">
              <div className="flex items-center gap-4">
                <div className="w-20 h-20 rounded-full bg-primary-100 flex items-center justify-center">
                  <span className="text-2xl font-bold text-primary-700">
                    {user?.full_name?.charAt(0) || 'U'}
                  </span>
                </div>
                <div>
                  <h2 className="text-xl font-semibold text-secondary-900">{user?.full_name}</h2>
                  <p className="text-secondary-500">{user?.email}</p>
                  <span className={`badge ${
                    user?.role === 'admin' ? 'badge-danger' :
                    user?.role === 'operator' ? 'badge-warning' : 'badge-info'
                  }`}>
                    {user?.role?.charAt(0).toUpperCase() + user?.role?.slice(1)}
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="label block mb-1">Full Name</label>
                  <input
                    type="text"
                    value={profileForm.full_name}
                    onChange={(e) => setProfileForm(prev => ({ ...prev, full_name: e.target.value }))}
                    className="input"
                  />
                </div>
                <div>
                  <label className="label block mb-1">Email</label>
                  <input
                    type="email"
                    value={profileForm.email}
                    onChange={(e) => setProfileForm(prev => ({ ...prev, email: e.target.value }))}
                    className="input"
                  />
                </div>
              </div>

              <div className="border-t border-secondary-200 pt-6">
                <h3 className="text-lg font-medium text-secondary-900 mb-4">Change Password</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label className="label block mb-1">Current Password</label>
                    <div className="relative">
                      <input
                        type={showPassword ? 'text' : 'password'}
                        value={profileForm.current_password}
                        onChange={(e) => setProfileForm(prev => ({ ...prev, current_password: e.target.value }))}
                        className="input pr-10"
                        placeholder="Enter current password"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-secondary-400 hover:text-secondary-600"
                      >
                        {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                      </button>
                    </div>
                  </div>
                  <div>
                    <label className="label block mb-1">New Password</label>
                    <input
                      type={showPassword ? 'text' : 'password'}
                      value={profileForm.new_password}
                      onChange={(e) => setProfileForm(prev => ({ ...prev, new_password: e.target.value }))}
                      className="input"
                      placeholder="Enter new password"
                    />
                  </div>
                  <div>
                    <label className="label block mb-1">Confirm Password</label>
                    <input
                      type={showPassword ? 'text' : 'password'}
                      value={profileForm.confirm_password}
                      onChange={(e) => setProfileForm(prev => ({ ...prev, confirm_password: e.target.value }))}
                      className="input"
                      placeholder="Confirm new password"
                    />
                  </div>
                </div>
              </div>

              <div className="flex justify-end pt-4 border-t border-secondary-200">
                <button type="submit" className="btn-primary" disabled={isLoading}>
                  {isLoading ? <Loader2 className="w-4 h-4 spinner mr-2" /> : <Save className="w-4 h-4 mr-2" />}
                  Save Changes
                </button>
              </div>
            </form>
          )}

          {/* Notifications Tab */}
          {activeTab === 'notifications' && (
            <div className="card p-6 space-y-6">
              <h2 className="text-lg font-semibold text-secondary-900">Notification Preferences</h2>
              <div className="space-y-4">
                {[
                  { key: 'email_alerts', label: 'Email Alerts', description: 'Receive critical alerts via email' },
                  { key: 'push_alerts', label: 'Push Notifications', description: 'Receive real-time push notifications' },
                  { key: 'daily_summary', label: 'Daily Summary', description: 'Receive daily operational summary' },
                  { key: 'weekly_report', label: 'Weekly Report', description: 'Receive weekly analytics report' },
                  { key: 'critical_only', label: 'Critical Only', description: 'Only notify for critical severity alerts' },
                ].map(item => (
                  <div key={item.key} className="flex items-center justify-between p-4 bg-secondary-50 rounded-lg">
                    <div>
                      <p className="font-medium text-secondary-900">{item.label}</p>
                      <p className="text-sm text-secondary-500">{item.description}</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={notifications[item.key as keyof typeof notifications]}
                        onChange={(e) => handleNotificationChange(item.key, e.target.checked)}
                        className="sr-only peer"
                      />
                      <div className="w-11 h-6 bg-secondary-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"></div>
                    </label>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Security Tab */}
          {activeTab === 'security' && (
            <div className="card p-6 space-y-6">
              <h2 className="text-lg font-semibold text-secondary-900">Security Settings</h2>

              <div className="border border-secondary-200 rounded-lg p-4">
                <h3 className="font-medium text-secondary-900 mb-2">Two-Factor Authentication</h3>
                <p className="text-sm text-secondary-500 mb-4">Add an extra layer of security to your account.</p>
                <button className="btn-outline btn-sm">Enable 2FA</button>
              </div>

              <div className="border border-secondary-200 rounded-lg p-4">
                <h3 className="font-medium text-secondary-900 mb-2">Active Sessions</h3>
                <p className="text-sm text-secondary-500 mb-4">Manage your active login sessions.</p>
                <div className="space-y-2">
                  <div className="flex items-center justify-between p-3 bg-secondary-50 rounded">
                    <div>
                      <p className="font-medium text-secondary-900">Current Session</p>
                      <p className="text-sm text-secondary-500">Chrome on Windows • Active now</p>
                    </div>
                    <span className="badge badge-success">Active</span>
                  </div>
                </div>
                <button className="btn-outline btn-sm mt-2">Revoke All Other Sessions</button>
              </div>

              <div className="border border-secondary-200 rounded-lg p-4">
                <h3 className="font-medium text-secondary-900 mb-2">API Access</h3>
                <p className="text-sm text-secondary-500 mb-4">Manage API tokens for integrations.</p>
                <button className="btn-outline btn-sm">Generate API Token</button>
              </div>
            </div>
          )}

          {/* Appearance Tab */}
          {activeTab === 'appearance' && (
            <div className="card p-6 space-y-6">
              <h2 className="text-lg font-semibold text-secondary-900">Appearance</h2>

              <div className="border border-secondary-200 rounded-lg p-4">
                <h3 className="font-medium text-secondary-900 mb-2">Theme</h3>
                <div className="flex gap-4">
                  {['light', 'dark', 'system'].map(theme => (
                    <label
                      key={theme}
                      className={`flex flex-col items-center gap-2 p-4 rounded-lg border-2 cursor-pointer transition-colors ${
                        appearance.theme === theme
                          ? 'border-primary-500 bg-primary-50'
                          : 'border-secondary-200 hover:border-secondary-300'
                      }`}
                    >
                      <input
                        type="radio"
                        name="theme"
                        value={theme}
                        checked={appearance.theme === theme}
                        onChange={(e) => handleAppearanceChange('theme', e.target.value)}
                        className="sr-only"
                      />
                      <div className="w-16 h-10 rounded-lg flex items-center justify-center ${
                        theme === 'dark' ? 'bg-secondary-900' : theme === 'light' ? 'bg-white' : 'bg-gradient-to-r from-white to-secondary-900'
                      }">
                        {theme === 'dark' ? (
                          <span className="text-white text-xs">Dark</span>
                        ) : theme === 'light' ? (
                          <span className="text-secondary-900 text-xs">Light</span>
                        ) : (
                          <span className="text-xs">Auto</span>
                        )}
                      </div>
                      <span className="text-sm font-medium capitalize">{theme}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div className="border border-secondary-200 rounded-lg p-4 space-y-4">
                {[
                  { key: 'compact_mode', label: 'Compact Mode', description: 'Reduce spacing for more content' },
                  { key: 'animations', label: 'Animations', description: 'Enable UI animations and transitions' },
                ].map(item => (
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-secondary-900">{item.label}</p>
                      <p className="text-sm text-secondary-500">{item.description}</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={appearance[item.key as keyof typeof appearance]}
                        onChange={(e) => handleAppearanceChange(item.key, e.target.checked)}
                        className="sr-only peer"
                      />
                      <div className="w-11 h-6 bg-secondary-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"></div>
                    </label>
                  </div>
                ))}
              </div>

              <div className="border border-secondary-200 rounded-lg p-4">
                <h3 className="font-medium text-secondary-900 mb-2">Language</h3>
                <select className="input w-48" defaultValue="en">
                  <option value="en">English</option>
                  <option value="es">Spanish</option>
                  <option value="fr">French</option>
                  <option value="zh">Chinese</option>
                </select>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}