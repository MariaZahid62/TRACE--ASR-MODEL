"""Single entry point for processing transcripts into TRACE meeting reports."""

from pathlib import Path

try:
    from .analyzer import analyze_meeting
    from .pdf_report import generate_pdf
except ImportError:  # Support running main.py directly from this folder.
    from analyzer import analyze_meeting
    from pdf_report import generate_pdf


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "Output"
TEXT_REPORT_FILE = OUTPUT_DIR / "meeting_report.txt"


def _empty_report():
    """Return the complete report structure for an empty transcript."""
    return {
        "summary": [],
        "decisions": [],
        "discussion": [],
        "action_items": [],
        "deadlines": [],
        "important_dates": [],
        "people": [],
        "keywords": [],
        "scheduled_events": [],
        "summary_evidence": [],
        "decision_evidence": [],
        "discussion_evidence": [],
    }


def process_transcript(transcript, meeting_date=None):
    """Analyze transcript text received directly from the TRACE ASR module."""
    if not isinstance(transcript, str) or not transcript.strip():
        return {
            key: []
            for key in (
                "summary", "decisions", "discussion", "action_items",
                "deadlines", "important_dates", "people", "keywords",
                "scheduled_events", "summary_evidence",
                "decision_evidence", "discussion_evidence",
            )
        }

    return analyze_meeting(transcript, meeting_date=meeting_date)


def save_text_report(report, output_path=TEXT_REPORT_FILE):
    """Save the structured meeting report as a readable text file."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        file.write("TRACE - MEETING REPORT\n")
        file.write("=" * 60 + "\n\n")

        sections = [
            ("SUMMARY", "summary"),
            ("DECISIONS", "decisions"),
            ("DISCUSSION POINTS", "discussion"),
        ]
        for heading, key in sections:
            file.write(f"{heading}\n" + "-" * 60 + "\n")
            for item in report.get(key, []):
                file.write(f"- {item}\n")
            file.write("\n")

        file.write("ACTION ITEMS\n" + "-" * 60 + "\n")
        for item in report.get("action_items", []):
            file.write(f"Person: {item.get('person', 'Unknown')}\n")
            file.write(f"Task: {item.get('task', '')}\n")
            file.write(f"Deadline: {item.get('deadline', 'Not specified')}\n")
            file.write(f"Confidence: {item.get('confidence', 0):.2f}\n")
            file.write(f"Source: {item.get('source_text', item.get('sentence', ''))}\n\n")

        for heading, key in [
            ("SCHEDULED FOLLOW-UPS", "scheduled_events"),
            ("DEADLINES", "deadlines"),
            ("IMPORTANT DATES / EVENTS", "important_dates"),
            ("PEOPLE", "people"),
            ("KEYWORDS", "keywords"),
        ]:
            file.write(f"{heading}\n" + "-" * 60 + "\n")
            for item in report.get(key, []):
                if isinstance(item, dict):
                    timing = " ".join(
                        value for value in (item.get("date"), item.get("time")) if value
                    )
                    file.write(f"- {item.get('title', 'Follow-up')}: {timing or 'Date not specified'}\n")
                    file.write(f"  Source: {item.get('source_text', '')}\n")
                else:
                    file.write(f"- {item}\n")
            file.write("\n")

    return output_path


def process_and_generate_pdf(transcript, meeting_date=None, pdf_output_path=None):
    """Run the NLP stage and generate its PDF report.

    Returns:
        report: structured meeting report
        pdf_file: path to generated PDF
    """
    report = process_transcript(transcript, meeting_date=meeting_date)
    save_text_report(report)
    pdf_file = generate_pdf(
        report,
        transcript=transcript,
        output_path=pdf_output_path,
    )
    return report, pdf_file
