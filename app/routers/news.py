"""News articles endpoints."""

from fastapi import APIRouter, HTTPException, Query, Request

from app.models.news import CandidateNewsProfile, NewsDetail, NewsItem, NewsResponse

router = APIRouter(prefix="/noticias", tags=["news"])


@router.get("/", response_model=NewsResponse)
async def list_news(
    request: Request,
    party: str | None = Query(None, description="Filter by party name"),
    sentiment: str | None = Query(
        None, description="Filter by sentiment: adverse, neutral, positive"
    ),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List news articles, optionally filtered by party or sentiment."""
    if not request.app.state.chat_service.news_enabled:
        return NewsResponse(total=0, articles=[])

    conditions = []
    params: dict = {"limit": limit, "offset": offset}

    if party:
        conditions.append(
            "EXISTS (SELECT 1 FROM news_mentions nm "
            "WHERE nm.article_id = na.id AND nm.party_name ILIKE %(party)s)"
        )
        params["party"] = f"%{party}%"

    if sentiment:
        conditions.append("na.sentiment_label = %(sentiment)s")
        params["sentiment"] = sentiment

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    async with request.app.state.db_pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(f"SELECT COUNT(*) FROM news_articles na {where}", params)
        total = (await cur.fetchone())[0]

        await cur.execute(
            f"""SELECT na.id, na.title, na.url, na.source_name,
                           na.published_at, na.sentiment_label,
                           na.adverse_categories
                    FROM news_articles na
                    {where}
                    ORDER BY na.published_at DESC NULLS LAST
                    LIMIT %(limit)s OFFSET %(offset)s""",
            params,
        )
        rows = await cur.fetchall()

    articles = [
        NewsItem(
            id=r[0],
            title=r[1],
            url=r[2],
            source_name=r[3],
            published_at=r[4],
            sentiment_label=r[5],
            adverse_categories=r[6] or [],
        )
        for r in rows
    ]

    return NewsResponse(total=total, articles=articles)


@router.get("/profile/{party}", response_model=CandidateNewsProfile)
async def get_candidate_news_profile(request: Request, party: str):
    """'Lo que deberías saber' — news profile for a candidate/party."""
    if not request.app.state.chat_service.news_enabled:
        raise HTTPException(status_code=404, detail="News not enabled")

    async with request.app.state.db_pool.connection() as conn, conn.cursor() as cur:
        # Sentiment counts
        await cur.execute(
            """SELECT na.sentiment_label, COUNT(*)
                   FROM news_articles na
                   JOIN news_mentions nm ON nm.article_id = na.id
                   WHERE nm.party_name ILIKE %(party)s
                   GROUP BY na.sentiment_label""",
            {"party": f"%{party}%"},
        )
        sentiment_counts = dict(await cur.fetchall())
        total = sum(sentiment_counts.values())

        if total == 0:
            raise HTTPException(
                status_code=404,
                detail=f"No news found for '{party}'",
            )

        # Adverse category breakdown
        await cur.execute(
            """SELECT unnest(na.adverse_categories) AS cat, COUNT(*)
                   FROM news_articles na
                   JOIN news_mentions nm ON nm.article_id = na.id
                   WHERE nm.party_name ILIKE %(party)s
                     AND na.adverse_categories IS NOT NULL
                   GROUP BY cat ORDER BY COUNT(*) DESC""",
            {"party": f"%{party}%"},
        )
        adverse_cats = dict(await cur.fetchall())

        # Top controversial (adverse, most recent)
        await cur.execute(
            """SELECT na.id, na.title, na.url, na.source_name,
                          na.published_at, na.sentiment_label,
                          na.adverse_categories
                   FROM news_articles na
                   JOIN news_mentions nm ON nm.article_id = na.id
                   WHERE nm.party_name ILIKE %(party)s
                     AND na.sentiment_label = 'adverse'
                   ORDER BY na.published_at DESC NULLS LAST
                   LIMIT 5""",
            {"party": f"%{party}%"},
        )
        controversial = [
            NewsItem(
                id=r[0],
                title=r[1],
                url=r[2],
                source_name=r[3],
                published_at=r[4],
                sentiment_label=r[5],
                adverse_categories=r[6] or [],
            )
            for r in await cur.fetchall()
        ]

        # Top favorable (positive, most recent)
        await cur.execute(
            """SELECT na.id, na.title, na.url, na.source_name,
                          na.published_at, na.sentiment_label,
                          na.adverse_categories
                   FROM news_articles na
                   JOIN news_mentions nm ON nm.article_id = na.id
                   WHERE nm.party_name ILIKE %(party)s
                     AND na.sentiment_label = 'positive'
                   ORDER BY na.published_at DESC NULLS LAST
                   LIMIT 5""",
            {"party": f"%{party}%"},
        )
        favorable = [
            NewsItem(
                id=r[0],
                title=r[1],
                url=r[2],
                source_name=r[3],
                published_at=r[4],
                sentiment_label=r[5],
                adverse_categories=r[6] or [],
            )
            for r in await cur.fetchall()
        ]

        # Recent articles (all sentiments)
        await cur.execute(
            """SELECT na.id, na.title, na.url, na.source_name,
                          na.published_at, na.sentiment_label,
                          na.adverse_categories
                   FROM news_articles na
                   JOIN news_mentions nm ON nm.article_id = na.id
                   WHERE nm.party_name ILIKE %(party)s
                   ORDER BY na.published_at DESC NULLS LAST
                   LIMIT 10""",
            {"party": f"%{party}%"},
        )
        recent = [
            NewsItem(
                id=r[0],
                title=r[1],
                url=r[2],
                source_name=r[3],
                published_at=r[4],
                sentiment_label=r[5],
                adverse_categories=r[6] or [],
            )
            for r in await cur.fetchall()
        ]

        # Get candidate name
        candidate = ""
        await cur.execute(
            "SELECT candidate_name FROM news_mentions "
            "WHERE party_name ILIKE %(party)s AND candidate_name IS NOT NULL "
            "LIMIT 1",
            {"party": f"%{party}%"},
        )
        row = await cur.fetchone()
        if row:
            candidate = row[0]

    return CandidateNewsProfile(
        party=party,
        candidate=candidate or party,
        total_articles=total,
        adverse_count=sentiment_counts.get("adverse", 0),
        neutral_count=sentiment_counts.get("neutral", 0),
        positive_count=sentiment_counts.get("positive", 0),
        adverse_categories=adverse_cats,
        controversial=controversial,
        favorable=favorable,
        recent=recent,
    )


@router.get("/{article_id}", response_model=NewsDetail)
async def get_news_article(request: Request, article_id: int):
    """Get a news article with full content."""
    if not request.app.state.chat_service.news_enabled:
        raise HTTPException(status_code=404, detail="News not enabled")

    async with request.app.state.db_pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """SELECT na.id, na.title, na.url, na.source_name,
                          na.published_at, na.sentiment_label,
                          na.adverse_categories, na.content, na.description
                   FROM news_articles na WHERE na.id = %s""",
            (article_id,),
        )
        row = await cur.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Article not found")

        await cur.execute(
            "SELECT party_name FROM news_mentions WHERE article_id = %s",
            (article_id,),
        )
        mentions = [r[0] for r in await cur.fetchall()]

    return NewsDetail(
        id=row[0],
        title=row[1],
        url=row[2],
        source_name=row[3],
        published_at=row[4],
        sentiment_label=row[5],
        adverse_categories=row[6] or [],
        content=row[7],
        description=row[8],
        mentions=mentions,
    )
