'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, setToken } from '@/lib/api';

export default function LoginPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<'login' | 'register'>('login');
  
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [examDate, setExamDate] = useState('');
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      if (activeTab === 'login') {
        const res = await api.login({ email, password });
        setToken(res.accessToken);
        router.push('/dashboard');
      } else {
        const res = await api.register({ email, password, examDate });
        setToken(res.accessToken);
        router.push('/onboarding');
      }
    } catch (err: any) {
      setError(err.message || 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen flex items-center justify-center">
      <div className="w-full max-w-md p-6">
        <div className="text-center mb-10">
          <h1 className="text-4xl md:text-5xl font-extrabold mb-3 gradient-text tracking-tight">
            UPSC Memory OS
          </h1>
          <p className="text-slate-600 text-lg">AI-Powered Adaptive Revision System</p>
        </div>

        <div className="bg-white border border-sky-100 rounded-3xl shadow-md p-8">
          <div className="flex bg-sky-50 rounded-lg p-1 mb-6">
            <button
              onClick={() => { setActiveTab('login'); setError(''); }}
              className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors duration-150 ${activeTab === 'login' ? 'bg-gradient-to-r from-sky-500 to-blue-600 text-white' : 'text-slate-600 hover:text-slate-800'}`}
            >
              Login
            </button>
            <button
              onClick={() => { setActiveTab('register'); setError(''); }}
              className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors duration-150 ${activeTab === 'register' ? 'bg-gradient-to-r from-sky-500 to-blue-600 text-white' : 'text-slate-600 hover:text-slate-800'}`}
            >
              Register
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Email</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input-field"
                placeholder="aspirant@example.com"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Password</label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input-field"
                placeholder="••••••••"
              />
            </div>

            {activeTab === 'register' && (
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Target Exam Date</label>
                <input
                  type="date"
                  required
                  value={examDate}
                  onChange={(e) => setExamDate(e.target.value)}
                  className="input-field"
                />
              </div>
            )}

            {error && (
              <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full mt-4"
            >
              {loading ? (
                <span className="flex items-center justify-center">
                  <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Processing...
                </span>
              ) : activeTab === 'login' ? 'Sign In' : 'Create Account'}
            </button>
          </form>
        </div>
      </div>
    </main>
  );
}
