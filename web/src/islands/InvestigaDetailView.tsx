import { useState, useEffect } from 'preact/hooks';
import { getInvestigaDetail } from '../lib/api';
import { EVENT_CATEGORIES, CUESTIONABLE_STANCES } from '../lib/constants';
import { formatDate, sanitizeUrl } from '../lib/utils';
import type { InvestigaPartyDetail, InvestigaEventStance, StanceEvidence } from '../lib/types';

// ── Evidence card (reuses pattern from EventDetailView) ──────

interface EvidenceCardProps {
  evidence: StanceEvidence[];
}

function EvidenceSection({ evidence }: EvidenceCardProps) {
  const [expanded, setExpanded] = useState(false);

  if (!evidence || evidence.length === 0) return null;

  return (
    <div class="mt-3">
      <button
        onClick={() => setExpanded(!expanded)}
        class="flex items-center gap-1.5 text-xs font-medium text-surface-500 transition hover:text-accent"
      >
        <svg
          class={`h-3.5 w-3.5 transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
        {expanded ? 'Ocultar evidencia' : `Ver evidencia (${evidence.length})`}
      </button>

      {expanded && (
        <div class="mt-2 space-y-2">
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
                    href={sanitizeUrl(ev.source_url)}
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

// ── Event card ───────────────────────────────────────────────

function EventCard({ event }: { event: InvestigaEventStance }) {
  const stanceMeta = CUESTIONABLE_STANCES[event.stance];

  return (
    <div class="rounded-xl border border-surface-300/20 bg-surface-100/50 p-5">
      {/* Header: stance badge + date */}
      <div class="flex items-center gap-2 flex-wrap">
        {stanceMeta && (
          <span class={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${stanceMeta.color}`}>
            {stanceMeta.label}
          </span>
        )}
        {event.event_date && (
          <span class="text-xs text-surface-500">{formatDate(event.event_date)}</span>
        )}
      </div>

      {/* Title */}
      <h3 class="mt-3 text-base font-semibold text-white">{event.title}</h3>

      {/* Stance detail */}
      {event.stance_detail && (
        <p class="mt-2 text-sm leading-relaxed text-surface-600">
          {event.stance_detail}
        </p>
      )}

      {/* Description */}
      <p class="mt-3 text-sm leading-relaxed text-surface-700">
        {event.description}
      </p>

      {/* Why it matters */}
      <div class="mt-4 rounded-lg border border-accent/20 bg-accent/5 p-4">
        <p class="text-[10px] font-semibold uppercase tracking-wider text-accent-light">
          Por qué es importante
        </p>
        <p class="mt-1 text-sm leading-relaxed text-surface-700">
          {event.why_it_matters}
        </p>
      </div>

      {/* Evidence */}
      <EvidenceSection evidence={event.evidence} />

      {/* Sources */}
      {event.sources.length > 0 && (
        <div class="mt-4 flex flex-wrap gap-2">
          {event.sources.map((src, i) => {
            const domain = (() => { try { return new URL(src).hostname.replace('www.', ''); } catch { return 'fuente'; } })();
            return (
              <a
                key={i}
                href={sanitizeUrl(src)}
                target="_blank"
                rel="noopener noreferrer"
                class="inline-flex items-center gap-1 rounded-lg border border-surface-300/15 bg-surface-0/50 px-2.5 py-1.5 text-xs text-accent transition hover:border-accent/30"
              >
                <svg class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
                {domain}
              </a>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Main component ───────────────────────────────────────────

export default function InvestigaDetailView() {
  const [detail, setDetail] = useState<InvestigaPartyDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const id = params.get('id');
    if (!id || isNaN(Number(id))) {
      setError(true);
      setLoading(false);
      return;
    }
    getInvestigaDetail(Number(id))
      .then(setDetail)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div class="space-y-4 animate-fade-in">
        <div class="flex items-center gap-4">
          <div class="skeleton h-16 w-16 rounded-full" />
          <div>
            <div class="skeleton h-6 w-48" />
            <div class="skeleton mt-2 h-4 w-32" />
          </div>
        </div>
        <div class="skeleton mt-6 h-4 w-full" />
        <div class="skeleton h-4 w-3/4" />
        <div class="skeleton h-4 w-full" />
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div class="text-center py-12">
        <p class="text-lg font-semibold text-white">Partido no encontrado</p>
        <p class="mt-2 text-surface-600">El partido no existe o el servicio no está disponible.</p>
      </div>
    );
  }

  // Group events by category
  const grouped: Record<string, InvestigaEventStance[]> = {};
  for (const ev of detail.events) {
    if (!grouped[ev.category]) grouped[ev.category] = [];
    grouped[ev.category].push(ev);
  }

  const categoryOrder = ['corruption', 'democracy', 'human_rights', 'institutional', 'justice', 'economy'];
  const sortedCategories = Object.keys(grouped).sort(
    (a, b) => categoryOrder.indexOf(a) - categoryOrder.indexOf(b)
  );

  return (
    <article class="animate-fade-in-up">
      {/* Header */}
      <div class="flex items-center gap-5">
        <div class="h-16 w-16 flex-shrink-0 overflow-hidden rounded-full bg-surface-200 ring-2 ring-surface-300/30">
          {detail.photo_url ? (
            <img src={detail.photo_url} alt={detail.presidential_candidate} class="h-full w-full object-cover" />
          ) : (
            <div class="flex h-full w-full items-center justify-center text-2xl font-bold text-surface-500">
              {detail.presidential_candidate.charAt(0) || '?'}
            </div>
          )}
        </div>
        <div>
          <h1 class="text-2xl font-bold text-white">{detail.party_name}</h1>
          <p class="mt-0.5 text-sm text-surface-600">{detail.presidential_candidate}</p>
        </div>
      </div>

      {/* Summary stat */}
      <div class="mt-6 rounded-xl border border-surface-300/20 bg-surface-100/30 p-5">
        <div class="flex items-baseline gap-2">
          <span class={`text-3xl font-bold ${detail.cuestionable_count > 0 ? 'text-accent' : 'text-green-400'}`}>
            {detail.cuestionable_count}
          </span>
          <span class="text-sm text-surface-600">
            {detail.cuestionable_count === 1 ? 'evento cuestionable' : 'eventos cuestionables'}
          </span>
        </div>
        {detail.cuestionable_count === 0 && (
          <p class="mt-2 text-sm text-surface-500">
            No se encontraron eventos cuestionables para este partido en nuestra base de datos.
            Esto no significa que no existan.{' '}
            <a href="/eventos" class="text-accent hover:underline">Explorar todos los eventos →</a>
          </p>
        )}
      </div>

      {/* Events grouped by category */}
      {sortedCategories.map((cat) => {
        const catMeta = EVENT_CATEGORIES[cat];
        const events = grouped[cat];

        return (
          <section key={cat} class="mt-8">
            <div class="flex items-center gap-2 mb-4">
              <span class={`inline-block rounded-full px-3 py-1 text-xs font-medium ${catMeta?.color || 'bg-surface-200 text-surface-600'}`}>
                {catMeta?.name || cat}
              </span>
              <span class="text-xs text-surface-500">
                {events.length} {events.length === 1 ? 'evento' : 'eventos'}
              </span>
            </div>

            <div class="space-y-3">
              {events.map((ev) => (
                <EventCard key={ev.event_id} event={ev} />
              ))}
            </div>
          </section>
        );
      })}
    </article>
  );
}
