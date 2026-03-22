#!/usr/bin/env python3
"""Collect, scrape, embed, and store political events for Peru 2026.

Pipeline:
  Phase 1: For each seed event, search 3 static newspaper sites and fetch article content.
  Phase 2: Build political_events.json from real scraped content.
  Phase 3: Embed with BGE-M3 and store in political_events + event_chunks tables.

Usage:
    python scripts/collect_events.py              # Full pipeline
    python scripts/collect_events.py --dry-run    # Scrape but don't store
    python scripts/collect_events.py --skip-scrape # Only embed seed data (no scraping)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote_plus

import psycopg
import requests
import trafilatura
from _db import DATABASE_URL
from _news_common import make_url_hash, normalize_text
from pgvector.psycopg import register_vector
from sentence_transformers import SentenceTransformer

# ────────────────────────────── Paths ──────────────────────────────

_ROOT = Path(__file__).resolve().parent.parent
SEED_JSON = _ROOT / "data" / "political_events_seed.json"
OUTPUT_JSON = _ROOT / "data" / "political_events.json"

# ────────────────────────────── Constants ──────────────────────────────

REQUEST_DELAY = 2.0  # seconds between HTTP requests

MAX_CHUNK_CHARS = 3200
MIN_CHUNK_CHARS = 100
OVERLAP_CHARS = 200

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
]

# Newspaper search configs: (base_search_url_template, article_url_regex)
NEWSPAPER_SITES: list[tuple[str, str]] = [
    (
        "https://elbuho.pe/?s={query}",
        r'href="(https://elbuho\.pe/\d{4}/\d{2}/[^"]+)"',
    ),
    (
        "https://sudaca.pe/?s={query}",
        r'href="(https://sudaca\.pe/noticia/[^"]+)"',
    ),
    (
        "https://wayka.pe/?s={query}",
        r'href="(https://wayka\.pe/[^"]+)"',
    ),
]

# URL patterns that indicate non-article pages (category/tag pages, pagination, etc.)
NON_ARTICLE_PATTERNS = re.compile(
    r"/(category|tag|etiqueta|autor|author|page|pagina|search|\?s=|feed|sitemap)",
    re.IGNORECASE,
)

# Peruvian political parties for stance extraction
KNOWN_PARTIES = [
    "Fuerza Popular",
    "Alianza para el Progreso",
    "Renovación Popular",
    "Acción Popular",
    "Partido Aprista",
    "Perú Libre",
    "Juntos por el Perú",
    "Podemos Perú",
    "Somos Perú",
    "Avancemos",
    "Frente Amplio",
    "UPP",
    "PPC",
    "Fujimorismo",
    "Fujimori",
    "Castillo",
    "Boluarte",
    "Vizcarra",
    "García",
    "Toledo",
]


# ────────────────────────────── HTTP Session ──────────────────────────────


def make_session() -> requests.Session:
    """Create a requests.Session with User-Agent rotation and sane timeouts."""
    import random

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
    )
    return session


# ────────────────────────────── Phase 1: Scraping ──────────────────────────────


def is_article_url(url: str) -> bool:
    """Return True if URL looks like a real article (not a category/tag/page)."""
    if NON_ARTICLE_PATTERNS.search(url):
        return False
    # Must have a non-trivial path (at least one slash segment with content)
    path = url.split("//", 1)[-1].split("/", 1)[-1] if "//" in url else url
    segments = [s for s in path.split("/") if s]
    return len(segments) >= 1


def fetch_search_results(
    session: requests.Session,
    query: str,
    url_template: str,
    article_regex: str,
) -> list[str]:
    """Fetch search page and extract article URLs matching the given regex."""
    import random

    encoded_query = quote_plus(query)
    search_url = url_template.format(query=encoded_query)

    # Rotate User-Agent per request
    session.headers["User-Agent"] = random.choice(USER_AGENTS)

    try:
        resp = session.get(search_url, timeout=15)
        resp.raise_for_status()
    except requests.RequestException:
        return []

    time.sleep(REQUEST_DELAY)

    raw_urls = re.findall(article_regex, resp.text)
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for url in raw_urls:
        # Strip trailing query strings / fragments
        clean = re.sub(r"[?#].*$", "", url.rstrip("/"))
        if clean not in seen and is_article_url(clean):
            seen.add(clean)
            unique.append(clean)

    return unique


def score_relevance(content: str, title: str, event_title: str) -> int:
    """Score how relevant an article is to an event by keyword overlap."""
    event_norm = normalize_text(event_title)
    content_norm = normalize_text(f"{title} {content}")

    # Extract meaningful words (>3 chars) from the event title
    keywords = [w for w in re.split(r"\W+", event_norm) if len(w) > 3]
    if not keywords:
        return 0

    return sum(1 for kw in keywords if kw in content_norm)


def fetch_article(
    session: requests.Session,
    url: str,
) -> dict | None:
    """Fetch a single article URL and extract content with trafilatura.

    Returns dict with keys: url, title, content, date, evidence
    or None if extraction failed.
    """
    import random

    session.headers["User-Agent"] = random.choice(USER_AGENTS)

    try:
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
    except requests.RequestException:
        return None

    time.sleep(REQUEST_DELAY)

    html = resp.text
    result = trafilatura.bare_extraction(html, include_comments=False)

    if not result:
        return None

    content = getattr(result, "text", "") or ""
    title = getattr(result, "title", "") or ""
    date = getattr(result, "date", "") or ""

    if not content or len(content) < 100:
        return None

    # Evidence: first 2-3 sentences
    sentences = re.split(r"(?<=[.!?])\s+", content.strip())
    evidence = " ".join(sentences[:3]).strip()

    return {
        "url": url,
        "title": title,
        "content": content,
        "date": date,
        "evidence": evidence,
    }


def search_event_articles(
    session: requests.Session,
    event: dict,
    top_n: int = 3,
) -> list[dict]:
    """Search all newspaper sites for articles related to an event.

    Returns the top_n most relevant fetched articles.
    """
    candidate_urls: list[str] = []

    for url_template, article_regex in NEWSPAPER_SITES:
        for query in event.get("search_queries", []):
            urls = fetch_search_results(session, query, url_template, article_regex)
            candidate_urls.extend(urls)

    # Deduplicate candidate URLs
    seen: set[str] = set()
    deduped: list[str] = []
    for url in candidate_urls:
        h = make_url_hash(url)
        if h not in seen:
            seen.add(h)
            deduped.append(url)

    # Fetch each candidate and score relevance
    scored: list[tuple[int, dict]] = []
    for url in deduped:
        article = fetch_article(session, url)
        if article is None:
            continue
        score = score_relevance(
            article["content"], article["title"], event["title"]
        )
        if score > 0:
            scored.append((score, article))

    # Sort descending by relevance score and return top N
    scored.sort(key=lambda x: x[0], reverse=True)
    return [art for _, art in scored[:top_n]]


# ────────────────────────────── Party Stance Extraction ──────────────────────────────


def extract_party_stances(articles: list[dict]) -> dict[str, dict]:
    """Extract party stances from article content where parties are explicitly mentioned.

    Only includes stances with clear, attributable positions.
    Returns: {party_name: {stance, detail, evidence, source_url}}
    """
    stances: dict[str, dict] = {}

    # Sentences that indicate a stance
    stance_indicators = {
        "support": ["apoy", "respald", "promov", "defendi", "propus"],
        "against": [
            "rechaz", "denunci", "critic", "opuso", "condeno", "protest",
            "impugn", "cuestio",
        ],
        "neutral": ["señal", "indic", "manifest", "declar", "afirm", "dijo"],
    }

    for article in articles:
        content = article.get("content", "")
        url = article.get("url", "")

        # Split into sentences for local context
        sentences = re.split(r"(?<=[.!?])\s+", content)

        for party in KNOWN_PARTIES:
            party_norm = normalize_text(party)
            for sent in sentences:
                sent_norm = normalize_text(sent)
                if party_norm not in sent_norm:
                    continue

                # Determine stance from sentence
                detected_stance = "neutral"
                for stance_label, keywords in stance_indicators.items():
                    if any(kw in sent_norm for kw in keywords):
                        detected_stance = stance_label
                        break

                # Only store if not already captured (first mention wins)
                if party not in stances:
                    stances[party] = {
                        "stance": detected_stance,
                        "detail": sent.strip()[:300],
                        "evidence": [
                            {
                                "quote": sent.strip()[:300],
                                "source_url": url,
                            }
                        ],
                    }
                    break  # One stance per party per article pass

    return stances


# ────────────────────────────── Phase 2: Build Events JSON ──────────────────────────────


def build_event_record(seed: dict, articles: list[dict]) -> dict:
    """Compose a full event record from seed data + scraped articles."""
    event: dict = {
        "id": seed["id"],
        "title": seed["title"],
        "date": seed["date"],
        "category": seed["category"],
        "severity": seed["severity"],
    }

    if articles:
        best = articles[0]

        # Description: first 3-4 sentences from the best article
        sentences = re.split(r"(?<=[.!?])\s+", best["content"].strip())
        description = " ".join(sentences[:4]).strip()
        event["description"] = description

        # Why it matters: derived from following sentences or fallback
        if len(sentences) > 4:
            why = " ".join(sentences[4:7]).strip()
        else:
            why = (
                f"Este evento marcó un hito importante en la política peruana "
                f"relacionado con {seed['category']}."
            )
        event["why_it_matters"] = why

        # Sources: URLs of scraped articles
        event["sources"] = [a["url"] for a in articles]

        # Party stances extracted from all articles
        stances = extract_party_stances(articles)
        if stances:
            event["party_stances"] = stances

    else:
        # Fallback: use seed title as description, Wikipedia as source
        title_slug = re.sub(r"\s+", "_", seed["title"][:60])
        wiki_url = f"https://es.wikipedia.org/wiki/{title_slug}"
        event["description"] = seed["title"]
        event["why_it_matters"] = (
            f"Evento relevante para comprender el contexto político del Perú "
            f"en materia de {seed['category']}."
        )
        event["sources"] = [wiki_url]
        event["party_stances"] = {}

    return event


# ────────────────────────────── Phase 3: Embed + Store ──────────────────────────────


def build_event_content(event: dict) -> str:
    """Build rich text chunk content with metadata header for RAG context."""
    title = event.get("title", "")
    date_str = event.get("date") or event.get("event_date") or ""
    category = event.get("category", "")
    sources = event.get("sources", [])
    description = event.get("description", "")
    why_it_matters = event.get("why_it_matters", "")
    stances = event.get("party_stances", {})

    sources_str = ", ".join(sources[:3]) if sources else "N/A"

    header = (
        f"EVENT: {title}\n"
        f"DATE: {date_str}\n"
        f"CATEGORY: {category}\n"
        f"SOURCES: {sources_str}\n"
        f"TYPE: Political event\n\n"
    )

    body = description

    if why_it_matters:
        body += f"\n\nWHY IT MATTERS: {why_it_matters}"

    if stances:
        body += "\n\nPARTY STANCES:"
        for party_name, stance_data in stances.items():
            stance_val = stance_data.get("stance", "")
            detail = stance_data.get("detail", "")
            if detail:
                body += f"\n- {party_name}: {stance_val}. {detail}"
            else:
                body += f"\n- {party_name}: {stance_val}."

    return header + body


def chunk_event_content(content: str, source_url: str) -> list[dict]:
    """Chunk event content into RAG-ready segments."""
    if len(content) <= MAX_CHUNK_CHARS:
        return [
            {
                "content": content,
                "token_count": len(content) // 4,
                "index": 0,
                "source_url": source_url,
            }
        ]

    # Split header from body at the first double newline
    header_end = content.find("\n\n")
    if header_end == -1:
        header = ""
        body = content
    else:
        header = content[: header_end + 2]
        body = content[header_end + 2 :]

    paragraphs = re.split(r"\n\s*\n", body)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    chunks: list[dict] = []
    current = ""
    max_body = MAX_CHUNK_CHARS - len(header)

    for para in paragraphs:
        if (
            len(current) + len(para) + 2 > max_body
            and len(current) >= MIN_CHUNK_CHARS
        ):
            chunks.append(
                {
                    "content": header + current,
                    "token_count": len(current) // 4,
                    "source_url": source_url,
                }
            )
            overlap = current[-OVERLAP_CHARS:] if len(current) > OVERLAP_CHARS else ""
            current = overlap + "\n\n" + para if overlap else para
        else:
            current = current + "\n\n" + para if current else para

    if current and len(current) >= MIN_CHUNK_CHARS:
        chunks.append(
            {
                "content": header + current,
                "token_count": len(current) // 4,
                "source_url": source_url,
            }
        )

    if not chunks:
        chunks.append(
            {
                "content": content[:MAX_CHUNK_CHARS],
                "token_count": MAX_CHUNK_CHARS // 4,
                "source_url": source_url,
            }
        )

    for i, chunk in enumerate(chunks):
        chunk["index"] = i

    return chunks


def store_event(conn: psycopg.Connection, event: dict, model: SentenceTransformer) -> int:
    """Insert a single event + stances + chunks into the DB.

    Returns number of chunks inserted.
    """
    event_id = event["id"]
    sources = event.get("sources", [])
    best_source_url = sources[0] if sources else ""

    # Insert political_events row
    conn.execute(
        """
        INSERT INTO political_events
            (id, title, event_date, category, severity,
             description, why_it_matters, sources)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
        """,
        (
            event_id,
            event.get("title", ""),
            event.get("date") or event.get("event_date") or None,
            event.get("category", ""),
            event.get("severity", ""),
            event.get("description", ""),
            event.get("why_it_matters", ""),
            sources,
        ),
    )

    # Insert party stances
    stances = event.get("party_stances", {})
    for party_name, stance_data in stances.items():
        evidence_items = stance_data.get("evidence", [])
        # Store evidence list as JSONB
        evidence_json = json.dumps(evidence_items, ensure_ascii=False)

        conn.execute(
            """
            INSERT INTO event_party_stances
                (event_id, party_name, stance, detail, evidence)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            ON CONFLICT DO NOTHING
            """,
            (
                event_id,
                party_name,
                stance_data.get("stance", ""),
                stance_data.get("detail", ""),
                evidence_json,
            ),
        )

    # Build content and chunk
    content = build_event_content(event)
    chunks = chunk_event_content(content, best_source_url)

    # Embed all chunks in one batch
    texts = [c["content"] for c in chunks]
    embeddings = model.encode(texts, batch_size=32, normalize_embeddings=True)

    for chunk, embedding in zip(chunks, embeddings, strict=False):
        conn.execute(
            """
            INSERT INTO event_chunks
                (event_id, chunk_index, content, source_url,
                 token_count, embedding)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (
                event_id,
                chunk["index"],
                chunk["content"],
                chunk["source_url"],
                chunk["token_count"],
                embedding.tolist(),
            ),
        )

    conn.commit()
    return len(chunks)


