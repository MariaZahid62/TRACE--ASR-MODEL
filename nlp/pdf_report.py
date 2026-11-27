from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak
)


BASE_DIR = Path(__file__).resolve().parent

PDF_FILE = BASE_DIR / "Output" / "TRACE_Meeting_Report.pdf"


# =========================================================
# PDF STYLES
# =========================================================

styles = getSampleStyleSheet()

title_style = ParagraphStyle(
    "TRACE_Title",
    parent=styles["Title"],
    alignment=TA_CENTER,
    fontSize=22,
    spaceAfter=10
)

subtitle_style = ParagraphStyle(
    "TRACE_Subtitle",
    parent=styles["Normal"],
    alignment=TA_CENTER,
    fontSize=10,
    spaceAfter=20
)

section_style = ParagraphStyle(
    "TRACE_Section",
    parent=styles["Heading2"],
    fontSize=14,
    spaceBefore=12,
    spaceAfter=8
)

body_style = ParagraphStyle(
    "TRACE_Body",
    parent=styles["BodyText"],
    fontSize=10,
    leading=14,
    spaceAfter=5
)

small_style = ParagraphStyle(
    "TRACE_Small",
    parent=styles["BodyText"],
    fontSize=8,
    leading=10
)


# =========================================================
# PAGE HEADER / FOOTER
# =========================================================

def add_page_number(canvas, document):
    """
    Add TRACE footer and page number.
    """

    canvas.saveState()

    canvas.setFont(
        "Helvetica",
        8
    )

    canvas.drawString(
        40,
        25,
        "TRACE - Smart Meeting AI"
    )

    canvas.drawRightString(
        A4[0] - 40,
        25,
        f"Page {document.page}"
    )

    canvas.restoreState()


