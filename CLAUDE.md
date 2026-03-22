# Peru Elecciones 2026 - Vote Compass

Electoral matching platform for Peru's 2026 general elections (April 12, 2026). Quiz-based voter compass + RAG chatbot + adverse media monitoring.

## Quick Start

```bash
# Prerequisites: Python 3.13, Node.js >=22, Docker, uv
cp .env.example .env                  # Add your ANTHROPIC_API_KEY
make setup                            # Docker + deps + migrations + frontend build
make dev                              # http://localhost:8000
```

## Architecture

```
main.py (FastAPI + lifespan)
├── app/
│   ├── config.py                     # Settings via pydantic-settings (.env)
│   ├── models/
│   │   ├── candidates.py             # Candidate, PartyListItem, PartyDetail
│   │   ├── quiz.py                   # QuizQuestion, QuizAnswerRequest/Response, QuizResults
│   │   ├── news.py                   # NewsItem, NewsDetail, NewsResponse
│   │   ├── events.py                 # EventItem, EventDetail, EventPartyStance
│   │   └── investigation.py          # InvestigaPartyItem, InvestigaPartyDetail
│   ├── routers/
│   │   ├── candidates.py             # GET /candidates, /candidates/{id}
│   │   ├── quiz.py                   # POST /quiz/start, /quiz/answer, /quiz/results, /quiz/explain
│   │   ├── chat.py                   # POST /chat (RAG + LLM)
│   │   ├── news.py                   # GET /noticias, /noticias/{id}
│   │   ├── events.py                 # GET /events, /events/{id}
│   │   └── investigation.py          # GET /investiga, /investiga/{jne_id}
│   └── services/
│       ├── data_loader.py            # Loads JSON data into memory at startup
│       ├── adaptive_quiz.py          # Bayesian adaptive quiz with information gain
│       └── chat_service.py           # Hybrid search (vector + full-text) + Claude generation
├── migrations/
│   ├── 001_schema.sql                # Core DB schema (tracked via schema_migrations)
│   └── 002_political_events.sql      # Events + stances + event_chunks tables
├── scripts/
│   ├── migrate.py                    # SQL migration runner
│   ├── collect_candidates.py         # JNE API → JSON (--all for all elections)
│   ├── collect_planes.py             # Download PDFs + chunk + embed → pgvector
│   ├── collect_news.py               # RSS + search scraping + embed → pgvector
│   ├── collect_events.py             # political_events.json → embed → pgvector
│   └── extract_positions.py          # LLM-based position extraction (13 topics × 26 axes)
├── data/
│   ├── candidatos_2026.json          # 36 parties + presidential formulas
│   ├── all_candidates_2026.json      # All candidates across all elections
│   ├── question_bank.json            # Quiz questions across 13 topics
│   ├── posiciones_candidatos.json    # Extracted positions per party
│   ├── political_events.json         # Curated political events with party stances
│   └── planes_de_gobierno/           # Raw PDFs organized by party
└── web/                              # Frontend (Astro + Preact + Tailwind)
```

## Database

PostgreSQL 16 + pgvector. Connection: `postgresql://peru:peru2026@localhost:5434/peru_elecciones`

Schema managed via numbered SQL files in `migrations/`. Run with `make migrate`.

### Tables
- **parties** — Political parties (jne_id, name)
- **candidates** — All candidates (election_type, constituency, full_name)
- **government_plans** — One per party (party_key, party_name, pdf_path)
- **plan_chunks** — Text chunks with 768-dim BGE-M3 embeddings + tsvector
- **news_articles** — News with sentiment classification (adverse/neutral/positive)
- **news_mentions** — Article ↔ party links
- **news_chunks** — News text chunks with embeddings + tsvector
- **political_events** — Curated events (category, severity, sources)
- **event_party_stances** — Party positions on each event (stance + evidence)
- **event_chunks** — Event text chunks with 1024-dim embeddings + tsvector

### Embeddings
- Model: `BAAI/bge-m3` via sentence-transformers (local, free)
- Dimensions: 768, HNSW index (cosine), normalized

### RAG Pipeline
1. Embed query with BGE-M3
2. Hybrid search: vector similarity (top 30) + full-text ts_rank_cd (top 30)
3. Reciprocal Rank Fusion (RRF): `1/(60+rank)` merging
4. Top 6 plan chunks + top 3 news chunks
5. Context tagged by source type (Plan de Gobierno vs Cobertura mediática)
6. Generate with Claude Haiku (Spanish, neutral, paraphrased)

## Commands

```bash
make setup                # Full setup from scratch
make dev                  # Start API server (hot-reload)
make dev-frontend         # Start frontend dev server
make migrate              # Run pending DB migrations
make build                # Build frontend static site
make help                 # Show all commands
```

### Data Pipeline (one-time, SCOPE=presidential|formula|all)
```bash
make pipeline                       # Full pipeline (default: presidential)
make pipeline SCOPE=formula         # Full pipeline for formula (108 candidates)
make pipeline SCOPE=all             # Full pipeline for all elections

# Or step by step:
make fetch-candidates               # 1. Fetch candidates from JNE
make collect-content                # 2. Plans + news + events → embed → pgvector
make extract-positions              # 3. LLM extraction (costs API credits)
```

## Environment Variables

```
ANTHROPIC_API_KEY=...    # Required (Claude API)
DATABASE_URL=...         # Optional (has default)
```

## Style & Conventions

- **Language**: Python 3.13, async/await throughout
- **Code identifiers**: English everywhere
- **User-facing text**: Spanish (prompts, UI labels, error messages)
- **Package managers**: uv (backend), npm (frontend)
- **Linting**: ruff (check on pre-commit hook via pre-commit)
- **API models**: Pydantic, mirrored in `web/src/lib/types.ts` — keep in sync
- **Services**: initialized in FastAPI lifespan, attached to `app.state`
- **DB access**: raw psycopg (no ORM), migrations via numbered SQL files
- **Pre-commit**: runs `ruff check` on every commit (check only, no auto-fix). Installed automatically by `make setup`

### Frontend
- Astro (static output) + Preact islands + Tailwind CSS v4
- Static pages read JSON at build time (SSG) — no API needed
- Interactive features (quiz, chat, news, events) call API at runtime
- Preact signals for quiz state (persisted in sessionStorage)
- Chart.js for radar charts
