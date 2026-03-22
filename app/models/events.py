from datetime import date

from pydantic import BaseModel


class StanceEvidence(BaseModel):
    quote: str
    source_description: str
    source_url: str | None = None


class EventPartyStance(BaseModel):
    party_name: str
    stance: str  # supported, opposed, abstained, involved
    detail: str | None = None
    evidence: list[StanceEvidence] = []


class EventItem(BaseModel):
    id: str
    title: str
    event_date: date | None = None
    category: str
    severity: str
    description: str
    sources: list[str] = []


class EventDetail(EventItem):
    why_it_matters: str
    party_stances: list[EventPartyStance] = []


class EventsResponse(BaseModel):
    total: int
    events: list[EventItem]
