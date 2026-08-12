export interface User {
  id: string; email: string; examDate: string; timezone: string; onboardingDone: boolean;
}
export interface Document {
  id: string; filename: string; sourceType: string; topicCategory: string;
  uploadedAt: string; chunkCount: number; ingestionStatus: string; errorMessage?: string;
}
export interface AskResponse {
  answer: string; sources: Source[]; queryType: string; confidence?: number;
}
export interface Source {
  page?: number; documentId?: string; topicType?: string;
}
export interface UrgencyItem {
  topicId: string; topicName: string; topicType: string;
  urgencyScore: number; urgencyTier: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'STABLE';
}
export interface FlashcardItem {
  flashcardId: string; question: string; cardType: string; difficulty: string;
}
export interface QuizResult {
  correct: boolean; score: number; feedback: string;
}
export type TopicType = 'current_affairs' | 'government_schemes' | 'reports_indices' | 'environment' | 'economy' | 'geography' | 'polity' | 'history' | 'static_syllabus';

export const TOPIC_LABELS: Record<string, string> = {
  current_affairs: 'Current Affairs', government_schemes: 'Government Schemes',
  reports_indices: 'Reports & Indices', environment: 'Environment',
  economy: 'Economy', geography: 'Geography', polity: 'Polity',
  history: 'History', static_syllabus: 'Static Syllabus',
  art_and_culture: 'Art & Culture', society: 'Society',
  governance_social_justice: 'Governance & Social Justice',
  international_relations: 'International Relations',
  agriculture: 'Agriculture', science_tech: 'Science & Tech',
  internal_security: 'Internal Security',
  disaster_management: 'Disaster Management',
  ethics: 'Ethics', essay: 'Essay', csat: 'CSAT',
};

export const TIER_COLORS: Record<string, string> = {
  CRITICAL: 'urgency-critical', HIGH: 'urgency-high',
  MEDIUM: 'urgency-medium', STABLE: 'urgency-stable',
};
