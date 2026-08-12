'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import Link from 'next/link';

const TOPIC_LABELS: Record<string, string> = {
  current_affairs: 'Current Affairs', government_schemes: 'Government Schemes',
  reports_indices: 'Reports & Indices', environment: 'Environment',
  economy: 'Economy', geography: 'Geography', polity: 'Polity',
  history: 'History', art_and_culture: 'Art & Culture', society: 'Society',
  governance_social_justice: 'Governance & Social Justice',
  international_relations: 'International Relations',
  agriculture: 'Agriculture', science_tech: 'Science & Tech',
  internal_security: 'Internal Security', disaster_management: 'Disaster Management',
  ethics: 'Ethics', essay: 'Essay', csat: 'CSAT',
  static_syllabus: 'Static Syllabus',
};

type QuizView = 'hub' | 'session';

interface QuizStats {
  totalFlashcards: number;
  totalMcqs: number;
  topicBreakdown: { topicType: string; topicName: string; flashcards: number; mcqs: number }[];
}

export default function QuizPage() {
  const [view, setView] = useState<QuizView>('hub');

  const [stats, setStats] = useState<QuizStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);
  const [selectedTopicType, setSelectedTopicType] = useState<string>('all');
  const [availableTopicNames, setAvailableTopicNames] = useState<Record<string, string[]>>({});
  const [selectedTopicNames, setSelectedTopicNames] = useState<string[]>([]);
  const [generateCount, setGenerateCount] = useState(10);
  const [generating, setGenerating] = useState(false);
  const [generationMsg, setGenerationMsg] = useState('');
  const [hubError, setHubError] = useState('');

  const [session, setSession] = useState<{ sessionId: string; items: any[] } | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [showAnswer, setShowAnswer] = useState(false);
  const [sessionLoading, setSessionLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [sessionError, setSessionError] = useState('');
  const [completed, setCompleted] = useState(false);
  const [score, setScore] = useState(0);
  const [startTime, setStartTime] = useState(Date.now());
  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [sessionCardType, setSessionCardType] = useState<string | undefined>(undefined);

  useEffect(() => { loadStats(); loadTopics(); }, []);

  // Reset topic names when topic type changes
  useEffect(() => { setSelectedTopicNames([]); }, [selectedTopicType]);

  const loadStats = async () => {
    setStatsLoading(true);
    setHubError('');
    try {
      const data = await api.getQuizStats();
      setStats(data);
    } catch (err: any) {
      setHubError(err.message || 'Failed to load quiz stats');
    } finally {
      setStatsLoading(false);
    }
  };

  const loadTopics = async () => {
    try {
      const data = await api.getQuizTopics();
      setAvailableTopicNames(data.topics || {});
    } catch (err: any) {
      console.error('Failed to load topics:', err);
    }
  };

  const toggleTopicName = (name: string) => {
    setSelectedTopicNames(prev =>
      prev.includes(name) ? prev.filter(n => n !== name) : [...prev, name]
    );
  };

  const currentTopicNames = selectedTopicType !== 'all' ? (availableTopicNames[selectedTopicType] || []) : [];

  const handleGenerate = async (cardType: string) => {
    setGenerating(true);
    setHubError('');
    setGenerationMsg(`AI is generating ${cardType === 'mcq' ? 'MCQs' : 'flashcards'}...`);
    try {
      const topicArg = selectedTopicType === 'all' ? undefined : selectedTopicType;
      const namesArg = selectedTopicNames.length > 0 ? selectedTopicNames : undefined;
      await api.generateFlashcards(topicArg, generateCount, cardType, namesArg);
      setGenerationMsg('Done! Refreshing stats...');
      await loadStats();
      setGenerationMsg('');
    } catch (err: any) {
      setHubError(err.message || 'Generation failed');
    } finally {
      setGenerating(false);
      setGenerationMsg('');
    }
  };

  const startSession = async (cardType?: string) => {
    setSessionLoading(true);
    setSessionError('');
    setSessionCardType(cardType);
    try {
      const topicArg = selectedTopicType === 'all' ? undefined : selectedTopicType;
      const data = await api.createQuizSession(10, cardType, topicArg);
      if (!data.items || data.items.length === 0) {
        setSessionError('No cards available. Generate some first!');
        setSessionLoading(false);
        return;
      }
      setSession(data);
      setCurrentIndex(0);
      setCompleted(false);
      setScore(0);
      setShowAnswer(false);
      setSelectedOption(null);
      setStartTime(Date.now());
      setView('session');
    } catch (err: any) {
      setSessionError(err.message || 'Failed to start quiz session');
    } finally {
      setSessionLoading(false);
    }
  };

  const exitSession = () => {
    setView('hub');
    setSession(null);
    setCompleted(false);
    loadStats();
  };

  const handleReveal = () => { setShowAnswer(true); };

  const handleOptionClick = (optionKey: string) => {
    if (showAnswer) return;
    setSelectedOption(optionKey);
    setShowAnswer(true);
  };

  const handleRate = async (correct: boolean, errorType?: string) => {
    if (!session) return;
    const currentItem = session.items[currentIndex];
    const timeSpent = Math.floor((Date.now() - startTime) / 1000);

    setSubmitting(true);
    try {
      const res = await api.submitAnswer({
        sessionId: session.sessionId,
        flashcardId: currentItem.flashcardId,
        answer: '',
        errorType: errorType,
        timeSpentSec: timeSpent
      });

      if (res.correct) setScore(prev => prev + 1);

      if (currentIndex < session.items.length - 1) {
        setCurrentIndex(prev => prev + 1);
        setShowAnswer(false);
        setSelectedOption(null);
        setStartTime(Date.now());
      } else {
        setCompleted(true);
      }
    } catch (err: any) {
      setSessionError(err.message || 'Failed to submit answer');
    } finally {
      setSubmitting(false);
    }
  };

  // ═══════════════════════════════════════════════════════════════════
  //  VIEW 1: QUIZ HUB
  // ═══════════════════════════════════════════════════════════════════
  if (view === 'hub') {
    const totalCards = (stats?.totalFlashcards || 0) + (stats?.totalMcqs || 0);

    return (
      <div className="flex h-screen flex-col text-slate-800">
        <header className="p-4 border-b border-sky-100 bg-white flex justify-between items-center">
          <Link href="/dashboard" className="flex items-center text-slate-600 hover:text-slate-800 transition-colors duration-150">
            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7"></path></svg>
            Dashboard
          </Link>
          <h1 className="text-lg font-bold gradient-text">Quiz Hub</h1>
        </header>

        <main className="flex-1 overflow-y-auto p-4 md:p-8">
          <div className="max-w-3xl mx-auto space-y-6">
            {statsLoading ? (
              <div className="flex justify-center py-12">
                <div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-sky-500"></div>
              </div>
            ) : (
              <>
                {/* Stats Cards */}
                <div className="grid grid-cols-3 gap-4">
                  <div className="glass p-5 text-center">
                    <div className="text-3xl font-black gradient-text">{totalCards}</div>
                    <div className="text-xs text-slate-500 uppercase tracking-wider mt-1">Total Cards</div>
                  </div>
                  <div className="glass p-5 text-center">
                    <div className="text-3xl font-black text-sky-600">{stats?.totalFlashcards || 0}</div>
                    <div className="text-xs text-slate-500 uppercase tracking-wider mt-1">Flashcards</div>
                  </div>
                  <div className="glass p-5 text-center">
                    <div className="text-3xl font-black text-violet-600">{stats?.totalMcqs || 0}</div>
                    <div className="text-xs text-slate-500 uppercase tracking-wider mt-1">MCQs</div>
                  </div>
                </div>

                {/* Cards by Topic */}
                {stats && stats.topicBreakdown.length > 0 && (
                  <div className="glass p-5">
                    <h3 className="text-sm font-bold text-slate-500 uppercase tracking-widest mb-4">Cards by Topic</h3>
                    <div className="space-y-2">
                      {stats.topicBreakdown.map((t) => (
                        <div key={t.topicType} className="flex items-center justify-between py-2 px-3 bg-sky-50 rounded-lg">
                          <span className="text-sm text-slate-700">{TOPIC_LABELS[t.topicType] || t.topicName}</span>
                          <div className="flex gap-3 text-xs">
                            <span className="text-sky-600 font-medium">{t.flashcards} FC</span>
                            <span className="text-violet-600 font-medium">{t.mcqs} MCQ</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* ── Two-Level Topic Selector ── */}
                <div className="glass p-5">
                  <label className="block text-xs font-bold text-slate-500 uppercase tracking-widest mb-2">Focus Topic</label>
                  
                  {/* Level 1: Topic Type */}
                  <select
                    value={selectedTopicType}
                    onChange={(e) => setSelectedTopicType(e.target.value)}
                    className="w-full bg-white border border-sky-200 rounded-xl px-4 py-3 text-slate-800 text-sm focus:outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-400/20 appearance-none cursor-pointer"
                    style={{
                      backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%2394a3b8'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M19 9l-7 7-7-7'/%3E%3C/svg%3E")`,
                      backgroundRepeat: 'no-repeat',
                      backgroundPosition: 'right 12px center',
                      backgroundSize: '20px',
                    }}
                  >
                    <option value="all">All Topics (sorted by urgency)</option>
                    {Object.entries(TOPIC_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>

                  {/* Level 2: Topic Names (multi-select chips) */}
                  {selectedTopicType !== 'all' && currentTopicNames.length > 0 && (
                    <div className="mt-3">
                      <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">
                        Specific Topics (optional — select one or more)
                      </label>
                      <div className="flex flex-wrap gap-2">
                        {currentTopicNames.map((name) => {
                          const isSelected = selectedTopicNames.includes(name);
                          return (
                            <button
                              key={name}
                              onClick={() => toggleTopicName(name)}
                              className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-all duration-150 ${
                                isSelected
                                  ? 'bg-sky-500 text-white border-sky-500 shadow-sm'
                                  : 'bg-white text-slate-600 border-slate-200 hover:border-sky-300 hover:text-sky-700'
                              }`}
                            >
                              {name}
                              {isSelected && (
                                <span className="ml-1.5">✕</span>
                              )}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {selectedTopicType !== 'all' && currentTopicNames.length === 0 && (
                    <p className="text-slate-400 text-xs mt-2 italic">No specific topics found for this category. Upload a document first.</p>
                  )}

                  {selectedTopicType !== 'all' && (
                    <p className="text-sky-700 text-xs mt-2">
                      Focused on: <strong>{TOPIC_LABELS[selectedTopicType]}</strong>
                      {selectedTopicNames.length > 0 && (
                        <span> → <strong>{selectedTopicNames.join(', ')}</strong></span>
                      )}
                    </p>
                  )}
                </div>

                {/* Start Session */}
                <div className="glass p-6">
                  <h3 className="text-lg font-bold text-slate-800 mb-1">Start a Quiz Session</h3>
                  <p className="text-slate-500 text-sm mb-4">
                    {selectedTopicType === 'all'
                      ? 'Cards sorted by urgency — weakest topics first.'
                      : selectedTopicNames.length > 0
                        ? `Only cards from: ${selectedTopicNames.join(', ')}`
                        : `Only ${TOPIC_LABELS[selectedTopicType]} cards will appear.`}
                  </p>
                  {totalCards === 0 ? (
                    <p className="text-slate-500 text-sm">No cards available yet. Generate some below first!</p>
                  ) : (
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                      <button onClick={() => startSession()} disabled={sessionLoading} className="btn-primary py-4 font-bold">
                        {sessionLoading ? 'Starting...' : 'All Cards'}
                      </button>
                      <button onClick={() => startSession('flashcard')} disabled={sessionLoading || (stats?.totalFlashcards || 0) === 0} className="btn-secondary py-4 font-bold">
                        Flashcards Only
                      </button>
                      <button onClick={() => startSession('mcq')} disabled={sessionLoading || (stats?.totalMcqs || 0) === 0} className="btn-secondary py-4 font-bold">
                        MCQs Only
                      </button>
                    </div>
                  )}
                  {sessionError && <p className="text-red-600 text-sm mt-3">{sessionError}</p>}
                </div>

                {/* Generate Cards */}
                <div className="glass p-6">
                  <h3 className="text-lg font-bold text-slate-800 mb-1">Generate New Cards</h3>
                  <p className="text-slate-500 text-sm mb-5">AI will extract study cards from your uploaded documents.</p>
                  <div className="mb-5">
                    <label className="block text-xs font-bold text-slate-500 uppercase tracking-widest mb-2">Number of Cards</label>
                    <select
                      value={generateCount}
                      onChange={(e) => setGenerateCount(Number(e.target.value))}
                      className="w-full sm:w-48 bg-white border border-sky-200 rounded-xl px-4 py-3 text-slate-800 text-sm focus:outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-400/20 appearance-none cursor-pointer"
                      style={{
                        backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%2394a3b8'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M19 9l-7 7-7-7'/%3E%3C/svg%3E")`,
                        backgroundRepeat: 'no-repeat',
                        backgroundPosition: 'right 12px center',
                        backgroundSize: '20px',
                      }}
                    >
                      <option value={5}>5 cards</option>
                      <option value={10}>10 cards</option>
                      <option value={15}>15 cards</option>
                    </select>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <button onClick={() => handleGenerate('flashcard')} disabled={generating} className="btn-primary py-4 text-base font-bold flex items-center justify-center">
                      {generating && generationMsg.includes('flashcard') ? (
                        <span className="flex items-center">
                          <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                          {generationMsg}
                        </span>
                      ) : (
                        <>
                          <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path></svg>
                          Generate Flashcards
                        </>
                      )}
                    </button>
                    <button onClick={() => handleGenerate('mcq')} disabled={generating} className="py-4 text-base font-bold flex items-center justify-center rounded-xl border border-violet-300 bg-violet-50 text-violet-700 hover:bg-violet-100 hover:border-violet-400 transition-colors duration-150 disabled:opacity-50">
                      {generating && generationMsg.includes('MCQ') ? (
                        <span className="flex items-center">
                          <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-violet-700" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                          {generationMsg}
                        </span>
                      ) : (
                        <>
                          <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                          Generate MCQs
                        </>
                      )}
                    </button>
                  </div>
                  {hubError && <p className="text-red-600 text-sm mt-4">{hubError}</p>}
                </div>
              </>
            )}
          </div>
        </main>
      </div>
    );
  }

  // ═══════════════════════════════════════════════════════════════════
  //  VIEW 2: ACTIVE SESSION
  // ═══════════════════════════════════════════════════════════════════

  if (sessionLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-sky-500"></div>
      </div>
    );
  }

  if (completed) {
    return (
      <div className="flex h-screen items-center justify-center p-4">
        <div className="glass p-8 max-w-md w-full text-center">
          <div className="w-24 h-24 bg-sky-50 rounded-full flex items-center justify-center mx-auto mb-6">
            <span className="text-3xl font-black text-sky-700">{score}/{session?.items.length}</span>
          </div>
          <h2 className="text-2xl font-bold text-slate-800 mb-2">Session Complete!</h2>
          <p className="text-slate-600 mb-8">Your revision weights have been automatically adjusted based on your performance.</p>
          <div className="flex gap-4 justify-center">
            <button onClick={() => startSession(sessionCardType)} className="btn-primary">Another Round</button>
            <button onClick={exitSession} className="btn-secondary">Quiz Hub</button>
          </div>
        </div>
      </div>
    );
  }

  const currentItem = session?.items[currentIndex];

  let parsedMCQ: any = null;
  if (currentItem?.cardType === 'mcq' && currentItem?.answer) {
    try { parsedMCQ = JSON.parse(currentItem.answer); } catch (e) { console.error("Failed to parse MCQ answer", e); }
  }

  return (
    <div className="flex h-screen flex-col text-slate-800">
      <header className="p-4 border-b border-sky-100 bg-white flex justify-between items-center">
        <button onClick={exitSession} className="flex items-center text-slate-600 hover:text-slate-800 transition-colors duration-150">
          <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7"></path></svg>
          Exit Quiz
        </button>
        <div className="flex items-center gap-3">
          {currentItem?.cardType === 'mcq' && (
            <span className="text-xs font-bold uppercase tracking-wider px-2 py-1 bg-violet-50 rounded text-violet-700">MCQ</span>
          )}
          <div className="text-sm font-medium px-3 py-1 bg-sky-50 rounded-full text-sky-700">
            {currentIndex + 1} / {session?.items.length}
          </div>
        </div>
      </header>

      <main className="flex-1 flex flex-col items-center justify-center p-4">
        <div className="w-full max-w-2xl">
          <div className="glass w-full min-h-[300px] flex flex-col items-center justify-center p-8 md:p-12 text-center relative overflow-hidden">
            <span className="absolute top-4 left-4 text-xs font-bold uppercase tracking-wider px-2 py-1 bg-sky-50 rounded text-sky-700">
              {currentItem?.topicType?.replace(/_/g, ' ')}
            </span>
            <span className="absolute top-4 right-4 text-xs font-bold uppercase tracking-wider px-2 py-1 bg-blue-50 rounded text-blue-700">
              {currentItem?.difficulty}
            </span>

            <h3 className="text-2xl md:text-3xl font-medium leading-relaxed mb-6 whitespace-pre-wrap text-slate-800">
              {currentItem?.question}
            </h3>

            {parsedMCQ && (
              <div className="w-full mt-4 flex flex-col gap-3 text-left">
                {Object.entries(parsedMCQ.options).map(([key, text]) => {
                  const isSelected = selectedOption === key;
                  const isCorrect = parsedMCQ.correct === key;
                  let btnClass = "p-4 rounded-xl border text-left transition-colors duration-150 flex items-start gap-3 ";

                  if (!showAnswer) {
                    btnClass += "bg-white border-sky-200 hover:bg-sky-50 hover:border-sky-300 text-slate-700 cursor-pointer";
                  } else {
                    btnClass += "cursor-default ";
                    if (isCorrect) {
                      btnClass += "bg-emerald-50 border-emerald-400 text-emerald-800";
                    } else if (isSelected && !isCorrect) {
                      btnClass += "bg-red-50 border-red-300 text-red-700";
                    } else {
                      btnClass += "bg-slate-50 border-slate-200 text-slate-500 opacity-50";
                    }
                  }

                  return (
                    <button key={key} onClick={() => handleOptionClick(key)} className={btnClass} disabled={showAnswer}>
                      <span className="font-bold w-6 h-6 flex-shrink-0 flex items-center justify-center bg-sky-50 rounded text-sm text-sky-700">{key}</span>
                      <span>{text as string}</span>
                    </button>
                  );
                })}
              </div>
            )}

            {showAnswer && (
              <div className="w-full mt-6 pt-6 border-t border-sky-100">
                {parsedMCQ ? (
                  <div className="mb-8">
                    <p className="text-lg text-slate-700 text-left whitespace-pre-wrap">
                      <span className="font-bold text-sky-700 mr-2 block mb-2">Explanation:</span>
                      {parsedMCQ.explanation}
                    </p>
                  </div>
                ) : (
                  <p className="text-lg text-slate-700 mb-8 whitespace-pre-wrap">{currentItem?.answer}</p>
                )}

                {parsedMCQ ? (
                  <div className="flex flex-col items-center">
                    {selectedOption === parsedMCQ.correct ? (
                      <div className="w-full">
                        <div className="mb-4 inline-flex items-center px-4 py-1.5 bg-emerald-50 text-emerald-700 rounded-full text-sm font-bold border border-emerald-200">
                          <svg className="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path></svg>
                          Correct!
                        </div>
                        <button onClick={() => handleRate(true, 'correct')} disabled={submitting} className="btn-primary w-full py-4 text-lg font-bold">
                          {submitting ? 'Saving...' : 'Next Question'}
                        </button>
                      </div>
                    ) : (
                      <div className="w-full">
                        <h4 className="text-sm font-bold text-red-600 uppercase tracking-widest mb-4">You got this wrong. Why?</h4>
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                          <button onClick={() => handleRate(false, 'careless_mistake')} disabled={submitting} className="p-3 bg-white hover:bg-sky-50 border border-sky-200 hover:border-sky-300 rounded-xl transition-colors duration-150 text-sm font-medium text-slate-700">
                            Careless Mistake
                          </button>
                          <button onClick={() => handleRate(false, 'confused_similar')} disabled={submitting} className="p-3 bg-orange-50 hover:bg-orange-100 border border-orange-200 rounded-xl transition-colors duration-150 text-orange-700 text-sm font-medium">
                            Confused Concepts
                          </button>
                          <button onClick={() => handleRate(false, 'complete_blank')} disabled={submitting} className="p-3 bg-red-50 hover:bg-red-100 border border-red-200 rounded-xl transition-colors duration-150 text-red-700 text-sm font-medium">
                            Didn't Know It
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <>
                    <h4 className="text-sm font-bold text-slate-500 uppercase tracking-widest mb-4">Rate Your Recall</h4>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                      <button onClick={() => handleRate(false, 'complete_blank')} disabled={submitting} className="p-3 bg-red-50 hover:bg-red-100 border border-red-200 rounded-xl transition-colors duration-150 text-red-700 text-sm font-medium">
                        Blanked
                      </button>
                      <button onClick={() => handleRate(false, 'confused_similar')} disabled={submitting} className="p-3 bg-orange-50 hover:bg-orange-100 border border-orange-200 rounded-xl transition-colors duration-150 text-orange-700 text-sm font-medium">
                        Confused
                      </button>
                      <button onClick={() => handleRate(false, 'partial_recall')} disabled={submitting} className="p-3 bg-amber-50 hover:bg-amber-100 border border-amber-200 rounded-xl transition-colors duration-150 text-amber-700 text-sm font-medium">
                        Partial
                      </button>
                      <button onClick={() => handleRate(true, 'correct')} disabled={submitting} className="p-3 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 rounded-xl transition-colors duration-150 text-emerald-700 text-sm font-medium">
                        Perfect
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}

            {!showAnswer && !parsedMCQ && (
              <button onClick={handleReveal} className="mt-8 px-8 py-3 bg-white hover:bg-sky-50 border border-sky-200 hover:border-sky-300 rounded-xl font-medium transition-colors duration-150 text-slate-700">
                Reveal Answer
              </button>
            )}
          </div>
        </div>

        {sessionError && <p className="text-red-600 text-sm mt-4">{sessionError}</p>}
      </main>
    </div>
  );
}
