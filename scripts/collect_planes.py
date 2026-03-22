#!/usr/bin/env python3
"""Download government plans from JNE and ingest into pgvector.

Pipeline:
  1. Fetch plan PDF URLs from JNE API for each presidential candidate
  2. Download PDFs (skip already downloaded)
  3. Convert PDF → markdown → structured chunks
  4. Embed chunks with BGE-M3
  5. Store in PostgreSQL + pgvector

Usage:
    python scripts/collect_planes.py               # Download + ingest
    python scripts/collect_planes.py --download     # Only download PDFs
    python scripts/collect_planes.py --ingest       # Only ingest (PDFs must exist)
"""

import argparse
import json
import re
import time
from pathlib import Path

import psycopg
import pymupdf4llm
import requests
from _db import DATABASE_URL
from pgvector.psycopg import register_vector
from sentence_transformers import SentenceTransformer

BASE_DIR = Path(__file__).resolve().parent.parent / "data"
PLANES_DIR = BASE_DIR / "planes_de_gobierno"
CANDIDATES_JSON = BASE_DIR / "candidatos_2026.json"

API_URL = "https://web.jne.gob.pe/serviciovotoinformado/api/votoinf/plangobierno"
ELECTORAL_PROCESS_2026 = 124
ELECTION_TYPE_PRESIDENTIAL = "1"

MAX_CHUNK_CHARS = 3200
MIN_CHUNK_CHARS = 100
OVERLAP_CHARS = 200

# All 36 presidential candidates from JNE API (idOrganizacionPolitica, party_name, candidate_name)
CANDIDATES = [
    (1264, "JUNTOS POR EL PERU", "ROBERTO HELBERT SANCHEZ PALOMINO"),
    (14, "SOMOS PERU", "GEORGE PATRICK FORSYTH SOMMER"),
    (22, "RENOVACION POPULAR", "RAFAEL BERNARDO LOPEZ ALIAGA CAZORLA"),
    (1257, "ALIANZA PARA EL PROGRESO", "CESAR ACUÑA PERALTA"),
    (2956, "PAIS PARA TODOS", "CARLOS GONSALO ALVAREZ LOAYZA"),
    (2931, "PRIMERO LA GENTE", "MARIA SOLEDAD PEREZ TELLO DE RODRIGUEZ"),
    (2939, "PTE PERU", "NAPOLEON BECERRA GARCIA"),
    (2961, "PARTIDO DEL BUEN GOBIERNO", "JORGE NIETO MONTESINOS"),
    (2218, "PERU LIBRE", "VLADIMIR ROY CERRON ROJAS"),
    (2921, "PRIN", "WALTER GILMER CHIRINOS PURIZAGA"),
    (2731, "PODEMOS PERU", "JOSE LEON LUNA GALVEZ"),
    (2967, "PROGRESEMOS", "PAUL DAVIS JAIMES BLANCO"),
    (2980, "AHORA NACION", "PABLO ALFONSO LOPEZ CHAU NAVA"),
    (2898, "FE EN EL PERU", "ALVARO GONZALO PAZ DE LA BARRA FREIGEIRO"),
    (2840, "PARTIDO MORADO", "MESIAS ANTONIO GUEVARA AMASIFUEN"),
    (2857, "FRENTE DE LA ESPERANZA 2021", "LUIS FERNANDO OLIVERA VEGA"),
    (3023, "UNIDAD NACIONAL", "ROBERTO ENRIQUE CHIABRA LEON"),
    (2995, "COOPERACION POPULAR", "YONHY LESCANO ANCIETA"),
    (2867, "DEMOCRATA UNIDO PERU", "CHARLIE CARRASCO SALAZAR"),
    (2986, "DEMOCRATICO FEDERAL", "ARMANDO JOAQUIN MASSE FERNANDEZ"),
    (2869, "PARTIDO PATRIOTICO DEL PERU", "HERBERT CALLER GUTIERREZ"),
    (2895, "DEMOCRATA VERDE", "ALEX GONZALES CASTILLO"),
    (2998, "UN CAMINO DIFERENTE", "ROSARIO DEL PILAR FERNANDEZ BAZAN"),
    (2924, "PERU MODERNO", "CARLOS ERNESTO JAICO CARRANZA"),
    (2925, "PERU PRIMERO", "MARIO ENRIQUE VIZCARRA CORNEJO"),
    (3024, "FUERZA Y LIBERTAD", "FIORELLA GIANNINA MOLINELLI ARISTONDO"),
    (2927, "SALVEMOS AL PERU", "ANTONIO ORTIZ VILLANO"),
    (3025, "ALIANZA ELECTORAL VENCEREMOS", "RONALD DARWIN ATENCIO SOTOMAYOR"),
    (2985, "INTEGRIDAD DEMOCRATICA", "WOLFGANG MARIO GROZO COSTA"),
    (2941, "PARTIDO CIVICO OBRAS", "RICARDO PABLO BELMONT CASSINELLI"),
    (2930, "PARTIDO APRISTA PERUANO", "PITTER ENRIQUE VALDERRAMA PENA"),
    (2932, "PERU ACCION", "FRANCISCO ERNESTO DIEZ-CANSECO TAVARA"),
    (2933, "LIBERTAD POPULAR", "RAFAEL JORGE BELAUNDE LLOSA"),
    (1366, "FUERZA POPULAR", "KEIKO SOFIA FUJIMORI HIGUCHI"),
    (2935, "SICREO", "ALFONSO CARLOS ESPA Y GARCES-ALVEAR"),
    (2173, "AVANZA PAIS", "JOSE DANIEL WILLIAMS ZAPATA"),
]


