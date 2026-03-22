import { useState, useRef, useEffect } from 'preact/hooks';
import { sendChat, ApiError } from '../lib/api';
import type { ChatResponse, ChatMessage as ChatMessageType } from '../lib/types';
import ChatMessage from './ChatMessage';
import ChatInput from './ChatInput';

const SUGGESTED_QUESTIONS = [
  '¿Qué hizo Fuerza Popular con la vacancia de Vizcarra?',
  '¿Cuáles partidos apoyaron leyes que favorecen al crimen?',
  '¿Qué proponen los candidatos sobre seguridad ciudadana?',
  'Compara las propuestas de educación',
  '¿Qué noticias hay sobre Keiko Fujimori?',
  '¿Quiénes quieren nueva constitución?',
];

export default function ChatInterface() {
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  async function handleSend(question: string) {
    const userMsg: ChatMessageType = { id: `u-${Date.now()}`, role: 'user', content: question };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);
    setError(null);

    try {
      const res: ChatResponse = await sendChat(question);
      setMessages((prev) => [...prev, { id: `b-${Date.now()}`, role: 'assistant', content: res.answer, sources: res.sources }]);
    } catch (e: any) {
      if (e instanceof ApiError && e.status === 429) {
        setError('Has alcanzado el límite de consultas. Intenta de nuevo en un momento.');
      } else {
        setError(e.message || 'Error al procesar tu pregunta.');
      }
    } finally {
      setLoading(false);
    }
  }

  const showSuggestions = messages.length === 0 && !loading;

  return (
    <>
      {/* Scrollable message area — full width, scrollbar at window edge */}
      <div class="flex-1 overflow-y-auto">
        <div class="mx-auto max-w-3xl px-4 py-6 pb-32">
          {showSuggestions && (
            <div class="flex min-h-[60vh] flex-col items-center justify-center animate-fade-in-up">
              <div class="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-accent/10">
                <svg class="h-8 w-8 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                </svg>
              </div>
              <h2 class="mt-5 text-xl font-bold text-white">Pregúntale al Chasqui</h2>
              <p class="mt-1.5 text-sm text-surface-600">
                Responde con datos de planes de gobierno, noticias y eventos políticos.
              </p>
              <div class="mt-8 flex flex-wrap justify-center gap-2">
                {SUGGESTED_QUESTIONS.map((q, i) => (
                  <button
                    key={q}
                    onClick={() => handleSend(q)}
                    class="hover-scale rounded-full border border-surface-300/25 bg-surface-100/40 px-4 py-2.5 text-sm text-surface-700 backdrop-blur-sm transition-all hover:border-accent/30 hover:text-accent-light animate-fade-in-up"
                    style={{ animationDelay: `${300 + i * 80}ms` }}
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <ChatMessage key={msg.id} message={msg} />
          ))}

          {loading && (
            <div class="mb-6 flex gap-1.5 animate-fade-in py-2">
              <span class="h-2 w-2 animate-bounce rounded-full bg-accent" style={{ animationDelay: '0ms' }} />
              <span class="h-2 w-2 animate-bounce rounded-full bg-accent" style={{ animationDelay: '150ms' }} />
              <span class="h-2 w-2 animate-bounce rounded-full bg-accent" style={{ animationDelay: '300ms' }} />
            </div>
          )}

          {error && (
            <div class="mb-4 rounded-xl border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-400 animate-scale-in">
              {error}
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Fixed input at bottom — full width with centered content */}
      <div class="fixed bottom-0 left-0 right-0 z-40 border-t border-surface-300/20 bg-surface-0/90 backdrop-blur-xl">
        <div class="mx-auto max-w-3xl px-4 py-4">
          <ChatInput onSend={handleSend} disabled={loading} />
        </div>
      </div>
    </>
  );
}
