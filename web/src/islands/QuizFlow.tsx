import { useState, useCallback } from 'preact/hooks';
import { startQuiz, answerQuiz, getQuizResults } from '../lib/api';
import { saveSession, saveResults, resetQuiz } from '../lib/quiz-store';
import { ANSWER_LABELS, TOPICS } from '../lib/constants';
import type { QuizQuestion, QuizProgress } from '../lib/types';
import QuizProgress from './QuizProgress';

type Status = 'idle' | 'loading' | 'active' | 'answering' | 'finishing' | 'error';

function HintToggle({ hint }: { hint: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div class="relative mt-3 inline-block">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        class="inline-flex cursor-pointer items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-surface-500 transition hover:bg-surface-200/30 hover:text-surface-700"
        aria-expanded={open}
      >
        <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        ¿Qué significa esto?
      </button>
      {open && (
        <>
          <div class="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div class="absolute left-0 top-full z-50 mt-2 w-72 rounded-xl border border-surface-300/30 bg-surface-100 p-4 shadow-xl shadow-black/30 animate-scale-in sm:w-80">
            <p class="text-sm leading-relaxed text-surface-600">{hint}</p>
          </div>
        </>
      )}
    </div>
  );
}

export default function QuizFlow() {
  const [status, setStatus] = useState<Status>('idle');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [question, setQuestion] = useState<QuizQuestion | null>(null);
  const [progress, setProgress] = useState<QuizProgress>({ current: 0, min_questions: 8, max_questions: 20, confidence: null });
  const [canFinish, setCanFinish] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [slideDir, setSlideDir] = useState<'right' | 'left'>('right');
  const [animKey, setAnimKey] = useState(0);

  const progressPercent = progress.max_questions > 0 ? (progress.current / progress.max_questions) * 100 : 0;
  const confidenceLabel = progress.confidence === null ? null
    : progress.confidence >= 3.0 ? 'Alta'
    : progress.confidence >= 1.5 ? 'Media' : 'Baja';

  async function handleStart() {
    setStatus('loading');
    setError(null);
    try {
      const data = await startQuiz();
      setSessionId(data.session_id);
      saveSession(data.session_id);
      setQuestion(data.question);
      setProgress(data.progress);
      setCanFinish(data.can_finish);
      setStatus('active');
    } catch (e: any) {
      setError(e.message || 'Error al iniciar el quiz');
      setStatus('error');
    }
  }

  async function handleAnswer(questionId: string, value: number) {
    if (!sessionId) return;
    setStatus('answering');
    try {
      const data = await answerQuiz(sessionId, questionId, value);
      setProgress(data.progress);
      setCanFinish(data.can_finish);

      if (data.finished) {
        await handleFinish();
        return;
      }

      if (data.question) {
        setSlideDir('right');
        setAnimKey((k) => k + 1);
        setQuestion(data.question);
      }
      setStatus('active');
    } catch (e: any) {
      setError(e.message || 'Error al enviar respuesta');
      setStatus('error');
    }
  }

  async function handleFinish() {
    if (!sessionId) return;
    setStatus('finishing');
    try {
      const data = await getQuizResults(sessionId);
      saveResults(data);
      window.location.href = '/brujula/resultados';
    } catch (e: any) {
      setError(e.message || 'Error al obtener resultados');
      setStatus('error');
    }
  }

  // --- Idle ---
  if (status === 'idle') {
    return (
      <div class="mx-auto max-w-2xl animate-fade-in-up text-center">
        <div class="mx-auto flex h-20 w-20 items-center justify-center rounded-2xl bg-accent/10">
          <svg class="h-10 w-10 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
        </div>
        <h2 class="mt-7 text-3xl font-black text-white">Quiz Electoral</h2>
        <p class="mt-3 text-surface-600">
          El Chasqui te hace preguntas y busca qué candidatos piensan como tú.
          Se adapta en tiempo real para encontrar tu match ideal.
        </p>

        <div class="mt-8 space-y-2.5 text-left">
          {[
            { n: '01', t: 'El Chasqui te hace una pregunta', d: 'Se adapta a ti' },
            { n: '02', t: 'Elige la siguiente según tu respuesta', d: 'Máxima precisión' },
            { n: '03', t: 'Te muestra tus candidatos afines', d: '8-20 preguntas' },
          ].map((step, i) => (
            <div
              key={step.n}
              class="flex items-center gap-4 rounded-xl border border-surface-300/20 bg-surface-100/30 px-5 py-4 animate-fade-in-up"
              style={{ animationDelay: `${(i + 1) * 100}ms` }}
            >
              <span class="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/10 text-xs font-black text-accent">{step.n}</span>
              <span class="flex-1 text-sm font-medium text-surface-800">{step.t}</span>
              <span class="text-xs text-surface-500">{step.d}</span>
            </div>
          ))}
        </div>

        <button
          onClick={handleStart}
          class="hover-scale mt-10 inline-flex items-center gap-2.5 rounded-2xl bg-accent px-10 py-5 text-lg font-bold text-white shadow-xl shadow-accent/25 transition-all"
        >
          Iniciar
          <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
          </svg>
        </button>
      </div>
    );
  }

  // --- Loading ---
  if (status === 'loading') {
    return (
      <div class="flex flex-col items-center justify-center py-24 animate-fade-in">
        <div class="h-10 w-10 animate-spin rounded-full border-3 border-surface-300/30 border-t-accent" />
        <p class="mt-5 text-surface-600">Preparando tu brújula...</p>
      </div>
    );
  }

  // --- Error ---
  if (status === 'error') {
    return (
      <div class="mx-auto max-w-md text-center py-20 animate-scale-in">
        <div class="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-red-500/10">
          <svg class="h-8 w-8 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
        </div>
        <p class="mt-5 text-lg font-bold text-white">Algo salió mal</p>
        <p class="mt-2 text-sm text-surface-600">{error}</p>
        <button
          onClick={() => { resetQuiz(); setStatus('idle'); setError(null); handleStart(); }}
          class="hover-scale mt-6 rounded-xl bg-surface-200 px-6 py-3 text-sm font-semibold text-white transition hover:bg-surface-300"
        >
          Reintentar
        </button>
      </div>
    );
  }

  // --- Finishing ---
  if (status === 'finishing') {
    return (
      <div class="flex flex-col items-center justify-center py-24 animate-fade-in">
        <div class="relative h-16 w-16">
          <div class="absolute inset-0 animate-spin rounded-full border-3 border-accent/15 border-t-accent" style={{ animationDuration: '0.8s' }} />
          <div class="absolute inset-2 animate-spin rounded-full border-3 border-accent/10 border-b-accent-light" style={{ animationDuration: '1.2s', animationDirection: 'reverse' }} />
        </div>
        <p class="mt-6 text-xl font-bold text-white">El Chasqui está analizando</p>
        <p class="mt-2 text-sm text-surface-500">{progress.current} respuestas contra 36 partidos...</p>
      </div>
    );
  }

  // --- Active question ---
  if ((status === 'active' || status === 'answering') && question) {
    const topicMeta = TOPICS[question.topic];
    const isAnswering = status === 'answering';
    const slideClass = slideDir === 'right' ? 'animate-slide-in-right' : 'animate-slide-in-left';

    return (
      <div class="mx-auto max-w-2xl">
        <QuizProgress
          current={progress.current + 1}
          total={progress.max_questions}
          percent={progressPercent}
          topic={question.topic_display}
          confidence={confidenceLabel}
        />

        <div key={animKey} class={`mt-8 ${slideClass}`}>
          <div class="rounded-2xl border border-surface-300/20 bg-surface-100/40 p-6 backdrop-blur-sm sm:p-8">
            {topicMeta && (
              <span class="inline-block rounded-full bg-accent/10 px-3.5 py-1 text-xs font-bold text-accent">
                {topicMeta.name}
              </span>
            )}
            <p class="mt-5 text-lg font-medium leading-relaxed text-white sm:text-xl">{question.text}</p>
            {question.hint && <HintToggle hint={question.hint} />}

            <div class="mt-7 space-y-2">
              {([-2, -1, 0, 1, 2] as const).map((val) => (
                <button
                  key={val}
                  onClick={() => !isAnswering && handleAnswer(question.id, val)}
                  disabled={isAnswering}
                  class="hover-scale w-full rounded-xl border-2 border-surface-300/20 px-5 py-4 text-left text-sm font-medium text-surface-700 transition-all duration-200 hover:border-surface-400/50 hover:bg-surface-200/20 disabled:opacity-60"
                >
                  <div class="flex items-center gap-3">
                    <div class="flex h-6 w-6 items-center justify-center rounded-full border-2 border-surface-400" />
                    {ANSWER_LABELS[val]}
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>

        {canFinish && (
          <div class="mt-6 text-center animate-fade-in">
            <button
              onClick={handleFinish}
              disabled={isAnswering}
              class="hover-scale rounded-xl bg-accent px-8 py-3 text-sm font-bold text-white shadow-lg shadow-accent/25 transition-all disabled:opacity-50"
            >
              Ver resultados ({progress.current} preguntas respondidas)
            </button>
            <p class="mt-2 text-xs text-surface-500">Confianza suficiente para mostrar resultados</p>
          </div>
        )}
      </div>
    );
  }

  // --- Fallback ---
  return (
    <div class="mx-auto max-w-md text-center py-20 animate-fade-in">
      <p class="text-lg font-bold text-white">Algo no salió como esperado</p>
      <button
        onClick={() => { resetQuiz(); setStatus('idle'); }}
        class="hover-scale mt-6 rounded-xl bg-accent px-6 py-3 text-sm font-semibold text-white"
      >
        Reiniciar Brújula
      </button>
    </div>
  );
}
