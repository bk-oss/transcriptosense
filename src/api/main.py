from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes.transcription import router as transcription_router
from src.api.routes.history import router as history_router
from src.api.services.database import init_db

app = FastAPI(
    title="Transcriptosense API",
    version="2.0.0",
    description="Backend API for audio transcription with history"
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


app.include_router(transcription_router, prefix="/api")
app.include_router(history_router, prefix="/api")


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "2.0.0"}
