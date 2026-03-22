#!/usr/bin/env python3
"""Extract structured candidate positions from planes de gobierno via local pgvector RAG."""

import json
import os
import re
import time
from pathlib import Path

import anthropic
import psycopg
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from _db import DATABASE_URL  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_FILE = BASE_DIR / "posiciones_candidatos.json"
PROGRESS_FILE = BASE_DIR / "extraction_progress.json"
CANDIDATES_FILE = BASE_DIR / "candidatos_2026.json"

EXTRACTION_MODEL = "claude-sonnet-4-6-20250514"

# Topic definitions with display names, descriptions, and axes
TOPICS = {
    "economics": {
        "name": "Economía",
        "description": "Política económica, empleo, impuestos, informalidad, inversión",
        "axes": {
            "state_intervention": "(-1.0 = libre mercado total, +1.0 = control estatal fuerte)",
            "social_spending": "(-1.0 = austeridad fiscal, +1.0 = gasto social expansivo)",
            "formalization": "(-1.0 = tolerancia a informalidad, +1.0 = formalización agresiva)",
        },
    },
    "education": {
        "name": "Educación",
        "description": "Inversión educativa, calidad, rol del sector privado, currículo",
        "axes": {
            "public_investment": "(-1.0 = inversión mínima, +1.0 = inversión masiva en educación pública)",
            "private_sector_role": "(-1.0 = solo educación pública, +1.0 = fuerte participación privada)",
        },
    },
    "health": {
        "name": "Salud",
        "description": "Sistema de salud, cobertura universal, infraestructura hospitalaria",
        "axes": {
            "universal_system": "(-1.0 = sistema mixto público-privado, +1.0 = sistema universal gratuito)",
            "decentralization": "(-1.0 = sistema centralizado, +1.0 = descentralización regional fuerte)",
        },
    },
    "security": {
        "name": "Seguridad Ciudadana",
        "description": "Crimen, narcotráfico, policía, penas, Fuerzas Armadas",
        "axes": {
            "tough_on_crime": "(-1.0 = enfoque preventivo/social, +1.0 = enfoque punitivo/mano dura)",
            "military_security": "(-1.0 = no involucrar FFAA en seguridad, +1.0 = FFAA activas en seguridad interna)",
        },
    },
    "corruption": {
        "name": "Corrupción y Reforma del Estado",
        "description": "Transparencia, reforma judicial, lucha anticorrupción, reforma política",
        "axes": {
            "judicial_reform": "(-1.0 = ajustes incrementales, +1.0 = reforma radical del sistema de justicia)",
            "transparency": "(-1.0 = status quo, +1.0 = gobierno abierto total y radical)",
        },
    },
    "mining_environment": {
        "name": "Minería y Medio Ambiente",
        "description": "Actividad minera, regulación ambiental, comunidades, Amazonía",
        "axes": {
            "environmental_priority": "(-1.0 = priorizar inversión minera, +1.0 = priorizar protección ambiental)",
            "regulation": "(-1.0 = desregulación/flexibilización, +1.0 = regulación estricta)",
        },
    },
    "pensions": {
        "name": "Pensiones",
        "description": "AFP, ONP, sistema previsional, jubilación",
        "axes": {
            "pension_system": "(-1.0 = mantener/fortalecer AFP privadas, +1.0 = sistema estatal/público)",
            "universality": "(-1.0 = solo contributivo, +1.0 = pensión universal para todos)",
        },
    },
    "agriculture": {
        "name": "Agricultura",
        "description": "Pequeña agricultura, agroindustria, subsidios, seguridad alimentaria",
        "axes": {
            "subsidies": "(-1.0 = libre mercado agrícola, +1.0 = subsidios y apoyo estatal fuerte)",
            "small_farmer": "(-1.0 = priorizar agroindustria, +1.0 = priorizar pequeño agricultor)",
        },
    },
    "infrastructure": {
        "name": "Infraestructura y Transporte",
        "description": "Obras públicas, APP, descentralización, transporte",
        "axes": {
            "investment_model": "(-1.0 = APP y concesiones privadas, +1.0 = obra pública estatal)",
            "decentralization": "(-1.0 = inversión centrada en Lima, +1.0 = priorizar regiones)",
        },
    },
    "social_rights": {
        "name": "Derechos Sociales",
        "description": "Aborto, matrimonio igualitario, enfoque de género, pueblos indígenas",
        "axes": {
            "social_progressivism": "(-1.0 = conservador/tradicional, +1.0 = progresista/liberal)",
            "gender_equality": "(-1.0 = enfoque tradicional, +1.0 = políticas con enfoque de género)",
        },
    },
    "constitution": {
        "name": "Constitución",
        "description": "Nueva constitución, asamblea constituyente, reformas constitucionales",
        "axes": {
            "new_constitution": "(-1.0 = mantener constitución de 1993, +1.0 = nueva constitución)",
            "political_reform": "(-1.0 = sistema político actual, +1.0 = reforma política profunda)",
        },
    },
    "foreign_policy": {
        "name": "Política Exterior",
        "description": "Relaciones internacionales, integración regional, comercio exterior",
        "axes": {
            "regional_integration": "(-1.0 = bilateralismo, +1.0 = integración multilateral regional)",
            "trade_openness": "(-1.0 = proteccionismo, +1.0 = libre comercio/apertura)",
        },
    },
    "technology": {
        "name": "Tecnología y Digitalización",
        "description": "Gobierno digital, conectividad, innovación, regulación tecnológica",
        "axes": {
            "digital_government": "(-1.0 = baja prioridad, +1.0 = digitalización prioritaria del Estado)",
            "personal_data": "(-1.0 = sin regulación, +1.0 = regulación estricta de datos)",
        },
    },
}


