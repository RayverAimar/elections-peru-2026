import { useState, useMemo } from 'preact/hooks';
import { marked } from 'marked';
import type { ChatMessage as ChatMessageType } from '../lib/types';

// Configure marked for safe rendering
marked.setOptions({
  breaks: true,
  gfm: true,
});

interface Props {
  message: ChatMessageType;
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
      const ta = document.createElement('textarea');
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  return (
    <button
      onClick={handleCopy}
      class="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium text-surface-500 transition hover:bg-surface-200/30 hover:text-surface-700"
      aria-label="Copiar respuesta"
    >
      {copied ? (
        <>
          <svg class="h-3.5 w-3.5 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
          Copiado
        </>
      ) : (
        <>
          <svg class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
          Copiar
        </>
      )}
    </button>
  );
}

export default function ChatMessage({ message }: Props) {
  const isUser = message.role === 'user';

  const htmlContent = useMemo(() => {
    if (isUser) return null;
    return marked.parse(message.content) as string;
  }, [message.content, isUser]);

  if (isUser) {
    return (
      <div class="mb-5 flex justify-end animate-slide-in-right">
        <div class="max-w-[80%] rounded-2xl rounded-tr-sm bg-accent px-4 py-3">
          <p class="whitespace-pre-wrap text-sm leading-relaxed text-white">{message.content}</p>
        </div>
      </div>
    );
  }

  return (
    <div class="mb-6 animate-fade-in-up">
      <div
        class="chat-prose text-[15px] leading-relaxed text-surface-800"
        dangerouslySetInnerHTML={{ __html: htmlContent! }}
      />

      <div class="mt-3 flex items-center gap-3">
        <CopyButton text={message.content} />

        {message.sources && message.sources.length > 0 && (
          <div class="flex flex-wrap items-center gap-1.5">
            <span class="text-[11px] text-surface-500">Fuentes:</span>
            {message.sources.map((source, i) => {
              const typeStyles: Record<string, string> = {
                plan: 'bg-blue-500/10 text-blue-400',
                news: 'bg-green-500/10 text-green-400',
                event: 'bg-purple-500/10 text-purple-400',
              };
              const typeLabels: Record<string, string> = {
                plan: '📋',
                news: '📰',
                event: '⚡',
              };
              const style = typeStyles[source.source_type] || 'bg-accent/10 text-accent-light';
              const label = typeLabels[source.source_type] || '';

              if (source.url) {
                const isExternal = source.url.startsWith('http');
                return (
                  <a
                    key={source.name}
                    href={source.url}
                    target={isExternal ? '_blank' : undefined}
                    rel={isExternal ? 'noopener noreferrer' : undefined}
                    class={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium transition-opacity hover:opacity-80 animate-scale-in ${style}`}
                    style={{ animationDelay: `${200 + i * 80}ms` }}
                  >
                    {label} {source.name}
                    {isExternal && (
                      <svg class="h-3 w-3 opacity-60" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                      </svg>
                    )}
                  </a>
                );
              }

              return (
                <span
                  key={source.name}
                  class={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium animate-scale-in ${style}`}
                  style={{ animationDelay: `${200 + i * 80}ms` }}
                >
                  {label} {source.name}
                </span>
              );
            })}
          </div>
        )}
      </div>

      <div class="mt-4 border-b border-surface-300/10" />
    </div>
  );
}
