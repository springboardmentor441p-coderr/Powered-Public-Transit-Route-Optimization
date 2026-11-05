'use client';

import { useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import {
  Train,
  Mail,
  Lock,
  User,
  Eye,
  EyeOff,
  Loader2,
  AlertCircle,
  CheckCircle,
} from 'lucide-react';
import { useAuthStore } from '@/hooks/useAuthStore';

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login, isAuthenticated } = useAuthStore();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const callbackUrl = searchParams.get('callbackUrl') || '/';

  // Redirect if already authenticated
  if (isAuthenticated) {
    router.push(callbackUrl);
    return null;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      await login(email, password);
      setSuccess('Login successful! Redirecting...');
      setTimeout(() => {
        router.push(callbackUrl);
        router.refresh();
      }, 1000);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Invalid email or password');
    } finally {
      setIsLoading(false);
    }
  };

  const demoCredentials = [
    { email: 'admin@metroflow.com', password: 'admin123', role: 'Administrator' },
    { email: 'operator@metroflow.com', password: 'operator123', role: 'Operator' },
    { email: 'viewer@metroflow.com', password: 'viewer123', role: 'Viewer' },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-50 via-white to-secondary-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <Link href="/" className="inline-flex items-center justify-center gap-3 mb-6">
            <div className="w-16 h-16 bg-primary-600 rounded-2xl flex items-center justify-center">
              <Train className="w-8 h-8 text-white" />
            </div>
          </Link>
          <h1 className="text-3xl font-bold text-secondary-900">AI MetroFlow</h1>
          <p className="text-secondary-600 mt-2">Metro Crowd Management & Scheduling Platform</p>
        </div>

        {/* Login Card */}
        <div className="card p-8 shadow-xl">
          {success && (
            <div className="mb-6 flex items-center gap-3 p-4 bg-success-50 border border-success-200 rounded-lg text-success-800">
              <CheckCircle className="w-5 h-5 flex-shrink-0" />
              <span>{success}</span>
            </div>
          )}

          {error && (
            <div className="mb-6 flex items-center gap-3 p-4 bg-danger-50 border border-danger-200 rounded-lg text-danger-800">
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label htmlFor="email" className="label block mb-1">
                Email Address
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-secondary-400" />
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="input pl-10"
                  placeholder="Enter your email"
                  required
                  autoComplete="email"
                  disabled={isLoading}
                />
              </div>
            </div>

            <div>
              <label htmlFor="password" className="label block mb-1">
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-secondary-400" />
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="input pl-10 pr-10"
                  placeholder="Enter your password"
                  required
                  autoComplete="current-password"
                  disabled={isLoading}
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

            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  className="rounded border-secondary-300 text-primary-600 focus:ring-primary-500"
                />
                <span className="text-sm text-secondary-600">Remember me</span>
              </label>
              <Link href="/forgot-password" className="text-sm text-primary-600 hover:text-primary-700">
                Forgot password?
              </Link>
            </div>

            <button
              type="submit"
              className="btn-primary w-full py-3"
              disabled={isLoading}
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-5 h-5 spinner mr-2" />
                  Signing in...
                </>
              ) : (
                'Sign In'
              )}
            </button>
          </form>

          {/* Demo Credentials */}
          <div className="mt-8 p-4 bg-secondary-50 rounded-lg">
            <p className="text-sm font-medium text-secondary-700 mb-3">Demo Credentials</p>
            <div className="space-y-2">
              {demoCredentials.map((cred, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => {
                    setEmail(cred.email);
                    setPassword(cred.password);
                  }}
                  className="w-full text-left p-3 bg-white border border-secondary-200 rounded-lg hover:border-primary-300 hover:bg-primary-50 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-sm text-secondary-900">{cred.email}</p>
                      <p className="text-xs text-secondary-500">{cred.password}</p>
                    </div>
                    <span className="badge badge-info text-xs">{cred.role}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Features */}
          <div className="mt-8 grid grid-cols-3 gap-4 text-center">
            {[
              { icon: User, label: 'Role-Based Access', color: 'text-primary-600' },
              { icon: Lock, label: 'Secure Authentication', color: 'text-success-600' },
              { icon: Train, label: 'Real-Time Monitoring', color: 'text-warning-600' },
            ].map((item, i) => (
              <div key={i} className="p-3 bg-secondary-50 rounded-lg">
                <item.icon className={`w-6 h-6 mx-auto mb-2 ${item.color}`} />
                <p className="text-xs font-medium text-secondary-700">{item.label}</p>
              </div>
            ))}
          </div>

          <p className="mt-8 text-center text-sm text-secondary-500">
            By signing in, you agree to our{' '}
            <Link href="/terms" className="text-primary-600 hover:underline">Terms of Service</Link>
            {' '}and{' '}
            <Link href="/privacy" className="text-primary-600 hover:underline">Privacy Policy</Link>
          </p>
        </div>

        {/* Footer */}
        <div className="text-center mt-8 text-sm text-secondary-400">
          <p>AI MetroFlow v1.0.0</p>
          <p className="mt-1">AI-Powered Metro Crowd Management Platform</p>
        </div>
      </div>
    </div>
  );
}