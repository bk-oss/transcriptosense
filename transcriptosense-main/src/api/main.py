from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from src.api.routes.transcription import router as transcription_router
from src.api.routes.history import router as history_router
from src.api.routes.translation import router as translation_router
from src.api.services.database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="Transcriptosense API",
    version="2.1.0",
    description="Backend API for multilingual audio transcription with history and translation",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()


# ── API routes ────────────────────────────────────────────────────────────────
app.include_router(transcription_router, prefix="/api")
app.include_router(history_router, prefix="/api")
app.include_router(translation_router, prefix="/api")


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "2.1.0"}


# ── Serve the frontend (must be LAST so API routes take priority) ─────────────
_UI_DIR = Path(__file__).resolve().parent.parent / "ui"
if _UI_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_UI_DIR), html=True), name="ui")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
