import tempfile
import unittest
from pathlib import Path

from analyzer import analyze_meeting, extract_keywords, normalize_transcript
from pdf_report import generate_pdf, generate_transcript_pdf
from processor import process_transcript
from report_exports import generate_docx_report, generate_transcript_docx


BASE_DIR = Path(__file__).resolve().parent


def read_transcript(path):
    return path.read_text(encoding="utf-8")


def find_task(report, phrase):
    return next(
        (
            item for item in report["action_items"]
            if phrase.casefold() in item["task"].casefold()
        ),
        None,
    )


class MeetingAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = analyze_meeting(
            "Emily: The stock count shows discrepancies: 240 units, "
            "but the invoice says 550.\n"
            "Emily: I'm quite sure the microphone is working.\n"
            "We seem to be discussing five different things.\n"
            "Emily: I'll contact the supplier before Friday.\n"
            "Rachel: I'll coordinate that.\n"
            "David: I'll contact IT about the scanner.\n"
            "David: I'll check whether it's working after the meeting.\n"
            "Please update the shared sheet today.\n"
            "Don't approve the payment until the invoice quantity is verified.\n"
            "We decided to finish the urgent items tomorrow."
        )
        cls.samples = {
            path.stem: analyze_meeting(read_transcript(path))
            for path in sorted((BASE_DIR / "Test_input").glob("*.txt"))
        }

    def test_empty_transcript_preserves_report_schema(self):
        expected_keys = {
            "summary", "decisions", "discussion", "action_items",
            "deadlines", "important_dates", "people", "keywords",
            "scheduled_events", "summary_evidence", "decision_evidence",
            "discussion_evidence",
        }
        self.assertEqual(set(analyze_meeting("")), expected_keys)
        self.assertEqual(process_transcript(None), {key: [] for key in expected_keys})

    def test_plain_transcript_api_extracts_decisions_and_owned_tasks(self):
        report = process_transcript(
            "The committee approved the revised policy. "
            "Maria will submit the report by Friday."
        )

        self.assertIn("The committee approved the revised policy.", report["decisions"])
        task = find_task(report, "submit the report")
        self.assertIsNotNone(task)
        self.assertEqual(task["person"], "Maria")
        self.assertEqual(task["deadline"], "Friday")

    def test_timestamped_speaker_labels_preserve_action_ownership(self):
        report = analyze_meeting(
            "[00:00:01] Speaker 1: I will submit the report by Friday.\n"
            "00:00:07 - Participant 2: The committee approved the revised plan.\n"
            "(00:00:12) Speaker 1: I will prepare the meeting notes."
        )

        report_task = find_task(report, "submit the report")
        notes_task = find_task(report, "prepare the meeting notes")
        self.assertEqual(report_task["person"], "Speaker 1")
        self.assertEqual(report_task["deadline"], "Friday")
        self.assertEqual(notes_task["person"], "Speaker 1")
        self.assertIn("Participant 2", report["people"])
        self.assertIn(
            "The committee approved the revised plan.",
            report["decisions"],
        )
        self.assertNotIn("00:00:01", str(report))
        self.assertEqual(
            normalize_transcript("10:00 is the scheduled time."),
            "10:00 is the scheduled time.",
        )

    def test_website_meeting_extracts_decisions_and_merges_recap_actions(self):
        report = analyze_meeting(
            "[00:00:00] Sarah: The main purpose of today's meeting is to "
            "discuss the website redesign and clarify responsibilities.\n"
            "[00:00:00] Emily: I've completed most of the homepage designs, "
            "but I still need to finalize the mobile version.\n"
            "[00:00:10] Sarah: Let's use the existing assets for now. "
            "Let's keep November 20 as our internal review deadline.\n"
            "[00:00:20] John: I'll complete the API endpoints by Friday.\n"
            "[00:00:30] Sarah: John will complete the API endpoints by "
            "Friday, November 13, and investigate the authentication issue "
            "by Thursday, November 12.\n"
            "[00:00:40] Sarah: Emily will finalize desktop and mobile "
            "homepage designs by Wednesday, November 11.\n"
            "[00:00:45] Sarah: David, please have the initial test cases "
            "ready by Thursday.\n"
            "[00:00:50] Sarah: Ahmed will complete the staging environment "
            "by Friday, November 13, and implement the homepage by Monday, "
            "November 16.\n"
            "[00:01:00] Sarah: David will prepare the test cases by Thursday, "
            "November 12, and begin testing on Monday, November 16.\n"
            "[00:01:10] Emily: Design should be done by Wednesday.\n"
            "[00:01:20] Sarah: I'll coordinate with the marketing team and "
            "get the final content by next Tuesday, November 17.\n"
            "[00:01:30] Sarah: I'll coordinate with marketing and collect "
            "the final website content by Tuesday, November 17.\n"
            "[00:01:40] David: I can run the test cases directly on staging "
            "instead of everyone's local machines.\n"
            "[00:01:50] Sarah: Exactly. Let's have a quick progress check on "
            "Thursday afternoon."
            ,
            meeting_date="2026-11-09",
        )

        self.assertIn(
            "Let's use the existing assets for now.",
            report["decisions"],
        )
        self.assertIn(
            "Let's keep November 20 as our internal review deadline.",
            report["decisions"],
        )
        self.assertIn(
            "QA will use the staging environment instead of individual local machines.",
            report["decisions"],
        )
        self.assertFalse(any(
            "directly on staging" in item["source_text"].casefold()
            for item in report["action_items"]
        ))
        self.assertFalse(any(
            "directly on staging" in sentence.casefold()
            for sentence in report["discussion"]
        ))
        mobile_design = find_task(report, "mobile homepage designs")
        self.assertEqual(mobile_design["person"], "Emily")
        self.assertEqual(mobile_design["deadline"], "Wednesday, November 11")
        self.assertFalse(any(item["person"] == "Design" for item in report["action_items"]))

        api_tasks = [
            item for item in report["action_items"]
            if item["person"] == "John" and "API endpoints" in item["task"]
        ]
        self.assertEqual(len(api_tasks), 1)
        self.assertEqual(api_tasks[0]["deadline"], "Friday, November 13")
        authentication_tasks = [
            item for item in report["action_items"]
            if item["person"] == "John" and "investigate" in item["task"]
        ]
        self.assertEqual(len(authentication_tasks), 1)
        self.assertEqual(
            authentication_tasks[0]["deadline"],
            "Thursday, November 12",
        )
        content_tasks = [
            item for item in report["action_items"]
            if item["person"] == "Sarah" and "content" in item["task"]
        ]
        self.assertEqual(len(content_tasks), 1)
        self.assertIn("November 17", content_tasks[0]["deadline"])
        self.assertTrue(any(
            item["person"] == "John"
            and "investigate" in item["task"]
            and item["deadline"] == "Thursday, November 12"
            for item in report["action_items"]
        ))
        self.assertTrue(any(
            item["person"] == "Ahmed"
            and "implement the homepage" in item["task"]
            and item["deadline"] == "Monday, November 16"
            for item in report["action_items"]
        ))
        self.assertTrue(any(
            item["person"] == "David"
            and "begin testing" in item["task"]
            and item["deadline"] == "Monday, November 16"
            for item in report["action_items"]
        ))
        self.assertFalse(any(
            "please have the initial test cases ready" in sentence.lower()
            for sentence in report["discussion"]
        ))
        self.assertIn("Monday, November 16", report["deadlines"])
        self.assertNotIn("this week", report["deadlines"])
        self.assertNotIn("next Tuesday", report["important_dates"])
        self.assertTrue(any("meeting focused on" in line.lower() for line in report["summary"]))
        self.assertTrue(any("backend api integration" in line.lower() for line in report["summary"]))
        self.assertTrue(any("staging for QA" in line for line in report["summary"]))
        self.assertTrue(all(entry["source_text"] for entry in report["summary_evidence"]))
        self.assertTrue(all(entry["source_text"] for entry in report["decision_evidence"]))
        self.assertTrue(any(
            event["title"] == "Project progress check"
            and event["date"] == "Thursday"
            and event["time"] == "afternoon"
            and event["date_iso"] == "2026-11-12"
            for event in report["scheduled_events"]
        ))
        self.assertTrue(all(
            item["source_text"] == item["sentence"]
            for item in report["action_items"]
        ))
        self.assertEqual(
            find_task(report, "finalize desktop and mobile homepage designs")["date_iso"],
            "2026-11-11",
        )

    def test_calendar_resolution_requires_meeting_date_and_rejects_bad_metadata(self):
        report_without_date = analyze_meeting(
            "Maria will submit the report by Friday."
        )
        report_with_date = analyze_meeting(
            "Maria will submit the report by Friday.",
            meeting_date="2026-11-09",
        )

        self.assertIsNone(report_without_date["action_items"][0]["date_iso"])
        self.assertEqual(report_with_date["action_items"][0]["date_iso"], "2026-11-13")
        self.assertEqual(
            report_with_date["action_items"][0]["date_basis"],
            "weekday_from_meeting_date",
        )
        with self.assertRaises(ValueError):
            analyze_meeting("Meeting notes", meeting_date="not-a-date")

    def test_conditional_homepage_commitment_uses_its_own_deadline(self):
        report = analyze_meeting(
            "Emily: I will send the designs by Wednesday.\n"
            "Ahmed: If I receive the designs, I can have the homepage fully "
            "implemented by Monday."
        )

        task = find_task(report, "implement the homepage")
        self.assertIsNotNone(task)
        self.assertEqual(task["person"], "Ahmed")
        self.assertEqual(task["deadline"], "Monday")
        self.assertFalse(any(
            "homepage fully implemented" in sentence.lower()
            for sentence in report["discussion"]
        ))

    def test_keywords_prefer_repeated_topic_phrases(self):
        keywords = extract_keywords(
            "The team reviewed the test cases. The test cases cover login. "
            "The staging environment is ready. QA will use the staging environment."
        )

        self.assertIn("test cases", keywords)
        self.assertIn("staging environment", keywords)

    def test_deadlines_support_explicit_on_and_relative_phrasing(self):
        report = analyze_meeting(
            "Chris, please retest the scanner on November 7th. "
            "The final report must be submitted in two days."
        )

        retest = find_task(report, "retest the scanner")
        report_task = find_task(report, "complete final report")
        self.assertIsNotNone(retest)
        self.assertEqual(retest["deadline"], "November 7th")
        self.assertIsNotNone(report_task)
        self.assertEqual(report_task["deadline"], "in two days")

    def test_report_contains_core_inventory_summary_facts(self):
        summary = " ".join(self.inventory["summary"]).casefold()
        self.assertIn("discrepancies", summary)
        self.assertIn("240 units", summary)
        self.assertIn("invoice says 550", summary)
        self.assertNotIn("microphone", summary)
        self.assertNotIn("quite sure", summary)
        self.assertNotIn("discussing five different things", summary)

    def test_inventory_action_ownership_and_deadlines(self):
        supplier_contact = find_task(self.inventory, "contact the supplier")
        recount = find_task(self.inventory, "coordinate that")
        scanner_followup = find_task(self.inventory, "contact IT")
        scanner_check = find_task(self.inventory, "check whether it's working")
        sheet_update = find_task(self.inventory, "shared sheet")

        self.assertIsNotNone(supplier_contact)
        self.assertEqual(supplier_contact["person"], "Emily")
        self.assertIsNotNone(recount)
        self.assertEqual(recount["person"], "Rachel")
        self.assertIsNotNone(scanner_followup)
        self.assertEqual(scanner_followup["person"], "David")
        self.assertIsNotNone(scanner_check)
        self.assertEqual(scanner_check["deadline"], "after the meeting")
        self.assertIsNotNone(sheet_update)
        self.assertEqual(sheet_update["person"], "Unknown")
        self.assertEqual(sheet_update["deadline"], "today")
        self.assertIn("Friday", self.inventory["deadlines"])
        self.assertNotIn("He", self.inventory["people"])
        self.assertNotIn("jack", self.inventory["keywords"])
        self.assertNotIn("noise", self.inventory["keywords"])
        self.assertNotIn("thought", self.inventory["keywords"])
        self.assertNotIn("friday", self.samples["meeting2"]["keywords"])
        self.assertNotIn("november", self.samples["meeting2"]["keywords"])

    def test_project_transcript_assignments_and_dates(self):
        report = self.samples["meeting2"]

        design = find_task(report, "final checkout design")
        integration = find_task(report, "finish the payment integration")
        backend = find_task(report, "complete remaining backend work")
        retest = find_task(report, "retest it")

        self.assertIsNotNone(design)
        self.assertIsNotNone(integration)
        self.assertIsNotNone(backend)
        self.assertIsNotNone(retest)
        self.assertEqual(design["person"], "Zara")
        self.assertEqual(design["deadline"], "Wednesday, November 4th")
        self.assertEqual(integration["person"], "Hamza")
        self.assertEqual(integration["deadline"], "November 9th")
        self.assertEqual(backend["deadline"], "November 11th")
        self.assertEqual(retest["person"], "Chris")
        self.assertEqual(retest["deadline"], "November 7th")
        self.assertIn("November 7th", report["important_dates"])
        self.assertIn("November 19th and 20th", report["important_dates"])

    def test_decisions_cover_agreements_and_schedule_changes(self):
        inventory_decisions = " ".join(self.inventory["decisions"]).casefold()
        project_decisions = " ".join(self.samples["meeting2"]["decisions"]).casefold()
        formal_decisions = self.samples["meeting1"]["decisions"]

        self.assertIn("payment approval paused", inventory_decisions)
        self.assertIn("finish the urgent items tomorrow", inventory_decisions)
        self.assertIn("november 27th", project_decisions)
        self.assertTrue(any("approved unanimously" in item for item in formal_decisions))
        self.assertEqual(self.samples["meeting3"]["important_dates"], [])

    def test_action_confidence_is_a_bounded_rule_score(self):
        for report in [self.inventory, *self.samples.values()]:
            for item in report["action_items"]:
                self.assertGreaterEqual(item["confidence"], 0.0)
                self.assertLessEqual(item["confidence"], 1.0)

    def test_pdf_escapes_transcript_markup(self):
        report = {
            "summary": ["Research & Development <review>"],
            "decisions": [],
            "discussion": [],
            "action_items": [{
                "person": "A&B",
                "task": "Review <draft>",
                "deadline": "Friday",
                "confidence": 0.8,
            }],
            "deadlines": [],
            "important_dates": [],
            "people": [],
            "keywords": [],
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "report.pdf"
            result = generate_pdf(
                report,
                transcript="Transcript & <notes>",
                output_path=output_path,
            )

            self.assertEqual(result, output_path)
            self.assertTrue(output_path.is_file())
            self.assertTrue(output_path.read_bytes().startswith(b"%PDF"))

    def test_docx_export_contains_transcript_and_nlp_report(self):
        from docx import Document

        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "report.docx"
            result = generate_docx_report(
                "The team will meet Friday.",
                "MEETING SUMMARY\n- Prepare the project update.",
                output_path,
            )

            self.assertEqual(result, output_path)
            paragraphs = [paragraph.text for paragraph in Document(output_path).paragraphs]
            self.assertIn("The team will meet Friday.", paragraphs)
            self.assertIn("- Prepare the project update.", paragraphs)

    def test_transcript_only_exports_contain_the_transcript(self):
        from docx import Document

        transcript = "A&B discussed the <draft>."
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            pdf_path = generate_transcript_pdf(
                transcript,
                directory / "transcript.pdf",
            )
            docx_path = generate_transcript_docx(
                transcript,
                directory / "transcript.docx",
            )

            self.assertTrue(pdf_path.read_bytes().startswith(b"%PDF"))
            paragraphs = [paragraph.text for paragraph in Document(docx_path).paragraphs]
            self.assertIn(transcript, paragraphs)


if __name__ == "__main__":
    unittest.main()
