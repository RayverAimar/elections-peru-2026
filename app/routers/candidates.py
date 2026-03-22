from fastapi import APIRouter, HTTPException, Query, Request

from app.models.candidates import (
    CandidateListItem,
    CandidatesResponse,
    PartyDetail,
    PartyListItem,
)

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.get("/", response_model=list[PartyListItem])
async def list_parties(request: Request):
    """List all 36 parties with their presidential candidates."""
    return request.app.state.data_loader.get_all_parties()


@router.get("/search", response_model=CandidatesResponse)
async def search_candidates(
    request: Request,
    q: str | None = Query(None, description="Search by name"),
    election_type: str | None = Query(None, description="presidential, senator, representative, andean_parliament"),
    constituency: str | None = Query(None, description="Filter by constituency (for representatives)"),
    party: str | None = Query(None, description="Filter by party name"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Search across all 6,959 candidates with filters."""
    conditions = []
    params: dict = {"limit": limit, "offset": offset}

    if q:
        conditions.append("c.full_name ILIKE %(q)s")
        params["q"] = f"%{q}%"

    if election_type:
        conditions.append("c.election_type = %(election_type)s")
        params["election_type"] = election_type

    if constituency:
        conditions.append("c.constituency ILIKE %(constituency)s")
        params["constituency"] = f"%{constituency}%"

    if party:
        conditions.append("p.name ILIKE %(party)s")
        params["party"] = f"%{party}%"

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    async with request.app.state.db_pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"SELECT COUNT(*) FROM candidates c JOIN parties p ON p.id = c.party_id {where}",
            params,
        )
        total = (await cur.fetchone())[0]

        await cur.execute(
            f"""SELECT c.id, p.name, c.election_type, c.constituency,
                           c.full_name, c.position, c.photo_url
                    FROM candidates c
                    JOIN parties p ON p.id = c.party_id
                    {where}
                    ORDER BY p.name, c.candidate_number
                    LIMIT %(limit)s OFFSET %(offset)s""",
            params,
        )
        rows = await cur.fetchall()

    candidates = [
        CandidateListItem(
            id=r[0], party_name=r[1], election_type=r[2],
            constituency=r[3], full_name=r[4], position=r[5], photo_url=r[6],
        )
        for r in rows
    ]

    return CandidatesResponse(total=total, candidates=candidates)


@router.get("/{party_id}", response_model=PartyDetail)
async def get_party(party_id: int, request: Request):
    """Get party detail with presidential formula and positions."""
    detail = request.app.state.data_loader.get_party_detail(party_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    return detail