# ── Helpers ───────────────────────────────────────────────────


def sanitize_dirname(name: str) -> str:
    """Convert a name to a safe directory name."""
    name = name.strip().title()
    name = re.sub(r"[^\w\s\-áéíóúñÁÉÍÓÚÑ]", "", name)
    name = re.sub(r"\s+", "_", name)
    return name


# ── Download ──────────────────────────────────────────────────


def fetch_plan_urls(org_id: int) -> dict | None:
    """Fetch government plan URLs from JNE API for a given organization."""
    payload = {
        "pageSize": 10,
        "skip": 1,
        "filter": {
            "idProcesoElectoral": ELECTORAL_PROCESS_2026,
            "idTipoEleccion": ELECTION_TYPE_PRESIDENTIAL,
            "idOrganizacionPolitica": str(org_id),
            "txDatoCandidato": "",
            "idJuradoElectoral": "0",
        },
    }
    resp = requests.post(API_URL, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if not data.get("data"):
        return None

    plan = data["data"][0]
    return {
        "full_plan": plan.get("txRutaCompleto", ""),
        "summary_plan": plan.get("txRutaResumen", ""),
        "org_name": plan.get("txOrganizacionPolitica", ""),
        "plan_id": plan.get("idPlanGobierno"),
    }


def download_pdf(url: str, dest: Path) -> bool:
    """Download a PDF file from a URL."""
    if not url:
        return False
    if dest.exists():
        print(f"    [EXISTS] {dest.name}")
        return True
    try:
        resp = requests.get(url, timeout=60, stream=True)
        resp.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        size_mb = dest.stat().st_size / (1024 * 1024)
        print(f"    Downloaded: {dest.name} ({size_mb:.1f} MB)")
        return True
    except Exception as e:
        print(f"    ERROR downloading {url}: {e}")
        return False


def download_all() -> dict:
    """Download all government plan PDFs from JNE API."""
    print(f"═══ Downloading planes de gobierno ({len(CANDIDATES)} candidates) ═══\n")

    results = {"success": [], "no_plan": [], "error": []}

    for org_id, party_name, candidate_name in CANDIDATES:
        party_dir = sanitize_dirname(party_name)
        candidate_safe = sanitize_dirname(candidate_name)
        dest_dir = PLANES_DIR / party_dir / "presidencia"

        print(f"[{party_name}] {candidate_name}")

        try:
            plan = fetch_plan_urls(org_id)
        except Exception as e:
            print(f"  ERROR fetching API: {e}")
            results["error"].append((party_name, candidate_name, str(e)))
            continue

        if not plan:
            print("  No plan de gobierno found")
            results["no_plan"].append((party_name, candidate_name))
            continue

        downloaded = False
        if plan["full_plan"]:
            ok = download_pdf(plan["full_plan"], dest_dir / f"{candidate_safe}_plan_completo.pdf")
            downloaded = downloaded or ok

        if plan["summary_plan"]:
            ok = download_pdf(
                plan["summary_plan"], dest_dir / f"{candidate_safe}_plan_resumen.pdf"
            )
            downloaded = downloaded or ok

        if downloaded:
            results["success"].append((party_name, candidate_name))
        else:
            results["no_plan"].append((party_name, candidate_name))

        time.sleep(0.5)

    # Save metadata
    metadata = {
        "electoral_process": "ELECCIONES GENERALES 2026",
        "election_type": "PRESIDENCIAL",
        "download_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_candidates": len(CANDIDATES),
        "downloaded": len(results["success"]),
        "without_plan": len(results["no_plan"]),
        "errors": len(results["error"]),
    }
    meta_path = PLANES_DIR / "metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(
        f"\n✓ Download: {len(results['success'])} ok, "
        f"{len(results['no_plan'])} sin plan, {len(results['error'])} errores\n"
    )
    return results


