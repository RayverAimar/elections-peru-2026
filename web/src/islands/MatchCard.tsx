import { useEffect, useRef, useState } from 'preact/hooks';
import type { CandidateMatch } from '../lib/types';

interface Props {
  match: CandidateMatch;
  rank: number;
  isTop: boolean;
  delay?: number;
}

export default function MatchCard({ match, rank, isTop, delay = 0 }: Props) {
  const [animatedScore, setAnimatedScore] = useState(0);
  const [visible, setVisible] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const timer = setTimeout(() => setVisible(true), delay);
    return () => clearTimeout(timer);
  }, [delay]);

  useEffect(() => {
    if (!visible) return;
    const duration = 800;
    const start = performance.now();
    let rafId = 0;
    function tick(now: number) {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setAnimatedScore(match.score * eased);
      if (progress < 1) rafId = requestAnimationFrame(tick);
    }
    rafId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafId);
  }, [visible, match.score]);

  return (
    <div
      ref={ref}
      class={`overflow-hidden rounded-2xl border transition-all duration-500 ${
        visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'
      } ${
        isTop
          ? 'border-accent/30 bg-surface-100 shadow-xl shadow-accent/10'
          : 'border-surface-300/20 bg-surface-100/40'
      }`}
    >
      <div class="flex items-center gap-4 p-5">
        <div
          class={`flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full text-sm font-black transition-all ${
            isTop ? 'bg-accent text-white shadow-lg shadow-accent/30' : 'bg-surface-200 text-surface-600'
          }`}
        >
          #{rank}
        </div>

        <div class={`h-13 w-13 flex-shrink-0 overflow-hidden rounded-full ring-2 ${
          isTop ? 'ring-accent/30' : 'ring-surface-300/20'
        }`}>
          {match.photo_url ? (
            <img src={match.photo_url} alt={match.candidate} class="h-full w-full object-cover" loading="lazy" />
          ) : (
            <div class="flex h-full w-full items-center justify-center bg-surface-200 text-lg font-bold text-surface-500">
              {match.candidate.charAt(0)}
            </div>
          )}
        </div>

        <div class="min-w-0 flex-1">
          <h3 class="truncate font-bold text-white">{match.party}</h3>
          <p class="truncate text-sm text-surface-600">{match.candidate}</p>
        </div>

        <div class="flex-shrink-0 text-right">
          <p class={`text-3xl font-black tabular-nums ${isTop ? 'text-accent' : 'text-white'}`}>
            {animatedScore.toFixed(1)}%
          </p>
          <p class="text-xs text-surface-500">afinidad</p>
        </div>
      </div>

      <div class="px-5 pb-4">
        <div class="h-1.5 overflow-hidden rounded-full bg-surface-300/15">
          <div
            class={`h-full rounded-full transition-all duration-1000 ease-out ${
              isTop ? 'bg-accent shadow-sm shadow-accent/50' : 'bg-surface-400'
            }`}
            style={{ width: visible ? `${match.score}%` : '0%' }}
          />
        </div>
      </div>

      {isTop && match.evidence.length > 0 && (
        <div class="border-t border-surface-300/15 px-5 py-3">
          <p class="line-clamp-1 text-xs text-surface-500">{match.evidence[0].explanation}</p>
        </div>
      )}
    </div>
  );
}