# ────────────────────────────── Main Pipeline ──────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape, embed, and store political events for Peru 2026"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scrape and build JSON but do not store to DB",
    )
    parser.add_argument(
        "--skip-scrape",
        action="store_true",
        help="Skip web scraping; only embed and store data from existing political_events.json",
    )
    return parser.parse_args()


def load_seed() -> list[dict]:
    """Load events from the seed JSON file."""
    if not SEED_JSON.exists():
        print(f"ERROR: Seed file not found: {SEED_JSON}", file=sys.stderr)
        sys.exit(1)

    with open(SEED_JSON, encoding="utf-8") as f:
        data = json.load(f)

    return data.get("events", []) if isinstance(data, dict) else data


def run_scrape_phase(seeds: list[dict]) -> list[dict]:
    """Phase 1 + 2: Search newspapers, fetch articles, build event records."""
    session = make_session()
    events: list[dict] = []

    print("=" * 60)
    print("PHASE 1+2: Scraping newspaper articles")
    print("=" * 60)

    for i, seed in enumerate(seeds, 1):
        title_short = seed["title"][:55]
        print(f"[{i}/{len(seeds)}] Searching: {title_short}", end=" ", flush=True)

        articles = search_event_articles(session, seed, top_n=3)
        print(f"→ {len(articles) + _count_candidates(seed)} candidates found → {len(articles)} kept", flush=True)

        event = build_event_record(seed, articles)
        events.append(event)

    return events


