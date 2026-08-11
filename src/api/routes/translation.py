from fastapi import APIRouter, HTTPException

from src.api.schemas.translation import (
    TranslateRequest,
    TranslateResponse,
    LanguageListResponse,
    LanguageItem,
)
from src.api.services.translation_service import translate_text, get_supported_languages

router = APIRouter(tags=["Translation"])


@router.get("/languages", response_model=LanguageListResponse)
def list_languages():
    """Return all supported translation languages."""
    try:
        langs = get_supported_languages()
        return LanguageListResponse(
            languages=[LanguageItem(**l) for l in langs]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch languages: {str(e)}")


@router.post("/translate", response_model=TranslateResponse)
def translate(req: TranslateRequest):
    """Translate text to target language."""
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="Text is required.")
    if not req.target:
        raise HTTPException(status_code=400, detail="Target language is required.")

    try:
        result = translate_text(
            text=req.text,
            target=req.target,
            source=req.source or "auto",
        )
        return TranslateResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Translation failed: {str(e)}")
