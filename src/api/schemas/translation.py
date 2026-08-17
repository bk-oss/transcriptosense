from pydantic import BaseModel
from typing import Optional, List


class TranslateRequest(BaseModel):
    text: str
    target: str = "en"
    source: Optional[str] = "auto"


class TranslateResponse(BaseModel):
    translated_text: str
    source: str
    target: str


class LanguageItem(BaseModel):
    code: str
    name: str


class LanguageListResponse(BaseModel):
    languages: List[LanguageItem]
