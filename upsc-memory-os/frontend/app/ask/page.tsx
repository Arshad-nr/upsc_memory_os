'use client';

import { useState, useRef, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: { page?: number; documentId?: string; topicType?: string }[];
  queryType?: string;
}

export default function AskPage() {
  const router = useRouter();
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [documents, setDocuments] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    api.getDocuments().then(setDocuments).catch(console.error);
  }, []);

  const handleAsk = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || loading) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: question,
    };
    setMessages((prev) => [...prev, userMsg]);
    setQuestion('');
    setLoading(true);

    try {
      const result = await api.ask(question);
      const assistantMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: result.answer,
        sources: result.sources,
        queryType: result.queryType,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      const errorMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `Error: ${err.message || 'Failed to get answer'}`,
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const queryTypeLabel = (qt?: string) => {
    const labels: Record<string, string> = {
      factual: 'Factual', analytical: 'Analytical', current: 'Current Affairs',
      comparative: 'Comparative', definition: 'Definition',
    };
    return qt ? labels[qt] || qt : '';
  };

  const formatSource = (s: { page?: number; documentId?: string; topicType?: string }) => {
    const doc = documents.find(d => d.id === s.documentId);
    const docName = doc ? doc.filename.replace('.pdf', '') : 'Document';
    const topic = s.topicType ? s.topicType.replace(/_/g, ' ') : '';
    return `${docName} (Page ${s.page}) ${topic ? `• ${topic}` : ''}`;
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-sky-100 px-6 py-4 flex items-center justify-between">
        <button onClick={() => router.push('/dashboard')} className="flex items-center gap-2 text-slate-600 hover:text-slate-800 transition-colors duration-150">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
          Dashboard
        </button>
        <h1 className="text-lg font-semibold gradient-text">Ask Your Notes</h1>
        <div className="w-20" />
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 md:px-8 py-6 space-y-6 max-w-4xl mx-auto w-full">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center py-20">
            <div className="w-20 h-20 rounded-full bg-gradient-to-br from-sky-400 to-blue-500 flex items-center justify-center mb-6">
              <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
            </div>
            <h2 className="text-2xl font-bold text-slate-800 mb-2">Ask anything from your notes</h2>
            <p className="text-slate-500 max-w-md">
              Your uploaded PDFs are searchable. Ask factual, analytical, or comparative questions and get cited answers.
            </p>
            <div className="flex flex-wrap gap-2 mt-6">
              {['What are the Fundamental Rights?', 'Explain the Preamble', 'Compare Lok Sabha vs Rajya Sabha'].map((q) => (
                <button key={q} onClick={() => setQuestion(q)}
                  className="px-4 py-2 bg-white border border-sky-200 rounded-2xl text-sm text-slate-600 hover:text-sky-700 hover:bg-sky-50 hover:border-sky-300 transition-colors duration-150">
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => {
          const uniqueSources = Array.from(new Set(msg.sources?.filter(s => s.page).map(formatSource))) || [];
          
          return (
            <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[80%] rounded-2xl px-5 py-4 ${
                msg.role === 'user'
                  ? 'bg-gradient-to-r from-sky-500 to-blue-600 text-white'
                  : 'bg-white border border-sky-100 shadow-sm'
              }`}>
                <div className={`prose prose-sm max-w-none ${msg.role === 'user' ? 'prose-invert' : 'prose-slate'}`}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                </div>
                {msg.sources && msg.sources.length > 0 && (
                  <div className="mt-4 pt-3 border-t border-sky-100 flex flex-wrap gap-2">
                    {msg.queryType && (
                      <span className="px-2 py-0.5 rounded-full bg-sky-50 text-sky-700 text-xs font-medium">
                        {queryTypeLabel(msg.queryType)}
                      </span>
                    )}
                    {uniqueSources.map((sourceLabel, i) => (
                      <span key={i} className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 text-xs capitalize">
                        {sourceLabel}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-white border border-sky-100 shadow-sm px-5 py-4 rounded-2xl">
              <div className="flex items-center gap-2">
                <div className="flex gap-1">
                  <span className="w-2 h-2 bg-sky-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-2 h-2 bg-sky-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-2 h-2 bg-sky-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
                <span className="text-slate-500 text-sm">Searching your notes...</span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-sky-100 bg-white px-4 md:px-8 py-4">
        <form onSubmit={handleAsk} className="max-w-4xl mx-auto flex gap-3">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask a question about your uploaded notes..."
            className="input-field flex-1"
            disabled={loading}
            id="ask-input"
          />
          <button type="submit" disabled={loading || !question.trim()} className="btn-primary whitespace-nowrap" id="ask-submit">
            {loading ? 'Thinking...' : 'Ask'}
          </button>
        </form>
      </div>
    </div>
  );
}
