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
            entry["candidates"].append(
                {
                    "name": name,
                    "position": c.get("position", ""),
                    "election_type": c.get("election_type", ""),
                }
            )

    return result


# ────────────────────────────── Relevance filters ──────────────────────────────

# Words that indicate an article is about politics/elections
# NOTE: these are NORMALIZED (no accents) because we compare against normalized text
POLITICAL_CONTEXT_WORDS = {
    "candidato",
    "candidata",
    "elecciones",
    "congreso",
    "partido",
    "senador",
    "senadora",
    "diputado",
    "diputada",
    "parlamentario",
    "voto",
    "votacion",
    "campana",
    "electoral",
    "politica",
    "politico",
    "gobierno",
    "gobernador",
    "gobernadora",
    "alcalde",
    "alcaldesa",
    "presidente",
    "presidenta",
    "congresista",
    "legislador",
    "bancada",
    "plancha",
    "formula",
    "jne",
    "onpe",
    "jurado",
    "fiscal",
    "fiscalia",
    "ministro",
    "ministra",
    "gabinete",
    "vacancia",
    "investigacion",
    "corrupcion",
    "denuncia",
    "sentencia",
    "acusado",
    "plan de gobierno",
    "propuesta",
    "debate",
    "mitin",
    "encuesta",
    "circunscripcion",
    "comicios",
    "urna",
    "cedula",
    "sufragio",
    "parlamento",
    "republica",
    "constitucion",
    "reforma",
    "postulante",
    "electo",
    "reeleccion",
    "segunda vuelta",
    "primera vuelta",
    "municipalidad",
    "region",
    "prefecto",
}

# Words that indicate an article is NOT about politics (false positive signals)
NON_POLITICAL_SIGNALS = {
    "farandula",
    "espectaculo",
    "reality",
    "chollywood",
    "futbol",
    "liga 1",
    "seleccion peruana",
    "gol ",
    "fichaje",
    "horoscopo",
    "receta",
    "tendencia viral",
    "tiktok",
    "amor",
    "boda",
    "matrimonio",
    "novio",
    "novia",
    "pareja sentimental",
    "campeonato",
    "torneo",
    "copa america",
    "liga betplay",
    "pelicula",
    "serie",
    "estreno",
    "netflix",
    "concierto",
}

# Minimum relevance score to consider an article a match
# 10 = requires title/lead match + context, or high frequency mentions
MIN_RELEVANCE_SCORE = 10


def _has_political_context(normalized_text: str) -> bool:
    """Check if article text contains political context words."""
    matches = sum(1 for w in POLITICAL_CONTEXT_WORDS if w in normalized_text)
    return matches >= 2  # at least 2 political words


def _has_non_political_signals(normalized_text: str) -> bool:
    """Check if article text is clearly about entertainment/sports/etc."""
    matches = sum(1 for w in NON_POLITICAL_SIGNALS if w in normalized_text)
    return matches >= 2  # at least 2 non-political signals


def _find_name_variants(candidate_name: str) -> list[str]:
    """Build search variants for a candidate name (normalized).

    Handles compound surnames like LOPEZ ALIAGA, DIEZ-CANSECO, PEREZ TELLO.
    Generates all consecutive 2-word and 3-word combinations.
    """
    variants: list[str] = []
    seen: set[str] = set()

    def _add(v: str) -> None:
        if v and len(v) >= 8 and v not in seen:
            seen.add(v)
            variants.append(v)

    # Full name
    candidate_norm = normalize_text(candidate_name)
    _add(candidate_norm)

    parts = candidate_name.split()

    # All consecutive 2-word combinations (catches compound surnames)
    for i in range(len(parts) - 1):
        _add(normalize_text(f"{parts[i]} {parts[i + 1]}"))

    # All consecutive 3-word combinations (catches "LOPEZ ALIAGA CAZORLA")
    for i in range(len(parts) - 2):
        _add(normalize_text(f"{parts[i]} {parts[i + 1]} {parts[i + 2]}"))

    # First name alone (only if long enough and unique — "Keiko" is 5 chars, too short)
    if len(parts) >= 1:
        first = normalize_text(parts[0])
        if len(first) >= 6:
            _add(first)

    return variants


def _count_occurrences(text: str, term: str) -> int:
    """Count how many times a term appears in text."""
    count = 0
    start = 0
    while True:
        idx = text.find(term, start)
        if idx == -1:
            break
        count += 1
        start = idx + len(term)
    return count


