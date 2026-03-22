import { useState, useEffect, useCallback, useRef } from 'preact/hooks';
import { getNews } from '../lib/api';
import { SENTIMENT_LABELS, SENTIMENT_STYLES } from '../lib/constants';
import { formatDate } from '../lib/utils';
import type { NewsItem } from '../lib/types';

const SENTIMENTS = ['', 'positive', 'neutral', 'adverse'] as const;
const PAGE_SIZE = 12;

export default function NewsFilter() {
  const [articles, setArticles] = useState<NewsItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sentiment, setSentiment] = useState('');
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

  async function fetchNews(s: string, p: string, o: number) {
    setLoading(true);
    setError(null);
    try {
      const res = await getNews({
        limit: PAGE_SIZE, offset: o,
        ...(s && { sentiment: s }),
        ...(p && { party: p }),
      });
      setArticles(res.articles);
      setTotal(res.total);
    } catch (e: any) {
      setError(e.message || 'Error al cargar noticias');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchNews(sentiment, partyQuery, offset);
  }, [sentiment, partyQuery, offset]);

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
        <div class="flex gap-1.5">
          {SENTIMENTS.map((s) => (
            <button
              key={s}
              onClick={() => { setSentiment(s); setOffset(0); }}
              class={`rounded-lg px-3.5 py-2 text-sm font-medium transition-all ${
                sentiment === s
                  ? 'bg-accent text-white shadow-md shadow-accent-glow'
                  : 'border border-surface-300/30 text-surface-600 hover:border-surface-400 hover:text-white'
              }`}
            >
              {s ? SENTIMENT_LABELS[s] : 'Todos'}
            </button>
          ))}
        </div>
      </div>

      <p class="mt-4 text-sm text-surface-500">{total} {total === 1 ? 'noticia' : 'noticias'}</p>

      {loading && (
        <div class="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} class="rounded-xl border border-surface-300/20 bg-surface-100/30 p-4 animate-fade-in" style={{ animationDelay: `${i * 60}ms` }}>
              <div class="skeleton h-4 w-20" />
              <div class="skeleton mt-3 h-4 w-full" />
              <div class="skeleton mt-2 h-4 w-3/4" />
              <div class="mt-4 flex justify-between">
                <div class="skeleton h-3 w-16" />
                <div class="skeleton h-3 w-24" />
              </div>
            </div>
          ))}
        </div>
      )}

      {error && (
        <div class="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-400">{error}</div>
      )}

      {!loading && !error && (
        <div class="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {articles.map((n) => {
            const sentStyle = SENTIMENT_STYLES[n.sentiment_label] || 'bg-surface-200 text-surface-600';
            const sentLabel = SENTIMENT_LABELS[n.sentiment_label] || n.sentiment_label;
            return (
              <a
                key={n.id}
                href={`/noticias/detalle?id=${n.id}`}
                class="group flex flex-col rounded-xl border border-surface-300/30 bg-surface-100/50 p-4 transition-all hover:border-accent/30 hover:bg-surface-100"
              >
                <div class="flex items-center gap-2">
                  <span class={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${sentStyle}`}>{sentLabel}</span>
                </div>
                <h3 class="mt-3 line-clamp-2 text-sm font-semibold text-white group-hover:text-accent-light">
                  {n.title}
                </h3>
                <div class="mt-auto flex items-center justify-between pt-3 text-xs text-surface-500">
                  <span>{n.source_name}</span>
                  {n.published_at && <span>{formatDate(n.published_at)}</span>}
                </div>
              </a>
            );
          })}
        </div>
      )}

      {!loading && !error && articles.length === 0 && (
        <div class="mt-12 text-center text-surface-500">No se encontraron noticias con estos filtros.</div>
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