def build_extraction_prompt(party_name: str, topics_batch: dict[str, dict]) -> str:
    """Build the extraction prompt for a batch of topics for one party."""
    topics_section = ""
    for topic_key, topic_def in topics_batch.items():
        axes_desc = "\n".join(
            f'      "{axis}": <float> // {desc}' for axis, desc in topic_def["axes"].items()
        )
        topics_section += f"""
    "{topic_key}": {{
      "summary": "<2-3 oraciones EN TUS PROPIAS PALABRAS>",
      "key_proposals": ["<propuesta 1>", "<propuesta 2>", ...],
      "axes": {{
{axes_desc}
      }},
      "confidence": "<high|medium|low>"
    }},"""

    return f"""Analiza el plan de gobierno de {party_name} y extrae sus posiciones sobre los siguientes temas.

INSTRUCCIONES CRÍTICAS:
1. PARAFRASEA siempre. NO copies texto textual del documento.
2. Si el plan NO menciona un tema, pon confidence "low" y axes en 0.0.
3. Los scores de axes van de -1.0 a +1.0, usa todo el rango.
4. "confidence" indica qué tan claramente el plan aborda el tema:
   - "high": el plan tiene propuestas específicas y detalladas
   - "medium": menciones parciales o vagas
   - "low": no menciona el tema o es extremadamente vago
5. Máximo 5 key_proposals por tema, cada una en 1 oración corta.

Responde EXCLUSIVAMENTE con un JSON válido (sin markdown, sin ```):

{{{topics_section}
}}"""


def retrieve_context(
    embedder: SentenceTransformer,
    conn: psycopg.Connection,
    party_name: str,
    top_k: int = 30,
) -> str:
    """Retrieve relevant chunks for a party from pgvector."""
    query_text = f"Plan de gobierno {party_name} propuestas políticas"
    embedding = embedder.encode(query_text, normalize_embeddings=True)
    emb_str = "[" + ",".join(str(v) for v in embedding.tolist()) + "]"

    rows = conn.execute(
        """
        SELECT c.content
        FROM plan_chunks c
        JOIN government_plans d ON d.id = c.plan_id
        WHERE d.party_name = %s
        ORDER BY c.embedding <=> %s::vector
        LIMIT %s
        """,
        [party_name, emb_str, top_k],
    ).fetchall()

    return "\n\n---\n\n".join(row[0] for row in rows)


def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_progress(progress: dict):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def _empty_position(topic_def: dict) -> dict:
    return {
        "summary": "El plan de gobierno no aborda este tema de manera significativa.",
        "key_proposals": [],
        "axes": {axis: 0.0 for axis in topic_def["axes"]},
        "confidence": "low",
    }


def sanitize_key(name: str) -> str:
    key = name.upper().strip()
    key = re.sub(r"[^\w\s]", "", key)
    key = re.sub(r"\s+", "_", key)
    return key


