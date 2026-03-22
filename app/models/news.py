from datetime import datetime

from pydantic import BaseModel


class NewsItem(BaseModel):
    id: int
    title: str
    url: str
    source_name: str
    published_at: datetime | None = None
    sentiment_label: str
    adverse_categories: list[str] = []


class NewsDetail(NewsItem):
    content: str | None = None
    description: str | None = None
    mentions: list[str] = []  # party names


class NewsResponse(BaseModel):
    total: int
    articles: list[NewsItem]


class CandidateNewsProfile(BaseModel):
    """'Lo que deberías saber' — news-based profile for a candidate."""

    party: str
    candidate: str
    total_articles: int
    adverse_count: int
    neutral_count: int
    positive_count: int
    adverse_categories: dict[str, int]  # category → count
    # Top controversial articles (full detail for display)
    controversial: list[NewsItem]
    # Top positive articles
    favorable: list[NewsItem]
    # Recent articles (all sentiments, just titles + urls)
    recent: list[NewsItem]
