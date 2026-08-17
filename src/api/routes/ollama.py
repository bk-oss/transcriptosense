import httpx
from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from typing import Optional

router = APIRouter(tags=["Ollama"])

OLLAMA_TAGS = "http://localhost:11434/api/tags"
OLLAMA_GEN  = "http://localhost:11434/api/generate"
MODEL_NAME  = "mistral:latest"
TIMEOUT_SEC = 120.0


# ── Schemas ────────────────────────────────────────────────────
class NLPRequest(BaseModel):
    text:         str
    clean:        bool          = True
    translate_to: Optional[str] = None
    summarize:    bool          = False


class NLPResponse(BaseModel):
    cleaned_text:    Optional[str] = None
    translated_text: Optional[str] = None
    summary:         Optional[str] = None


class WordTranslationResponse(BaseModel):
    original:    str
    translation: str
    language:    str


# ── Helper ─────────────────────────────────────────────────────
def _ask_ollama(prompt: str) -> str:
    """Send prompt to Ollama and return response text."""
    with httpx.Client(timeout=TIMEOUT_SEC, verify=False) as client:
        response = client.post(
            OLLAMA_GEN,
            json={
                "model":  MODEL_NAME,
                "prompt": prompt,
                "stream": False,
            },
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()


# ── Status ─────────────────────────────────────────────────────
@router.get("/ollama/status")
async def ollama_status():
    """Check if Ollama is running and mistral model is available."""
    try:
        async with httpx.AsyncClient(timeout=3.0, verify=False) as client:
            response = await client.get(OLLAMA_TAGS)
            response.raise_for_status()
            data = response.json()

        models_list = data.get("models", [])
        models      = {item.get("name") for item in models_list if isinstance(item, dict)}
        available   = MODEL_NAME in models

        return {
            "available": available,
            "model":     MODEL_NAME if available else None,
        }

    except Exception:
        return {"available": False, "model": None}


# ── NLP ────────────────────────────────────────────────────────
@router.post("/ollama/nlp", response_model=NLPResponse)
async def run_nlp(request: NLPRequest):
    """
    Run NLP pipeline on transcription text:
    - Clean text (remove fillers, fix grammar)
    - Translate to any language
    - Summarize
    """
    # ✅ Check Ollama is available
    status = await ollama_status()
    if not status["available"]:
        raise HTTPException(
            status_code=503,
            detail="Ollama is not running or mistral model not found. Run: ollama run mistral"
        )

    result = NLPResponse()

    # ── Clean ──────────────────────────────────────────────────
    if request.clean:
        try:
            prompt = f"""You are a professional transcription editor.
Clean the following transcription text by:
- Removing filler words (uh, um, like, you know, etc.)
- Removing repetitions
- Fixing obvious grammar mistakes
- Keeping the original meaning intact
- Do NOT translate — keep the original language

Return ONLY the cleaned text, nothing else.

Text:
{request.text}"""
            result.cleaned_text = await run_in_threadpool(_ask_ollama, prompt)
            print(f"[NLP] Cleaned ✅ | Words: {len(result.cleaned_text.split())}")
        except Exception as e:
            print(f"[NLP] Clean failed: {e}")
            result.cleaned_text = request.text

    # ── Translate ──────────────────────────────────────────────
    if request.translate_to:
        try:
            source = result.cleaned_text or request.text
            prompt = f"""You are a professional translator.
Translate the following text to {request.translate_to}.
Return ONLY the translated text, nothing else.

Text:
{source}"""
            result.translated_text = await run_in_threadpool(_ask_ollama, prompt)
            print(f"[NLP] Translated to {request.translate_to} ✅")
        except Exception as e:
            print(f"[NLP] Translation failed: {e}")
            result.translated_text = None

    # ── Summarize ──────────────────────────────────────────────
    if request.summarize:
        try:
            source = result.cleaned_text or request.text
            prompt = f"""You are a professional summarizer.
Summarize the following transcription in 3-5 sentences.
Keep the most important points.
Return ONLY the summary, nothing else.

Text:
{source}"""
            result.summary = await run_in_threadpool(_ask_ollama, prompt)
            print(f"[NLP] Summarized ✅ | Words: {len(result.summary.split())}")
        except Exception as e:
            print(f"[NLP] Summarize failed: {e}")
            result.summary = None

    return result


# ── Word translation ───────────────────────────────────────────
@router.get("/ollama/translate-word", response_model=WordTranslationResponse)
async def translate_word(word: str, target_language: str = "English"):
    """Translate a single word or short phrase to any language."""
    status = await ollama_status()
    if not status["available"]:
        raise HTTPException(
            status_code=503,
            detail="Ollama is not running."
        )

    try:
        prompt = f"""Translate the word or phrase "{word}" to {target_language}.
Return ONLY the translation, nothing else."""
        translation = await run_in_threadpool(_ask_ollama, prompt)
        return WordTranslationResponse(
            original    = word,
            translation = translation,
            language    = target_language,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
