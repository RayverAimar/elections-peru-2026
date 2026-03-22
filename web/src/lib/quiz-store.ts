import { signal, computed } from '@preact/signals';
import type { QuizQuestion, QuizProgress, QuizResultsResponse } from './types';

export type QuizStatus = 'idle' | 'loading' | 'active' | 'answering' | 'finishing' | 'results' | 'error';

const SESSION_KEY = 'brujula_session_id';
const RESULTS_KEY = 'brujula_results';

// --- Signals ---
export const status = signal<QuizStatus>('idle');
export const sessionId = signal<string | null>(null);
export const currentQuestion = signal<QuizQuestion | null>(null);
export const progress = signal<QuizProgress>({ current: 0, min_questions: 8, max_questions: 20, confidence: null });
export const canFinish = signal(false);
export const errorMsg = signal<string | null>(null);
export const results = signal<QuizResultsResponse | null>(null);

// --- Computed ---
export const progressPercent = computed(() => {
  const p = progress.value;
  return p.max_questions > 0 ? (p.current / p.max_questions) * 100 : 0;
});

export const confidenceLabel = computed(() => {
  const c = progress.value.confidence;
  if (c === null || c === undefined) return null;
  if (c >= 3.0) return 'Alta';
  if (c >= 1.5) return 'Media';
  return 'Baja';
});

// --- Session persistence ---
export function saveSession(id: string) {
  sessionId.value = id;
  try { sessionStorage.setItem(SESSION_KEY, id); } catch {}
}

export function restoreSession(): string | null {
  try {
    const stored = sessionStorage.getItem(SESSION_KEY);
    if (stored) sessionId.value = stored;
    return stored;
  } catch { return null; }
}

export function saveResults(r: QuizResultsResponse) {
  results.value = r;
  try { sessionStorage.setItem(RESULTS_KEY, JSON.stringify(r)); } catch {}
}

export function loadResults(): QuizResultsResponse | null {
  if (results.value) return results.value;
  try {
    const stored = sessionStorage.getItem(RESULTS_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      results.value = parsed;
      return parsed;
    }
  } catch {}
  return null;
}

export function resetQuiz() {
  status.value = 'idle';
  sessionId.value = null;
  currentQuestion.value = null;
  progress.value = { current: 0, min_questions: 8, max_questions: 20, confidence: null };
  canFinish.value = false;
  errorMsg.value = null;
  results.value = null;
  try {
    sessionStorage.removeItem(SESSION_KEY);
    sessionStorage.removeItem(RESULTS_KEY);
  } catch {}
}
