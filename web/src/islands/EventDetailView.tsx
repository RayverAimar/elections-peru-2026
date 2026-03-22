import { useState, useEffect, useCallback } from 'preact/hooks';
import { getEventDetail } from '../lib/api';
import { EVENT_CATEGORIES, EVENT_STANCES } from '../lib/constants';
import { formatDate, sanitizeUrl } from '../lib/utils';
import type { EventDetail } from '../lib/types';

interface StanceCardProps {
  partyName: string;
  stanceLabel: string;
  stanceColor: string;
  borderColor: string;
  detail?: string;
  evidence: Array<{ quote: string; source_description: string }>;
  hasEvidence: boolean;
}

function StanceCard({ partyName, stanceLabel, stanceColor, borderColor, detail, evidence, hasEvidence }: StanceCardProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div class={`rounded-xl border ${borderColor} bg-surface-100/50 overflow-hidden`}>
      <button
        onClick={() => hasEvidence && setExpanded(!expanded)}
        class={`w-full p-4 text-left ${hasEvidence ? 'cursor-pointer hover:bg-surface-200/30 transition-colors' : ''}`}
      >
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <span class="text-sm font-semibold text-white">{partyName}</span>
            <span class={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${stanceColor} bg-surface-200/50`}>
              {stanceLabel}
            </span>
          </div>
          {hasEvidence && (
            <svg
              class={`h-4 w-4 text-surface-500 transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`}
              fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          )}
        </div>
        {detail && (
          <p class="mt-2 text-sm leading-relaxed text-surface-600">
            {detail}
          </p>
        )}
      </button>

      {expanded && evidence.length > 0 && (
        <div class="border-t border-surface-300/15 bg-surface-0/30 px-4 py-3 space-y-3">
          <p class="text-[10px] font-semibold uppercase tracking-wider text-surface-500">Evidencia</p>
          {evidence.map((ev, i) => (
            <div key={i} class="rounded-lg border-l-2 border-accent/40 bg-surface-100/40 px-4 py-3">
              <p class="text-sm italic leading-relaxed text-surface-700">
                "{ev.quote}"
              </p>
              <div class="mt-2 flex items-center gap-1.5 text-xs text-surface-500">
                <svg class="h-3 w-3 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                {ev.source_url ? (
                  <a
                    href={ev.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    class="text-accent transition hover:text-accent-light hover:underline"
                  >
                    {ev.source_description} ↗
                  </a>
                ) : (
                  <span>{ev.source_description}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


export default function EventDetailView() {
  const [event, setEvent] = useState<EventDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const id = params.get('id');
    if (!id) {
      setError(true);
      setLoading(false);
      return;
    }
    getEventDetail(id)
      .then(setEvent)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div class="space-y-4 animate-fade-in">
        <div class="skeleton h-5 w-24" />
        <div class="skeleton h-8 w-full" />
        <div class="skeleton h-8 w-3/4" />
        <div class="skeleton mt-4 h-4 w-full" />
        <div class="skeleton h-4 w-full" />
        <div class="skeleton h-4 w-2/3" />
      </div>
    );
  }

  if (error || !event) {
    return (
      <div class="text-center py-12">
        <p class="text-lg font-semibold text-white">Evento no encontrado</p>
        <p class="mt-2 text-surface-600">El evento no existe o el servicio no está disponible.</p>
      </div>
    );
  }

  const catMeta = EVENT_CATEGORIES[event.category];
  const catLabel = catMeta?.name || event.category;
  const catColor = catMeta?.color || 'bg-surface-200 text-surface-600';

  return (
    <article class="animate-fade-in-up">
      <div class="flex items-center gap-3 flex-wrap">
        <span class={`inline-block rounded-full px-3 py-1 text-xs font-medium ${catColor}`}>
          {catLabel}
        </span>
        <span class="text-sm text-surface-500 capitalize">{event.severity}</span>
        {event.event_date && (
          <span class="text-sm text-surface-500">{formatDate(event.event_date)}</span>
        )}
      </div>

      <h1 class="mt-5 text-2xl font-bold text-white sm:text-3xl">{event.title}</h1>

      <div class="mt-6 whitespace-pre-wrap text-sm leading-relaxed text-surface-700">
        {event.description}
      </div>

      {/* Why it matters */}
      <div class="mt-8 rounded-2xl border border-accent/20 bg-accent/5 p-5">
        <h2 class="text-xs font-semibold uppercase tracking-wider text-accent-light">
          Por qué es importante
        </h2>
        <p class="mt-2 text-sm leading-relaxed text-surface-700">
          {event.why_it_matters}
        </p>
      </div>

      {/* Sources — shown prominently before stances */}
      {event.sources && event.sources.length > 0 && (
        <div class="mt-8 rounded-2xl border border-surface-300/20 bg-surface-100/30 p-5">
          <h3 class="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-surface-500">
            <svg class="h-4 w-4 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Fuentes verificables
          </h3>
          <div class="mt-3 space-y-2">
            {event.sources.map((src, i) => {
              const domain = (() => { try { return new URL(src).hostname.replace('www.', '').replace('es.', ''); } catch { return src; } })();
              return (
                <a
                  key={i}
                  href={sanitizeUrl(src)}
                  target="_blank"
                  rel="noopener noreferrer"
                  class="flex items-center gap-3 rounded-lg border border-surface-300/15 bg-surface-0/50 px-4 py-3 text-sm transition hover:border-accent/30 hover:bg-surface-100"
                >
                  <svg class="h-4 w-4 flex-shrink-0 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                  </svg>
                  <span class="font-medium text-accent">{domain}</span>
                  <span class="truncate text-surface-500">{src}</span>
                </a>
              );
            })}
          </div>
        </div>
      )}

      {/* Party stances */}
      {event.party_stances && event.party_stances.length > 0 && (
        <div class="mt-8">
          <h3 class="text-xs font-semibold uppercase tracking-wider text-surface-500">
            Posición de los partidos
          </h3>
          <p class="mt-1 text-xs text-surface-600">
            Basado en votaciones, declaraciones públicas y acciones documentadas en las fuentes anteriores.
          </p>
          <div class="mt-4 space-y-3">
            {event.party_stances.map((ps) => {
              const stanceMeta = EVENT_STANCES[ps.stance];
              const stanceLabel = stanceMeta?.name || ps.stance;
              const stanceColor = stanceMeta?.color || 'text-surface-500';
              const stanceBg: Record<string, string> = {
                supported: 'border-green-500/20',
                opposed: 'border-red-500/20',
                abstained: 'border-yellow-500/20',
                involved: 'border-orange-500/20',
              };
              const borderColor = stanceBg[ps.stance] || 'border-surface-300/20';
              const hasEvidence = ps.evidence && ps.evidence.length > 0;

              return (
                <StanceCard
                  key={ps.party_name}
                  partyName={ps.party_name}
                  stanceLabel={stanceLabel}
                  stanceColor={stanceColor}
                  borderColor={borderColor}
                  detail={ps.detail}
                  evidence={ps.evidence || []}
                  hasEvidence={hasEvidence}
                />
              );
            })}
          </div>
        </div>
      )}
    </article>
  );
}
