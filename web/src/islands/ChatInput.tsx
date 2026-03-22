import { useState, useRef, useEffect } from 'preact/hooks';

interface Props {
  onSend: (message: string) => void;
  disabled: boolean;
}

const MIN_LENGTH = 5;
const MAX_LENGTH = 500;

export default function ChatInput({ onSend, disabled }: Props) {
  const [text, setText] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-focus on any keypress
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key.length !== 1) return;
      const active = document.activeElement;
      if (active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA')) return;
      textareaRef.current?.focus();
    }
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
  }, [text]);

  function handleSubmit(e: Event) {
    e.preventDefault();
    const trimmed = text.trim();
    if (trimmed.length >= MIN_LENGTH && trimmed.length <= MAX_LENGTH && !disabled) {
      onSend(trimmed);
      setText('');
    }
  }

  function handleKeyDown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  }

  const charCount = text.trim().length;
  const isValid = charCount >= MIN_LENGTH && charCount <= MAX_LENGTH;

  return (
    <form onSubmit={handleSubmit} class="flex items-end gap-3">
      <div class="relative flex-1">
        <textarea
          ref={textareaRef}
          value={text}
          onInput={(e) => setText((e.target as HTMLTextAreaElement).value)}
          onKeyDown={handleKeyDown}
          placeholder="Escribe tu pregunta..."
          disabled={disabled}
          rows={1}
          class="w-full resize-none rounded-xl border border-surface-300/50 bg-surface-100 px-4 py-3 pr-16 text-sm leading-relaxed text-white placeholder-surface-500 transition-colors focus:border-accent/50 focus:outline-none focus:ring-2 focus:ring-accent/20 disabled:opacity-50"
        />
        <span
          class={`absolute bottom-2.5 right-3 text-xs ${
            charCount > MAX_LENGTH ? 'text-red-400' : 'text-surface-500'
          }`}
        >
          {charCount}/{MAX_LENGTH}
        </span>
      </div>
      <button
        type="submit"
        disabled={disabled || !isValid}
        class="flex h-[46px] w-[46px] flex-shrink-0 items-center justify-center rounded-xl bg-accent text-white transition-all hover:bg-accent-dark hover:shadow-lg hover:shadow-accent-glow disabled:opacity-20 disabled:hover:bg-accent disabled:hover:shadow-none"
        aria-label="Enviar"
      >
        <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 19V5m0 0l-7 7m7-7l7 7" />
        </svg>
      </button>
    </form>
  );
}
