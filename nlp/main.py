from pathlib import Path

try:
    from .processor import process_and_generate_pdf
except ImportError:
    from processor import process_and_generate_pdf


BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = BASE_DIR / "Input" / "Meeting.txt"
OUTPUT_FILE = BASE_DIR / "Output" / "meeting_report.txt"
MEETING_DATE = None


def print_section(title):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def save_report(report):
    """Save the report using the shared processor output writer."""
    try:
        from .processor import save_text_report
    except ImportError:
        from processor import save_text_report
    return save_text_report(report, OUTPUT_FILE)


def display_report(report):
    """
    Display the meeting report in the terminal.
    """

    print_section("MEETING SUMMARY")

    for item in report["summary"]:
        print("-", item)

    print_section("DECISIONS")

    for item in report["decisions"]:
        print("-", item)

    print_section("DISCUSSION POINTS")

    for item in report["discussion"]:
        print("-", item)

    print_section("ACTION ITEMS")

    for item in report["action_items"]:

        print(
            f"Person: {item['person']}"
        )

        print(
            f"Task: {item['task']}"
        )

        print(
            f"Deadline: {item['deadline']}"
            + (
                f" (normalized: {item['date_iso']}; {item['date_basis']})"
                if item.get("date_iso") else ""
            )
        )

        print(
            f"Confidence: {item['confidence']:.2f}"
        )
        print(
            f"Source: {item.get('source_text', item.get('sentence', ''))}"
        )

        print()

    print_section("SCHEDULED FOLLOW-UPS")
    for item in report.get("scheduled_events", []):
        timing = " ".join(
            value for value in (item.get("date"), item.get("time")) if value
        )
        print(f"- {item['title']}: {timing or 'Date not specified'}")

    print_section("DEADLINES")

    for item in report["deadlines"]:
        print("-", item)

    print_section("IMPORTANT DATES / EVENTS")

    for item in report["important_dates"]:
        print("-", item)

    print_section("PEOPLE")

    for person in report["people"]:
        print("-", person)

    print_section("KEYWORDS")

    for keyword in report["keywords"]:
        print("-", keyword)


def main():

    # -----------------------------------------------------
    # TEST INPUT
    # -----------------------------------------------------
    # Currently we read Meeting.txt.
    # Later the STT module will provide this string.
    # -----------------------------------------------------

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        transcript = file.read()

    # -----------------------------------------------------
    # PROCESS TRANSCRIPT
    # -----------------------------------------------------

    report, pdf_file = process_and_generate_pdf(
        transcript,
        meeting_date=MEETING_DATE,
    )

    print(
        "\nMeeting analysis completed!"
    )

    # -----------------------------------------------------
    # DISPLAY REPORT
    # -----------------------------------------------------

    display_report(
        report
    )

    # -----------------------------------------------------
    # SAVE TEXT REPORT
    # -----------------------------------------------------

    save_report(
        report
    )

    print(
        f"\nText report saved to: {OUTPUT_FILE}"
    )

    # -----------------------------------------------------
    # PDF
    # -----------------------------------------------------

    print(
        f"PDF report saved to: {pdf_file}"
    )


if __name__ == "__main__":
    main()