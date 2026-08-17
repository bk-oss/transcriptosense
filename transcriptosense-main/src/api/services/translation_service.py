"""
Translation service using deep-translator (Google Translate backend).
Supports 100+ languages, free, no API key needed.
✅ Preserves "Speaker X:" diarization structure across all engines.
"""

import os
import re
import httpx
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Optional

from deep_translator import GoogleTranslator, LibreTranslator

# Ollama local API
_OLLAMA_TAGS = "http://localhost:11434/api/tags"
_OLLAMA_GEN = "http://localhost:11434/api/generate"
_OLLAMA_MODEL = "mistral:latest"
_OLLAMA_TIMEOUT = 30.0

# Maximum characters Google Translate accepts per request
_MAX_CHUNK = 4500

# Hard timeout for the Google Translate call.
_GOOGLE_TIMEOUT = 8.0

_executor = ThreadPoolExecutor(max_workers=4)

_GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
_GROQ_MODEL = "llama-3.3-70b-versatile"
_GROQ_TIMEOUT = 15.0

# ✅ Matches lines like "Speaker 1: some text"
_SPEAKER_LINE_RE = re.compile(r"^(Speaker\s+\d+)\s*:\s*(.*)$", re.IGNORECASE)


def _groq_translate(chunk: str, target: str) -> Optional[str]:
    """Translate a plain text chunk (no speaker labels) via Groq."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return None

    prompt = (
        f"Translate the following text into {target}. "
        "Return ONLY the translated text, with no explanation, no quotes, "
        "and no preamble.\n\n"
        f"Text:\n{chunk}"
    )

    with httpx.Client(timeout=_GROQ_TIMEOUT) as client:
        resp = client.post(
            _GROQ_CHAT_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": _GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return content.strip() if content else None

def _is_valid_translation(original: str, translated: str) -> bool:
    """Strictly verify that the translation is not identical to the source text."""
    if not translated:
        return False
    # If it's very short (like "Ok", "Yes"), it might naturally be identical or not translatable easily
    # But for anything substantial, they shouldn't match exactly.
    orig_clean = original.strip().lower()
    trans_clean = translated.strip().lower()
    if len(orig_clean) > 3 and orig_clean == trans_clean:
        return False
    return True


def get_supported_languages() -> list[dict]:
    """Return list of {code, name} dicts for all supported languages."""
    langs = GoogleTranslator().get_supported_languages(as_dict=True)
    return [
        {"code": code, "name": name.title()}
        for name, code in sorted(langs.items())
    ]


def _google_translate_with_timeout(chunk: str, src: str, target: str, timeout: float = _GOOGLE_TIMEOUT) -> str:
    """Run GoogleTranslator().translate() in a worker thread and enforce a real timeout."""
    def _do():
        translator = GoogleTranslator(source=src, target=target)
        return translator.translate(chunk)

    future = _executor.submit(_do)
    try:
        result = future.result(timeout=timeout)
        if not result:
            raise RuntimeError("Google Translate returned an empty result")
        return result
    except FutureTimeoutError:
        raise RuntimeError(f"Google Translate timed out after {timeout}s (check network/SSL interception)")


def _translate_chunk(chunk: str, target: str, src: str) -> tuple[str, Optional[str], list[str]]:
    """
    Run the full multi-engine fallback pipeline on a SINGLE plain text chunk
    (no speaker labels, no line breaks expected).

    Returns (translated_text, engine_used, errors).
    """
    chunk_errors: list[str] = []
    translated = None
    engine_used = None

    libre_api_key = os.environ.get("LIBRE_API_KEY")
    libre_urls = [
        "https://translate.argosopentech.com",
        "https://libretranslate.de",
        "https://libretranslate.com",
    ]

    # 1) Groq (primary)
    try:
        res = _groq_translate(chunk, target)
        if _is_valid_translation(chunk, res):
            translated = res
            engine_used = "groq"
    except Exception as e_groq:
        chunk_errors.append(f"groq: {e_groq}")

    # 2) Ollama local model, if available
    if translated is None and not os.environ.get("OLLAMA_DISABLED"):
        try:
            with httpx.Client(timeout=2.0, verify=False) as client:
                resp = client.get(_OLLAMA_TAGS)
                if resp.status_code == 200:
                    data = resp.json()
                    models = {item.get("name") for item in data.get("models", []) if isinstance(item, dict)}
                    if _OLLAMA_MODEL in models:
                        prompt = (
                            "You are a professional translator.\n"
                            f"Translate the following text to {target}.\n"
                            "Return ONLY the translated text, nothing else.\n\n"
                            f"Text:\n{chunk}"
                        )
                        gen = client.post(
                            _OLLAMA_GEN,
                            json={"model": _OLLAMA_MODEL, "prompt": prompt, "stream": False},
                            timeout=_OLLAMA_TIMEOUT,
                        )
                        gen.raise_for_status()
                        res = gen.json().get("response")
                        if _is_valid_translation(chunk, res):
                            translated = res.strip()
                            engine_used = "ollama"
        except Exception as e_ollama:
            chunk_errors.append(f"ollama: {e_ollama}")

    # 3) Argos Translate (offline), if installed
    if translated is None:
        try:
            import argostranslate.translate
            from_code = "en" if src == "auto" else src
            try:
                res = argostranslate.translate.translate(chunk, from_code, target)
                if _is_valid_translation(chunk, res):
                    translated = res
                    engine_used = "argos"
            except Exception as e_argos:
                chunk_errors.append(f"argos: {e_argos}")
        except ImportError:
            pass

    # 4) Google Translate, with timeout
    if translated is None:
        try:
            res = _google_translate_with_timeout(chunk, src, target)
            if _is_valid_translation(chunk, res):
                translated = res
                engine_used = "google"
        except Exception as e_google:
            chunk_errors.append(f"google: {e_google}")

    # 5) LibreTranslate fallback
    if translated is None and libre_api_key:
        for url in libre_urls:
            try:
                libre = LibreTranslator(
                    source=src if src != "auto" else "auto",
                    target=target,
                    base_url=url,
                    api_key=libre_api_key,
                )
                res = libre.translate(chunk)
                if _is_valid_translation(chunk, res):
                    translated = res
                    engine_used = f"libre:{url}"
                    break
            except Exception as e_libre:
                chunk_errors.append(f"libre({url}): {e_libre}")

    if translated is None:
        translated = chunk  # every backend failed — return original untouched
        print(f"[Translate] WARNING: All engines failed for chunk. Target={target}. Errors={chunk_errors}")
    else:
        print(f"[Translate] target={target} engine={engine_used} success=True")

    return translated, engine_used, chunk_errors


def translate_text(text: str, target: str, source: str = "auto") -> dict:
    """
    Translate text to the target language.

    ✅ If the text is diarized (contains "Speaker N:" lines), each speaker
       turn is translated independently and the "Speaker N:" labels are
       preserved exactly, with one turn per line in the output.

    Returns:
        {
            "translated_text": str,
            "source": str,
            "target": str,
            "success": bool,
            "engine": str | None,
            "errors": list[str],
        }
    """
    if not text or not text.strip():
        return {"translated_text": "", "source": source, "target": target, "success": True, "engine": None, "errors": []}

    src = source if source and source != "auto" else "auto"

    lines = text.split("\n")
    non_empty_lines = [ln for ln in lines if ln.strip()]
    is_diarized = bool(non_empty_lines) and all(
        _SPEAKER_LINE_RE.match(ln.strip()) for ln in non_empty_lines
    )

    all_errors: list[str] = []
    engine_used = None
    overall_success = True

    if is_diarized:
        # ✅ Translate each speaker turn independently, preserving labels
        translated_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                translated_lines.append("")
                continue

            match = _SPEAKER_LINE_RE.match(stripped)
            speaker_label = match.group(1)
            spoken_text = match.group(2)

            if not spoken_text.strip():
                translated_lines.append(f"{speaker_label}:")
                continue

            translated, engine, errors = _translate_chunk(spoken_text, target, src)
            engine_used = engine_used or engine
            all_errors.extend(errors)
            if translated == spoken_text and errors:
                overall_success = False

            translated_lines.append(f"{speaker_label}: {translated}")

        final_text = "\n".join(translated_lines)

    else:
        # ── Plain text (no diarization) — original chunk-by-size behaviour ──
        chunks = _split_text(text, _MAX_CHUNK)
        translated_chunks = []

        for chunk in chunks:
            translated, engine, errors = _translate_chunk(chunk, target, src)
            engine_used = engine_used or engine
            all_errors.extend(errors)
            if translated == chunk and errors:
                overall_success = False
            translated_chunks.append(translated)

        final_text = " ".join(translated_chunks)

    return {
        "translated_text": final_text,
        "source": src,
        "target": target,
        "success": overall_success,
        "engine": engine_used,
        "errors": all_errors,
    }


def _split_text(text: str, max_len: int) -> list[str]:
    """Split plain (non-diarized) text into chunks at sentence boundaries."""
    if len(text) <= max_len:
        return [text]

    chunks = []
    current = ""
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
