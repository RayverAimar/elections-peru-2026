// Mirrors backend Pydantic models from app/models/

// --- Candidates ---

export interface Candidate {
  full_name: string;
  position: string;
  document_number?: string;
  status?: string;
  photo_url?: string;
}

export interface PresidentialFormula {
  president?: Candidate;
  first_vice_president?: Candidate;
  second_vice_president?: Candidate;
}

export interface GovernmentPlan {
  plan_id?: number;
  full_plan_url?: string;
  summary_plan_url?: string;
}

export interface PartyListItem {
  id: number;
  name: string;
  presidential_candidate: string;
  photo_url?: string;
}

export interface PartyDetail {
  id: number;
  name: string;
  presidential_formula: PresidentialFormula;
  government_plan?: GovernmentPlan;
  positions?: Record<string, TopicPosition>;
}

export interface TopicPosition {
  summary: string;
  key_proposals: string[];
  axes: Record<string, number>;
  confidence: 'high' | 'medium' | 'low';
}

// --- Quiz ---

export interface QuizQuestion {
  id: string;
  text: string;
  topic: string;
  topic_display: string;
  hint?: string;
}

export interface QuizProgress {
  current: number;
  min_questions: number;
  max_questions: number;
  confidence: number | null;
}

export interface QuizStartResponse {
  session_id: string;
  question: QuizQuestion;
  progress: QuizProgress;
  can_finish: boolean;
}

export interface QuizAnswerResponse {
  question: QuizQuestion | null;
  progress: QuizProgress;
  can_finish: boolean;
  finished: boolean;
}

export interface EvidenceItem {
  question: string;
  user_answer: number;
  party_score: number;
  explanation: string;
}

export interface CandidateMatch {
  party: string;
  candidate: string;
  photo_url?: string;
  score: number;
  agreement_by_topic: Record<string, number>;
  evidence: EvidenceItem[];
}

export interface QuizResultsResponse {
  top_candidates: CandidateMatch[];
  user_profile: Record<string, number>;
  total_questions_answered: number;
}

export interface QuizExplainResponse {
  explanation: string;
  sources: string[];
}

// --- Chat ---

export interface ChatRequest {
  question: string;
}

export interface ChatSourceItem {
  name: string;
  source_type: 'plan' | 'news' | 'event';
  url?: string;
}

export interface ChatResponse {
  answer: string;
  sources: ChatSourceItem[];
}

// --- News ---

export interface NewsItem {
  id: number;
  title: string;
  url: string;
  source_name: string;
  published_at?: string;
  sentiment_label: string;
  adverse_categories: string[];
}

export interface NewsDetail extends NewsItem {
  content?: string;
  description?: string;
  mentions: string[];
}

export interface NewsResponse {
  total: number;
  articles: NewsItem[];
}

export interface CandidateNewsProfile {
  party: string;
  candidate: string;
  total_articles: number;
  adverse_count: number;
  neutral_count: number;
  positive_count: number;
  adverse_categories: Record<string, number>;
  controversial: NewsItem[];
  favorable: NewsItem[];
  recent: NewsItem[];
}

// --- Chat UI ---

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: ChatSourceItem[];
}

// --- Topics metadata ---

export interface TopicMeta {
  name: string;
  description: string;
  axes: string[];
}

// --- Political Events ---

export interface StanceEvidence {
  quote: string;
  source_description: string;
  source_url?: string;
}

export interface EventPartyStance {
  party_name: string;
  stance: 'supported' | 'opposed' | 'abstained' | 'involved';
  detail?: string;
  evidence?: StanceEvidence[];
}

export interface EventItem {
  id: string;
  title: string;
  event_date?: string;
  category: string;
  severity: string;
  description: string;
  sources: string[];
}

export interface EventDetail extends EventItem {
  why_it_matters: string;
  party_stances: EventPartyStance[];
}

export interface EventsResponse {
  total: number;
  events: EventItem[];
}

// --- Investiga ---

export interface CategoryCount {
  category: string;
  count: number;
}

export interface InvestigaPartyItem {
  party_name: string;
  jne_id: number;
  presidential_candidate: string;
  photo_url?: string;
  cuestionable_count: number;
  category_counts: CategoryCount[];
}

export interface InvestigaListResponse {
  parties: InvestigaPartyItem[];
}

export interface InvestigaEventStance {
  event_id: string;
  title: string;
  event_date?: string;
  category: string;
  severity: string;
  description: string;
  why_it_matters: string;
  sources: string[];
  stance: string;
  stance_detail?: string;
  evidence: StanceEvidence[];
}

export interface InvestigaPartyDetail {
  party_name: string;
  jne_id: number;
  presidential_candidate: string;
  photo_url?: string;
  cuestionable_count: number;
  events: InvestigaEventStance[];
}
