import { useEffect, useState, useRef } from 'preact/hooks';
import { loadResults, resetQuiz } from '../lib/quiz-store';
import { getCandidateNewsProfile } from '../lib/api';
import { TOPICS } from '../lib/constants';
import type { QuizResultsResponse, CandidateNewsProfile } from '../lib/types';
import MatchCard from './MatchCard';
import TopicBreakdown from './TopicBreakdown';
import RadarChart from './RadarChart';

const CATEGORY_LABELS: Record<string, string> = {
  corruption: 'Corrupción',
  legal: 'Judicial',
  fraud: 'Fraude',
  ethics: 'Ética',
  violence: 'Violencia',
};

const SENTIMENT_COLORS: Record<string, string> = {
  adverse: 'bg-red-500/20 text-red-400 border-red-500/30',
  neutral: 'bg-surface-300/20 text-surface-600 border-surface-300/30',
  positive: 'bg-green-500/20 text-green-400 border-green-500/30',
};

function NewsProfileSection({ party }: { party: string }) {
  const [profile, setProfile] = useState<CandidateNewsProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    getCandidateNewsProfile(party)
      .then(setProfile)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [party]);

  if (loading) {
    return (
      <div class="mt-16 animate-fade-in-up">
        <h2 class="text-xl font-bold text-white">Lo que deberías saber</h2>
        <div class="mt-4 flex items-center gap-3 text-sm text-surface-500">
          <div class="h-4 w-4 animate-spin rounded-full border-2 border-surface-300/20 border-t-accent" />
          Cargando noticias...
        </div>
      </div>
    );
  }

  if (error || !profile || profile.total_articles === 0) return null;

  const total = profile.total_articles;
  const adversePct = total > 0 ? Math.round((profile.adverse_count / total) * 100) : 0;
  const positivePct = total > 0 ? Math.round((profile.positive_count / total) * 100) : 0;

  return (
    <div class="mt-16 animate-fade-in-up">
      <h2 class="text-xl font-bold text-white">Lo que deberías saber</h2>
      <p class="mt-1 text-sm text-surface-500">
        Noticias recientes sobre {profile.candidate || profile.party} en medios peruanos.
      </p>

      {/* Sentiment summary bar */}
      <div class="mt-4 rounded-xl border border-surface-300/20 bg-surface-100/40 p-4">
        <div class="flex items-center gap-3 text-xs text-surface-500">
          <span>{total} noticias analizadas:</span>
          <span class="text-red-400 font-semibold">{profile.adverse_count} adversas ({adversePct}%)</span>
          <span class="text-surface-600">{profile.neutral_count} neutrales</span>
          <span class="text-green-400 font-semibold">{profile.positive_count} positivas ({positivePct}%)</span>
        </div>
        <div class="mt-2 flex h-2 rounded-full overflow-hidden bg-surface-300/20">
          {profile.adverse_count > 0 && (
            <div class="bg-red-500/80" style={{ width: `${adversePct}%` }} />
          )}
          {profile.neutral_count > 0 && (
            <div class="bg-surface-400/40" style={{ width: `${100 - adversePct - positivePct}%` }} />
          )}
          {profile.positive_count > 0 && (
            <div class="bg-green-500/80" style={{ width: `${positivePct}%` }} />
          )}
        </div>

        {/* Adverse categories */}
        {Object.keys(profile.adverse_categories).length > 0 && (
          <div class="mt-3 flex flex-wrap gap-2">
            {Object.entries(profile.adverse_categories).map(([cat, count]) => (
              <span key={cat} class="rounded-full border border-red-500/30 bg-red-500/10 px-2.5 py-0.5 text-xs text-red-400">
                {CATEGORY_LABELS[cat] || cat}: {count}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Controversial news */}
      {profile.controversial.length > 0 && (
        <div class="mt-6">
          <h3 class="text-sm font-semibold text-red-400 uppercase tracking-wider">Noticias adversas</h3>
          <div class="mt-2 space-y-2">
            {profile.controversial.map((article) => (
              <a
                key={article.id}
                href={article.url}
                target="_blank"
                rel="noopener noreferrer"
                class="block rounded-lg border border-red-500/20 bg-red-500/5 p-3 transition hover:bg-red-500/10"
              >
                <p class="text-sm text-white leading-snug">{article.title}</p>
                <div class="mt-1.5 flex items-center gap-2 text-xs text-surface-500">
                  <span>{article.source_name}</span>
                  {article.published_at && (
                    <span>· {new Date(article.published_at).toLocaleDateString('es-PE')}</span>
                  )}
                </div>
              </a>
            ))}
          </div>
        </div>
      )}

      {/* Favorable news */}
      {profile.favorable.length > 0 && (
        <div class="mt-6">
          <h3 class="text-sm font-semibold text-green-400 uppercase tracking-wider">Noticias favorables</h3>
          <div class="mt-2 space-y-2">
            {profile.favorable.map((article) => (
              <a
                key={article.id}
                href={article.url}
                target="_blank"
                rel="noopener noreferrer"
                class="block rounded-lg border border-green-500/20 bg-green-500/5 p-3 transition hover:bg-green-500/10"
              >
                <p class="text-sm text-white leading-snug">{article.title}</p>
                <div class="mt-1.5 flex items-center gap-2 text-xs text-surface-500">
                  <span>{article.source_name}</span>
                  {article.published_at && (
                    <span>· {new Date(article.published_at).toLocaleDateString('es-PE')}</span>
                  )}
                </div>
              </a>
            ))}
          </div>
        </div>
      )}

      {/* Recent articles list */}
      {profile.recent.length > 0 && (
        <div class="mt-6">
          <h3 class="text-sm font-semibold text-surface-600 uppercase tracking-wider">Últimas noticias</h3>
          <div class="mt-2 space-y-1">
            {profile.recent.map((article) => (
              <a
                key={article.id}
                href={article.url}
                target="_blank"
                rel="noopener noreferrer"
                class="flex items-start gap-2 rounded-lg p-2 transition hover:bg-surface-200/30"
              >
                <span class={`mt-0.5 inline-flex h-2 w-2 shrink-0 rounded-full ${
                  article.sentiment_label === 'adverse' ? 'bg-red-500' :
                  article.sentiment_label === 'positive' ? 'bg-green-500' : 'bg-surface-400'
                }`} />
                <div>
                  <p class="text-sm text-surface-700 leading-snug">{article.title}</p>
                  <span class="text-xs text-surface-500">{article.source_name}</span>
                </div>
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function QuizResults() {
  const [data, setData] = useState<QuizResultsResponse | null>(null);
  const [showRadar, setShowRadar] = useState(false);
  const [showBreakdown, setShowBreakdown] = useState(false);
  const [showNews, setShowNews] = useState(false);
  const loaded = useRef(false);

  useEffect(() => {
    if (loaded.current) return;
    loaded.current = true;
    const results = loadResults();
    if (!results) { window.location.href = '/brujula'; return; }
    setData(results);
    setTimeout(() => setShowRadar(true), 600);
    setTimeout(() => setShowBreakdown(true), 900);
    setTimeout(() => setShowNews(true), 1200);
    const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (!prefersReduced) {
      setTimeout(() => {
        import('canvas-confetti').then(({ default: confetti }) => {
          confetti({ particleCount: 80, spread: 70, origin: { y: 0.6 }, colors: ['#E11D48', '#FB7185', '#FAFAFA'] });
        });
      }, 400);
    }
  }, []);

  if (!data) {
    return (
      <div class="flex items-center justify-center py-24">
        <div class="relative h-12 w-12">
          <div class="absolute inset-0 animate-spin rounded-full border-3 border-surface-300/20 border-t-accent" />
        </div>
      </div>
    );
  }

  const topMatch = data.top_candidates[0];

  // Radar chart: use agreement_by_topic from top match (0-100% per topic)
  const radarTopics = topMatch ? Object.keys(topMatch.agreement_by_topic) : [];
  const topicLabels = radarTopics.map((t) => TOPICS[t]?.name || t);
  const topMatchValues = radarTopics.map((t) => topMatch?.agreement_by_topic[t] ?? 0);
  // For user profile, normalize raw axis values to 0-100 scale
  const userValues = radarTopics.map((topic) => {
    // Find user_profile keys that belong to this topic
    const topicKeys = Object.keys(data.user_profile).filter((k) => k.startsWith(topic + '.'));
    if (topicKeys.length === 0) return 50; // neutral if no data
    const avg = topicKeys.reduce((sum, k) => sum + data.user_profile[k], 0) / topicKeys.length;
    // Map from [-2, +2] range to [0, 100]
    return Math.max(0, Math.min(100, ((avg + 2) / 4) * 100));
  });

  return (
    <div class="mx-auto max-w-4xl">
      <div class="animate-fade-in-up text-center">
        <p class="text-xs font-bold uppercase tracking-[0.2em] text-accent">El Chasqui encontró</p>
        <h1 class="mt-3 text-3xl font-black text-white sm:text-4xl">Tus Candidatos</h1>
        <p class="mt-2 text-surface-600">
          Basado en {data.total_questions_answered} preguntas adaptativas.
        </p>
      </div>

      <div class="mt-10 space-y-3">
        {data.top_candidates.map((match, i) => (
          <MatchCard key={match.party} match={match} rank={i + 1} isTop={i === 0} delay={i * 150} />
        ))}
      </div>

      {/* Evidence section for top match */}
      {showBreakdown && topMatch && topMatch.evidence.length > 0 && (
        <div class="mt-16 animate-fade-in-up">
          <h2 class="text-xl font-bold text-white">¿Por qué este resultado?</h2>
          <p class="mt-1 text-sm text-surface-500">Las respuestas que más influyeron en tu match con {topMatch.party}.</p>
          <div class="mt-4 space-y-2">
            {topMatch.evidence.slice(0, 5).map((ev, i) => (
              <div key={i} class="rounded-xl border border-surface-300/20 bg-surface-100/40 p-4 animate-fade-in-up" style={{ animationDelay: `${i * 80}ms` }}>
                <p class="text-sm text-white">{ev.question}</p>
                <div class="mt-2 flex items-center gap-4 text-xs">
                  <span class="text-surface-500">
                    Tú: <span class={ev.user_answer === ev.party_score ? 'text-green-400 font-semibold' : 'text-surface-700'}>{ev.user_answer > 0 ? '+' : ''}{ev.user_answer}</span>
                  </span>
                  <span class="text-surface-500">
                    {topMatch.party}: <span class="text-surface-700">{ev.party_score > 0 ? '+' : ''}{ev.party_score}</span>
                  </span>
                </div>
                <p class="mt-1.5 text-xs text-surface-500 leading-relaxed">{ev.explanation}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {showRadar && topMatch && (
        <div class="mt-16 animate-fade-in-up">
          <h2 class="text-xl font-bold text-white">Comparación por temas</h2>
          <p class="mt-1 text-sm text-surface-500">Tu perfil vs {topMatch.party}</p>
          <div class="mt-6 flex justify-center">
            <div class="w-full max-w-lg rounded-2xl border border-surface-300/20 bg-surface-100/40 p-6 backdrop-blur-sm">
              <RadarChart labels={topicLabels} userValues={userValues} matchValues={topMatchValues} matchLabel={topMatch.party} />
            </div>
          </div>
        </div>
      )}

      {showBreakdown && topMatch && (
        <div class="mt-16 animate-fade-in-up">
          <h2 class="text-xl font-bold text-white">Desglose por tema</h2>
          <div class="mt-4">
            <TopicBreakdown agreement={topMatch.agreement_by_topic} topCandidates={data.top_candidates} />
          </div>
        </div>
      )}

      {/* News profile: "Lo que deberías saber" */}
      {showNews && topMatch && (
        <NewsProfileSection party={topMatch.party} />
      )}

      <div class="mt-16 flex flex-col items-center gap-4 animate-fade-in sm:flex-row sm:justify-center" style={{ animationDelay: '1.5s' }}>
        <button
          onClick={() => {
            if (window.confirm('¿Estás seguro? Perderás tus respuestas actuales.')) {
              resetQuiz();
              window.location.href = '/brujula';
            }
          }}
          class="hover-scale rounded-xl border border-surface-300/40 px-6 py-3 text-sm font-semibold text-surface-700 transition hover:bg-surface-200/30"
        >
          Repetir Brújula
        </button>
        <a href="/chat" class="hover-scale rounded-xl bg-accent px-6 py-3 text-sm font-bold text-white shadow-lg shadow-accent/25 transition-all hover:bg-accent-dark">
          Chatea sobre los candidatos
        </a>
      </div>
    </div>
  );
}
