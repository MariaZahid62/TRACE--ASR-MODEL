# TRACE NLP — Test Inputs, Reference Outputs, and Components

These are the three paired transcript examples included with the project. The
normal application does **not** process them automatically. To run one, copy its
transcript into `Input/Meeting.txt` and run `python main.py`. The corresponding
`Test_output` file is the bundled reference output from the project archive.

## Test 1 — Formal recruitment policy meeting

- Input: `Test_input/meeting1.txt`
- Reference output: `Test_output/meeting1_report.txt`
- Transcript characteristics: formal meeting, policy proposal, unanimous amendment,
  approval vote, effective date, implementation deadline, and assigned minutes/policy
  circulation.
- Recorded output includes: recruitment-policy summary; unanimous approval of the
  technical-assessment amendment; policy approval with four votes and one abstention;
  December 1st implementation; November 25th documentation deadline; named people;
  and action items for Susan and Elizabeth.
- Notable gap in the recorded output: the `DISCUSSION` section says no items detected,
  although the transcript contains discussion. Some follow-up/ownership details are
  also represented as `Unknown`.

## Test 2 — Application launch and development meeting

- Input: `Test_input/meeting2.txt`
- Reference output: `Test_output/meeting2_report.txt`
- Transcript characteristics: multiple named owners, design and payment integration,
  backend work, password-reset bug, QA schedule, marketing campaign, client demo,
  launch date, and several deadlines.
- Recorded output includes: decisions on campaign preparation, testing dates,
  correction window, and target launch; people Daniel, Zara, Hamza, Chris, and Olivia;
  dates from November 4th through November 27th; and multiple action items.
- Notable gaps in the recorded output: some actions have `Unknown` owners; some
  recap assignments are not fully captured; some discussion lines remain in the
  discussion section even when they are recap/action statements.

## Test 3 — Informal office environment discussion

- Input: `Test_input/meeting3.txt`
- Reference output: `Test_output/meeting3_report.txt`
- Transcript characteristics: informal conversation, cafeteria crowding, staggered
  lunch-break suggestion, meeting-room booking issues, reminders, and team activities.
- Recorded output includes: office-environment summary, discussion topics, named
  participants, and keywords.
- Recorded output correctly has no deadlines or action items in this sample.
  It also has no formal decisions, because the suggestions are discussed but not
  explicitly approved in the supplied transcript.

## Components involved

| Component | Role in the single path |
|---|---|
| `main.py` | Reads `Input/Meeting.txt`; starts one report run |
| `processor.py` | Calls the analyzer and PDF generator |
| `analyzer.py` | Extracts report sections from the transcript |
| `preprocessing.py` | Lightweight text cleaning used by the analyzer |
| `pdf_report.py` | Formats the same report as a PDF |
| `Output/meeting_report.txt` | Final text report |
| `Output/TRACE_Meeting_Report.pdf` | Final PDF report |
| `test_core.py` | Automated regression tests; not part of normal report generation |

## Important distinction

The bundled reference outputs are not a guarantee that every test will produce
perfect extraction. They document the outputs included in this project archive.
Use them to compare later changes and fix extraction errors. Do not treat the
generated report as verified ground truth without checking it against the source
transcript.