def _count_candidates(seed: dict) -> int:
    """Estimate candidate URLs before filtering (display only)."""
    return len(seed.get("search_queries", [])) * len(NEWSPAPER_SITES)


def run_embed_store_phase(
    events: list[dict],
    dry_run: bool = False,
) -> dict:
    """Phase 3: Load BGE-M3, embed, insert into DB, write output JSON."""
    stats = {"inserted": 0, "skipped": 0, "total_chunks": 0}

    # Always write the JSON output
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(
            {"version": "3.0", "events": events},
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"\nWrote {len(events)} events to {OUTPUT_JSON}")

    if dry_run:
        print("\n[DRY RUN] Skipping DB insertion.")
        return stats

    print("\nLoading BGE-M3 embedding model...")
    model = SentenceTransformer("BAAI/bge-m3")
    print(f"Model loaded. Dimensions: {model.get_sentence_embedding_dimension()}\n")

    conn = psycopg.connect(DATABASE_URL)
    register_vector(conn)

    print("=" * 60)
    print("PHASE 3: Embedding and storing events")
    print("=" * 60)

    for i, event in enumerate(events, 1):
        event_id = event.get("id", "")
        title_short = event.get("title", "")[:55]
        print(f"  [{i}/{len(events)}] {title_short}...", end=" ", flush=True)

        if not event_id:
            print("SKIP (no id)")
            stats["skipped"] += 1
            continue

        # Skip if already in DB
        existing = conn.execute(
            "SELECT id FROM political_events WHERE id = %s",
            (event_id,),
        ).fetchone()

        if existing:
            print("SKIP (already stored)")
            stats["skipped"] += 1
            continue

        n_chunks = store_event(conn, event, model)
        stats["inserted"] += 1
        stats["total_chunks"] += n_chunks

        category = event.get("category", "")
        severity = event.get("severity", "")
        n_sources = len(event.get("sources", []))
        print(f"→ {n_chunks} chunk(s) | {category} | {severity} | {n_sources} source(s)")

    conn.close()
    return stats


def main() -> None:
    args = parse_args()

    if args.skip_scrape:
        # Load from existing political_events.json (already scraped)
        if not OUTPUT_JSON.exists():
            print(
                f"ERROR: --skip-scrape requires {OUTPUT_JSON} to already exist.",
                file=sys.stderr,
            )
            sys.exit(1)

        print(f"Loading existing events from {OUTPUT_JSON}")
        with open(OUTPUT_JSON, encoding="utf-8") as f:
            data = json.load(f)
        events = data.get("events", []) if isinstance(data, dict) else data
        print(f"Loaded {len(events)} events.\n")

    else:
        seeds = load_seed()
        print(f"Loaded {len(seeds)} seed events from {SEED_JSON}\n")
        events = run_scrape_phase(seeds)

    stats = run_embed_store_phase(events, dry_run=args.dry_run)

    # Summary
    print(f"\n{'=' * 60}")
    print("PIPELINE COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Events processed: {len(events)}")
    if not args.dry_run:
        print(f"  Events inserted:  {stats['inserted']}")
        print(f"  Events skipped:   {stats['skipped']}")
        print(f"  Total chunks:     {stats['total_chunks']}")
    else:
        print("  [DRY RUN] No DB writes performed.")


if __name__ == "__main__":
    main()
