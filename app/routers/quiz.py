"""Adaptive quiz endpoints."""

from fastapi import APIRouter, HTTPException, Request

from app.models.quiz import (
    CandidateMatch,
    EvidenceItem,
    QuizAnswerRequest,
    QuizAnswerResponse,
    QuizExplainRequest,
    QuizExplainResponse,
    QuizProgress,
    QuizQuestion,
    QuizResultsRequest,
    QuizResultsResponse,
    QuizStartRequest,
    QuizStartResponse,
)
from app.services.adaptive_quiz import MIN_QUESTIONS

router = APIRouter(prefix="/quiz", tags=["quiz"])


def _to_question(q: dict) -> QuizQuestion:
    return QuizQuestion(
        id=q["id"],
        text=q.get("text", ""),
        topic=q.get("topic", ""),
        topic_display=q.get("topic_display", ""),
        hint=q.get("hint"),
    )


def _to_progress(p: dict) -> QuizProgress:
    return QuizProgress(**p)


@router.post("/start", response_model=QuizStartResponse)
async def start_quiz(body: QuizStartRequest, request: Request):
    engine = request.app.state.quiz_engine
    if not engine.available:
        raise HTTPException(status_code=503, detail="Quiz no disponible aún")

    session_id, question, progress = engine.start_session(body.preferred_topics)

    return QuizStartResponse(
        session_id=session_id,
        question=_to_question(question),
        progress=_to_progress(progress),
        can_finish=progress["current"] >= MIN_QUESTIONS,
    )


@router.post("/answer", response_model=QuizAnswerResponse)
async def answer_question(body: QuizAnswerRequest, request: Request):
    engine = request.app.state.quiz_engine

    try:
        next_q, progress, finished = engine.answer(body.session_id, body.question_id, body.value)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None

    return QuizAnswerResponse(
        question=_to_question(next_q) if next_q else None,
        progress=_to_progress(progress),
        can_finish=progress["current"] >= MIN_QUESTIONS,
        finished=finished,
    )


@router.post("/results", response_model=QuizResultsResponse)
async def get_results(body: QuizResultsRequest, request: Request):
    engine = request.app.state.quiz_engine

    try:
        results = engine.get_results(body.session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None

    def _to_match(c: dict) -> CandidateMatch:
        return CandidateMatch(
            party=c["party"],
            candidate=c["candidate"],
            photo_url=c["photo_url"],
            score=c["score"],
            agreement_by_topic=c["agreement_by_topic"],
            evidence=[EvidenceItem(**e) for e in c["evidence"]],
        )

    return QuizResultsResponse(
        top_candidates=[_to_match(c) for c in results["top_candidates"]],
        also_matches=[_to_match(c) for c in results.get("also_matches", [])],
        user_profile=results["user_profile"],
        total_questions_answered=results["total_questions_answered"],
    )


@router.post("/explain", response_model=QuizExplainResponse)
async def explain_match(body: QuizExplainRequest, request: Request):
    engine = request.app.state.quiz_engine
    session = engine.get_session(body.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    chat_service = request.app.state.chat_service
    question = (
        f"Explica detalladamente las propuestas del partido {body.party_key} "
        f"sobre el tema {body.topic}, según su plan de gobierno."
    )

    response = await chat_service.ask(question)

    return QuizExplainResponse(
        explanation=response.answer,
        sources=response.sources,
    )
