'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import Link from 'next/link';

// ── Topic Categories (matches backend TopicType enum exactly) ────────
const TOPIC_CATEGORIES: Record<string, string> = {
  current_affairs: 'Current Affairs',
  government_schemes: 'Government Schemes',
  reports_indices: 'Reports & Indices',
  history: 'History',
  art_and_culture: 'Art & Culture',
  geography: 'Geography',
  society: 'Society',
  polity: 'Polity & Constitution',
  governance_social_justice: 'Governance & Social Justice',
  international_relations: 'International Relations',
  economy: 'Economy',
  agriculture: 'Agriculture',
  environment: 'Environment & Ecology',
  science_tech: 'Science & Technology',
  internal_security: 'Internal Security',
  disaster_management: 'Disaster Management',
  ethics: 'Ethics & Integrity',
  essay: 'Essay',
  csat: 'CSAT',
  static_syllabus: 'General / Static Syllabus',
};

const TOPIC_GROUPS = [
  { label: 'Dynamic / Current', topics: ['current_affairs', 'government_schemes', 'reports_indices'] },
  { label: 'GS Paper 1', topics: ['history', 'art_and_culture', 'geography', 'society'] },
  { label: 'GS Paper 2', topics: ['polity', 'governance_social_justice', 'international_relations'] },
  { label: 'GS Paper 3', topics: ['economy', 'agriculture', 'environment', 'science_tech', 'internal_security', 'disaster_management'] },
  { label: 'GS Paper 4 & Others', topics: ['ethics', 'essay', 'csat', 'static_syllabus'] },
];

const SOURCE_TYPES = [
  { value: 'newspaper', label: 'Newspaper / Current Affairs', icon: '📰', desc: 'The Hindu, Indian Express, PIB' },
  { value: 'coaching_notes', label: 'Coaching Material', icon: '📚', desc: 'Vision IAS, ForumIAS, Vajiram' },
  { value: 'handwritten', label: 'Handwritten Notes', icon: '✍️', desc: 'Your personal handwritten notes' },
  { value: 'official_report', label: 'Official Report / Document', icon: '🏛️', desc: 'Government reports, policies, budgets' },
];

const formatDate = (dateStr?: string) => {
  if (!dateStr) return 'Unknown Date';
  try {
    // Standardize database timestamp formats to ISO 8601
    const cleanStr = dateStr.includes(' ') ? dateStr.replace(' ', 'T') : dateStr;
    const date = new Date(cleanStr);
    if (isNaN(date.getTime())) {
      return 'Invalid Date';
    }
    return date.toLocaleDateString(undefined, { dateStyle: 'medium' });
  } catch (e) {
    return 'Invalid Date';
  }
};

