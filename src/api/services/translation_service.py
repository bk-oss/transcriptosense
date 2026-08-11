"""
Translation service using deep-translator (Google Translate backend).
Supports 100+ languages, free, no API key needed.
"""

from deep_translator import GoogleTranslator

# Maximum characters Google Translate accepts per request
_MAX_CHUNK = 4500


def get_supported_languages() -> list[dict]:
    """Return list of {code, name} dicts for all supported languages."""
    langs = GoogleTranslator().get_supported_languages(as_dict=True)
    # langs is {name: code} — flip to list of dicts
    return [
        {"code": code, "name": name.title()}
        for name, code in sorted(langs.items())
    ]


def translate_text(text: str, target: str, source: str = "auto") -> dict:
    """
    Translate text to the target language.

    Args:
        text:   The text to translate.
        target: ISO-639-1 target language code (e.g. "en", "fr", "ar").
        source: ISO-639-1 source language code, or "auto" for auto-detect.

    Returns:
        {"translated_text": str, "source": str, "target": str}
    """
    if not text or not text.strip():
        return {"translated_text": "", "source": source, "target": target}

    src = source if source and source != "auto" else "auto"

    # Split long texts into chunks
    chunks = _split_text(text, _MAX_CHUNK)
    translated_chunks = []

    for chunk in chunks:
        translator = GoogleTranslator(source=src, target=target)
        result = translator.translate(chunk)
        translated_chunks.append(result or "")

    return {
        "translated_text": " ".join(translated_chunks),
        "source": src,
        "target": target,
    }


def _split_text(text: str, max_len: int) -> list[str]:
    """Split text into chunks at sentence boundaries."""
    if len(text) <= max_len:
        return [text]

    chunks = []
    current = ""
    # Split on sentence-ending punctuation
    sentences = text.replace(". ", ".\n").replace("? ", "?\n").replace("! ", "!\n").split("\n")

    for sentence in sentences:
        if len(current) + len(sentence) + 1 > max_len:
            if current:
                chunks.append(current.strip())
            current = sentence
        else:
            current = current + " " + sentence if current else sentence

    if current.strip():
        chunks.append(current.strip())

    return chunks if chunks else [text[:max_len]]
