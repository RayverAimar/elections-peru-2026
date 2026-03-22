from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=5, max_length=500)


class ChatSource(BaseModel):
    name: str
    source_type: str  # "plan", "news", "event"
    url: str | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[ChatSource]
