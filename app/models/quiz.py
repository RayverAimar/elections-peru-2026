from pydantic import BaseModel, Field


class QuizStartRequest(BaseModel):
    preferred_topics: list[str] | None = None


class QuizQuestion(BaseModel):
    id: str
    text: str
    topic: str
    topic_display: str
    hint: str | None = None


class QuizProgress(BaseModel):
    current: int
    min_questions: int
    max_questions: int
    confidence: float | None = None


class QuizStartResponse(BaseModel):
    session_id: str
    question: QuizQuestion
    progress: QuizProgress
    can_finish: bool


class QuizAnswerRequest(BaseModel):
    session_id: str
    question_id: str
    value: int = Field(ge=-2, le=2)


class QuizAnswerResponse(BaseModel):
    question: QuizQuestion | None
    progress: QuizProgress
    can_finish: bool
    finished: bool


class QuizResultsRequest(BaseModel):
    session_id: str


class EvidenceItem(BaseModel):
    question: str
    user_answer: int
    party_score: int
    explanation: str


class CandidateMatch(BaseModel):
    party: str
    candidate: str
    photo_url: str | None = None
    score: float
    agreement_by_topic: dict[str, float]
    evidence: list[EvidenceItem]


class QuizResultsResponse(BaseModel):
    top_candidates: list[CandidateMatch]
    also_matches: list[CandidateMatch] | None = None
    user_profile: dict[str, float]
    total_questions_answered: int


class QuizExplainRequest(BaseModel):
    session_id: str
    party_key: str
    topic: str


class QuizExplainResponse(BaseModel):
    explanation: str
    sources: list[str]
