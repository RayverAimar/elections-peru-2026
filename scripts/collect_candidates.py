#!/usr/bin/env python3
"""Fetch candidates from JNE API.

By default fetches presidential candidates with formula (president + VPs)
and government plan URLs. With --all, fetches all election types and
populates the database.

Usage:
    python scripts/collect_candidates.py               # Presidential → candidatos_2026.json
    python scripts/collect_candidates.py --all          # All elections → all_candidates_2026.json + DB
    python scripts/collect_candidates.py --all --json-only  # All elections, skip DB
    python scripts/collect_candidates.py --all --probe      # Only probe election types
"""

import argparse
import json
import sys
import time
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent.parent / "data"
ELECTORAL_PROCESS_2026 = 124

API_CANDIDATES = "https://web.jne.gob.pe/serviciovotoinformado/api/votoinf/avanzada-voto"
API_PLAN = "https://web.jne.gob.pe/serviciovotoinformado/api/votoinf/plangobierno"
PHOTO_BASE = "https://mpesije.jne.gob.pe/apidocs"

# All 36 presidential parties (idOrganizacionPolitica, party_name, candidate_name)
PARTIES = [
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

# Map JNE election type IDs to English names
ELECTION_TYPE_MAP = {
    "1": "presidential",
    "3": "andean_parliament",
    "15": "representative",
    "20": "senator",
}

KNOWN_ELECTION_TYPES = ["1", "3", "15", "20"]


# ── Shared API helpers ────────────────────────────────────────


def fetch_candidates_api(org_id: int, election_type_id: str, page_size: int = 200) -> list[dict]:
    """Fetch candidates from JNE API for a given party and election type."""
    payload = {
        "pageSize": page_size,
        "skip": 1,
        "filter": {
            "IdTipoEleccion": election_type_id,
            "IdOrganizacionPolitica": org_id,
            "ubigeo": "0",
            "IdAnioExperiencia": 0,
            "cargoOcupado": [0],
            "IdSentenciaDeclarada": 0,
            "IdGradoAcademico": 0,
            "IdExpedienteDadiva": 0,
            "IdProcesoElectoral": ELECTORAL_PROCESS_2026,
            "IdEstado": 0,
        },
    }
    resp = requests.post(API_CANDIDATES, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json().get("data", [])


def fetch_plan(org_id: int) -> dict | None:
    """Fetch government plan URLs for a party."""
    payload = {
        "pageSize": 10,
        "skip": 1,
        "filter": {
            "idProcesoElectoral": ELECTORAL_PROCESS_2026,
            "idTipoEleccion": "1",
            "idOrganizacionPolitica": str(org_id),
            "txDatoCandidato": "",
            "idJuradoElectoral": "0",
        },
    }
    resp = requests.post(API_PLAN, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json().get("data", [])
    if not data:
        return None
    plan = data[0]
    return {
        "plan_id": plan.get("idPlanGobierno"),
        "full_plan_url": plan.get("txRutaCompleto", ""),
        "summary_plan_url": plan.get("txRutaResumen", ""),
    }


def build_candidate_dict(raw: dict, **extra) -> dict:
    """Build a clean candidate dict from JNE API response."""
    foto_guid = raw.get("txGuidFoto") or ""
    photo_url = f"{PHOTO_BASE}/{foto_guid}.jpg" if foto_guid else None

    result = {
        "full_name": (raw.get("nombreCompleto") or "").strip(),
        "position": raw.get("cargo", ""),
        "document_number": raw.get("numeroDocumento", ""),
        "status": raw.get("estado", ""),
        "jne_profile_id": raw.get("idHojaVida"),
        "photo_url": photo_url,
        "candidate_number": raw.get("numeroCandidato"),
    }
    result.update(extra)
    return result


# ── Presidential mode ─────────────────────────────────────────


def collect_presidential():
    """Fetch presidential formulas with VPs and plan URLs → candidatos_2026.json."""
    print(f"═══ Fetching presidential candidates ({len(PARTIES)} parties) ═══\n")

    parties = []

    for org_id, party_name, _ in PARTIES:
        print(f"  [{party_name}] (id={org_id})...", end=" ", flush=True)

        # Fetch presidential formula
        try:
            formula_raw = fetch_candidates_api(org_id, "1", page_size=10)
        except Exception as e:
            print(f"ERROR formula: {e}")
            formula_raw = []

        time.sleep(0.3)

        # Fetch government plan
        try:
            plan = fetch_plan(org_id)
        except Exception as e:
            print(f"ERROR plan: {e}")
            plan = None

        time.sleep(0.3)

        # Parse candidates by position
        president = None
        first_vp = None
        second_vp = None

        for c in formula_raw:
            cargo = c.get("cargo", "")
            candidate = build_candidate_dict(c)
            if cargo == "PRESIDENTE DE LA REPÚBLICA":
                president = candidate
            elif "PRIMER" in cargo and "VICE" in cargo:
                first_vp = candidate
            elif "SEGUNDO" in cargo and "VICE" in cargo:
                second_vp = candidate

        party_data = {
            "jne_id": org_id,
            "party_name": party_name,
            "electoral_process": "ELECCIONES GENERALES 2026",
            "election_type": "PRESIDENCIAL",
            "presidential_formula": {
                "president": president,
                "first_vice_president": first_vp,
                "second_vice_president": second_vp,
            },
            "government_plan": plan,
        }

        parties.append(party_data)
        n_candidates = sum(1 for x in [president, first_vp, second_vp] if x)
        print(f"{n_candidates} candidatos, plan={'si' if plan else 'no'}")

    parties.sort(key=lambda p: p["party_name"])

    output = {
        "election": "ELECCIONES GENERALES 2026",
        "election_date": "2026-04-12",
        "type": "PRESIDENCIAL",
        "electoral_process_id": ELECTORAL_PROCESS_2026,
        "total_parties": len(parties),
        "total_with_plan": sum(1 for p in parties if p["government_plan"]),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source": "JNE - Jurado Nacional de Elecciones (web.jne.gob.pe/serviciovotoinformado)",
        "parties": parties,
    }

    out_path = BASE_DIR / "candidatos_2026.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✓ {out_path}")
    print(
        f"  {len(parties)} partidos, "
        f"{sum(1 for p in parties if p['government_plan'])} con plan de gobierno"
    )


# ── All elections mode ────────────────────────────────────────


def probe_election_types(sample_org_id: int = 1366) -> dict[str, str]:
    """Probe the JNE API to discover which election types exist."""
    print("Probing JNE API for election types...")
    found = {}

    for type_id in KNOWN_ELECTION_TYPES:
        try:
            data = fetch_candidates_api(sample_org_id, type_id, page_size=1)
            if data:
                cargo = data[0].get("cargo", "UNKNOWN")
                found[str(type_id)] = cargo
                print(f"  Type {type_id}: {cargo} ({len(data)} result in sample)")
            else:
                print(f"  Type {type_id}: (no data)")
        except Exception as e:
            print(f"  Type {type_id}: ERROR - {e}")
        time.sleep(0.3)

    print(f"\nFound {len(found)} election types\n")
    return found


def insert_into_db(all_candidates: list[dict]):
    """Insert candidates into the parties + candidates DB tables."""
    try:
        import psycopg
        from _db import DATABASE_URL as db_url
    except ImportError:
        print("WARNING: psycopg not available, skipping DB insert")
        return

    conn = psycopg.connect(db_url)

    # Insert parties (upsert)
    seen_parties = set()
    for c in all_candidates:
        key = (c["party_jne_id"], c["party_name"])
        if key not in seen_parties:
            conn.execute(
                """INSERT INTO parties (jne_id, name)
                   VALUES (%s, %s)
                   ON CONFLICT (jne_id) DO NOTHING""",
                (c["party_jne_id"], c["party_name"]),
            )
            seen_parties.add(key)

    conn.commit()

    # Get party_id mapping
    party_id_map = {}
    rows = conn.execute("SELECT id, jne_id FROM parties").fetchall()
    for row in rows:
        party_id_map[row[1]] = row[0]

    # Insert candidates (clear existing first to allow re-runs)
    conn.execute("DELETE FROM candidates")

    for c in all_candidates:
        party_id = party_id_map.get(c["party_jne_id"])
        if not party_id:
            continue

        conn.execute(
            """INSERT INTO candidates
                   (party_id, election_type, constituency, full_name, position,
                    document_number, status, photo_url, jne_profile_id, candidate_number)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                party_id,
                c["election_type"],
                c["constituency"],
                c["full_name"],
                c["position"],
                c["document_number"],
                c["status"],
                c["photo_url"],
                c["jne_profile_id"],
                c["candidate_number"],
            ),
        )

    conn.commit()

    count = conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]
    party_count = conn.execute("SELECT COUNT(*) FROM parties").fetchone()[0]
    print(f"\nDB: {party_count} parties, {count} candidates inserted")

    conn.close()


def collect_all(*, json_only: bool = False):
    """Fetch all candidates across all election types → all_candidates_2026.json + DB."""
    found_types = probe_election_types()

    if not found_types:
        print("No election types found. Exiting.")
        sys.exit(1)

    print("=" * 60)
    print("Fetching ALL candidates across all election types")
    print("=" * 60)

    all_candidates: list[dict] = []
    stats: dict[str, int] = {}

    for type_id, cargo_sample in found_types.items():
        election_type = ELECTION_TYPE_MAP.get(type_id, f"type_{type_id}")
        print(f"\n--- {election_type.upper()} (type={type_id}, sample: {cargo_sample}) ---")
        type_count = 0

        for org_id, party_name, _ in PARTIES:
            try:
                raw_candidates = fetch_candidates_api(org_id, type_id)
                for raw in raw_candidates:
                    candidate = build_candidate_dict(
                        raw,
                        party_name=party_name,
                        party_jne_id=org_id,
                        election_type=election_type,
                        constituency=(raw.get("txUbigeoDescripcion") or None),
                    )
                    if candidate["full_name"]:
                        all_candidates.append(candidate)
                        type_count += 1

                if raw_candidates:
                    print(f"  {party_name[:35]:<35} → {len(raw_candidates):>3} candidates")
            except Exception as e:
                print(f"  {party_name[:35]:<35} → ERROR: {e}")

            time.sleep(0.2)

        stats[election_type] = type_count
        print(f"  Subtotal: {type_count}")

    output = {
        "election": "ELECCIONES GENERALES 2026",
        "electoral_process_id": ELECTORAL_PROCESS_2026,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source": "JNE - Jurado Nacional de Elecciones",
        "total_candidates": len(all_candidates),
        "by_type": stats,
        "total_parties": len(PARTIES),
        "candidates": all_candidates,
    }

    out_path = BASE_DIR / "all_candidates_2026.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"✓ {out_path}")
    print(f"  Total: {len(all_candidates)} candidates")
    for etype, count in stats.items():
        print(f"    {etype:<25} {count:>5}")

    if not json_only:
        print("\nInserting into database...")
        insert_into_db(all_candidates)


# ── Main ──────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Fetch candidates from JNE API")
    parser.add_argument(
        "--all", action="store_true", help="Fetch all election types (not just presidential)"
    )
    parser.add_argument("--probe", action="store_true", help="Only probe election types")
    parser.add_argument("--json-only", action="store_true", help="Skip DB insert (with --all)")
    args = parser.parse_args()

    if args.probe:
        probe_election_types()
    elif args.all:
        collect_all(json_only=args.json_only)
    else:
        collect_presidential()


if __name__ == "__main__":
    main()
