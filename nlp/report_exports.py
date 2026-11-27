"""Export the ASR transcript and NLP report to downloadable document formats."""

from pathlib import Path

from docx import Document


def generate_transcript_docx(transcript, output_path):
    """Create a DOCX containing only the ASR transcript."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    document = Document()
    document.add_heading("TRACE ASR Transcript", 0)
    document.add_paragraph(transcript)
    document.save(output_path)
    return output_path


def generate_docx_report(transcript, processed_report, output_path):
    """Create a DOCX containing both the ASR transcript and NLP report."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    document = Document()
    document.add_heading("TRACE Meeting Report", 0)
    document.add_heading("ASR Transcription", level=1)
    document.add_paragraph(transcript)
    document.add_heading("NLP Processed Report", level=1)

    for line in processed_report.splitlines():
        document.add_paragraph(line)

    document.save(output_path)
    return output_path
