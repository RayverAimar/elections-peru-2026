"""Political events endpoints."""

from fastapi import APIRouter, HTTPException, Query, Request

from app.models.events import (
    EventDetail,
    EventItem,
    EventPartyStance,
    EventsResponse,
    StanceEvidence,
)

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/", response_model=EventsResponse)
async def list_events(
    request: Request,
    category: str | None = Query(None, description="Filter by event category"),
    party: str | None = Query(None, description="Filter by party name"),
    severity: str | None = Query(None, description="Filter by severity level"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List political events, optionally filtered by category, party, or severity."""
    if not request.app.state.chat_service.events_enabled:
        return EventsResponse(total=0, events=[])

    conditions = []
    params: dict = {"limit": limit, "offset": offset}

    if category:
        conditions.append("pe.category = %(category)s")
        params["category"] = category

    if severity:
        conditions.append("pe.severity = %(severity)s")
        params["severity"] = severity

    if party:
        conditions.append(
            "EXISTS (SELECT 1 FROM event_party_stances eps "
            "WHERE eps.event_id = pe.id AND eps.party_name ILIKE %(party)s)"
        )
        params["party"] = f"%{party}%"

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    async with request.app.state.db_pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"SELECT COUNT(*) FROM political_events pe {where}", params
        )
        total = (await cur.fetchone())[0]

        await cur.execute(
            f"""SELECT pe.id, pe.title, pe.event_date, pe.category,
                           pe.severity, pe.description, pe.sources
                    FROM political_events pe
                    {where}
                    ORDER BY pe.event_date DESC NULLS LAST
                    LIMIT %(limit)s OFFSET %(offset)s""",
            params,
        )
        rows = await cur.fetchall()

    events = [
        EventItem(
            id=r[0],
            title=r[1],
            event_date=r[2],
            category=r[3],
            severity=r[4],
            description=r[5],
            sources=r[6] or [],
        )
        for r in rows
    ]

    return EventsResponse(total=total, events=events)


@router.get("/{event_id}", response_model=EventDetail)
async def get_event(request: Request, event_id: str):
    """Get a political event with full detail and party stances."""
    if not request.app.state.chat_service.events_enabled:
        raise HTTPException(status_code=404, detail="Events not enabled")

    async with request.app.state.db_pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """SELECT pe.id, pe.title, pe.event_date, pe.category,
                          pe.severity, pe.description, pe.sources,
                          pe.why_it_matters
                   FROM political_events pe WHERE pe.id = %s""",
            (event_id,),
        )
        row = await cur.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Event not found")

        await cur.execute(
            """SELECT party_name, stance, detail, evidence
                   FROM event_party_stances WHERE event_id = %s
                   ORDER BY party_name""",
            (event_id,),
        )
        stance_rows = await cur.fetchall()

    stances = [
        EventPartyStance(
            party_name=s[0],
            stance=s[1],
            detail=s[2],
            evidence=[StanceEvidence(**e) for e in (s[3] or [])],
        )
        for s in stance_rows
    ]

    return EventDetail(
        id=row[0],
        title=row[1],
        event_date=row[2],
        category=row[3],
        severity=row[4],
        description=row[5],
        sources=row[6] or [],
        why_it_matters=row[7] or "",
        party_stances=stances,
    )
