'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { api, clearToken } from '@/lib/api';
import { UrgencyItem, TOPIC_LABELS, TIER_COLORS } from '@/lib/types';
import Link from 'next/link';

export default function DashboardPage() {
  const router = useRouter();
  const [items, setItems] = useState<UrgencyItem[]>([]);
  const [critical, setCritical] = useState<UrgencyItem[]>([]);
  const [stable, setStable] = useState<UrgencyItem[]>([]);
  const [daysRemaining, setDaysRemaining] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchDashboard = async () => {
      try {
        const data = await api.getDashboard();
        setItems(data.items || []);
        setCritical(data.critical || []);
        setStable(data.stable || []);
        setDaysRemaining(data.daysRemaining);
      } catch (err: any) {
        if (err.message === 'Unauthorized') {
          // api client handles redirect
        } else {
          setError(err.message || 'Failed to load dashboard');
        }
      } finally {
        setLoading(false);
      }
    };
    fetchDashboard();
  }, []);

  const handleLogout = () => {
    clearToken();
    router.push('/');
  };

  const renderTopicCard = (item: UrgencyItem) => {
    const safeTier = item.urgencyTier || 'STABLE';
    const urgencyClass = `urgency-${safeTier.toLowerCase()}`;
    const tierClass = `tier-${safeTier.toLowerCase()}`;
    const pct = Math.min(100, Math.max(0, item.urgencyScore * 100));

    return (
      <div key={item.topicId} className={`bg-white border rounded-2xl p-5 flex flex-col justify-between ${urgencyClass}`}>
        <div>
          <div className="flex justify-between items-start mb-3">
            <span className="bg-sky-50 text-sky-700 text-[10px] uppercase tracking-wider px-2 py-1 rounded-md font-medium">
              {TOPIC_LABELS[item.topicType as keyof typeof TOPIC_LABELS] || item.topicType}
            </span>
            <span className={`text-[10px] uppercase font-bold px-2 py-1 rounded-md ${tierClass}`}>
              {item.urgencyTier}
            </span>
          </div>
          <h3 className="font-semibold text-lg text-slate-800 leading-tight mb-4">{item.topicName}</h3>
        </div>
        <div>
          <div className="flex justify-between text-xs text-slate-600 mb-1">
            <span>Urgency Score</span>
            <span>{item.urgencyScore.toFixed(2)}</span>
          </div>
          <div className="w-full h-1.5 bg-slate-200 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full ${item.urgencyTier === 'CRITICAL' ? 'bg-red-500' : item.urgencyTier === 'HIGH' ? 'bg-orange-500' : item.urgencyTier === 'MEDIUM' ? 'bg-amber-500' : 'bg-emerald-500'}`}
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="flex h-screen overflow-hidden text-slate-800">
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r border-sky-100 m-4 mr-0 rounded-2xl flex flex-col justify-between hidden md:flex">
        <div className="p-6">
          <h1 className="text-xl font-bold gradient-text tracking-tight mb-10">UPSC Memory OS</h1>
          <nav className="space-y-2">
            <Link href="/dashboard" className="flex items-center px-4 py-3 bg-sky-50 text-sky-700 rounded-xl font-medium">
              <svg className="w-5 h-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"></path></svg>
              Dashboard
            </Link>
            <Link href="/ask" className="flex items-center px-4 py-3 text-slate-600 hover:bg-sky-50 hover:text-sky-700 rounded-xl font-medium transition-colors duration-150">
              <svg className="w-5 h-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"></path></svg>
              Ask RAG
            </Link>
            <Link href="/quiz" className="flex items-center px-4 py-3 text-slate-600 hover:bg-sky-50 hover:text-sky-700 rounded-xl font-medium transition-colors duration-150">
              <svg className="w-5 h-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"></path></svg>
              Quiz Session
            </Link>
            <Link href="/upload" className="flex items-center px-4 py-3 text-slate-600 hover:bg-sky-50 hover:text-sky-700 rounded-xl font-medium transition-colors duration-150">
              <svg className="w-5 h-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path></svg>
              Upload PDF
            </Link>
          </nav>
        </div>
        <div className="p-6">
          <button onClick={handleLogout} className="text-slate-500 hover:text-slate-800 text-sm transition-colors duration-150 flex items-center">
            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"></path></svg>
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden m-4 p-6 bg-white border border-sky-100 rounded-2xl">
        <header className="flex justify-between items-center mb-8">
          <div>
            <h2 className="text-2xl font-bold text-slate-800">Revision Dashboard</h2>
            <p className="text-slate-500 text-sm mt-1">Focus on what matters most today.</p>
          </div>
          <div className="flex gap-4">
            {daysRemaining !== null && (
              <div className={`flex items-center px-4 py-2 rounded-xl border ${daysRemaining < 30 ? 'bg-red-50 border-red-200 text-red-700' : 'bg-sky-50 border-sky-200 text-sky-700'}`}>
                <span className="font-bold text-xl mr-2">{daysRemaining}</span>
                <span className="text-xs uppercase tracking-wide">Days Left</span>
              </div>
            )}
            <Link href="/upload" className="btn-secondary hidden sm:flex">Upload PDF</Link>
            <Link href="/quiz" className="btn-primary">Start Quiz</Link>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto pr-2">
          {loading ? (
            <div className="flex justify-center items-center h-64">
              <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-sky-500"></div>
            </div>
          ) : error ? (
            <div className="p-4 bg-red-50 border border-red-200 text-red-700 rounded-xl">
              {error}
            </div>
          ) : items.length === 0 ? (
            <div className="text-center mt-20 p-10 bg-white border border-sky-100 rounded-2xl mx-auto max-w-lg">
              <div className="w-16 h-16 bg-sky-50 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-sky-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
              </div>
              <h3 className="text-xl font-medium mb-2 text-slate-800">No data yet</h3>
              <p className="text-slate-600 mb-6">Upload your first study material to generate topics and begin adaptive revision.</p>
              <Link href="/upload" className="btn-primary">Upload PDF</Link>
            </div>
          ) : (
            <div className="space-y-8">
              {/* ── Critical / Needs Revision ── */}
              {critical.length > 0 && (
                <section>
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></div>
                    <h3 className="text-lg font-bold text-red-700">Revise Now</h3>
                    <span className="text-xs text-red-500 bg-red-50 px-2 py-0.5 rounded-full font-medium">{critical.length} topics</span>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                    {critical.map(renderTopicCard)}
                  </div>
                </section>
              )}

              {/* ── Stable / On Track ── */}
              {stable.length > 0 && (
                <section>
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-2 h-2 rounded-full bg-emerald-500"></div>
                    <h3 className="text-lg font-bold text-slate-600">On Track</h3>
                    <span className="text-xs text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full font-medium">{stable.length} topics</span>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                    {stable.map(renderTopicCard)}
                  </div>
                </section>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
