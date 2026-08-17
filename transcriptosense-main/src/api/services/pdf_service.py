import json
import re
from pathlib import Path
from datetime import datetime
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
)
from reportlab.lib.enums import TA_CENTER

_BASE_DIR = Path(__file__).resolve().parents[3]

# ✅ Matches lines like "Speaker 1: some text"
_SPEAKER_LINE_RE = re.compile(r"^(Speaker\s+\d+)\s*:\s*(.*)$", re.IGNORECASE)


def _render_diarized_flowables(text: str, speaker_style, plain_style) -> list:
    """
    Render text as a list of PDF flowables, one per line.
    Lines matching "Speaker N: ..." get a bold, colored speaker label.
    Plain lines (no diarization) are rendered as normal paragraphs.
    """
    flowables = []
    if not text:
        return flowables

    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue

        match = _SPEAKER_LINE_RE.match(stripped)
        if match:
            speaker_label = match.group(1)
            spoken_text   = match.group(2)
            flowables.append(Paragraph(
                f'<font color="#0066cc"><b>{speaker_label}:</b></font> {spoken_text}',
                speaker_style,
            ))
            flowables.append(Spacer(1, 0.12 * cm))
        else:
            flowables.append(Paragraph(stripped, plain_style))
            flowables.append(Spacer(1, 0.12 * cm))

    return flowables


def _build_diarized_text_from_segments(segments: list) -> str:
    """Fallback: rebuild 'Speaker N: text' lines from a segments list."""
    if not segments:
        return ""

    lines = []
    for seg in segments:
        speaker = seg.get("speaker", "1")
        text    = (seg.get("text") or "").strip()
        if text:
            lines.append(f"Speaker {speaker}: {text}")
    return "\n".join(lines)


def generate_pdf(
    record:          dict,
    segments:        list,
    cleaned_text:    Optional[str] = None,
    translated_text: Optional[str] = None,
    summary:         Optional[str] = None,
    output_path:     Optional[str] = None,
) -> str:
    """
    Generate a focused PDF report containing only:
      1. The diarized transcription (Speaker 1 / Speaker 2 ... format)
      2. The translation (if provided), with speaker labels preserved
    """

    # ✅ If segments is a JSON string, parse it
    if isinstance(segments, str):
        try:
            segments = json.loads(segments)
        except Exception:
            segments = []

    if not output_path:
        output_dir = _BASE_DIR / "data" / "reports"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(
            output_dir / f"report_{record['id']}_{record['filename']}.pdf"
        )

    print(f"[PDF] Generating: {output_path}")

    doc    = SimpleDocTemplate(
        output_path,
        pagesize     = A4,
        rightMargin  = 2 * cm,
        leftMargin   = 2 * cm,
        topMargin    = 2 * cm,
        bottomMargin = 2 * cm,
    )
    styles = getSampleStyleSheet()
    story  = []

    # ── Styles ─────────────────────────────────────────────────
    title_style = ParagraphStyle(
        "CustomTitle",
        parent     = styles["Title"],
        fontSize   = 22,
        textColor  = colors.HexColor("#1a1a2e"),
        alignment  = TA_CENTER,
        spaceAfter = 4,
    )
    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent     = styles["Normal"],
        fontSize   = 9,
        textColor  = colors.HexColor("#666666"),
        alignment  = TA_CENTER,
        spaceAfter = 16,
    )
    section_style = ParagraphStyle(
        "Section",
        parent      = styles["Heading2"],
        fontSize    = 13,
        textColor   = colors.HexColor("#1a1a2e"),
        spaceBefore = 14,
        spaceAfter  = 6,
    )
    speaker_style = ParagraphStyle(
        "SpeakerLine",
        parent     = styles["Normal"],
        fontSize   = 10,
        leading    = 15,
        textColor  = colors.HexColor("#333333"),
        leftIndent = 6,
    )
    plain_style = ParagraphStyle(
        "PlainLine",
        parent    = styles["Normal"],
        fontSize  = 10,
        leading   = 15,
        textColor = colors.HexColor("#333333"),
    )
    footer_style = ParagraphStyle(
        "Footer",
        parent    = styles["Normal"],
        fontSize  = 8,
        textColor = colors.grey,
        alignment = TA_CENTER,
    )

    # ── Header ────────────────────────────────────────────────
    story.append(Paragraph("TranscriptoSense", title_style))
    filename = record.get("filename", "")
    language = record.get("language", "")
    story.append(Paragraph(f"{filename} — {language}", subtitle_style))
    story.append(HRFlowable(
        width="100%", thickness=1,
        color=colors.HexColor("#cccccc")
    ))
    story.append(Spacer(1, 0.4 * cm))

    # ── Original Transcription (diarized) ───────────────────────
    diarized_text = (
        record.get("diarized_text")
        or _build_diarized_text_from_segments(segments)
        or record.get("transcription", "")
        or ""
    )

    story.append(Paragraph("Original Transcription", section_style))
    story.append(HRFlowable(
        width="100%", thickness=0.5,
        color=colors.HexColor("#cccccc")
    ))
    story.append(Spacer(1, 0.2 * cm))
    story.extend(_render_diarized_flowables(diarized_text, speaker_style, plain_style))

    # ── Translation ───────────────────────────────────────────
    if translated_text:
        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph("Translation", section_style))
        story.append(HRFlowable(
            width="100%", thickness=0.5,
            color=colors.HexColor("#cccccc")
        ))
        story.append(Spacer(1, 0.2 * cm))
        story.extend(_render_diarized_flowables(translated_text, speaker_style, plain_style))

    # ── Footer ────────────────────────────────────────────────
    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(
        width="100%", thickness=0.5,
        color=colors.HexColor("#cccccc")
    ))
    story.append(Paragraph(
        f"Generated by TranscriptoSense — "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        footer_style,
    ))

    doc.build(story)
    print(f"[PDF] Done: {output_path}")
    return output_path
