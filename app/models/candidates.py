from pydantic import BaseModel


class Candidate(BaseModel):
    full_name: str
    position: str
    document_number: str | None = None
    status: str | None = None
    photo_url: str | None = None


class PresidentialFormula(BaseModel):
    president: Candidate | None = None
    first_vice_president: Candidate | None = None
    second_vice_president: Candidate | None = None


class GovernmentPlan(BaseModel):
    plan_id: int | None = None
    full_plan_url: str | None = None
    summary_plan_url: str | None = None


class PartyListItem(BaseModel):
    id: int
    name: str
    presidential_candidate: str
    photo_url: str | None = None


class PartyDetail(BaseModel):
    id: int
    name: str
    presidential_formula: PresidentialFormula
    government_plan: GovernmentPlan | None = None
    positions: dict | None = None


class CandidateListItem(BaseModel):
    id: int
    party_name: str
    election_type: str
    constituency: str | None = None
    full_name: str
    position: str | None = None
    photo_url: str | None = None


class CandidatesResponse(BaseModel):
    total: int
    candidates: list[CandidateListItem]
