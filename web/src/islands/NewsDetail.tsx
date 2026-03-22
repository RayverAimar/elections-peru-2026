import { useState, useEffect } from 'preact/hooks';
import { getNewsDetail } from '../lib/api';
import { SENTIMENT_LABELS, SENTIMENT_STYLES } from '../lib/constants';
import { formatDate, sanitizeUrl } from '../lib/utils';
import type { NewsDetail as NewsDetailType } from '../lib/types';

export default function NewsDetail() {
  const [article, setArticle] = useState<NewsDetailType | null>(null);
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
    getNewsDetail(Number(id))
      .then(setArticle)
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

  if (error || !article) {
    return (
      <div class="text-center py-12">
        <p class="text-lg font-semibold text-white">Noticia no encontrada</p>
        <p class="mt-2 text-surface-600">La noticia no existe o el servicio no está disponible.</p>
      </div>
    );
  }

  const sentLabel = SENTIMENT_LABELS[article.sentiment_label] || article.sentiment_label;
  const sentStyle = SENTIMENT_STYLES[article.sentiment_label] || 'bg-surface-200 text-surface-600';

  return (
    <article class="animate-fade-in-up">
      <div class="flex items-center gap-3 flex-wrap">
        <span class={`inline-block rounded-full px-3 py-1 text-xs font-medium ${sentStyle}`}>
          {sentLabel}
        </span>
        <span class="text-sm text-surface-500">{article.source_name}</span>
        {article.published_at && (
          <span class="text-sm text-surface-500">{formatDate(article.published_at)}</span>
        )}
      </div>

      <h1 class="mt-5 text-2xl font-bold text-white sm:text-3xl">{article.title}</h1>

      {article.description && (
        <p class="mt-4 text-lg text-surface-600">{article.description}</p>
      )}

      {article.content && (
        <div class="mt-6 whitespace-pre-wrap text-sm leading-relaxed text-surface-700">
          {article.content}
        </div>
      )}

      {article.mentions && article.mentions.length > 0 && (
        <div class="mt-8">
          <h3 class="text-xs font-semibold uppercase tracking-wider text-surface-500">
            Partidos mencionados
          </h3>
          <div class="mt-2 flex flex-wrap gap-2">
            {article.mentions.map((m) => (
              <span key={m} class="inline-block rounded-full bg-accent/10 px-3 py-1 text-xs font-medium text-accent-light">
                {m}
              </span>
            ))}
          </div>
        </div>
      )}

      <div class="mt-8">
        <a
          href={sanitizeUrl(article.url)}
          target="_blank"
          rel="noopener noreferrer"
          class="inline-flex items-center gap-2 text-sm font-medium text-accent transition hover:text-accent-light"
        >
          Ver artículo original
          <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
          </svg>
        </a>
      </div>
    </article>
  );
}