def extract_party_positions(
    client: anthropic.Anthropic,
    context: str,
    party_name: str,
) -> dict:
    """Extract positions for one party — ALL 13 topics in a single call using local RAG context."""
    topic_keys = list(TOPICS.keys())
    prompt = build_extraction_prompt(party_name, TOPICS)
    full_prompt = f"""CONTEXTO del plan de gobierno de {party_name}:

{context}

---

{prompt}"""

    print(f"    Extracting all 13 topics with {EXTRACTION_MODEL}...")

    for attempt in range(3):
        try:
            message = client.messages.create(
                model=EXTRACTION_MODEL,
                max_tokens=4096,
                messages=[{"role": "user", "content": full_prompt}],
            )

            text = message.content[0].text
            if not text:
                if attempt < 2:
                    time.sleep(3)
                    continue
                return {k: _empty_position(TOPICS[k]) for k in topic_keys}

            text = text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0]
            text = text.strip()

            parsed = json.loads(text)
            all_positions = {}
            for k in topic_keys:
                all_positions[k] = parsed.get(k, _empty_position(TOPICS[k]))
            return all_positions

        except json.JSONDecodeError as e:
            print(f"      JSON parse error: {e}")
            if attempt < 2:
                time.sleep(3)
                continue
            return {k: _empty_position(TOPICS[k]) for k in topic_keys}
        except anthropic.RateLimitError:
            print("      Rate limited, waiting 30s...")
            time.sleep(30)
            if attempt < 2:
                continue
            return {k: _empty_position(TOPICS[k]) for k in topic_keys}
        except Exception as e:
            print(f"      Error: {e}")
            if attempt < 2:
                time.sleep(3)
                continue
            return {k: _empty_position(TOPICS[k]) for k in topic_keys}

    return {k: _empty_position(TOPICS[k]) for k in topic_keys}


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not found in .env")
        return

    client = anthropic.Anthropic(api_key=api_key)

    # Load embedding model for RAG retrieval
    print("Loading embedding model...")
    embedder = SentenceTransformer("BAAI/bge-m3")
    print("Model loaded.")

    # Connect to pgvector DB
    conn = psycopg.connect(DATABASE_URL)

    # Load candidates
    with open(CANDIDATES_FILE, encoding="utf-8") as f:
        candidates_data = json.load(f)

    progress = load_progress()

    parties = []
    for p in candidates_data["parties"]:
        plan = p.get("government_plan")
        if not plan or not plan.get("full_plan_url"):
            continue
        pres = p["presidential_formula"].get("president", {})
        parties.append(
            {
                "name": p["party_name"],
                "candidate": pres.get("full_name", ""),
                "key": sanitize_key(p["party_name"]),
            }
        )

    print(f"Extracting positions for {len(parties)} parties...")
    print(f"Topics: {len(TOPICS)}\n")

    results = {}

    for i, party in enumerate(parties, 1):
        key = party["key"]

        if key in progress:
            existing = progress[key]
            has_real_data = any(
                pos.get("confidence") != "low" for pos in existing.get("positions", {}).values()
            )
            if has_real_data:
                print(f"[{i}/{len(parties)}] {party['name']} — SKIPPED (already done)")
                results[key] = existing
                continue

        print(f"[{i}/{len(parties)}] {party['name']} ({party['candidate']})")

        # Retrieve context from pgvector (LOCAL, free, unlimited)
        context = retrieve_context(embedder, conn, party["name"])

        positions = extract_party_positions(client, context, party["name"])

        party_result = {
            "party_name": party["name"],
            "presidential_candidate": party["candidate"],
            "positions": positions,
        }

        results[key] = party_result
        progress[key] = party_result
        save_progress(progress)
        print("    Done. Saved progress.\n")
        time.sleep(1)

    conn.close()

    # Build final output
    topics_metadata = {}
    for topic_key, topic_def in TOPICS.items():
        topics_metadata[topic_key] = {
            "name": topic_def["name"],
            "description": topic_def["description"],
            "axes": list(topic_def["axes"].keys()),
        }

    output = {
        "version": "1.0",
        "extracted_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_parties": len(results),
        "total_topics": len(TOPICS),
        "topics": topics_metadata,
        "parties": results,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("\nExtraction complete!")
    print(f"Output: {OUTPUT_FILE}")
    print(f"Parties: {len(results)}")

    low_confidence_count = 0
    total_positions = 0
    for party_data in results.values():
        for pos in party_data["positions"].values():
            total_positions += 1
            if pos.get("confidence") == "low":
                low_confidence_count += 1

    print(f"Total positions: {total_positions}")
    print(
        f"Low confidence: {low_confidence_count} ({low_confidence_count * 100 // max(total_positions, 1)}%)"
    )


if __name__ == "__main__":
    main()