export default function UploadPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [sourceType, setSourceType] = useState('');
  const [topicCategory, setTopicCategory] = useState('');

  const [isDragging, setIsDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const [documents, setDocuments] = useState<any[]>([]);
  const [docsLoading, setDocsLoading] = useState(true);
  const [docsError, setDocsError] = useState('');
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchDocs = async () => {
    try {
      setDocsLoading(true);
      const data = await api.getDocuments();
      setDocuments(data);
    } catch (err: any) {
      setDocsError(err.message || 'Failed to load documents');
    } finally {
      setDocsLoading(false);
    }
  };

  useEffect(() => {
    fetchDocs();
  }, []);

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this document? This will permanently remove all associated chunks, vector embeddings, and flashcards.')) {
      return;
    }
    setDeletingId(id);
    try {
      await api.deleteDocument(id);
      setDocuments((prev) => prev.filter((doc) => doc.id !== id));
    } catch (err: any) {
      alert(err.message || 'Failed to delete document');
    } finally {
      setDeletingId(null);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError('');
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
      setError('');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) { setError('Please select a PDF file'); return; }
    if (!topicCategory) { setError('Please select a topic category'); return; }
    if (!sourceType) { setError('Please select a source type'); return; }

    console.log(`[Upload] Upload button clicked! Starting upload for: ${file.name}`);
    const startTime = Date.now();

    setLoading(true);
    setError('');

    try {
      await api.uploadDocument(file, topicCategory, sourceType);
      console.log(`[Upload] SUCCESS: Received 200 OK from backend after ${(Date.now() - startTime) / 1000}s`);
      setSuccess(true);
      setFile(null);
      setTopicCategory('');
      setSourceType('');
      fetchDocs();
      setTimeout(() => { router.push('/dashboard'); }, 2500);
    } catch (err: any) {
      setError(err.message || 'Failed to upload document');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen">
      <main className="p-4 md:p-8">
        <div className="max-w-3xl mx-auto">
          {/* Header */}
          <div className="flex items-center mb-8">
            <Link href="/dashboard" className="mr-4 p-2.5 rounded-full bg-white border border-sky-200 hover:bg-sky-50 hover:border-sky-300 transition-colors duration-150">
              <svg className="w-5 h-5 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"></path></svg>
            </Link>
            <div>
              <h1 className="text-3xl md:text-4xl font-bold text-slate-800">Upload Study Material</h1>
              <p className="text-slate-600 text-sm mt-1">Feed your AI memory engine with UPSC documents</p>
            </div>
          </div>

          {/* Main Card */}
          <div className="bg-white border border-sky-100 rounded-3xl p-6 md:p-10 shadow-md">
            {success ? (
              <div className="text-center py-16">
                <div className="w-24 h-24 bg-emerald-50 rounded-full flex items-center justify-center mx-auto mb-6">
                  <svg className="w-12 h-12 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path></svg>
                </div>
                <h2 className="text-3xl font-bold text-slate-800 mb-3">Upload Complete!</h2>
                <p className="text-slate-600 mb-2 text-lg">Your document has been queued for AI processing.</p>
                <p className="text-slate-500 text-sm">Topics & chunks will be extracted automatically.</p>
                <div className="mt-8 flex items-center justify-center gap-2 text-sky-600 font-medium">
                  <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg>
                  Redirecting to dashboard...
                </div>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-8">

                {/* Step 1: File Upload Zone */}
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <span className="w-7 h-7 rounded-full bg-sky-50 text-sky-700 text-xs font-bold flex items-center justify-center border border-sky-200">1</span>
                    <h3 className="text-lg font-semibold text-slate-800">Select PDF File</h3>
                  </div>
                  <div
                    className={`border-2 border-dashed rounded-2xl p-10 text-center transition-colors duration-150 ${isDragging ? 'border-sky-400 bg-sky-50' : 'border-sky-200 hover:border-sky-300 bg-white'} ${file ? 'border-sky-400 bg-sky-50' : ''}`}
                    onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                    onDragLeave={() => setIsDragging(false)}
                    onDrop={handleDrop}
                  >
                    <input type="file" id="file-upload" accept=".pdf" className="hidden" onChange={handleFileChange} />

                    {file ? (
                      <div className="flex flex-col items-center">
                        <div className="w-14 h-14 bg-sky-50 rounded-2xl flex items-center justify-center mb-4">
                          <svg className="w-7 h-7 text-sky-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                        </div>
                        <p className="text-lg font-semibold text-slate-800 mb-1">{file.name}</p>
                        <p className="text-sm text-slate-500 mb-4">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                        <label htmlFor="file-upload" className="text-sky-600 hover:text-sky-700 text-sm font-semibold cursor-pointer underline underline-offset-4">
                          Change File
                        </label>
                      </div>
                    ) : (
                      <label htmlFor="file-upload" className="cursor-pointer flex flex-col items-center group">
                        <div className="w-16 h-16 bg-sky-50 rounded-full flex items-center justify-center mb-4 group-hover:bg-sky-100 transition-colors duration-150">
                          <svg className="w-8 h-8 text-sky-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"></path></svg>
                        </div>
                        <p className="text-lg font-medium text-slate-700 mb-1">Click to upload or drag and drop</p>
                        <p className="text-sm text-slate-500">PDF files only, up to 50MB</p>
                      </label>
                    )}
                  </div>
                </div>

                {/* Step 2: Topic Category Dropdown */}
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <span className="w-7 h-7 rounded-full bg-sky-50 text-sky-700 text-xs font-bold flex items-center justify-center border border-sky-200">2</span>
                    <h3 className="text-lg font-semibold text-slate-800">Topic Category</h3>
                  </div>
                  <select
                    required
                    className="w-full px-4 py-3.5 bg-white border border-sky-200 rounded-xl text-slate-800 focus:outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-400/20 transition-colors duration-150 appearance-none cursor-pointer"
                    style={{
                      backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%2394a3b8'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M19 9l-7 7-7-7'/%3E%3C/svg%3E")`,
                      backgroundRepeat: 'no-repeat',
                      backgroundPosition: 'right 12px center',
                      backgroundSize: '20px',
                    }}
                    value={topicCategory}
                    onChange={(e) => setTopicCategory(e.target.value)}
                  >
                    <option value="" disabled>— Select UPSC topic category —</option>
                    {TOPIC_GROUPS.map((group) => (
                      <optgroup key={group.label} label={group.label}>
                        {group.topics.map((key) => (
                          <option key={key} value={key}>{TOPIC_CATEGORIES[key]}</option>
                        ))}
                      </optgroup>
                    ))}
                  </select>
                  <p className="text-xs text-slate-500 mt-2 ml-1">This determines which GS Paper and decay rate applies to your flashcards.</p>
                </div>

                {/* Step 3: Source Type */}
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <span className="w-7 h-7 rounded-full bg-sky-50 text-sky-700 text-xs font-bold flex items-center justify-center border border-sky-200">3</span>
                    <h3 className="text-lg font-semibold text-slate-800">Source Type</h3>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {SOURCE_TYPES.map((source) => (
                      <button
                        key={source.value}
                        type="button"
                        onClick={() => setSourceType(source.value)}
                        className={`p-4 rounded-xl border text-left transition-colors duration-150 ${
                          sourceType === source.value
                            ? 'bg-sky-50 border-sky-400'
                            : 'bg-white border-sky-200 hover:bg-sky-50 hover:border-sky-300'
                        }`}
                      >
                        <div className="flex items-start gap-3">
                          <span className="text-2xl">{source.icon}</span>
                          <div className="flex-1 min-w-0">
                            <p className={`font-semibold text-sm ${sourceType === source.value ? 'text-sky-700' : 'text-slate-700'}`}>
                              {source.label}
                            </p>
                            <p className="text-xs text-slate-500 mt-0.5">{source.desc}</p>
                          </div>
                          {sourceType === source.value && (
                            <svg className="w-5 h-5 text-sky-500 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                            </svg>
                          )}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Error */}
                {error && (
                  <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm flex items-center gap-3">
                    <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                    {error}
                  </div>
                )}

                {/* Submit */}
                <div className="pt-4 border-t border-sky-100">
                  <button
                    type="submit"
                    disabled={loading || !file || !topicCategory || !sourceType}
                    className={`w-full py-4 rounded-xl font-bold text-lg transition-colors duration-150 ${
                      (!loading && file && topicCategory && sourceType)
                        ? 'bg-gradient-to-r from-sky-500 to-blue-600 text-white hover:from-sky-400 hover:to-blue-500 active:scale-[0.98]'
                        : 'bg-slate-100 text-slate-500 cursor-not-allowed'
                    }`}
                  >
                    {loading ? (
                      <span className="flex items-center justify-center gap-3">
                        <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg>
                        Uploading & Processing...
                      </span>
                    ) : (
                      '🚀 Upload to Memory OS'
                    )}
                  </button>
                </div>
              </form>
            )}
          </div>

          {/* Manage Documents Card */}
          <div className="bg-white border border-sky-100 rounded-3xl p-6 md:p-10 shadow-md mt-8">
            <h2 className="text-2xl font-bold text-slate-800 mb-2">Manage Documents</h2>
            <p className="text-slate-600 text-sm mb-6">View ingestion progress or delete uploaded files.</p>
            
            {docsLoading ? (
              <div className="flex justify-center items-center py-8">
                <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-sky-500"></div>
              </div>
            ) : docsError ? (
              <div className="p-4 bg-red-50 border border-red-200 text-red-700 rounded-xl text-sm">
                {docsError}
              </div>
            ) : documents.length === 0 ? (
              <div className="text-center py-8 border border-dashed border-sky-100 rounded-2xl bg-slate-50/50">
                <p className="text-slate-500 text-sm">No documents uploaded yet.</p>
              </div>
            ) : (
              <div className="space-y-4">
                {documents.map((doc) => (
                  <div key={doc.id} className="flex flex-col sm:flex-row sm:items-center justify-between p-4 border border-sky-100 rounded-2xl bg-white hover:bg-sky-50/20 transition-colors duration-150">
                    <div className="flex-1 min-w-0 mr-4">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-semibold text-slate-800 truncate text-base" title={doc.filename}>
                          {doc.filename}
                        </span>
                        {doc.topicCategory && (
                          <span className="bg-sky-50 border border-sky-100 text-sky-700 text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-md font-medium">
                            {TOPIC_CATEGORIES[doc.topicCategory] || doc.topicCategory}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 text-xs text-slate-500 mt-1 flex-wrap">
                        <span>Uploaded: {formatDate(doc.uploadedAt)}</span>
                        <span>•</span>
                        <span>Chunks: {doc.chunkCount || 0}</span>
                        <span>•</span>
                        <span className="capitalize">{(doc.sourceType || '').replace('_', ' ')}</span>
                      </div>
                      {doc.ingestionStatus === 'failed' && doc.errorMessage && (
                        <p className="text-xs text-red-500 mt-1.5 bg-red-50/50 border border-red-100 rounded-lg p-2 font-mono">
                          Error: {doc.errorMessage}
                        </p>
                      )}
                    </div>
                    
                    <div className="flex items-center gap-3 mt-3 sm:mt-0 flex-shrink-0">
                      {/* Ingestion Status Badges */}
                      {doc.ingestionStatus === 'complete' && (
                        <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-100">
                          <span className="w-1.5 h-1.5 mr-1.5 rounded-full bg-emerald-500"></span>
                          Complete
                        </span>
                      )}
                      {(doc.ingestionStatus === 'processing' || doc.ingestionStatus === 'pending') && (
                        <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-100 animate-pulse">
                          <span className="w-1.5 h-1.5 mr-1.5 rounded-full bg-amber-500"></span>
                          Processing
                        </span>
                      )}
                      {doc.ingestionStatus === 'failed' && (
                        <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-red-50 text-red-700 border border-red-100">
                          <span className="w-1.5 h-1.5 mr-1.5 rounded-full bg-red-500"></span>
                          Failed
                        </span>
                      )}
                      
                      {/* Delete Button */}
                      <button
                        onClick={() => handleDelete(doc.id)}
                        disabled={deletingId === doc.id}
                        type="button"
                        className={`p-2 rounded-xl text-red-500 hover:text-red-700 hover:bg-red-50 border border-transparent hover:border-red-100 transition-all duration-150 ${deletingId === doc.id ? 'opacity-50 cursor-not-allowed' : ''}`}
                        title="Delete Document"
                      >
                        {deletingId === doc.id ? (
                          <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg>
                        ) : (
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                        )}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <p className="text-center text-slate-500 text-xs mt-6">
            Your PDF will be chunked, embedded, and indexed by the AI engine automatically.
          </p>
        </div>
      </main>
    </div>
  );
}
