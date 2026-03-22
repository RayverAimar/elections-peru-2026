from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from psycopg_pool import AsyncConnectionPool

from app.config import Settings
from app.routers import candidates, chat, events, investigation, news, quiz
from app.services.adaptive_quiz import AdaptiveQuizEngine
from app.services.chat_service import ChatService
from app.services.data_loader import DataLoader


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    app.state.settings = settings
    app.state.data_loader = DataLoader(settings.data_dir)
    app.state.quiz_engine = AdaptiveQuizEngine(settings.data_dir)

    pool = AsyncConnectionPool(settings.database_url, min_size=2, max_size=5)
    await pool.open()
    app.state.db_pool = pool

    chat_service = ChatService(
        api_key=settings.anthropic_api_key,
        pool=pool,
    )
    await chat_service.startup()
    app.state.chat_service = chat_service

    yield

    await chat_service.shutdown()
    await pool.close()


app = FastAPI(
    title="Peru 2026 Vote Compass",
    description="Quiz electoral para las elecciones generales 2026 del Perú",
    version="0.1.0",
    lifespan=lifespan,
)

settings_for_cors = Settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings_for_cors.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(candidates.router)
app.include_router(quiz.router)
app.include_router(chat.router)
app.include_router(news.router)
app.include_router(events.router)
app.include_router(investigation.router)


@app.get("/")
async def root():
    return {
        "name": "Peru 2026 Vote Compass",
        "version": "0.1.0",
        "endpoints": {
            "candidates": "/candidates",
            "quiz_start": "/quiz/start",
            "quiz_answer": "/quiz/answer",
            "quiz_results": "/quiz/results",
            "chat": "/chat",
            "news": "/noticias",
            "events": "/events",
            "investiga": "/investiga",
            "docs": "/docs",
        },
    }
