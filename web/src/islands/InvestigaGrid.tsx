import { useState, useEffect } from 'preact/hooks';
import { getInvestiga } from '../lib/api';
import { EVENT_CATEGORIES } from '../lib/constants';
import type { InvestigaPartyItem } from '../lib/types';

const CATEGORIES = ['', ...Object.keys(EVENT_CATEGORIES)] as const;

export default function InvestigaGrid() {
  const [parties, setParties] = useState<InvestigaPartyItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('');

  useEffect(() => {
    getInvestiga()
      .then((res) => setParties(res.parties))
      .catch((e: any) => setError(e.message || 'Error al cargar datos'))
      .finally(() => setLoading(false));
  }, []);

  const filtered = parties.filter((p) => {
    const q = query.toLowerCase();
    const matchesQuery =
      !q || p.party_name.toLowerCase().includes(q) || p.presidential_candidate.toLowerCase().includes(q);
    const matchesCategory =
      !category || p.category_counts.some((cc) => cc.category === category);
    return matchesQuery && matchesCategory;
  });

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
            placeholder="Buscar por partido o candidato..."
            value={query}
            onInput={(e) => setQuery((e.target as HTMLInputElement).value)}
            class="w-full rounded-xl border border-surface-300/50 bg-surface-100 py-2.5 pl-11 pr-4 text-sm text-white placeholder-surface-500 transition-all focus:border-accent/50 focus:outline-none focus:ring-2 focus:ring-accent/20"
          />
        </div>
        <div class="flex flex-wrap gap-1.5">
          {CATEGORIES.map((c) => {
            const label = c ? EVENT_CATEGORIES[c]?.name : 'Todos';
            return (
              <button
                key={c}
                onClick={() => setCategory(c)}
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

      <p class="mt-4 text-sm text-surface-500">
        {filtered.length} {filtered.length === 1 ? 'partido' : 'partidos'}
        {query && ' encontrados'}
      </p>

      {/* Loading */}
      {loading && (
        <div class="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} class="rounded-xl border border-surface-300/20 bg-surface-100/30 p-4 animate-fade-in" style={{ animationDelay: `${i * 60}ms` }}>
              <div class="flex items-center gap-3">
                <div class="skeleton h-12 w-12 rounded-full" />
                <div class="flex-1">
                  <div class="skeleton h-4 w-32" />
                  <div class="skeleton mt-2 h-3 w-24" />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Error */}
      {error && (
        <div class="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-400">{error}</div>
      )}

      {/* Grid */}
      {!loading && !error && (
        <div class="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((p, i) => {
            const hasCuestionable = p.cuestionable_count > 0;
            return (
              <a
                key={p.jne_id}
                href={`/investiga/detalle?id=${p.jne_id}`}
                class={`group flex items-center gap-4 rounded-xl border p-4 transition-all animate-fade-in-up ${
                  hasCuestionable
                    ? 'border-surface-300/30 bg-surface-100/50 hover:border-accent/30 hover:bg-surface-100 hover:shadow-lg hover:shadow-accent-glow'
                    : 'border-surface-300/15 bg-surface-100/20 opacity-60 hover:opacity-80'
                }`}
                style={{ animationDelay: `${i * 30}ms` }}
              >
                {/* Photo */}
                <div class="h-12 w-12 flex-shrink-0 overflow-hidden rounded-full bg-surface-200 ring-2 ring-surface-300/30">
                  {p.photo_url ? (
                    <img src={p.photo_url} alt={p.presidential_candidate} class="h-full w-full object-cover" loading="lazy" />
                  ) : (
                    <div class="flex h-full w-full items-center justify-center text-lg font-bold text-surface-500">
                      {p.presidential_candidate.charAt(0) || '?'}
                    </div>
                  )}
                </div>

                {/* Info */}
                <div class="min-w-0 flex-1">
                  <h3 class={`truncate text-sm font-semibold ${hasCuestionable ? 'text-white group-hover:text-accent-light' : 'text-surface-600'}`}>
                    {p.party_name}
                  </h3>
                  <p class="mt-0.5 truncate text-xs text-surface-500">{p.presidential_candidate}</p>

                  {/* Category badges */}
                  {p.category_counts.length > 0 && (
                    <div class="mt-1.5 flex flex-wrap gap-1">
                      {p.category_counts.map((cc) => {
                        const meta = EVENT_CATEGORIES[cc.category];
                        return (
                          <span
                            key={cc.category}
                            class={`inline-block rounded-full px-1.5 py-0.5 text-[10px] font-medium ${meta?.color || 'bg-surface-200 text-surface-500'}`}
                          >
                            {meta?.name || cc.category} {cc.count}
                          </span>
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* Count */}
                <div class="flex flex-col items-center flex-shrink-0">
                  <span class={`text-2xl font-bold ${hasCuestionable ? 'text-accent' : 'text-surface-500'}`}>
                    {p.cuestionable_count}
                  </span>
                  <span class="text-[10px] text-surface-500">
                    {p.cuestionable_count === 1 ? 'evento' : 'eventos'}
                  </span>
                </div>
              </a>
            );
          })}
        </div>
      )}

      {/* Empty */}
      {!loading && !error && filtered.length === 0 && (
        <div class="mt-12 text-center text-surface-500">No se encontraron partidos con "{query}"</div>
      )}
    </div>
  );
}
