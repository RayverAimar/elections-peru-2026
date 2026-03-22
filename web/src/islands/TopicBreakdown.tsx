import { useState } from 'preact/hooks';
import { TOPICS } from '../lib/constants';
import type { CandidateMatch } from '../lib/types';

interface Props {
  agreement: Record<string, number>;
  topCandidates: CandidateMatch[];
}

export default function TopicBreakdown({ agreement, topCandidates }: Props) {
  const [openTopic, setOpenTopic] = useState<string | null>(null);
  const sorted = Object.entries(agreement).sort(([, a], [, b]) => b - a);

  return (
    <div class="space-y-2">
      {sorted.map(([key, value]) => {
        const isOpen = openTopic === key;
        const meta = TOPICS[key];

        return (
          <div key={key} class="overflow-hidden rounded-xl border border-surface-300/30 bg-surface-100/50">
            <button
              onClick={() => setOpenTopic(isOpen ? null : key)}
              class="flex w-full items-center gap-3 px-4 py-3.5 text-left transition hover:bg-surface-200/30 min-h-[48px]"
            >
              <span class="w-28 flex-shrink-0 text-sm font-medium text-white">{meta?.name || key}</span>
              <div class="flex-1">
                <div class="h-1.5 overflow-hidden rounded-full bg-surface-300/20">
                  <div
                    class="h-full rounded-full bg-accent transition-all"
                    style={{ width: `${value}%` }}
                  />
                </div>
              </div>
              <span class="w-14 text-right text-sm font-semibold text-surface-700">
                {value.toFixed(1)}%
              </span>
              <svg
                class={`h-4 w-4 text-surface-500 transition ${isOpen ? 'rotate-180' : ''}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {isOpen && (
              <div class="border-t border-surface-300/20 px-4 py-3 space-y-2">
                {topCandidates.slice(0, 3).map((c) => {
                  const topicScore = c.agreement_by_topic[key];
                  if (topicScore === undefined) return null;
                  return (
                    <div key={c.party} class="flex items-center justify-between rounded-lg bg-surface-200/30 px-3 py-2">
                      <span class="text-sm text-surface-700">{c.party}</span>
                      <span class="text-xs font-medium text-surface-500">{topicScore.toFixed(1)}%</span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