# ── Chunking ──────────────────────────────────────────────────


def pdf_to_markdown(pdf_path: Path) -> str:
    """Convert PDF to markdown preserving structure."""
    return pymupdf4llm.to_markdown(str(pdf_path))


def chunk_by_structure(markdown: str, party: str, candidate: str) -> list[dict]:
    """Split markdown by headers, with fallback to paragraph-based chunking."""
    header = f"PARTIDO: {party}\nCANDIDATO: {candidate}\n\n"

    sections = re.split(r"\n(#{1,3}\s+.+)\n", markdown)

    chunks = []
    current_title = "Introducción"
    current_text = ""

    for part in sections:
        part = part.strip()
        if not part:
            continue

        if re.match(r"^#{1,3}\s+", part):
            if current_text and len(current_text) >= MIN_CHUNK_CHARS:
                chunks.extend(_split_large_section(current_text, current_title, header))
            current_title = re.sub(r"^#{1,3}\s+", "", part).strip()
            current_text = ""
        else:
            current_text += part + "\n\n"

    if current_text and len(current_text) >= MIN_CHUNK_CHARS:
        chunks.extend(_split_large_section(current_text, current_title, header))

    if not chunks:
        chunks = _chunk_by_paragraphs(markdown, header)

    for i, chunk in enumerate(chunks):
        chunk["index"] = i

    return chunks


