import { useState, useEffect, useRef } from 'preact/hooks';
import { getEvents } from '../lib/api';
import { EVENT_CATEGORIES } from '../lib/constants';
import { formatDate } from '../lib/utils';
import type { EventItem } from '../lib/types';

const CATEGORIES = ['', ...Object.keys(EVENT_CATEGORIES)] as const;
const PAGE_SIZE = 10;

const SEVERITY_DOT: Record<string, string> = {
  high: 'bg-red-400',
  medium: 'bg-yellow-400',
  low: 'bg-surface-500',
};

export default function EventsFilter() {
  const [events, setEvents] = useState<EventItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [category, setCategory] = useState('');
  const [partyInput, setPartyInput] = useState('');
  const [partyQuery, setPartyQuery] = useState('');
  const [offset, setOffset] = useState(0);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  function handlePartyInput(value: string) {
    setPartyInput(value);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setPartyQuery(value);
      setOffset(0);
    }, 350);
  }

  async function fetchEvents(cat: string, party: string, o: number) {
    setLoading(true);
    setError(null);
    try {
      const res = await getEvents({
        limit: PAGE_SIZE,
        offset: o,
        ...(cat && { category: cat }),
        ...(party && { party }),
      });
      setEvents(res.events);
      setTotal(res.total);
    } catch (e: any) {
      setError(e.message || 'Error al cargar eventos');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchEvents(category, partyQuery, offset);
  }, [category, partyQuery, offset]);

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  return (
    <div>
      {/* Filters */}
      <div class="flex flex-col gap-4 sm:flex-row">
        <div class="relative flex-1">
          <svg class="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-surface-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            placeholder="Buscar por partido..."
            value={partyInput}
            onInput={(e) => handlePartyInput((e.target as HTMLInputElement).value)}
            class="w-full rounded-xl border border-surface-300/50 bg-surface-100 py-2.5 pl-11 pr-4 text-sm text-white placeholder-surface-500 transition-all focus:border-accent/50 focus:outline-none focus:ring-2 focus:ring-accent/20"
          />
        </div>
        <div class="flex flex-wrap gap-1.5">
          {CATEGORIES.map((c) => {
            const label = c ? EVENT_CATEGORIES[c]?.name : 'Todos';
            return (
              <button
                key={c}
                onClick={() => { setCategory(c); setOffset(0); }}
                class={`rounded-lg px-3.5 py-2 text-sm font-medium transition-all ${
                  category === c
                    ? 'bg-accent text-white shadow-md shadow-accent-glow'
                    : 'border border-surface-300/30 text-surface-600 hover:border-surface-400 hover:text-white'
                }`}
              >
                {label}
              </button>
            );
          })}
        </div>
      </div>

      <p class="mt-4 text-sm text-surface-500">{total} {total === 1 ? 'evento' : 'eventos'}</p>

      {loading && (
        <div class="mt-4 grid gap-3 sm:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} class="rounded-2xl border border-surface-300/20 bg-surface-100/30 p-5 animate-fade-in" style={{ animationDelay: `${i * 60}ms` }}>
              <div class="flex items-center gap-2">
                <div class="skeleton h-4 w-20" />
                <div class="skeleton h-3 w-3 rounded-full" />
              </div>
              <div class="skeleton mt-3 h-5 w-full" />
              <div class="skeleton mt-2 h-4 w-3/4" />
              <div class="skeleton mt-3 h-4 w-full" />
              <div class="skeleton mt-1 h-4 w-2/3" />
              <div class="mt-4 flex justify-between">
                <div class="skeleton h-3 w-24" />
                <div class="skeleton h-3 w-16" />
              </div>
            </div>
          ))}
        </div>
      )}

      {error && (
        <div class="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-400">{error}</div>
      )}

      {!loading && !error && (
        <div class="mt-4 grid gap-3 sm:grid-cols-2">
          {events.map((ev) => {
            const catMeta = EVENT_CATEGORIES[ev.category];
            const catLabel = catMeta?.name || ev.category;
            const catColor = catMeta?.color || 'bg-surface-200 text-surface-600';
            const dotColor = SEVERITY_DOT[ev.severity] || SEVERITY_DOT.low;

            return (
              <a
                key={ev.id}
                href={`/eventos/detalle?id=${ev.id}`}
                class="group flex flex-col rounded-2xl border border-surface-300/30 bg-surface-100/50 p-5 transition-all hover:border-accent/30 hover:bg-surface-100"
              >
                <div class="flex items-center gap-2">
                  <span class={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${catColor}`}>
                    {catLabel}
                  </span>
                  <span class={`inline-block h-2.5 w-2.5 rounded-full ${dotColor}`} title={`Severidad: ${ev.severity}`} />
                </div>

                <h3 class="mt-3 line-clamp-2 text-sm font-semibold text-white group-hover:text-accent-light">
                  {ev.title}
                </h3>

                <p class="mt-2 line-clamp-2 text-xs leading-relaxed text-surface-600">
                  {ev.description}
                </p>

                <div class="mt-auto flex items-center justify-between pt-4 text-xs text-surface-500">
                  {ev.event_date ? (
                    <span>{formatDate(ev.event_date)}</span>
                  ) : (
                    <span />
                  )}
                  <span>{ev.sources.length} {ev.sources.length === 1 ? 'fuente' : 'fuentes'}</span>
                </div>
              </a>
            );
          })}
        </div>
      )}

      {!loading && !error && events.length === 0 && (
        <div class="mt-12 text-center text-surface-500">No se encontraron eventos con estos filtros.</div>
      )}

      {totalPages > 1 && (
        <div class="mt-8 flex items-center justify-center gap-3">
          <button
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            disabled={offset === 0}
            class="rounded-lg px-4 py-2 text-sm font-medium text-surface-600 transition hover:bg-surface-200/50 hover:text-white disabled:opacity-20"
          >
            Anterior
          </button>
          <span class="text-sm text-surface-500">{currentPage} / {totalPages}</span>
          <button
            onClick={() => setOffset(offset + PAGE_SIZE)}
            disabled={currentPage >= totalPages}
            class="rounded-lg px-4 py-2 text-sm font-medium text-surface-600 transition hover:bg-surface-200/50 hover:text-white disabled:opacity-20"
          >
            Siguiente
          </button>
        </div>
      )}
    </div>
  );
}
