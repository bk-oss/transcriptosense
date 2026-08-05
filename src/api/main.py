from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import traceback

from src.api.routes.transcription import router as transcription_router
from src.api.routes.history       import router as history_router
from src.api.routes.ollama        import router as ollama_router
from src.api.services.database    import init_db

app = FastAPI(
    title="Transcriptosense API",
    version="2.0.0",
    description="Backend API for multilingual audio transcription with history",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "null",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()
    print("[APP] All routers registered. Backend ready.")


# ✅ Fix: Proper JSON error handler for ALL exceptions
@app.exception_handler(Exception)
async def internal_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc) or "Internal server error."},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


# ── API routes ────────────────────────────────────────────────
app.include_router(transcription_router, prefix="/api")
app.include_router(history_router,       prefix="/api")
app.include_router(ollama_router,        prefix="/api")


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "2.0.0"}


# ── Serve frontend (MUST be last) ─────────────────────────────
_UI_DIR = Path(__file__).resolve().parent.parent / "ui"
if _UI_DIR.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(_UI_DIR), html=True),
        name="ui",
    )
