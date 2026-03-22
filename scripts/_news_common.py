"""Shared utilities for news ingestion scripts.

Pure utility module: only standard library imports.
No sentence_transformers, psycopg, or other heavy dependencies.
"""

import hashlib
import re
import unicodedata

# ────────────────────────────── Chunking constants ──────────────────────────────

MAX_CHUNK_CHARS = 3200
MIN_CHUNK_CHARS = 100
OVERLAP_CHARS = 200

# ────────────────────────────── Classification keywords ──────────────────────────────

ADVERSE_KEYWORDS: dict[str, list[str]] = {
    "corruption": [
        "corrupcion",
        "corrupto",
        "soborno",
        "cohecho",
        "malversacion",
        "peculado",
        "lavado de activos",
        "enriquecimiento ilicito",
        "coima",
        "irregularidad",
    ],
    "legal": [
        "investigacion fiscal",
        "investigado por",
        "acusado de",
        "procesado",
        "sentenciado",
        "denuncia penal",
        "fiscalia",
        "prision preventiva",
        "detencion",
        "orden de captura",
        "profugo",
        "juicio oral",
        "impedimento de salida",
    ],
    "fraud": [
        "fraude",
        "estafa",
        "falsificacion",
        "plagio",
        "documentos falsos",
        "firmas falsas",
    ],
    "ethics": [
        "escandalo",
        "nepotismo",
        "conflicto de intereses",
        "abuso de poder",
        "trafico de influencias",
    ],
    "violence": [
        "violencia familiar",
        "agresion",
        "abuso sexual",
        "acoso",
    ],
}

POSITIVE_KEYWORDS: list[str] = [
    "reconocimiento",
    "premio",
    "logro",
    "aprobacion ciudadana",
    "respaldo popular",
    "liderazgo destacado",
]


# ────────────────────────────── Text helpers ──────────────────────────────


