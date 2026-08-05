import json
from pathlib import Path
from datetime import datetime
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    Table, TableStyle, HRFlowable,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER

_BASE_DIR = Path(__file__).resolve().parents[3]


def generate_pdf(
    record:          dict,
    segments:        list,
    cleaned_text:    Optional[str] = None,
    translated_text: Optional[str] = None,
    summary:         Optional[str] = None,
    output_path:     Optional[str] = None,
) -> str:
    """Generate a full PDF report for a transcription."""

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
        fontSize   = 10,
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
    body_style = ParagraphStyle(
        "Body",
        parent    = styles["Normal"],
        fontSize  = 10,
        leading   = 16,
        textColor = colors.HexColor("#333333"),
    )
    speaker_label_style = ParagraphStyle(
        "SpeakerLabel",
        parent   = styles["Normal"],
        fontSize = 10,
        textColor = colors.HexColor("#0066cc"),
        fontName  = "Helvetica-Bold",
    )
    speaker_text_style = ParagraphStyle(
        "SpeakerText",
        parent     = styles["Normal"],
        fontSize   = 10,
        leading    = 15,
        textColor  = colors.HexColor("#333333"),
        leftIndent = 12,
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
    story.append(Paragraph("Transcription Report", subtitle_style))
    story.append(HRFlowable(
        width="100%", thickness=1,
        color=colors.HexColor("#cccccc")
    ))
    story.append(Spacer(1, 0.4 * cm))

    # ── Metadata ──────────────────────────────────────────────
    dur     = record.get("duration_sec") or 0
    m, s    = divmod(int(dur), 60)
    dur_str = f"{m}m {s:02d}s" if m else f"{s}s"

    meta_rows = [
        ["Field",      "Value"],
        ["ID",         str(record.get("id", ""))],
        ["Filename",   str(record.get("filename", ""))],
        ["Language",   str(record.get("language", ""))],
        ["Duration",   dur_str],
        ["File Size",  str(record.get("file_size", ""))],
        ["Model",      str(record.get("model_used", ""))],
        ["Created At", str(record.get("created_at", ""))],
    ]

    meta_table = Table(meta_rows, colWidths=[4 * cm, 13 * cm])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0),  colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR",      (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",       (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",       (0, 0), (-1, 0),  10),
        ("BACKGROUND",     (0, 1), (0, -1),  colors.HexColor("#f0f4ff")),
        ("FONTNAME",       (0, 1), (0, -1),  "Helvetica-Bold"),
        ("FONTSIZE",       (0, 1), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f9f9f9")]),
        ("GRID",           (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
        ("PADDING",        (0, 0), (-1, -1), 6),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 0.4 * cm))

    # ── Summary ───────────────────────────────────────────────
    if summary:
        story.append(Paragraph("Summary", section_style))
        story.append(HRFlowable(
            width="100%", thickness=0.5,
            color=colors.HexColor("#cccccc")
        ))
        story.append(Spacer(1, 0.2 * cm))
        story.append(Paragraph(
            summary.replace("\n", "<br/>"), body_style
        ))

    # ── Original transcription ────────────────────────────────
    story.append(Paragraph("Original Transcription", section_style))
    story.append(HRFlowable(
        width="100%", thickness=0.5,
        color=colors.HexColor("#cccccc")
    ))
    story.append(Spacer(1, 0.2 * cm))
    original = record.get("transcription", "") or ""
    story.append(Paragraph(original.replace("\n", "<br/>"), body_style))

    # ── Cleaned text ──────────────────────────────────────────
    if cleaned_text:
        story.append(Paragraph("Cleaned Text", section_style))
        story.append(HRFlowable(
            width="100%", thickness=0.5,
            color=colors.HexColor("#cccccc")
        ))
        story.append(Spacer(1, 0.2 * cm))
        story.append(Paragraph(
            cleaned_text.replace("\n", "<br/>"), body_style
        ))

    # ── Translation ───────────────────────────────────────────
    if translated_text:
        story.append(Paragraph("Translation", section_style))
        story.append(HRFlowable(
            width="100%", thickness=0.5,
            color=colors.HexColor("#cccccc")
        ))
        story.append(Spacer(1, 0.2 * cm))
        story.append(Paragraph(
            translated_text.replace("\n", "<br/>"), body_style
        ))

    # ── Speaker segments ──────────────────────────────────────
    if segments:
        story.append(Paragraph("Speaker Segments", section_style))
        story.append(HRFlowable(
            width="100%", thickness=0.5,
            color=colors.HexColor("#cccccc")
        ))
        story.append(Spacer(1, 0.2 * cm))

        for seg in segments:
            start   = seg.get("start", 0) or 0
            end     = seg.get("end",   0) or 0
            speaker = seg.get("speaker", "Speaker")
            text    = seg.get("text",   "")

            m_s, s_s = divmod(int(start), 60)
            m_e, s_e = divmod(int(end),   60)
            ts_str   = f"[{m_s:02d}:{s_s:02d} → {m_e:02d}:{s_e:02d}]"

            story.append(Paragraph(
                f'<font color="#0066cc"><b>{speaker}</b></font> '
                f'<font color="#999999" size="8">{ts_str}</font>',
                speaker_label_style,
            ))
            story.append(Paragraph(text, speaker_text_style))
            story.append(Spacer(1, 0.12 * cm))

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
