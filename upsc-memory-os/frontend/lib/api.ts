const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

let accessToken: string | null = null;

export function setToken(token: string) { accessToken = token; }
export function getToken() { return accessToken; }
export function clearToken() { accessToken = null; }

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    ...((options.headers as Record<string,string>) || {}),
  };
  if (accessToken) headers['Authorization'] = `Bearer ${accessToken}`;
  if (!(options.body instanceof FormData)) headers['Content-Type'] = 'application/json';

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers, credentials: 'include' });
  if (res.status === 401) {
    // Try refresh
    const refreshRes = await fetch(`${API_BASE}/api/v1/auth/refresh`, { method: 'POST', credentials: 'include' });
    if (refreshRes.ok) {
      const data = await refreshRes.json();
      setToken(data.accessToken);
      headers['Authorization'] = `Bearer ${data.accessToken}`;
      const retry = await fetch(`${API_BASE}${path}`, { ...options, headers, credentials: 'include' });
      if (!retry.ok) throw new Error(`API error: ${retry.status}`);
      return retry.json();
    }
    clearToken();
    if (typeof window !== 'undefined') window.location.href = '/';
    throw new Error('Unauthorized');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    let errorMsg = err.detail || `API error: ${res.status}`;
    if (typeof errorMsg === 'object') {
      errorMsg = JSON.stringify(errorMsg);
    }
    throw new Error(errorMsg);
  }
  return res.json();
}

export const api = {
  // Auth
  register: (data: { email: string; password: string; examDate: string }) =>
    request<{ accessToken: string }>('/api/v1/auth/register', { method: 'POST', body: JSON.stringify(data) }),
  login: (data: { email: string; password: string }) =>
    request<{ accessToken: string }>('/api/v1/auth/login', { method: 'POST', body: JSON.stringify(data) }),

  // Onboarding
  setExamDate: (examDate: string) =>
    request('/api/v1/onboarding/exam-date', { method: 'POST', body: JSON.stringify({ examDate }) }),
  setSubjects: (weakSubjects: string[]) =>
    request('/api/v1/onboarding/subjects', { method: 'POST', body: JSON.stringify({ weakSubjects }) }),
  completeOnboarding: () =>
    request('/api/v1/onboarding/complete', { method: 'POST' }),

  // Documents
  uploadDocument: (file: File, topicCategory: string, sourceType: string) => {
    const form = new FormData();
    form.append('file', file);
    form.append('topic_category', topicCategory);
    form.append('source_type', sourceType);
    return request<{ documentId: string; status: string }>('/api/v1/documents/upload', { method: 'POST', body: form });
  },
  getDocuments: () => request<any[]>('/api/v1/documents'),
  deleteDocument: (id: string) => request(`/api/v1/documents/${id}`, { method: 'DELETE' }),

  // RAG
  ask: (question: string) =>
    request<{ answer: string; sources: any[]; queryType: string }>('/api/v1/ask', { method: 'POST', body: JSON.stringify({ question }) }),

  // Quiz
  getQuizStats: () =>
    request<{ totalFlashcards: number; totalMcqs: number; topicBreakdown: any[] }>('/api/v1/quiz/stats'),
  getQuizTopics: () =>
    request<{ topics: Record<string, string[]> }>('/api/v1/quiz/topics'),
  createQuizSession: (size = 10, cardType?: string, topicType?: string, topicIds?: string[]) => {
    const params = new URLSearchParams();
    if (cardType) params.set('card_type', cardType);
    if (topicType && topicType !== 'all') params.set('topic_type', topicType);
    const qs = params.toString() ? `?${params.toString()}` : '';
    return request<{ sessionId: string; items: any[] }>(`/api/v1/quiz/session${qs}`, {
      method: 'POST',
      body: JSON.stringify({ size, topicIds: topicIds || null }),
    });
  },
  submitAnswer: (data: { sessionId: string; flashcardId: string; answer: string; errorType?: string; timeSpentSec?: number }) =>
    request<{ correct: boolean; score: number; feedback: string }>('/api/v1/quiz/answer', { method: 'POST', body: JSON.stringify(data) }),
  generateFlashcards: (topicType?: string, count = 5, cardType = 'flashcard', topicNames?: string[]) => {
    const params = new URLSearchParams();
    params.set('limit', String(count));
    params.set('card_type', cardType);
    if (topicType) params.set('topic_type', topicType);
    if (topicNames && topicNames.length > 0) params.set('topic_names', topicNames.join(','));
    return request(`/api/v1/quiz/flashcards/generate?${params.toString()}`, { method: 'POST' });
  },

  // Revision
  getDashboard: () =>
    request<{ items: any[]; critical?: any[]; stable?: any[]; daysRemaining: number; totalTopics: number }>('/api/v1/revision/dashboard'),
  getRevisionSession: () =>
    request<{ items: any[]; count: number }>('/api/v1/revision/session'),
};