def _score_candidate_match(
    title_norm: str,
    body_norm: str,
    lead_norm: str,
    candidate_name: str,
    party_name: str,
) -> tuple[int, list[str]]:
    """Score how relevant an article is to a specific candidate/party.

    Returns: (score, reasons) where reasons explain WHY the match was made.

    Scoring signals:
    1. TITLE match:    candidate +15, party +8
    2. LEAD match:     candidate +10, party +5
    3. FREQUENCY:      3+ mentions +5, 5+ mentions +8
    4. CONTEXT:        political +3, non-political -8
    """
    score = 0
    reasons: list[str] = []
    full_text = f"{title_norm} {body_norm}"

    name_variants = _find_name_variants(candidate_name)
    party_norm = normalize_text(party_name)

    # ── Signal 1: TITLE match ──
    candidate_in_title = any(v in title_norm for v in name_variants)
    party_in_title = party_norm in title_norm

    if candidate_in_title:
        score += 15
        reasons.append("Candidato mencionado en el titular")
    if party_in_title:
        score += 8
        reasons.append("Partido mencionado en el titular")

    # ── Signal 2: LEAD match (first 3 sentences) ──
    if not candidate_in_title:
        candidate_in_lead = any(v in lead_norm for v in name_variants)
        if candidate_in_lead:
            score += 10
            reasons.append("Candidato mencionado en las primeras oraciones")

    if not party_in_title and party_norm in lead_norm:
        score += 5
        reasons.append("Partido mencionado en las primeras oraciones")

    # ── Signal 3: FREQUENCY in body ──
    best_count = 0
    for v in name_variants:
        count = _count_occurrences(body_norm, v)
        if count > best_count:
            best_count = count

    if best_count >= 5:
        score += 8
        reasons.append(f"Candidato mencionado {best_count} veces en el artículo")
    elif best_count >= 3:
        score += 5
        reasons.append(f"Candidato mencionado {best_count} veces en el artículo")
    elif best_count >= 1 and score == 0:
        score += 2

    # Party frequency (only if no candidate match)
    if best_count == 0:
        party_count = _count_occurrences(body_norm, party_norm)
        if party_count >= 3:
            score += 5
            reasons.append(f"Partido mencionado {party_count} veces en el artículo")
        elif party_count >= 1 and score == 0:
            score += 2

    # ── Signal 4: Context ──
    if _has_political_context(full_text):
        score += 3
    if _has_non_political_signals(full_text):
        score -= 8
        reasons.append("Penalización: contenido no político detectado")

    return score, reasons


def match_parties(text: str, title: str, party_terms: dict) -> list[dict]:
    """Find which parties/candidates are mentioned in the article.

    Determines if the article is ABOUT a candidate/party using:
    - Title match (strongest signal)
    - Lead paragraph match (first 3 sentences)
    - Mention frequency (3+ times = article is about them)
    - Political context requirement

    Returns list of matches with relevance_score and match_reason.
    Minimum score: 10.
    """
    title_norm = normalize_text(title)
    body_norm = normalize_text(text)

    # Extract lead (first 3 sentences)
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    lead = " ".join(sentences[:3])
    lead_norm = normalize_text(lead)

    full_norm = f"{title_norm} {body_norm}"

    # Quick reject: no political context
    if not _has_political_context(full_norm):
        return []

    mentions = []

    for party, info in party_terms.items():
        best_score = 0
        best_reasons: list[str] = []
        best_candidate = info.get("presidential_candidate", "")

        # Score each candidate
        for c in info["candidates"]:
            score, reasons = _score_candidate_match(
                title_norm, body_norm, lead_norm, c["name"], party
            )
            if score > best_score:
                best_score = score
                best_reasons = reasons
                best_candidate = c["name"]

        if best_score >= MIN_RELEVANCE_SCORE:
            match_reason = (
                ". ".join(best_reasons) if best_reasons else "Mención en contexto político"
            )
            mentions.append(
                {
                    "party_name": party,
                    "candidate_name": best_candidate,
                    "is_primary": best_score >= 15,
                    "relevance_score": best_score,
                    "match_reason": match_reason,
                }
            )

    mentions.sort(key=lambda m: m["relevance_score"], reverse=True)
    return mentions