def normalize_text(text: str) -> str:
    """Remove accents and lowercase for matching."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def make_url_hash(url: str) -> str:
    """SHA-256 hash of normalized URL (without query params)."""
    cleaned = re.sub(r"[?#].*$", "", url.strip().rstrip("/").lower())
    return hashlib.sha256(cleaned.encode()).hexdigest()


# ────────────────────────────── Classification ──────────────────────────────


def classify_article(text: str, title: str) -> tuple[str, list[str]]:
    """Classify article using keyword matching.

    Returns: (sentiment_label, adverse_categories)
    """
    normalized = normalize_text(f"{title} {text}")

    adverse_cats = []
    for category, keywords in ADVERSE_KEYWORDS.items():
        if any(kw in normalized for kw in keywords):
            adverse_cats.append(category)

    if adverse_cats:
        return "adverse", adverse_cats

    if any(kw in normalized for kw in POSITIVE_KEYWORDS):
        return "positive", []

    return "neutral", []


# ────────────────────────────── Chunking ──────────────────────────────


def chunk_article(article: dict, content: str, mentions: list[dict]) -> list[dict]:
    """Chunk article content with metadata header for RAG context."""
    partidos_str = ", ".join(m["party_name"] for m in mentions[:4])
    date_str = ""
    if article.get("published_at"):
        date_str = article["published_at"].strftime("%Y-%m-%d")

    header = (
        f"FUENTE: {article['source_name']}\n"
        f"FECHA: {date_str}\n"
        f"TÍTULO: {article['title']}\n"
        f"PARTIDOS MENCIONADOS: {partidos_str}\n"
        f"TIPO: Cobertura mediática\n\n"
    )

    full_text = header + content

    if len(full_text) <= MAX_CHUNK_CHARS:
        return [{"content": full_text, "token_count": len(full_text) // 4, "index": 0}]

    # Split by paragraphs
    paragraphs = re.split(r"\n\s*\n", content)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    chunks = []
    current = ""
    max_body = MAX_CHUNK_CHARS - len(header)

    for para in paragraphs:
        if len(current) + len(para) + 2 > max_body and len(current) >= MIN_CHUNK_CHARS:
            chunks.append(
                {
                    "content": header + current,
                    "token_count": len(current) // 4,
                }
            )
            overlap = current[-OVERLAP_CHARS:] if len(current) > OVERLAP_CHARS else ""
            current = overlap + "\n\n" + para if overlap else para
        else:
            current = current + "\n\n" + para if current else para

    if current and len(current) >= MIN_CHUNK_CHARS:
        chunks.append({"content": header + current, "token_count": len(current) // 4})

    if not chunks:
        chunks.append(
            {
                "content": full_text[:MAX_CHUNK_CHARS],
                "token_count": MAX_CHUNK_CHARS // 4,
            }
        )

    for i, chunk in enumerate(chunks):
        chunk["index"] = i

    return chunks


# ────────────────────────────── Candidate matching ──────────────────────────────


def _build_query_name(parts: list[str]) -> str:
    """Build a search-friendly name: first name + last two words (apellidos)."""
    if len(parts) >= 4:
        return f"{parts[0]} {parts[-2]} {parts[-1]}"
    return " ".join(parts)


def build_party_search_terms(
    presidential_data: dict,
    all_candidates: list[dict] | None = None,
) -> dict:
    """Build search terms for each party using ALL candidates.

    Uses presidential formula for Google News queries (most prominent names),
    but includes ALL candidates (senators, representatives, andean parliament)
    for entity matching within article text.

    Returns: {party_name: {candidates: [...], search_terms: [str], search_queries: [str]}}
    """
    result: dict[str, dict] = {}

    # Step 1: Initialize with presidential formula (for Google News queries)
    for p in presidential_data["parties"]:
        party_name = p["party_name"]
        formula = p.get("presidential_formula", {})
        terms: set[str] = set()
        candidates: list[dict] = []
        search_queries: list[str] = []

        # Party name
        terms.add(normalize_text(party_name))
        search_queries.append(f'"{party_name}"')

        # Presidential formula members (also used as Google News queries)
        for position_key in ("president", "first_vice_president", "second_vice_president"):
            member = formula.get(position_key, {})
            name = member.get("full_name", "")
            if not name:
                continue

            candidates.append({"name": name, "position": position_key})
            terms.add(normalize_text(name))

            parts = name.split()
            for i in range(len(parts) - 1):
                term = normalize_text(f"{parts[i]} {parts[i + 1]}")
                if len(term) >= 6:
                    terms.add(term)

            query_name = _build_query_name(parts)
            search_queries.append(f'"{query_name}"')

        result[party_name] = {
            "candidates": candidates,
            "presidential_candidate": candidates[0]["name"] if candidates else "",
            "search_terms": list(terms),
            "search_queries": search_queries,
        }

    # Step 2: Add ALL candidates for entity matching (no extra Google News queries)
    if all_candidates:
        for c in all_candidates:
            party_name = c.get("party_name", "")
            if party_name not in result:
                continue

            name = c.get("full_name", "")
            if not name:
                continue

            entry = result[party_name]

            # Add name terms for matching
            terms_set = set(entry["search_terms"])
            terms_set.add(normalize_text(name))

            parts = name.split()
            for i in range(len(parts) - 1):
                term = normalize_text(f"{parts[i]} {parts[i + 1]}")
                if len(term) >= 6:
                    terms_set.add(term)

            entry["search_terms"] = list(terms_set)
            entry["candidates"].append({
                "name": name,
                "position": c.get("position", ""),
                "election_type": c.get("election_type", ""),
            })

    return result


# ────────────────────────────── Relevance filters ──────────────────────────────

# Words that indicate an article is about politics/elections
POLITICAL_CONTEXT_WORDS = {
    "candidato", "candidata", "elecciones", "congreso", "partido",
    "senador", "senadora", "diputado", "diputada", "parlamentario",
    "voto", "votacion", "campaña", "electoral", "politica", "politico",
    "gobierno", "presidente", "presidenta", "congresista", "legislador",
    "bancada", "plancha", "formula", "jne", "onpe", "jurado", "fiscal",
    "fiscalia", "ministro", "ministra", "gabinete", "vacancia",
    "investigacion", "corrupcion", "denuncia", "sentencia", "acusado",
    "plan de gobierno", "propuesta", "debate", "mitin", "encuesta",
    "circunscripcion", "comicios", "urna", "cedula", "sufragio",
    "parlamento", "republica", "constitucion", "reforma",
}

# Words that indicate an article is NOT about politics (false positive signals)
NON_POLITICAL_SIGNALS = {
    "farandula", "espectaculo", "reality", "chollywood",
    "futbol", "liga 1", "seleccion peruana", "gol ", "fichaje",
    "horoscopo", "receta", "tendencia viral", "tiktok",
    "amor", "boda", "matrimonio", "novio", "novia", "pareja sentimental",
    "campeonato", "torneo", "copa america", "liga betplay",
    "pelicula", "serie", "estreno", "netflix", "concierto",
}

# Minimum relevance score to consider an article a match
MIN_RELEVANCE_SCORE = 6


def _has_political_context(normalized_text: str) -> bool:
    """Check if article text contains political context words."""
    matches = sum(1 for w in POLITICAL_CONTEXT_WORDS if w in normalized_text)
    return matches >= 2  # at least 2 political words


def _has_non_political_signals(normalized_text: str) -> bool:
    """Check if article text is clearly about entertainment/sports/etc."""
    matches = sum(1 for w in NON_POLITICAL_SIGNALS if w in normalized_text)
    return matches >= 2  # at least 2 non-political signals


def _score_candidate_match(
    normalized_text: str,
    candidate_name: str,
    party_name: str,
) -> int:
    """Score how relevant an article is to a specific candidate.

    Scoring:
      Full name (3+ words):  +10
      Two apellidos:          +8
      First name + apellido:  +6
      Party name (full):      +4
      Party name (2-word):    +2
      Political context:      +3 bonus
      Non-political signals:  -5 penalty

    Returns: relevance score (higher = more relevant)
    """
    score = 0

    # Full candidate name
    candidate_norm = normalize_text(candidate_name)
    if candidate_norm in normalized_text:
        score += 10
    else:
        # Try partial matches
        parts = candidate_name.split()
        if len(parts) >= 3:
            # Two apellidos (last 2 words)
            apellidos = normalize_text(f"{parts[-2]} {parts[-1]}")
            if len(apellidos) >= 8 and apellidos in normalized_text:
                score += 8

            # First name + first apellido
            nombre_apellido = normalize_text(f"{parts[0]} {parts[-2]}")
            if len(nombre_apellido) >= 8 and nombre_apellido in normalized_text:
                score += 6

        elif len(parts) == 2:
            both = normalize_text(f"{parts[0]} {parts[1]}")
            if both in normalized_text:
                score += 8

    # Party name match
    party_norm = normalize_text(party_name)
    if party_norm in normalized_text:
        score += 4
    else:
        # 2-word party fragments (only if 8+ chars to avoid "peru", "para")
        party_parts = party_name.split()
        for i in range(len(party_parts) - 1):
            fragment = normalize_text(f"{party_parts[i]} {party_parts[i + 1]}")
            if len(fragment) >= 10 and fragment in normalized_text:
                score += 2
                break

    # Context bonuses/penalties
    if _has_political_context(normalized_text):
        score += 3
    if _has_non_political_signals(normalized_text):
        score -= 5

    return score


def match_parties(text: str, title: str, party_terms: dict) -> list[dict]:
    """Find which parties/candidates are mentioned in the article.

    Uses a scoring system to reduce false positives:
    - Requires minimum relevance score (name match + political context)
    - Penalizes entertainment/sports articles
    - Scores based on how specifically the candidate is mentioned

    Returns list of matches sorted by relevance score (highest first).
    """
    normalized = normalize_text(f"{title} {text}")
    mentions = []

    # Quick reject: if article has no political context at all, skip
    if not _has_political_context(normalized):
        return []

    for party, info in party_terms.items():
        best_score = 0
        best_candidate = info.get("presidential_candidate", "")

        # Score each candidate in this party
        for c in info["candidates"]:
            score = _score_candidate_match(normalized, c["name"], party)
            if score > best_score:
                best_score = score
                best_candidate = c["name"]

        # Also check party-only match (no specific candidate)
        party_only_score = 0
        party_norm = normalize_text(party)
        if party_norm in normalized:
            party_only_score = 4
            if _has_political_context(normalized):
                party_only_score += 3

        best_score = max(best_score, party_only_score)

        if best_score >= MIN_RELEVANCE_SCORE:
            mentions.append({
                "party_name": party,
                "candidate_name": best_candidate,
                "is_primary": best_score >= 10,
                "relevance_score": best_score,
            })

    # Sort by relevance score (most relevant first)
    mentions.sort(key=lambda m: m["relevance_score"], reverse=True)
    return mentions
