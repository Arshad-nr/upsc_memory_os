'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { TOPIC_LABELS } from '@/lib/types';

export default function OnboardingPage() {
  const router = useRouter();
  const [selectedSubjects, setSelectedSubjects] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const toggleSubject = (key: string) => {
    setSelectedSubjects(prev => 
      prev.includes(key) 
        ? prev.filter(s => s !== key)
        : [...prev, key]
    );
  };

  const handleComplete = async () => {
    setLoading(true);
    setError('');
    try {
      if (selectedSubjects.length > 0) {
        await api.setSubjects(selectedSubjects);
      }
      await api.completeOnboarding();
      router.push('/dashboard');
    } catch (err: any) {
      setError(err.message || 'Failed to complete onboarding');
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-4">
      <div className="max-w-2xl w-full">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-sky-400 to-blue-500 rounded-full mb-4">
            <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
          </div>
          <h1 className="text-3xl md:text-4xl font-bold text-slate-800 mb-3">Customize Your Engine</h1>
          <p className="text-slate-600 text-lg">Select the syllabus areas you find most difficult. We'll prioritize these in your revision queue.</p>
        </div>

        <div className="bg-white border border-sky-100 rounded-3xl shadow-md p-6 md:p-8">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-8">
            {Object.entries(TOPIC_LABELS).map(([key, label]) => {
              const isSelected = selectedSubjects.includes(key);
              return (
                <button
                  key={key}
                  onClick={() => toggleSubject(key)}
                  className={`p-4 rounded-xl text-sm font-medium border transition-colors duration-150 text-left flex flex-col justify-between h-24 ${isSelected ? 'bg-sky-50 border-sky-400 text-sky-800' : 'bg-white border-sky-200 text-slate-700 hover:bg-sky-50 hover:border-sky-300'}`}
                >
                  <div className={`w-4 h-4 rounded-full border transition-colors ${isSelected ? 'border-sky-400 bg-sky-500' : 'border-slate-300 bg-transparent'}`} />
                  {label}
                </button>
              );
            })}
          </div>

          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
              {error}
            </div>
          )}

          <div className="flex flex-col sm:flex-row gap-4 items-center justify-between pt-6 border-t border-sky-100">
            <p className="text-sm text-slate-600">
              {selectedSubjects.length} subjects selected
            </p>
            <div className="flex gap-3 w-full sm:w-auto">
              <button 
                onClick={handleComplete} 
                disabled={loading}
                className="btn-secondary flex-1 sm:flex-none"
              >
                Skip for now
              </button>
              <button 
                onClick={handleComplete} 
                disabled={loading}
                className="btn-primary flex-1 sm:flex-none"
              >
                {loading ? 'Saving...' : 'Complete Setup'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
