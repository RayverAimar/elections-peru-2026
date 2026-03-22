"""Investiga a tu candidato endpoints."""

from collections import defaultdict

from fastapi import APIRouter, HTTPException, Request

from app.models.investigation import (
    CategoryCount,
    InvestigaEventStance,
    InvestigaListResponse,
    InvestigaPartyDetail,
    InvestigaPartyItem,
)

router = APIRouter(prefix="/investiga", tags=["investiga"])

# Cuestionable = high-severity events where the party supported/was involved,
# OR abstained on human rights events.
CUESTIONABLE_WHERE = """
    (eps.stance IN ('supported', 'involved') AND pe.severity = 'high')
    OR (eps.stance = 'abstained' AND pe.category = 'human_rights')
"""


@router.get("/", response_model=InvestigaListResponse)
async def list_parties(request: Request):
    """List all parties with their cuestionable event counts."""
    if not request.app.state.chat_service.events_enabled:
        return InvestigaListResponse(parties=[])

    # 1. Get all 36 parties from in-memory data
    all_parties = request.app.state.data_loader.get_all_parties()

    # 2. Query cuestionable counts grouped by party + category
    async with request.app.state.db_pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""SELECT eps.party_name, pe.category, COUNT(*) as cnt
                    FROM event_party_stances eps
                    JOIN political_events pe ON pe.id = eps.event_id
                    WHERE {CUESTIONABLE_WHERE}
                    GROUP BY eps.party_name, pe.category
                    ORDER BY eps.party_name"""
        )
        rows = await cur.fetchall()

    # 3. Build lookup: {party_name: {category: count}}
    party_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for party_name, category, cnt in rows:
        party_counts[party_name][category] = cnt

    # 4. Merge with all parties
    items = []
    for p in all_parties:
        counts = party_counts.get(p.name, {})
        total = sum(counts.values())
        category_list = [
            CategoryCount(category=cat, count=cnt) for cat, cnt in sorted(counts.items())
        ]
        items.append(
            InvestigaPartyItem(
                party_name=p.name,
                jne_id=p.id,
                presidential_candidate=p.presidential_candidate,
                photo_url=p.photo_url,
                cuestionable_count=total,
                category_counts=category_list,
            )
        )

    # Sort: most cuestionable first, then alphabetical
    items.sort(key=lambda x: (-x.cuestionable_count, x.party_name))

    return InvestigaListResponse(parties=items)


@router.get("/{jne_id}", response_model=InvestigaPartyDetail)
async def get_party_detail(request: Request, jne_id: int):
    """Get all cuestionable events for a specific party."""
    if not request.app.state.chat_service.events_enabled:
        raise HTTPException(status_code=404, detail="Events not enabled")

    # Lookup party from in-memory data
    party = request.app.state.data_loader.get_party_detail(jne_id)
    if not party:
        raise HTTPException(status_code=404, detail="Party not found")

    pres = party.presidential_formula.president

    # Query cuestionable events for this party
    async with request.app.state.db_pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""SELECT pe.id, pe.title, pe.event_date, pe.category, pe.severity,
                           pe.description, pe.why_it_matters, pe.sources,
                           eps.stance, eps.detail, eps.evidence
                    FROM event_party_stances eps
                    JOIN political_events pe ON pe.id = eps.event_id
                    WHERE eps.party_name = %(party_name)s
                      AND ({CUESTIONABLE_WHERE})
                    ORDER BY pe.category, pe.event_date DESC NULLS LAST""",
            {"party_name": party.name},
        )
        rows = await cur.fetchall()

    events = [
        InvestigaEventStance(
            event_id=r[0],
            title=r[1],
            event_date=r[2],
            category=r[3],
            severity=r[4],
            description=r[5],
            why_it_matters=r[6],
            sources=r[7] or [],
            stance=r[8],
            stance_detail=r[9],
            evidence=r[10] or [],
        )
        for r in rows
    ]

    return InvestigaPartyDetail(
        party_name=party.name,
        jne_id=jne_id,
        presidential_candidate=pres.full_name if pres else "",
        photo_url=pres.photo_url if pres else None,
        cuestionable_count=len(events),
        events=events,
    )
