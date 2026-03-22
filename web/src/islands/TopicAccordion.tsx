import { useState } from 'preact/hooks';
import { TOPICS, CONFIDENCE_LABELS, CONFIDENCE_STYLES } from '../lib/constants';
import type { TopicPosition } from '../lib/types';

interface Props {
  positions: Record<string, TopicPosition>;
}

export default function TopicAccordion({ positions }: Props) {
  const [openTopic, setOpenTopic] = useState<string | null>(null);
  const entries = Object.entries(positions);

  if (entries.length === 0) {
    return <p class="text-surface-500">No hay posiciones disponibles para este partido.</p>;
  }

  return (
    <div class="space-y-2">
      {entries.map(([key, pos]) => {
        const isOpen = openTopic === key;
        const meta = TOPICS[key];
        const confStyle = CONFIDENCE_STYLES[pos.confidence] || '';
        const confLabel = CONFIDENCE_LABELS[pos.confidence] || pos.confidence;

        return (
          <div key={key} class="overflow-hidden rounded-xl border border-surface-300/30 bg-surface-100/50">
            <button
              onClick={() => setOpenTopic(isOpen ? null : key)}
              class="flex w-full items-center justify-between gap-2 px-4 py-3.5 text-left transition hover:bg-surface-200/50 min-h-[48px]"
            >
              <div class="flex flex-wrap items-center gap-x-2 gap-y-1 min-w-0">
                <span class="text-sm font-semibold text-white">{meta?.name || key}</span>
                <span class={`inline-block shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${confStyle}`}>
                  {confLabel}
                </span>
              </div>
              <svg
                class={`h-4 w-4 flex-shrink-0 text-surface-500 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
                fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {isOpen && (
              <div class="border-t border-surface-300/20 px-4 pb-5 pt-4 animate-fade-in-up">
                <p class="text-sm leading-relaxed text-surface-700">{pos.summary}</p>

                {pos.key_proposals?.length > 0 && (
                  <div class="mt-5">
                    <h4 class="text-xs font-semibold uppercase tracking-wider text-surface-500">Propuestas clave</h4>
                    <ul class="mt-2.5 space-y-2">
                      {pos.key_proposals.map((p, i) => (
                        <li key={i} class="flex items-start gap-2.5 text-sm text-surface-700">
                          <span class="mt-2 h-1 w-1 flex-shrink-0 rounded-full bg-accent" />
                          {p}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {pos.axes && Object.entries(pos.axes).length > 0 && (
                  <div class="mt-5">
                    <h4 class="text-xs font-semibold uppercase tracking-wider text-surface-500">Ejes de posición</h4>
                    <div class="mt-3 space-y-3">
                      {Object.entries(pos.axes).map(([axis, value]) => {
                        const position = ((value + 1) / 2) * 100;
                        return (
                          <div key={axis}>
                            <div class="mb-1.5 flex items-center justify-between">
                              <span class="text-xs text-surface-500">{axis.replace(/_/g, ' ')}</span>
                              <span class="text-xs font-medium text-surface-600">{value > 0 ? '+' : ''}{value.toFixed(1)}</span>
                            </div>
                            <div class="relative h-2 rounded-full bg-surface-300/30">
                              <div class="absolute left-1/2 top-0 h-full w-px bg-surface-400/50" />
                              <div
                                class="absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-surface-0 bg-accent shadow-md shadow-accent/30"
                                style={{ left: `${position}%` }}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
