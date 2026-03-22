"""Models for the Investiga a tu candidato feature."""

from datetime import date

from pydantic import BaseModel


class CategoryCount(BaseModel):
    category: str
    count: int


class InvestigaPartyItem(BaseModel):
    """One party card on the landing page."""

    party_name: str
    jne_id: int
    presidential_candidate: str
    photo_url: str | None = None
    cuestionable_count: int
    category_counts: list[CategoryCount]


class InvestigaListResponse(BaseModel):
    parties: list[InvestigaPartyItem]


class InvestigaEventStance(BaseModel):
    """One cuestionable event for a party."""

    event_id: str
    title: str
    event_date: date | None = None
    category: str
    severity: str
    description: str
    why_it_matters: str
    sources: list[str]
    stance: str
    stance_detail: str | None = None
    evidence: list[dict] = []


class InvestigaPartyDetail(BaseModel):
    """Full detail for one party's cuestionable events."""

    party_name: str
    jne_id: int
    presidential_candidate: str
    photo_url: str | None = None
    cuestionable_count: int
    events: list[InvestigaEventStance]