def generate_transcript_pdf(transcript, output_path):
    """Create a PDF containing only the ASR transcript."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )
    story = [
        Paragraph("TRACE ASR Transcript", title_style),
        Paragraph(
            escape(transcript).replace("\n", "<br/>"),
            body_style,
        ),
    ]
    document.build(
        story,
        onFirstPage=add_page_number,
        onLaterPages=add_page_number,
    )
    return output_path


# =========================================================
# BULLET SECTION
# =========================================================

def add_bullet_section(
    story,
    title,
    items,
    evidence=None,
):
    """
    Add a section containing bullet points.
    """

    story.append(
        Paragraph(
            title,
            section_style
        )
    )

    if not items:

        story.append(
            Paragraph(
                "No information detected.",
                body_style
            )
        )

        return

    for item in items:
        source_text = ""
        if evidence:
            match = next(
                (
                    entry for entry in evidence
                        if entry.get("summary", entry.get("decision", entry.get("discussion"))) == item
                ),
                None,
            )
            if match:
                sources = match.get("source_text", [])
                if sources:
                    source_text = (
                        "<br/><font size='7'>Evidence: "
                        + escape(" | ".join(sources))
                        + "</font>"
                    )
        story.append(
            Paragraph(
                f"• {escape(str(item))}{source_text}",
                body_style
            )
        )


# =========================================================
# ACTION ITEM TABLE
# =========================================================

def add_action_items(
    story,
    action_items
):
    """
    Add action items as a table.
    """

    story.append(
        Paragraph(
            "ACTION ITEMS",
            section_style
        )
    )

    if not action_items:

        story.append(
            Paragraph(
                "No action items detected.",
                body_style
            )
        )

        return

    data = [
        [
            "Person",
            "Task",
            "Deadline",
            "Confidence"
        ]
    ]

    for item in action_items:

        data.append(
            [
                str(item["person"]),
                Paragraph(
                    escape(str(item["task"]))
                    + "<br/><font size='7'>Source: "
                    + escape(str(item.get("source_text", item.get("sentence", ""))))
                    + "</font>",
                    body_style,
                ),
                str(item["deadline"])
                + (
                    f"<br/>{item['date_iso']} ({item['date_basis']})"
                    if item.get("date_iso") else ""
                ),
                f"{item['confidence']:.2f}"
            ]
        )

    table = Table(
        data,
        colWidths=[
            1.25 * inch,
            2.8 * inch,
            1.25 * inch,
            0.85 * inch
        ],
        repeatRows=1
    )

    table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.grey
            ),
            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white
            ),
            (
                "FONTNAME",
                (0, 0),
                (-1, 0),
                "Helvetica-Bold"
            ),
            (
                "FONTSIZE",
                (0, 0),
                (-1, -1),
                8
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "TOP"
            ),
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.grey
            ),
            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                5
            ),
            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                5
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                5
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                5
            )
        ])
    )

    story.append(table)


# =========================================================
# GENERATE PDF
# =========================================================

def generate_pdf(report, transcript=None, output_path=None):
    """
    Generate a TRACE meeting report PDF, optionally including its transcript.
    """

    output_path = Path(output_path) if output_path else PDF_FILE
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    story = []

    # -----------------------------------------------------
    # TITLE
    # -----------------------------------------------------

    story.append(
        Paragraph(
            "TRACE",
            title_style
        )
    )

    story.append(
        Paragraph(
            "Smart Meeting AI",
            subtitle_style
        )
    )

    story.append(
        Paragraph(
            "Automated Meeting Analysis Report",
            subtitle_style
        )
    )

    story.append(
        Spacer(
            1,
            10
        )
    )

    if transcript is not None:
        story.append(Paragraph("ASR TRANSCRIPTION", section_style))
        story.append(
            Paragraph(
                escape(transcript).replace("\n", "<br/>"),
                body_style
            )
        )

    # -----------------------------------------------------
    # SUMMARY
    # -----------------------------------------------------

    add_bullet_section(
        story,
        "MEETING SUMMARY",
        report["summary"],
        report.get("summary_evidence"),
    )

    # -----------------------------------------------------
    # DECISIONS
    # -----------------------------------------------------

    add_bullet_section(
        story,
        "DECISIONS",
        report["decisions"],
        report.get("decision_evidence"),
    )

    # -----------------------------------------------------
    # DISCUSSION
    # -----------------------------------------------------

    add_bullet_section(
        story,
        "DISCUSSION POINTS",
        report["discussion"],
        report.get("discussion_evidence"),
    )

    # -----------------------------------------------------
    # ACTION ITEMS
    # -----------------------------------------------------

    add_action_items(
        story,
        report["action_items"]
    )

    # -----------------------------------------------------
    # DEADLINES
    # -----------------------------------------------------

    add_bullet_section(
        story,
        "DEADLINES",
        report["deadlines"]
    )

    # -----------------------------------------------------
    # IMPORTANT DATES
    # -----------------------------------------------------

    add_bullet_section(
        story,
        "IMPORTANT DATES / EVENTS",
        report["important_dates"]
    )

    add_bullet_section(
        story,
        "SCHEDULED FOLLOW-UPS",
        [
            f"{item['title']}: "
            + " ".join(
                value for value in (item.get("date"), item.get("time")) if value
            )
            + (
                f" ({item['date_iso']}; {item['date_basis']})"
                if item.get("date_iso") else ""
            )
            for item in report.get("scheduled_events", [])
        ],
        [
            {
                "summary": (
                    f"{item['title']}: "
                    + " ".join(
                        value for value in (item.get("date"), item.get("time")) if value
                    )
                    + (
                        f" ({item['date_iso']}; {item['date_basis']})"
                        if item.get("date_iso") else ""
                    )
                ),
                "source_text": [item.get("source_text", "")],
            }
            for item in report.get("scheduled_events", [])
        ],
    )

    # -----------------------------------------------------
    # PEOPLE
    # -----------------------------------------------------

    add_bullet_section(
        story,
        "PEOPLE",
        report["people"]
    )

    # -----------------------------------------------------
    # KEYWORDS
    # -----------------------------------------------------

    add_bullet_section(
        story,
        "KEYWORDS",
        report["keywords"]
    )

    # -----------------------------------------------------
    # BUILD PDF
    # -----------------------------------------------------

    document.build(
        story,
        onFirstPage=add_page_number,
        onLaterPages=add_page_number
    )

    return output_path