def _split_large_section(text: str, title: str, header: str) -> list[dict]:
    """Split a section that's too large into smaller chunks with overlap."""
    if len(text) <= MAX_CHUNK_CHARS:
        return [
            {
                "content": header + f"SECCIÓN: {title}\n\n" + text,
                "section_title": title,
                "token_count": len(text) // 4,
            }
        ]

    paragraphs = re.split(r"\n\s*\n", text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    chunks = []
    current_chunk = ""

    for para in paragraphs:
        if (
            len(current_chunk) + len(para) + 2 > MAX_CHUNK_CHARS
            and len(current_chunk) >= MIN_CHUNK_CHARS
        ):
            chunks.append(
                {
                    "content": header + f"SECCIÓN: {title}\n\n" + current_chunk,
                    "section_title": title,
                    "token_count": len(current_chunk) // 4,
                }
            )
            overlap = current_chunk[-OVERLAP_CHARS:] if len(current_chunk) > OVERLAP_CHARS else ""
            current_chunk = overlap + "\n\n" + para if overlap else para
        else:
            current_chunk = current_chunk + "\n\n" + para if current_chunk else para

    if current_chunk and len(current_chunk) >= MIN_CHUNK_CHARS:
        chunks.append(
            {
                "content": header + f"SECCIÓN: {title}\n\n" + current_chunk,
                "section_title": title,
                "token_count": len(current_chunk) // 4,
            }
        )

    return chunks


def _chunk_by_paragraphs(text: str, header: str) -> list[dict]:
    """Fallback: chunk by paragraphs (for unstructured documents)."""
    paragraphs = re.split(r"\n\s*\n", text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    chunks = []
    current_chunk = ""

    for para in paragraphs:
        if (
            len(current_chunk) + len(para) + 2 > MAX_CHUNK_CHARS
            and len(current_chunk) >= MIN_CHUNK_CHARS
        ):
            chunks.append(
                {
                    "content": header + current_chunk,
                    "section_title": None,
                    "token_count": len(current_chunk) // 4,
                }
            )
            overlap = current_chunk[-OVERLAP_CHARS:] if len(current_chunk) > OVERLAP_CHARS else ""
            current_chunk = overlap + "\n\n" + para if overlap else para
        else:
            current_chunk = current_chunk + "\n\n" + para if current_chunk else para

    if current_chunk and len(current_chunk) >= MIN_CHUNK_CHARS:
        chunks.append(
            {
                "content": header + current_chunk,
                "section_title": None,
                "token_count": len(current_chunk) // 4,
            }
        )

    return chunks


# ── Ingest ────────────────────────────────────────────────────


def ingest_all():
    """Extract, chunk, embed, and store all downloaded PDFs."""
    print("═══ Ingesting planes de gobierno ═══\n")

    print("Loading BGE-M3 model...")
    model = SentenceTransformer("BAAI/bge-m3")
    print(f"Model loaded. Dimensions: {model.get_sentence_embedding_dimension()}\n")

    with open(CANDIDATES_JSON, encoding="utf-8") as f:
        candidates = json.load(f)

    party_info = {}
    for p in candidates["parties"]:
        pres = p["presidential_formula"].get("president", {})
        dir_name = sanitize_dirname(p["party_name"])
        party_info[dir_name] = {
            "name": p["party_name"],
            "candidate": pres.get("full_name", ""),
        }

    conn = psycopg.connect(DATABASE_URL)
    register_vector(conn)

    pdfs = sorted(PLANES_DIR.rglob("*_plan_completo.pdf"))
    print(f"Found {len(pdfs)} PDFs to ingest\n")

    total_chunks = 0
    for pdf_path in pdfs:
        party_dir = pdf_path.parent.parent.name
        info = party_info.get(party_dir, {"name": party_dir, "candidate": ""})

        existing = conn.execute(
            "SELECT id FROM government_plans WHERE party_key = %s", (party_dir,)
        ).fetchone()
        if existing:
            print(f"  [SKIP] {info['name']}")
            continue

        print(f"  [{info['name']}]", end=" ", flush=True)

        try:
            markdown = pdf_to_markdown(pdf_path)
        except Exception as e:
            print(f"PDF error: {e}")
            continue

        chunks = chunk_by_structure(markdown, info["name"], info["candidate"])
        sections = set(c["section_title"] for c in chunks if c["section_title"])
        print(f"{len(chunks)} chunks, {len(sections)} sections.", end=" ", flush=True)

        texts = [c["content"] for c in chunks]
        embeddings = model.encode(texts, batch_size=32, normalize_embeddings=True)
        print("Embedded.", end=" ", flush=True)

        plan_id = conn.execute(
            """INSERT INTO government_plans (party_key, party_name, candidate_name, pdf_path, total_chunks)
               VALUES (%s, %s, %s, %s, %s) RETURNING id""",
            (party_dir, info["name"], info["candidate"], str(pdf_path), len(chunks)),
        ).fetchone()[0]

        for chunk, embedding in zip(chunks, embeddings, strict=False):
            conn.execute(
                """INSERT INTO plan_chunks (plan_id, chunk_index, section_title, content,
                   page_start, page_end, token_count, embedding)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    plan_id,
                    chunk["index"],
                    chunk.get("section_title"),
                    chunk["content"],
                    chunk.get("page_start"),
                    chunk.get("page_end"),
                    chunk.get("token_count"),
                    embedding.tolist(),
                ),
            )

        conn.commit()
        total_chunks += len(chunks)
        print("Stored.")

    conn.close()

    print(f"\n✓ Ingestion complete. Total chunks: {total_chunks}")

    print("Creating HNSW vector index...")
    with psycopg.connect(DATABASE_URL) as idx_conn:
        idx_conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_plan_chunks_embedding ON plan_chunks "
            "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
        )
        idx_conn.commit()
    print("Index created.")

    with psycopg.connect(DATABASE_URL) as verify_conn:
        plan_count = verify_conn.execute("SELECT COUNT(*) FROM government_plans").fetchone()[0]
        chunk_count = verify_conn.execute("SELECT COUNT(*) FROM plan_chunks").fetchone()[0]
        print(f"Plans: {plan_count}, Chunks: {chunk_count}")


# ── Main ──────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Download and ingest government plans")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--download", action="store_true", help="Only download PDFs")
    group.add_argument("--ingest", action="store_true", help="Only ingest (PDFs must exist)")
    args = parser.parse_args()

    if args.download:
        download_all()
    elif args.ingest:
        ingest_all()
    else:
        download_all()
        ingest_all()


if __name__ == "__main__":
    main()
