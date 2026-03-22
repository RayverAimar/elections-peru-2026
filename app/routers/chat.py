import time
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Request

from app.models.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])

# Simple in-memory rate limiter
_request_times: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(client_ip: str, max_rpm: int):
    now = time.time()
    times = _request_times[client_ip]
    # Remove entries older than 60 seconds
    _request_times[client_ip] = [t for t in times if now - t < 60]
    if len(_request_times[client_ip]) >= max_rpm:
        raise HTTPException(
            status_code=429,
            detail=f"Límite de {max_rpm} consultas por minuto excedido. Intenta de nuevo en un momento.",
        )
    _request_times[client_ip].append(now)


@router.post("/", response_model=ChatResponse)
async def chat(body: ChatRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip, request.app.state.settings.chat_rate_limit_rpm)

    chat_service = request.app.state.chat_service
    return await chat_service.ask(body.question)
