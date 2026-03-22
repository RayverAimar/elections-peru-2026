import { useState } from 'preact/hooks';

interface Candidate {
  id: number;
  name: string;
  candidate: string;
  photoUrl?: string;
}

interface Props {
  candidates: Candidate[];
}

export default function CandidateSearch({ candidates }: Props) {
  const [query, setQuery] = useState('');

  const filtered = candidates.filter((c) => {
    const q = query.toLowerCase();
    return c.name.toLowerCase().includes(q) || c.candidate.toLowerCase().includes(q);
  });

  return (
    <div>
      <div class="relative">
        <svg
          class="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-surface-500"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input
          type="text"
          placeholder="Buscar por partido o candidato..."
          value={query}
          onInput={(e) => setQuery((e.target as HTMLInputElement).value)}
          class="w-full rounded-xl border border-surface-300/50 bg-surface-100 py-3.5 pl-12 pr-4 text-sm text-white placeholder-surface-500 transition-all focus:border-accent/50 focus:outline-none focus:ring-2 focus:ring-accent/20"
        />
      </div>

      <p class="mt-4 text-sm text-surface-500">
        {filtered.length} {filtered.length === 1 ? 'partido' : 'partidos'}
        {query && ' encontrados'}
      </p>

      <div class="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {filtered.map((c) => (
          <a
            key={c.id}
            href={`/candidatos/${c.id}`}
            class="group flex items-center gap-4 rounded-xl border border-surface-300/30 bg-surface-100/50 p-4 transition-all hover:border-accent/30 hover:bg-surface-100 hover:shadow-lg hover:shadow-accent-glow"
          >
            <div class="h-12 w-12 flex-shrink-0 overflow-hidden rounded-full bg-surface-200 ring-2 ring-surface-300/30">
              {c.photoUrl ? (
                <img src={c.photoUrl} alt={c.candidate} class="h-full w-full object-cover" loading="lazy" />
              ) : (
                <div class="flex h-full w-full items-center justify-center text-lg font-bold text-surface-500">
                  {c.candidate.charAt(0)}
                </div>
              )}
            </div>
            <div class="min-w-0 flex-1">
              <h3 class="truncate text-sm font-semibold text-white group-hover:text-accent-light">
                {c.name}
              </h3>
              <p class="mt-0.5 truncate text-xs text-surface-600">{c.candidate}</p>
            </div>
            <svg
              class="h-4 w-4 flex-shrink-0 text-surface-500 transition-all group-hover:translate-x-0.5 group-hover:text-accent"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
          </a>
        ))}
      </div>

      {filtered.length === 0 && (
        <div class="mt-12 text-center">
          <p class="text-surface-500">No se encontraron partidos con "{query}"</p>
        </div>
      )}
    </div>
  );
}
