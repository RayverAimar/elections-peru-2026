import type {
  PartyListItem,
  PartyDetail,
  QuizStartResponse,
  QuizAnswerResponse,
  QuizResultsResponse,
  QuizExplainResponse,
  ChatResponse,
  NewsResponse,
  NewsDetail,
  CandidateNewsProfile,
  EventsResponse,
  EventDetail,
  InvestigaListResponse,
  InvestigaPartyDetail,
} from './types';

const API_BASE = import.meta.env.PUBLIC_API_URL || 'http://localhost:8000';

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    if (res.status === 429) throw new ApiError(429, 'Límite de consultas alcanzado');
    throw new ApiError(res.status, `Error del servidor: ${res.status}`);
  }
  return res.json();
}

// Candidates
export const getCandidates = () => fetchAPI<PartyListItem[]>('/candidates');
export const getCandidate = (id: number) => fetchAPI<PartyDetail>(`/candidates/${id}`);

// Quiz
export const startQuiz = (preferredTopics?: string[]) =>
  fetchAPI<QuizStartResponse>('/quiz/start', {
    method: 'POST',
    body: JSON.stringify({ preferred_topics: preferredTopics || null }),
  });

export const answerQuiz = (sessionId: string, questionId: string, value: number) =>
  fetchAPI<QuizAnswerResponse>('/quiz/answer', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId, question_id: questionId, value }),
  });

export const getQuizResults = (sessionId: string) =>
  fetchAPI<QuizResultsResponse>('/quiz/results', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId }),
  });

export const explainQuiz = (sessionId: string, partyKey: string, topic: string) =>
  fetchAPI<QuizExplainResponse>('/quiz/explain', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId, party_key: partyKey, topic }),
  });

// Chat
export const sendChat = (question: string) =>
  fetchAPI<ChatResponse>('/chat', {
    method: 'POST',
    body: JSON.stringify({ question }),
  });

// News
export const getNews = (params?: {
  party?: string;
  sentiment?: string;
  limit?: number;
  offset?: number;
}) => {
  const qs = new URLSearchParams();
  if (params?.party) qs.set('party', params.party);
  if (params?.sentiment) qs.set('sentiment', params.sentiment);
  if (params?.limit) qs.set('limit', String(params.limit));
  if (params?.offset) qs.set('offset', String(params.offset));
  const query = qs.toString();
  return fetchAPI<NewsResponse>(`/noticias${query ? `?${query}` : ''}`);
};

export const getNewsDetail = (id: number) => fetchAPI<NewsDetail>(`/noticias/${id}`);

export const getCandidateNewsProfile = (party: string) =>
  fetchAPI<CandidateNewsProfile>(`/noticias/profile/${encodeURIComponent(party)}`);

// Events
export const getEvents = (params?: {
  category?: string;
  party?: string;
  severity?: string;
  limit?: number;
  offset?: number;
}) => {
  const qs = new URLSearchParams();
  if (params?.category) qs.set('category', params.category);
  if (params?.party) qs.set('party', params.party);
  if (params?.severity) qs.set('severity', params.severity);
  if (params?.limit) qs.set('limit', String(params.limit));
  if (params?.offset) qs.set('offset', String(params.offset));
  const query = qs.toString();
  return fetchAPI<EventsResponse>(`/events${query ? `?${query}` : ''}`);
};

export const getEventDetail = (id: string) => fetchAPI<EventDetail>(`/events/${id}`);

// Investiga
export const getInvestiga = () => fetchAPI<InvestigaListResponse>('/investiga');
export const getInvestigaDetail = (jneId: number) =>
  fetchAPI<InvestigaPartyDetail>(`/investiga/${jneId}`);

export { ApiError };
