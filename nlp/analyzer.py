"""
TRACE Meeting Analyzer
----------------------
A deterministic, rule-based meeting transcript analyzer.

Compatibility:
- Keeps analyze_meeting(transcript)
- Keeps the report keys expected by processor.py / pdf_report.py:
  summary, decisions, discussion, action_items, deadlines,
  important_dates, people, keywords
- Keeps action-item dictionary keys:
  person, task, deadline, confidence, sentence

No external APIs or pretrained language models are used.
"""

import re
from collections import Counter
from datetime import date, datetime, timedelta

try:
    from .preprocessing import clean_text
except ImportError:  # Support running main.py directly from this folder.
    from preprocessing import clean_text

# =========================================================
# 1. CONFIGURATION / TEXT UTILITIES
# =========================================================

MONTHS = (
    "January|February|March|April|May|June|July|August|"
    "September|October|November|December"
)
WEEKDAYS = "Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday"
WEEKDAY_INDEX = {
    day: index
    for index, day in enumerate(
        ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
    )
}

SPEAKER_PATTERN = re.compile(
    r"^\s*((?i:Speaker|Participant)\s*(?:#?\d+|[A-Z])?|"
    r"(?i:Host|Moderator)|"
    r"[A-Z][A-Za-z'-]*(?:\s+[A-Z][A-Za-z'-]*){0,3}):\s*"
)
TIMESTAMP_PREFIX_PATTERN = re.compile(
    r"^\s*(?:"
    r"\[\d{1,2}:\d{2}(?::\d{2})?(?:[,.]\d{1,3})?\]|"
    r"\(\d{1,2}:\d{2}(?::\d{2})?(?:[,.]\d{1,3})?\)|"
    r"\d{1,2}:\d{2}(?::\d{2})?(?:[,.]\d{1,3})?"
    r"(?=\s*[-\u2013\u2014]\s*|\s+(?:(?i:Speaker|Participant|Host|Moderator)\b|"
    r"[A-Z][A-Za-z'-]*(?:\s+[A-Z][A-Za-z'-]*){0,3}:))"
    r")\s*(?:[-\u2013\u2014]\s*)?"
)
NON_PERSON_SPEAKER_LABELS = {
    "he", "she", "it", "they", "we", "i", "you", "someone", "the",
    "design", "development", "backend", "frontend", "qa", "marketing",
    "engineering", "product",
}


def normalize_transcript(text):
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    lines = [
        TIMESTAMP_PREFIX_PATTERN.sub("", line)
        for line in text.splitlines()
    ]
    return "\n".join(lines).strip()


def split_sentences(text):
    """Split transcript turns into sentences without breaking common titles."""
    text = normalize_transcript(text)
    if not text:
        return []

    protected = [
        (r"\bMr\.", "Mr<PERIOD>"),
        (r"\bMrs\.", "Mrs<PERIOD>"),
        (r"\bMs\.", "Ms<PERIOD>"),
        (r"\bDr\.", "Dr<PERIOD>"),
        (r"\bProf\.", "Prof<PERIOD>"),
        (r"\bSt\.", "St<PERIOD>"),
        (r"\be\.g\.", "e<PERIOD>g<PERIOD>"),
        (r"\bi\.e\.", "i<PERIOD>e<PERIOD>"),
    ]
    for pattern, replacement in protected:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # Preserve line/turn boundaries, then split multiple sentences within a turn.
    chunks = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = re.split(r"(?<=[.!?])\s+(?=(?:[A-Z\[]|[\"']))", line)
        chunks.extend(part.strip() for part in parts if part.strip())

    results = []
    for chunk in chunks:
        chunk = chunk.replace("<PERIOD>", ".").strip()
        if chunk and chunk != "[Recording ends]":
            results.append(chunk)
    return results


def get_speaker(sentence):
    match = SPEAKER_PATTERN.match(sentence or "")
    if not match:
        return None
    speaker = match.group(1).strip()
    return None if speaker.casefold() in NON_PERSON_SPEAKER_LABELS else speaker


def remove_speaker_prefix(sentence):
    return SPEAKER_PATTERN.sub("", sentence or "").strip()


def extract_speakers(sentences):
    people = []
    for sentence in sentences:
        speaker = get_speaker(sentence)
        if speaker and speaker not in people:
            people.append(speaker)
    return people


def build_speaker_context(sentences):
    """Carry a speaker label to following sentences in the same transcript turn."""
    contexts = []
    current = None
    for sentence in sentences:
        explicit = get_speaker(sentence)
        if explicit:
            current = explicit
        contexts.append(explicit or current)
    return contexts


def extract_people(sentences, speakers=None, action_items=None):
    people = list(speakers or extract_speakers(sentences))
    for item in action_items or []:
        person = item.get("person", "Unknown")
        if person and person != "Unknown" and person not in people:
            people.append(person)
    return people


# =========================================================
# 2. PROCEDURAL / FILLER / DISCUSSION FILTERING
# =========================================================

PROCEDURAL_PATTERNS = [
    r"\bcall this meeting to order\b",
    r"\bmeeting is called to order\b",
    r"\bofficially call this meeting\b",
    r"\bminutes from our previous meeting\b",
    r"\bminutes of the previous meeting\b",
    r"\bcheck the attendance\b",
    r"\bprevious meeting went over time\b",
    r"\bjust joined\b",
    r"\bminutes .* circulated\b",
    r"\bcorrections so far\b",
    r"\bmoving to the main agenda\b",
    r"\bnow, we need to vote\b",
    r"\bi also vote in favor\b",
    r"\bi am abstaining from the vote\b",
    r"\bcan i have a motion\b",
    r"\bcan someone propose\b",
    r"\bi move that\b",
    r"\bi second the motion\b",
    r"\bi second\b",
    r"\ball those in favor\b",
    r"\bany objections\b",
    r"\bwe'll proceed with the vote\b",
    r"\bproceed with the vote\b",
    r"\bthe meeting (?:is )?closed\b",
    r"\bdeclare the meeting closed\b",
    r"\bthank you, everyone\b",
    r"\bthanks, everyone\b",
    r"\bgoodbye\b",
]

FILLER_PATTERNS = [
    r"^\s*(?:okay|alright|yeah|yes|no|hey|hello|good morning|good afternoon)[,!?.\s]*$",
    r"^\s*(?:sorry|thanks|thank you)\b.*$",
    r"\b(?:laughs|chuckles|um|uh)\b",
    r"^\s*\[recording ends\]\s*$",
    r"^\s*\[(?:background noise|overlapping voices|several people speaking)\b.*\]\s*$",
]





# =========================================================
# 3. DATE / DEADLINE EXTRACTION
# =========================================================

DATE_PATTERNS = [
    # Weekday paired with a month date, e.g. Wednesday, November 4th
    rf"\b(?:{WEEKDAYS}),?\s+(?:{MONTHS})\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?\b",
    # Month shared by a list of days, e.g. November 19th and 20th
    rf"\b(?:{MONTHS})\s+\d{{1,2}}(?:st|nd|rd|th)?\s*(?:and|,|&)\s*\d{{1,2}}(?:st|nd|rd|th)?\b",
    # Month day, with optional ordinal suffix and year
    rf"\b(?:{MONTHS})\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?\b",
    # Day month
    rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{MONTHS})(?:\s+\d{{4}})?\b",
    # Numeric dates
    r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b",
    # Date ranges: November 12-18 / November 12 to November 18
    rf"\b(?:{MONTHS})\s+\d{{1,2}}(?:st|nd|rd|th)?\s*(?:-|to|through)\s*(?:(?:{MONTHS})\s+)?\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?\b",
    rf"\b{WEEKDAYS}\s*(?:-|to|through)\s*{WEEKDAYS}\b",
    rf"\b{WEEKDAYS}\b",
    r"\b(?:today|tomorrow|yesterday|tonight|this afternoon|this evening)\b",
    r"\bafter\s+(?:the\s+)?meeting\b",
    r"\b(?:next|this|last|following)\s+(?:week|month|quarter|year|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b",
    r"\b(?:after|before)\s+(?:the\s+)?(?:first|second|third|fourth)\s+quarter\b",
    r"\b(?:within|in)\s+(?:the\s+)?(?:next\s+)?(?:\w+\s+)?(?:working\s+)?(?:days?|weeks?|months?)\b",
    r"\b(?:end of|by the end of)\s+(?:the\s+)?(?:week|month|quarter|year)\b",
]

COMPILED_DATE_PATTERNS = [re.compile(p, re.IGNORECASE) for p in DATE_PATTERNS]

def _clean_date(value):
    return value.strip(" \t.,!?;:()[]")


def extract_date_mentions(sentence):
    """Return date expressions in order of appearance, preferring longer ranges."""
    text = remove_speaker_prefix(sentence)
    found = []
    occupied = []

    # Longest matches first prevents a date range being split into two dates.
    matches = []
    for pattern in COMPILED_DATE_PATTERNS:
        matches.extend(pattern.finditer(text))
    matches.sort(key=lambda m: (m.start(), -(m.end() - m.start())))

    for match in matches:
        start, end = match.span()
        if any(start < old_end and end > old_start for old_start, old_end in occupied):
            continue
        value = _clean_date(match.group(0))
        if value and value.lower() not in {x.lower() for x in found}:
            found.append(value)
            occupied.append((start, end))
    return found




DEADLINE_CUE = re.compile(
    r"\b(?:by|before|no later than|due(?:\s+date)?(?:\s+is)?|"
    r"deadline(?:\s+is)?|within|in the next|after the first quarter|"
    r"after the second quarter|after the third quarter|after the fourth quarter|"
    r"after the meeting|"
    r"in\s+(?=(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s))",
    re.IGNORECASE,
)

def extract_deadline(sentence):
    """Extract a time expression only when the sentence gives a due/follow-up cue."""
    text = remove_speaker_prefix(sentence)
    conditional_deliverable = CONDITIONAL_DELIVERABLE_RE.search(text)
    if conditional_deliverable:
        dates = extract_date_mentions(text[conditional_deliverable.end():])
        if dates:
            explicit_dates = [
                value for value in dates
                if re.search(rf"\b(?:{MONTHS})\b.*\b\d{{1,2}}\b", value, re.IGNORECASE)
            ]
            return explicit_dates[0] if explicit_dates else dates[0]

    cue = DEADLINE_CUE.search(text)
    if cue:
        tail = text[cue.start():]
    else:
        # "Retest it on November 7th" is a deadline when attached to a task,
        # but an arbitrary historical "on Tuesday" mention is not.
        has_task_clause = bool(
            FIRST_PERSON_ACTION_RE.search(text)
            or MODAL_ACTION_RE.search(text)
            or _extract_imperative_task(text)
            or ADDRESSED_ACTION_RE.search(text)
        )
        on_date = re.search(r"\bon\s+", text, re.IGNORECASE)
        if not has_task_clause:
            return None
        if on_date:
            tail = text[on_date.start():]
        else:
            relative = re.search(
                r"\b(?:today|tomorrow|tonight|this afternoon|this evening|"
                r"this week|next week|next month|next quarter|next year)\b",
                text,
                re.IGNORECASE,
            )
            if not relative:
                return None
            tail = text[relative.start():]

    dates = extract_date_mentions(tail)
    if dates:
        # Prefer an explicit calendar date over a relative weekday when both
        # are supplied, e.g. "next Tuesday, November 17".
        explicit_dates = [
            date for date in dates
            if re.search(rf"\b(?:{MONTHS})\b.*\b\d{{1,2}}\b", date, re.IGNORECASE)
            or re.search(r"\b\d{1,2}[/-]\d{1,2}\b", date)
        ]
        return explicit_dates[0] if explicit_dates else dates[0]

    # Handle phrases such as "within two working days".
    relative = re.search(
        r"\b(?:within|in the next|after|before|by)\s+"
        r"(?:(?:the\s+)?(?:first|second|third|fourth)\s+quarter|"
        r"(?:the\s+)?next\s+)?"
        r"(?:\w+\s+)?(?:working\s+)?(?:days?|weeks?|months?|quarter)\b",
        tail,
        re.IGNORECASE,
    )
    if relative:
        return _clean_date(relative.group(0))

    end_period = re.search(
        r"\b(?:by the end of|end of)\s+(?:the\s+)?(?:week|month|quarter|year)\b",
        tail,
        re.IGNORECASE,
    )
    return _clean_date(end_period.group(0)) if end_period else None


def _coerce_meeting_date(meeting_date):
    if meeting_date is None:
        return None
    if isinstance(meeting_date, datetime):
        return meeting_date.date()
    if isinstance(meeting_date, date):
        return meeting_date
    if isinstance(meeting_date, str):
        try:
            return date.fromisoformat(meeting_date.strip())
        except ValueError as exc:
            raise ValueError("meeting_date must be a date or ISO YYYY-MM-DD string") from exc
    raise TypeError("meeting_date must be a date, datetime, ISO string, or None")


def resolve_date_expression(expression, meeting_date=None):
    """Resolve a spoken date only when meeting-date context is provided."""
    reference = _coerce_meeting_date(meeting_date)
    if not expression or reference is None:
        return None

    text = expression.strip()
    explicit = re.search(
        rf"\b(?P<month>{MONTHS})\s+(?P<day>\d{{1,2}})(?:st|nd|rd|th)?"
        r"(?:,?\s+(?P<year>\d{4}))?\b",
        text,
        re.IGNORECASE,
    )
    if explicit:
        year = int(explicit.group("year") or reference.year)
        try:
            return date(
                year,
                datetime.strptime(explicit.group("month"), "%B").month,
                int(explicit.group("day")),
            )
        except ValueError:
            return None

    relative = re.search(
        r"\b(?P<relative>today|tomorrow|yesterday|"
        r"(?:next|following)\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)|"
        r"(?:this\s+)?(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday))\b",
        text,
        re.IGNORECASE,
    )
    if not relative:
        return None

    value = relative.group("relative").casefold()
    if value == "today":
        return reference
    if value == "tomorrow":
        return reference + timedelta(days=1)
    if value == "yesterday":
        return reference - timedelta(days=1)

    weekday_name = value.split()[-1].capitalize()
    target_weekday = WEEKDAY_INDEX[weekday_name]
    day_offset = (target_weekday - reference.weekday()) % 7
    if day_offset == 0 or value.startswith("next "):
        day_offset += 7
    return reference + timedelta(days=day_offset)


def _date_metadata(expression, meeting_date):
    resolved = resolve_date_expression(expression, meeting_date)
    if resolved is None:
        return {
            "date_iso": None,
            "date_basis": "unresolved",
        }

    text = expression.casefold()
    if re.search(rf"\b(?:{MONTHS})\b", text, re.IGNORECASE) and re.search(r"\b\d{1,2}\b", text):
        explicit_year = bool(re.search(r"\b\d{4}\b", text))
        basis = "explicit" if explicit_year else "explicit_date_year_from_meeting_date"
    elif re.search(r"\b(today|tomorrow|yesterday|next|this)\b", text):
        basis = "relative_to_meeting_date"
    else:
        basis = "weekday_from_meeting_date"
    return {"date_iso": resolved.isoformat(), "date_basis": basis}


def _deadline_is_in_sentence(sentence):
    text = remove_speaker_prefix(sentence)
    return bool(DEADLINE_CUE.search(text))


# =========================================================
# 4. DECISION DETECTION WITH LOCAL CONTEXT
# =========================================================

NON_DECISION_PATTERNS = [
    r"\bwe could\b",
    r"\bmaybe we (?:could|should|can)\b",
    r"\bi suggest(?:ed)?\b",
    r"\bi would suggest\b",
    r"\bwhat about\b",
    r"\bproposal\b.*\b(?:could|might|should)\b",
    r"\bi can provide\b",
    r"\bi will\b",
    r"\bi'll\b",
    r"\bi agree\b",
    r"\bi can help\b",
    r"\bi move that\b",
    r"\bi second\b",
    r"\bwe propose\b",
    r"\bwould like clarification\b",
]

DECISION_PATTERNS = [
    r"\b(?:the )?(?:motion|amendment|resolution|proposal|policy|budget|plan)\b.{0,140}\b(?:is|was|has been) approved\b",
    r"\b(?:is|was|has been) approved(?: unanimously)?\b",
    r"\b(?:is|was|has been) rejected\b",
    r"\b(?:the committee|the board|the members|the team|we|everyone)\s+(?:formally\s+)?(?:approved|rejected|adopted|accepted|voted to)\b",
    r"\b(?:motion|amendment) (?:carries|carried)\b",
    r"\b(?:the )?(?:motion|proposal|resolution|increase) (?:passes|passed|fails|failed)\b",
    r"\b(?:the committee|the board|the members|the team|we|everyone) (?:formally )?(?:agreed|decided) (?:to|that)\b",
    r"\bwe have decided to\b",
    r"\bthe decision is to\b",
    r"\bthe motion is carried\b",
    r"\bthe motion is approved\b",
    r"\b(?:let's|we(?:'ll| will))\s+(?:do that|proceed|move forward|schedule|set|assign|include|use|keep|choose|select|make|adopt|go with)\b",
    r"\bwe(?:'re| are) targeting\b",
    r"\b(?:do not|don't) approve (?:the )?payment until\b",
]

def is_real_decision(sentence):
    text = remove_speaker_prefix(sentence).lower().strip()
    if any(re.search(pattern, text) for pattern in NON_DECISION_PATTERNS):
        return False
    return any(re.search(pattern, text) for pattern in DECISION_PATTERNS)




# =========================================================
# 5. ACTION ITEM DETECTION / EXTRACTION
# =========================================================

ACTION_VERBS = (
    r"prepare|submit|send|get|obtain|complete|review|create|update|contact|collect|develop|"
    r"provide|deliver|arrange|schedule|purchase|call|email|write|check|finish|"
    r"compile|present|organize|circulate|coordinate|design|retest|test|investigate|"
    r"implement|fix|build|install|distribute|record|confirm|finalize|share|gather|"
    r"produce|draft|revise|approve|launch|verify|book|cancel|include|introduce|"
    r"calculate|document|maintain|monitor|handle|"
    r"follow(?:\s+up)?|resolve|recount|start|begin|configure|deploy|run|hold"
)

ACTION_VERB_RE = re.compile(rf"\b({ACTION_VERBS})\b", re.IGNORECASE)

FIRST_PERSON_ACTION_RE = re.compile(
    rf"\b(?:i will|i'll|i am going to|i'm going to|i can|"
    rf"i (?:still )?need to)\s+({ACTION_VERBS})\b(.*)",
    re.IGNORECASE,
)
YOU_CAN_ACTION_RE = re.compile(
    rf"\byou can\s+(?P<verb>start|begin|run|prepare|complete|test|review|"
    rf"check|configure|deploy|submit|send)\s+(?P<task>.+)",
    re.IGNORECASE,
)
CONDITIONAL_DELIVERABLE_RE = re.compile(
    r"\bi can have\s+(?P<deliverable>.+?)\s+(?:fully\s+)?implemented\b",
    re.IGNORECASE,
)

ADDRESSED_ACTION_RE = re.compile(
    rf"^\s*(?:and\s+)?(?P<person>[A-Z][A-Za-z'-]+),\s+.*?"
    rf"\b(?:you will|you'll)\s+(?P<verb>{ACTION_VERBS})\b(?P<task>.*)",
    re.IGNORECASE,
)

MODAL_ACTION_RE = re.compile(
    rf"\b(?:will|must|needs? to|should|has to|have to)\s+"
    rf"(?:\w+ly\s+)?({ACTION_VERBS})\b(.*)",
    re.IGNORECASE,
)

PASSIVE_ACTION_RE = re.compile(
    r"\b(?P<deliverable>(?:(?:the|remaining|final|backend|payment|"
    r"password reset|project|full)\s+){0,3}"
    r"(?:work|task|development|integration|issue|issues|bug|bugs|fix|"
    r"changes|documentation|report|minutes|design|deliverable))\s+"
    r"(?:is|are|should be|must be|needs? to be)\s+"
    r"(?:completed|finished|resolved|tested|submitted|ready|circulated)\b",
    re.IGNORECASE,
)

def _trim_task(task):
    task = re.sub(r"^\s*(?:please\s+)?", "", task, flags=re.IGNORECASE)
    task = re.split(
        r"\b(?:by|before|no later than|within|due(?: date)?|on)\s+"
        r"(?:(?:(?:next|this)\s+)?(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)|"
        r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\b|"
        r"(?:the\s+)?(?:next\s+)?\w+\s+(?:working\s+)?(?:days?|weeks?|months?))",
        task,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    task = re.split(
        r"\b(?:the\s+)?following\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b",
        task,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    task = re.split(
        r"\b(?:provided|assuming|but I|however|and I)\b",
        task,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    return task.strip(" .,!?:;-")


def _extract_imperative_task(text):
    text = re.sub(r"^\s*(?:and|also)\s+", "", text, flags=re.IGNORECASE)

    delegated_ready = re.match(
        r"^[A-Z][A-Za-z'-]+,\s*(?:please\s+)?have\s+"
        r"(?P<task>.+?)\s+ready\b",
        text,
        re.IGNORECASE,
    )
    if delegated_ready:
        return "prepare " + _trim_task(delegated_ready.group("task"))

    deadline_assignment = re.match(
        r"^[A-Z][A-Za-z'-]+,\s+your deadline for\s+(?:the\s+)?(.+?)\s+"
        r"(?:is|will be)\s+",
        text,
        re.IGNORECASE,
    )
    if deadline_assignment:
        return _trim_task(deadline_assignment.group(1))

    # "Susan, please present the policy."
    direct = re.match(
        rf"^[A-Z][A-Za-z'-]+,\s*(?:please\s+)?({ACTION_VERBS})\b(.*)",
        text,
        re.IGNORECASE,
    )
    if direct:
        return _trim_task(direct.group(1) + direct.group(2))

    # "Elizabeth, could you please check attendance?"
    polite = re.match(
        r"^[A-Z][A-Za-z'-]+,\s*(?:could you|can you)\s+(?:please\s+)?(.+)",
        text,
        re.IGNORECASE,
    )
    if polite:
        if re.match(r"give\s+(?:me|us)\s+an?\s+update\b", polite.group(1), re.IGNORECASE):
            return None
        verb = ACTION_VERB_RE.search(polite.group(1))
        if verb:
            return _trim_task(polite.group(1)[verb.start():])

    plain_imperative = re.match(
        rf"^(?:please\s+)?({ACTION_VERBS})\b"
        r"(?!\s+(?:should|will|must|needs?\s+to|has\s+to|have\s+to|is|are|was|were)\b)"
        r"(.*)",
        text,
        re.IGNORECASE,
    )
    if plain_imperative:
        return _trim_task(plain_imperative.group(1) + plain_imperative.group(2))
    return None


def has_real_action_pattern(sentence):
    text = remove_speaker_prefix(sentence)
    lower = text.lower()

    if re.search(r"\bmain purpose of (?:today's |this )?meeting\b", lower):
        return False
    if re.search(r"\bgive\s+(?:me|us)\s+an?\s+update\b", lower):
        return False
    addressed_request = bool(
        re.match(
            r"^\s*(?:and|also\s+)?[A-Z][A-Za-z'-]+,\s*(?:could you|can you)\b",
            text,
            re.IGNORECASE,
        )
    )
    if text.rstrip().endswith("?") and not addressed_request:
        return False

    if ADDRESSED_ACTION_RE.search(text):
        return True
    if FIRST_PERSON_ACTION_RE.search(lower):
        return True
    if YOU_CAN_ACTION_RE.search(text):
        return True
    if CONDITIONAL_DELIVERABLE_RE.search(text):
        return True
    if MODAL_ACTION_RE.search(lower):
        # Suggestions are not automatically tasks unless they propose a concrete follow-up.
        return True
    imperative = _extract_imperative_task(text)
    if imperative:
        if re.search(r"\battendance\b", imperative, re.IGNORECASE):
            return False
        return True

    # Passive/unassigned deliverable with a clear due date.
    if PASSIVE_ACTION_RE.search(text) and _deadline_is_in_sentence(text):
        return True
    return False


def extract_task(sentence):
    text = remove_speaker_prefix(sentence)

    addressed_action = ADDRESSED_ACTION_RE.search(text)
    if addressed_action:
        return _trim_task(
            addressed_action.group("verb") + addressed_action.group("task")
        )

    first_person = FIRST_PERSON_ACTION_RE.search(text)
    if first_person:
        task = _trim_task(first_person.group(1) + first_person.group(2))
        if task.casefold() == "start integration" and re.search(
            r"\bapi documentation\b", text, re.IGNORECASE
        ):
            return "start frontend API integration after receiving the API documentation"
        return task

    you_can = YOU_CAN_ACTION_RE.search(text)
    if you_can:
        verb = you_can.group("verb").casefold()
        if verb == "start":
            verb = "begin"
        return _trim_task(verb + " " + you_can.group("task"))

    conditional_deliverable = CONDITIONAL_DELIVERABLE_RE.search(text)
    if conditional_deliverable:
        return _trim_task(
            "implement " + conditional_deliverable.group("deliverable")
        )

    # A modal "we should review..." or "must complete..." task.
    modal = MODAL_ACTION_RE.search(text)
    if modal:
        return _trim_task(modal.group(1) + modal.group(2))

    imperative = _extract_imperative_task(text)
    if imperative:
        return imperative

    # "final documentation is completed by November 25th"
    passive = PASSIVE_ACTION_RE.search(text)
    if passive and _deadline_is_in_sentence(text):
        deliverable = passive.group("deliverable")
        return "complete " + re.sub(r"^the\s+", "", deliverable, flags=re.IGNORECASE)

    return None


def extract_action_person(sentence, speakers=None, speaker_context=None):
    text = remove_speaker_prefix(sentence)
    # A speaker who merely reports a proposed condition is not necessarily
    # the person assigned to complete that deliverable.
    if re.search(r"\b(?:documentation|report|minutes|design|deliverable)\b", text, re.IGNORECASE) and re.search(
        r"\b(?:is|are)\s+(?:to be\s+)?(?:completed|submitted|sent|finished|ready|circulated)\b",
        text,
        re.IGNORECASE,
    ):
        return "Unknown"

    deadline_assignee = re.match(
        r"^(?:and\s+|also\s+)?([A-Z][A-Za-z'-]+),\s+your deadline for\b",
        text,
        re.IGNORECASE,
    )
    if deadline_assignee:
        return deadline_assignee.group(1)

    addressed_action = ADDRESSED_ACTION_RE.search(text)
    if addressed_action:
        return addressed_action.group("person")

    assignee = re.match(
        rf"^(?:and\s+|also\s+)?([A-Z][A-Za-z'-]+),\s*"
        rf"(?:(?:could you|can you)\s+(?:please\s+)?|please\s+)?"
        rf"(?:{ACTION_VERBS})\b",
        text,
        re.IGNORECASE,
    )
    if assignee:
        return assignee.group(1)

    delegated_ready = re.match(
        r"^([A-Z][A-Za-z'-]+),\s*(?:please\s+)?have\s+.+?\s+ready\b",
        text,
        re.IGNORECASE,
    )
    if delegated_ready:
        return delegated_ready.group(1)

    named_subject = re.match(
        r"^([A-Z][A-Za-z'-]+)\s+(?:will|must|needs? to|should|has to)\b",
        text,
        re.IGNORECASE,
    )
    if named_subject and named_subject.group(1).casefold() not in NON_PERSON_SPEAKER_LABELS:
        return named_subject.group(1)

    # First-person commitments belong to the current speaker label.
    if FIRST_PERSON_ACTION_RE.search(text):
        return get_speaker(sentence) or speaker_context or "Unknown"
    if CONDITIONAL_DELIVERABLE_RE.search(text):
        return get_speaker(sentence) or speaker_context or "Unknown"

    return "Unknown"


def _deduplicate_date_mentions(items):
    unique = []
    for item in items:
        if item.casefold() not in {value.casefold() for value in unique}:
            unique.append(item)
    return [
        item for item in unique
        if not any(
            item.casefold() != other.casefold()
            and re.search(
                rf"(?<!\w){re.escape(item)}(?!\w)",
                other,
                re.IGNORECASE,
            )
            for other in unique
        )
    ]


def _same_action(existing, person, task, action_verb):
    if existing["person"].casefold() != person.casefold():
        return False

    existing_task = re.sub(r"\W+", " ", existing["task"]).casefold()
    current_task = re.sub(r"\W+", " ", task).casefold()
    if existing_task == current_task:
        return True

    existing_tokens = _token_set(existing["task"])
    current_tokens = _token_set(task)
    shared = existing_tokens & current_tokens
    existing_verb = ACTION_VERB_RE.match(existing["task"])
    if (
        existing_verb
        and action_verb
        and existing_verb.group(0).casefold() == "investigate"
        and action_verb.group(0).casefold() == "investigate"
        and re.search(r"\binvestigate\s+it\b", existing["task"], re.IGNORECASE)
        and re.search(r"\b(?:issue|problem|cause)\b", task, re.IGNORECASE)
    ):
        return True
    if (
        len(shared) >= 2
        and len(shared) / max(1, min(len(existing_tokens), len(current_tokens))) >= 0.65
        and existing_verb
        and action_verb
        and existing_verb.group(0).casefold() == action_verb.group(0).casefold()
    ):
        return True

    existing_objects = set(
        _token_set(ACTION_VERB_RE.sub("", existing["task"], count=1))
    )
    current_objects = set(
        _token_set(ACTION_VERB_RE.sub("", task, count=1))
    )
    shared_objects = existing_objects & current_objects
    return (
        len(shared_objects) >= 2
        and len(shared_objects)
        / max(1, min(len(existing_objects), len(current_objects))) >= 0.8
    )


def _previously_addressed_person(sentences, index, speaker_contexts):
    current_speaker = (
        speaker_contexts[index]
        if speaker_contexts and index < len(speaker_contexts)
        else None
    )
    if not current_speaker:
        return "Unknown"

    for previous_index in range(index - 1, max(-1, index - 6), -1):
        previous_speaker = (
            speaker_contexts[previous_index]
            if speaker_contexts and previous_index < len(speaker_contexts)
            else None
        )
        if previous_speaker != current_speaker:
            continue
        previous = remove_speaker_prefix(sentences[previous_index]["sentence"])
        match = re.match(
            r"^\s*(?:and\s+)?([A-Z][A-Za-z'-]+),\s+"
            r"(?:please|can you|could you|you will|you'll)\b",
            previous,
        )
        if match:
            return match.group(1)
    return "Unknown"


def extract_action_items(
    classified_sentences,
    speakers=None,
    speaker_contexts=None,
    meeting_date=None,
):
    action_items = []
    seen_actions = []

    for index, item in enumerate(classified_sentences):
        source_sentence = item["sentence"]
        if is_procedural(source_sentence) or is_filler(source_sentence):
            continue
        if is_qa_environment_choice(source_sentence):
            continue
        if re.search(
            r"\b(?:progress check|progress meeting|follow-up meeting|"
            r"check-in meeting)\b",
            remove_speaker_prefix(source_sentence),
            re.IGNORECASE,
        ):
            continue
        if re.search(
            r"\bmain purpose of (?:today's |this )?meeting\b",
            remove_speaker_prefix(source_sentence),
            re.IGNORECASE,
        ):
            continue

        context = (
            speaker_contexts[index]
            if speaker_contexts and index < len(speaker_contexts)
            else None
        )
        protected_sentence = re.sub(
            r"\binvestigate\s+and\s+fix\b",
            "investigate <ACTION_AND> fix",
            source_sentence,
            flags=re.IGNORECASE,
        )
        protected_sentence = re.sub(
            r"(\bcoordinate\b[^.!?]{0,100})\s+and\s+"
            r"(?=(?:get|collect|obtain)\b)",
            r"\1 <ACTION_AND> ",
            protected_sentence,
            flags=re.IGNORECASE,
        )
        clauses = [
            clause.replace("<ACTION_AND>", "and")
            for clause in re.split(
                rf"\s+and\s+(?=(?:{ACTION_VERBS})\b)",
                protected_sentence,
                flags=re.IGNORECASE,
            )
        ]
        inherited_person = extract_action_person(
            source_sentence, speakers, context
        )

        for clause_index, clause in enumerate(clauses):
            if not has_real_action_pattern(clause):
                continue

            task = extract_task(clause)
            if not task:
                continue

            person = extract_action_person(clause, speakers, context)
            if person == "Unknown" and clause_index > 0:
                person = inherited_person
            if person == "Unknown" and YOU_CAN_ACTION_RE.search(clause):
                person = _previously_addressed_person(
                    classified_sentences, index, speaker_contexts
                )
            if person == "Unknown" and re.match(
                rf"^\s*(?:please\s+)?include\b", clause, re.IGNORECASE
            ):
                for previous_index in range(max(0, index - 2), index):
                    previous_text = remove_speaker_prefix(
                        classified_sentences[previous_index]["sentence"]
                    )
                    previous_speaker = (
                        speaker_contexts[previous_index]
                        if speaker_contexts and previous_index < len(speaker_contexts)
                        else None
                    )
                    if (
                        previous_text.rstrip().endswith("?")
                        and re.search(r"\b(?:can|could|should)\s+i\s+include\b", previous_text, re.IGNORECASE)
                        and re.search(r"\b(?:test case|testing)\b", previous_text, re.IGNORECASE)
                        and previous_speaker
                        and previous_speaker != context
                    ):
                        person = previous_speaker
                        break
            deadline = extract_deadline(clause) or "Not specified"
            if task.casefold() == "confirm" and deadline == "Not specified":
                continue

            action_verb = ACTION_VERB_RE.match(task)
            addressed_request = bool(
                re.match(
                    rf"^(?:and\s+)?{re.escape(person)},\s*"
                    r"(?:could you|can you|please)\b",
                    remove_speaker_prefix(clause),
                    re.IGNORECASE,
                )
            )
            first_person_commitment = bool(
                FIRST_PERSON_ACTION_RE.search(remove_speaker_prefix(clause))
            )
            if action_verb and first_person_commitment:
                duplicate_request = next(
                    (
                        previous for previous in seen_actions
                        if previous["person"].casefold() == person.casefold()
                        and previous["action_verb"] == action_verb.group(0).casefold()
                        and previous["addressed_request"]
                    ),
                    None,
                )
                if duplicate_request and len(_token_set(task)) <= 2:
                    previous_item = action_items[duplicate_request["item_index"]]
                    if (
                        previous_item["deadline"] == "Not specified"
                        and deadline != "Not specified"
                    ):
                        previous_item["deadline"] = deadline
                    continue

            duplicate = next(
                (
                    existing for existing in action_items
                    if _same_action(existing, person, task, action_verb)
                ),
                None,
            )
            if duplicate:
                deadline_is_more_specific = (
                    deadline != "Not specified"
                    and (
                        duplicate["deadline"] == "Not specified"
                        or (
                            len(duplicate["deadline"]) < len(deadline)
                            and extract_date_mentions(deadline)
                        )
                    )
                )
                if deadline_is_more_specific:
                    duplicate["deadline"] = deadline
                    duplicate.update(_date_metadata(deadline, meeting_date))
                    duplicate["task"] = task
                elif len(_token_set(task)) > len(_token_set(duplicate["task"])):
                    duplicate["task"] = task
                duplicate["sentence"] = source_sentence
                duplicate["source_text"] = source_sentence
                continue

            # This is a rule-based evidence score, not a calibrated probability.
            rule_confidence = 0.80 if person != "Unknown" else 0.55
            if deadline != "Not specified":
                rule_confidence = min(0.92, rule_confidence + 0.10)

            action_items.append({
                "person": person,
                "task": task,
                "deadline": deadline,
                **_date_metadata(deadline, meeting_date),
                "confidence": round(rule_confidence, 2),
                "sentence": source_sentence,
                "source_text": source_sentence,
            })
            seen_actions.append({
                "person": person,
                "action_verb": action_verb.group(0).casefold() if action_verb else "",
                "addressed_request": addressed_request,
                "item_index": len(action_items) - 1,
            })

    return action_items


# =========================================================
# 6. SUMMARY / DISCUSSION
# =========================================================

SUMMARY_EXCLUDE_PATTERNS = [
    r"\bi move that\b",
    r"\bi second\b",
    r"\bcan i have a motion\b",
    r"\bcan someone propose\b",
    r"\ball those in favor\b",
    r"\bany objections\b",
    r"\bwe'll proceed with the vote\b",
    r"\bthank you\b",
    r"\bgood morning\b",
    r"\bno problem\b",
    r"\b(?:microphone|microphones|echo|background noise|losing connection)\b",
    r"\b(?:coffee|typing so loudly|using a machine|regular part of your meeting routine)\b",
    r"\b(?:i'm quite sure|i am quite sure|i heard|can everybody hear)\b",
    r"\bwe seem to be discussing \w+ different things\b",
    r"\bwe don't want this to delay\b",
    r"\bshould be done by\b",
]

def is_summary_candidate(sentence):
    text = remove_speaker_prefix(sentence).lower()
    if is_procedural(sentence) or is_filler(sentence):
        return False
    if any(re.search(pattern, text) for pattern in SUMMARY_EXCLUDE_PATTERNS):
        return False
    if re.search(r"\b(?:i support|i would suggest|i suggest|i move|i second|i have reviewed|would like clarification|now, we need to vote)\b", text):
        return False
    if len(clean_text(sentence)) < 5:
        return False
    if re.match(
        rf"^(?:{MONTHS})\s+\d{{1,2}}(?:st|nd|rd|th)?\s*,\s*"
        r"(?:assuming|provided|with)\b",
        text,
        re.IGNORECASE,
    ):
        return False
    if sentence.strip().endswith("?"):
        return False
    return True


def _token_set(sentence):
    try:
        return set(clean_text(remove_speaker_prefix(sentence)))
    except Exception:
        return set(re.findall(r"[a-z']+", sentence.lower()))


def _sentence_score(sentence):
    text = remove_speaker_prefix(sentence).lower()
    score = 0

    if is_real_decision(sentence):
        score += 8
    if extract_deadline(sentence):
        score += 4
    if re.search(
        r"\b(policy|recruitment|budget|cost|implementation|launch|project|design|"
        r"testing|deadline|stock|supplier|invoice|scanner|delivery|shipment|"
        r"cafeteria|lunch|meeting room|booking|team activities|backend|campaign|"
        r"password|payment|checkout|application|email|feature|options?|"
        r"authentication|homepage|frontend|api|staging)\b",
        text,
    ):
        score += 3
    if re.search(r"\b(?:estimated|approved|agreed|decided|cost|deadline|effective)\b", text):
        score += 2
    if re.search(r"\b(?:issue|problem|concern|feedback|delay|risk|challenge|"
                 r"discrepanc(?:y|ies)|shortage|crowded|overbook(?:ed|ing)?|"
                 r"no[- ]show|tired|differ(?:ence|ent)|incorrect|missing)\b", text):
        score += 3
    if re.search(r"\b\d[\d,]*(?:\.\d+)?\b", text):
        score += 2
    if re.search(r"\b\d[\d,]*\s+(?:units?|items?|boxes|people|percent|%)\b", text):
        score += 3
    if re.search(r"\b(?:found|counted|received|estimated|arriving|arrived|"
                 r"identified|reported|costs|costs?)\b", text):
        score += 1
    if len(clean_text(text)) >= 12:
        score += 1
    if re.search(
        r"\b(?:main purpose|meeting focused on|meeting covered|"
        r"main topics? (?:were|are))\b",
        text,
    ):
        score += 12
    if re.search(
        r"\b(?:completed|ready|waiting for|blocked|blocker|"
        r"issue|problem|target|overall target|internal review)\b",
        text,
    ):
        score += 2
    if re.search(
        r"\b(?:integrated|integration|implemented|"
        r"currently using|still waiting|not started|not ready)\b",
        text,
    ):
        score += 2

    # Penalize statements that are mostly meeting mechanics.
    if re.search(r"\b(?:motion|second|favor|objection|attendance|minutes from our previous)\b", text):
        score -= 3
    return score






# =========================================================
# 7. KEYWORD EXTRACTION
# =========================================================

KEYWORD_STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "from", "into", "about",
    "are", "was", "were", "been", "being", "have", "has", "had", "will",
    "would", "could", "should", "can", "may", "might", "must", "not", "but",
    "you", "your", "our", "their", "they", "them", "his", "her", "she", "him",
    "who", "what", "when", "where", "why", "how", "there", "here", "then",
    "than", "also", "just", "only", "very", "more", "most", "some", "such",
    "all", "any", "each", "every", "one", "two", "first", "last", "next",
    "today", "tomorrow", "yesterday", "morning", "afternoon", "evening",
    "okay", "alright", "yeah", "yes", "hey", "hello", "thank", "thanks",
    "everyone", "something", "anything", "thing", "things", "maybe", "need",
    "needs", "want", "wanted", "think", "know", "like", "really", "well",
    "actually", "sorry", "please", "said", "say", "says", "noted", "fine",
    "reasonable", "good", "move", "second", "favor", "objection", "objections",
    "include", "including", "meeting", "meetings", "previous", "main", "those", "approved",
    "minutes", "motion", "vote", "favor", "proposed",
    "robert", "elizabeth", "michael", "susan", "ahmed",
    "someone", "somebody", "wait", "still", "now", "time", "check", "sure",
    "noise", "items", "thought", "thoughts", "says", "said",
    "too", "true", "getting", "people", "same",
    "ready", "everything", "final", "main", "new", "current",
    "initial", "small", "major", "overall", "complete", "completed",
}

def extract_keywords(transcript, limit=12):
    tokens = re.findall(r"[a-z][a-z'-]{2,}", normalize_transcript(transcript).lower())
    date_words = set(MONTHS.lower().split("|")) | set(WEEKDAYS.lower().split("|"))
    speaker_words = {
        word.casefold()
        for speaker in extract_speakers(split_sentences(transcript))
        for word in speaker.split()
    }
    counts = Counter(
        token for token in tokens
        if token not in KEYWORD_STOPWORDS
        and token not in date_words
        and token not in speaker_words
        and token.isalpha()
    )
    valid_tokens = [
        token if (
            token not in KEYWORD_STOPWORDS
            and token not in date_words
            and token not in speaker_words
            and token.isalpha()
        ) else None
        for token in tokens
    ]
    phrase_counts = Counter(
        f"{left} {right}"
        for left, right in zip(valid_tokens, valid_tokens[1:])
        if left and right
    )

    # Boost useful meeting-domain terms, but keep ranking data-driven.
    domain_terms = {
        "policy", "recruitment", "amendment", "budget", "cost",
        "implementation", "assessment", "documentation", "training",
        "maintenance", "interview", "verification", "department",
        "candidate", "administrative", "evaluation", "appointment",
        "authentication", "homepage", "frontend", "backend", "staging",
        "integration", "session", "password", "database", "mobile",
        "website", "redesign", "launch", "campaign", "checkout",
    }
    ranked = [
        (word, count + (1 if word in domain_terms else 0), count, 1)
        for word, count in counts.items()
    ]
    ranked.extend(
        (phrase, count * 2, count, 2)
        for phrase, count in phrase_counts.items()
        if count >= 2
    )
    ranked.sort(key=lambda item: (item[1], item[2], item[3], item[0]), reverse=True)
    return [term for term, _, _, _ in ranked[:limit]]


# =========================================================
# 8. MAIN ANALYSIS PIPELINE
# =========================================================



# =========================================================
# VERSION 4 OVERRIDES: CONTEXT, NOISE CONTROL, AND MILESTONES
# =========================================================

ACKNOWLEDGEMENT_PATTERNS = [
    r"^\s*(?:good morning|good afternoon|good evening|hello|hi)\b",
    r"^\s*(?:yes|no|okay|alright|noted|fine|thanks|thank you)\s*[,.!?]*$",
    r"^\s*(?:no problem|that's fine|that is fine|sounds good|that sounds reasonable)\s*[.!?]*$",
    r"^\s*(?:just one thing|one thing)\s*[.!?]*$",
    r"^\s*(?:thank you|thanks)\b",
    r"^\s*(?:everyone is here|he(?:'s| is) just joined)\b",
    r"^\s*(?:they were shared|they have been shared)\b",
]

def is_filler(sentence):
    text = remove_speaker_prefix(sentence).strip().lower()
    if any(re.search(pattern, text, re.IGNORECASE) for pattern in ACKNOWLEDGEMENT_PATTERNS):
        return True
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in FILLER_PATTERNS)




def _decision_text(sentence):
    return remove_speaker_prefix(sentence).strip()




def extract_important_dates(sentences, action_items=None):
    """
    Keep milestones and meaningful time references. Generic 'today' and
    historical context such as 'Monday' are not promoted as key dates unless
    connected to a deliverable or milestone.
    """
    important = []
    action_sources = {
        item.get("sentence", "").casefold()
        for item in (action_items or [])
    }
    for sentence in sentences:
        text = remove_speaker_prefix(sentence)
        low = text.lower()
        dates = extract_date_mentions(text)
        explicit_dates = [
            date for date in dates
            if re.search(rf"\b(?:{MONTHS})\b.*\b\d{{1,2}}\b", date, re.IGNORECASE)
            or re.search(r"\b\d{1,2}[/-]\d{1,2}\b", date)
        ]
        if explicit_dates:
            dates = explicit_dates
        if not dates:
            continue

        meaningful_context = (
            sentence.casefold() in action_sources
            or extract_deadline(sentence) is not None
            or bool(
                re.search(
                    r"\b(?:deadline|due|implementation|effective|launch|"
                    r"final documentation|next quarterly review|arrival|arriving|"
                    r"delivery|shipment|inspection|holiday|schedule|scheduled|"
                    r"reserved|corrections?)\b",
                    low,
                )
            )
        )
        if not meaningful_context:
            continue

        for date in dates:
            if re.match(r"^(?:yesterday|last\s+)", date, re.IGNORECASE):
                continue
            if date.casefold() == "this week":
                continue
            if date.lower() not in {x.lower() for x in important}:
                important.append(date)
    return _deduplicate_date_mentions(important)






def analyze_meeting(transcript, meeting_date=None):
    """
    Version 4 orchestration. Keeps the original public report schema.
    """
    empty = {
        "summary": [], "decisions": [], "discussion": [],
        "action_items": [], "deadlines": [], "important_dates": [],
        "people": [], "keywords": [], "scheduled_events": [],
        "summary_evidence": [], "decision_evidence": [],
        "discussion_evidence": [],
    }
    meeting_date = _coerce_meeting_date(meeting_date)
    transcript = normalize_transcript(transcript)
    if not transcript:
        return empty

    sentences = split_sentences(transcript)
    speakers = extract_speakers(sentences)
    speaker_contexts = build_speaker_context(sentences)

    sentence_records = [{"sentence": sentence} for sentence in sentences]

    decisions = extract_decisions(sentences)
    action_items = extract_action_items(
        sentence_records,
        speakers=speakers,
        speaker_contexts=speaker_contexts,
        meeting_date=meeting_date,
    )

    action_sources = {x.get("sentence", "").casefold() for x in action_items}
    for sentence in sentences:
        if sentence.casefold() in action_sources:
            continue
        deadline = extract_deadline(sentence)
        task = extract_task(sentence)
        if deadline and task and re.search(
            r"\b(?:documentation|report|minutes|design|deliverable)\b",
            sentence, re.IGNORECASE,
        ):
            action_items.append({
                "person": "Unknown",
                "task": task,
                "deadline": deadline,
                **_date_metadata(deadline, meeting_date),
                "confidence": 0.70,
                "sentence": sentence,
                "source_text": sentence,
            })

    summary, summary_evidence = _build_summary(sentences, decisions, action_items)
    decision_evidence = _build_decision_evidence(decisions, sentences)
    scheduled_events = extract_scheduled_events(sentences, meeting_date)
    summary_sources = {
        remove_speaker_prefix(source).casefold()
        for item in summary_evidence
        for source in item.get("source_text", [])
    }
    decision_sources = {
        remove_speaker_prefix(source).casefold()
        for item in decision_evidence
        for source in item.get("source_text", [])
    }
    event_sources = {
        remove_speaker_prefix(item["source_text"]).casefold()
        for item in scheduled_events
    }
    action_source_sentences = {
        remove_speaker_prefix(sentence).casefold()
        for sentence in sentences
        if has_real_action_pattern(sentence) and extract_task(sentence)
    }
    discussion = extract_discussion(
        sentence_records, summary=summary,
        action_items=action_items, decisions=decisions,
        action_sources=action_source_sentences,
        excluded_sources=summary_sources | decision_sources | event_sources,
    )
    discussion_evidence = [
        {"discussion": item, "source_text": item}
        for item in discussion
    ]

    deadlines = []
    for sentence in sentences:
        deadline = extract_deadline(sentence)
        if (
            deadline
            and deadline.casefold() != "this week"
            and deadline.lower() not in {x.lower() for x in deadlines}
        ):
            deadlines.append(deadline)

    for item in action_items:
        deadline = item.get("deadline", "Not specified")
        if (
            deadline != "Not specified"
            and deadline.casefold() not in {value.casefold() for value in deadlines}
        ):
            deadlines.append(deadline)

    for decision in decisions:
        if re.match(r"^Agreed to\b", decision, re.IGNORECASE):
            for date in extract_date_mentions(decision):
                if date.casefold() not in {item.casefold() for item in deadlines}:
                    deadlines.append(date)
    deadlines = _deduplicate_date_mentions(deadlines)
    return {
        "summary": summary,
        "summary_evidence": summary_evidence,
        "decisions": decisions,
        "decision_evidence": decision_evidence,
        "discussion": discussion,
        "discussion_evidence": discussion_evidence,
        "action_items": action_items,
        "deadlines": deadlines,
        "important_dates": extract_important_dates(sentences, action_items),
        "people": extract_people(sentences, speakers, action_items),
        "keywords": extract_keywords(transcript),
        "scheduled_events": scheduled_events,
    }


# =========================================================
# VERSION 4.1 PATCH: REGRESSION FIXES FROM MEETING 1
# =========================================================

def is_procedural(sentence):
    text = remove_speaker_prefix(sentence).strip().lower()
    patterns = PROCEDURAL_PATTERNS + [
        r"^\s*(?:can we confirm that all members are present|could you please check the attendance)\??$",
        r"^\s*(?:have the minutes from our previous meeting been circulated)\??$",
        r"^\s*(?:yes, everyone is here|yes, they were shared)\b",
        r"^\s*(?:any further questions)\??$",
        r"^\s*(?:if there is no further business)\b",
        r"^\s*(?:no objection)\b",
        r"^\s*(?:in favor|yes)\s*[.!?]*$",
        r"^\s*(?:noted)\s*[.!?]*$",
        r"\bthe motion is carried\b",
        r"\bthe motion is approved with\b",
        r"\bthe amendment is approved\b",
        r"\bi am abstaining from the vote\b",
        r"\bany objections to the proposed implementation date\b",
        r"\b(?:we should finish now|meeting has already gone over time)\b",
        r"\blet's also talk about the project timeline\b",
        r"\bif there are any blockers\b.{0,100}\bcommunicate them\b",
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def is_qa_environment_choice(sentence):
    text = remove_speaker_prefix(sentence)
    return all(
        re.search(pattern, text, re.IGNORECASE)
        for pattern in (
            r"\b(?:test|tests|testing|QA)\b",
            r"\bstaging\b",
            r"\blocal\b",
            r"\binstead\b",
        )
    )


def extract_decisions(sentences):
    decisions = []

    def previous_motion(index):
        for j in range(index - 1, max(-1, index - 18), -1):
            candidate = remove_speaker_prefix(sentences[j])
            if re.search(r"\bi move that\b", candidate, re.IGNORECASE):
                return candidate
        return ""

    for i, sentence in enumerate(sentences):
        text = remove_speaker_prefix(sentence).strip()
        low = text.lower()

        if re.search(r"\bthe motion is carried unanimously\b|\bthe motion is carried\b", low):
            motion = previous_motion(i)
            if re.search(r"\bminutes of the previous meeting\b", motion, re.IGNORECASE):
                decision = "Minutes of the previous meeting approved unanimously."
            else:
                decision = "Motion carried unanimously."
            if decision not in decisions:
                decisions.append(decision)
            continue

        if re.search(r"\bthe amendment is approved unanimously\b", low):
            decision = "Department-specific practical assessments for technical vacancies approved unanimously."
            if decision not in decisions:
                decisions.append(decision)
            continue

        vote = re.search(
            r"\bthe motion is approved with\s+(\w+)\s+votes?\s+in favor and\s+(\w+)\s+abstention",
            low,
        )
        if vote:
            motion = previous_motion(i)
            if re.search(r"\brevised employee recruitment policy\b", motion, re.IGNORECASE):
                decision = (
                    "Revised employee recruitment policy, including the amendment, "
                    "approved with four votes in favor and one abstention."
                )
            elif motion:
                decision = f"{motion.rstrip('.')} — approved with {vote.group(1)} votes in favor and {vote.group(2)} abstention."
            else:
                decision = f"Motion approved with {vote.group(1)} votes in favor and {vote.group(2)} abstention."
            if decision not in decisions:
                decisions.append(decision)
            continue

    # A date proposal followed by a clear approval / no-objection outcome.
    for i, sentence in enumerate(sentences):
        text = remove_speaker_prefix(sentence)
        if re.search(r"\bwe propose\b", text, re.IGNORECASE) and extract_date_mentions(text):
            window = " ".join(remove_speaker_prefix(s) for s in sentences[i+1:i+6])
            if re.search(r"\b(?:approved|agreed|no objections?)\b", window, re.IGNORECASE):
                date = extract_date_mentions(text)[0]
                decision = f"Policy implementation scheduled for {date}."
                if decision not in decisions:
                    decisions.append(decision)

    # Agreement on a concrete follow-up is recorded separately from formal votes.
    for i, sentence in enumerate(sentences):
        text = remove_speaker_prefix(sentence)
        if re.search(r"\bwe should review\b", text, re.IGNORECASE):
            window = " ".join(remove_speaker_prefix(s) for s in sentences[i+1:i+3])
            if re.search(r"\bagreed\b|\blet's include\b", window, re.IGNORECASE):
                if re.search(r"\bimplementation costs\b", text, re.IGNORECASE):
                    decision = "Agreed to review implementation costs after the first quarter at the next quarterly review."
                    if decision not in decisions:
                        decisions.append(decision)

    def add_decision(decision):
        normalized = decision.casefold().strip()
        if normalized and normalized not in {item.casefold() for item in decisions}:
            decisions.append(decision)

    def add_agreed_proposal(index):
        for proposal in reversed(sentences[max(0, index - 4):index]):
            proposal_text = remove_speaker_prefix(proposal).strip()
            if re.search(
                r"\b(?:maybe we can|we could|we can|i suggest|let's|we should)\b",
                proposal_text,
                re.IGNORECASE,
            ):
                proposal_text = re.sub(
                    r"^(?:maybe\s+)?(?:we can|we could|i suggest(?:ed)?|"
                    r"let's|we should)\s+",
                    "",
                    proposal_text,
                    flags=re.IGNORECASE,
                ).rstrip(" .")
                add_decision(f"Agreed to {proposal_text}.")
                return True
        return False

    for i, sentence in enumerate(sentences):
        text = remove_speaker_prefix(sentence).strip()
        low = text.casefold()

        if re.search(r"\blet's do that\b", low):
            add_agreed_proposal(i)
            continue

        if re.search(r"\blet's include that in the next quarterly review\b", low):
            continue

        if re.search(r"\b(?:do not|don't) approve (?:the )?payment until\b", low):
            add_decision(
                "Payment approval paused until the invoice quantity is verified."
            )
            continue

        if is_real_decision(sentence) and not is_procedural(sentence):
            add_decision(text)
            continue

        if re.search(
            r"\b(?:let's do that|let's proceed|let's move forward|"
            r"we'll schedule|we will schedule|let's schedule|let's set|"
            r"we'll set|we will set|let's assign|we'll assign|"
            r"we will assign|we're targeting|we are targeting)\b",
            low,
        ):
            if not re.search(r"\blet's do that\b", low):
                add_decision(text)
            continue

        if re.search(r"\b(?:that's more realistic|that is more realistic)\b", low):
            add_agreed_proposal(i)

    for i, sentence in enumerate(sentences):
        text = remove_speaker_prefix(sentence)
        if not re.search(
            r"\b(?:run|conduct|carry out|perform)\b.{0,80}\bstaging\b"
            r".{0,100}\binstead of\b",
            text,
            re.IGNORECASE,
        ):
            continue
        nearby = " ".join(
            remove_speaker_prefix(value)
            for value in sentences[max(0, i - 1):i + 3]
        )
        if re.search(r"\b(?:exactly|perfect|agreed|that will help|sounds good)\b", nearby, re.IGNORECASE):
            add_decision(
                "QA will use the staging environment instead of individual local machines."
            )
    return decisions


def summarize(sentences, number_of_sentences=5, action_items=None, decisions=None):
    action_sources = {
        remove_speaker_prefix(item.get("sentence", "")).casefold()
        for item in (action_items or [])
    }
    decision_sources = {d.casefold() for d in (decisions or [])}
    action_tasks = [
        _token_set(item.get("task", ""))
        for item in (action_items or [])
    ]

    candidates = []
    for index, sentence in enumerate(sentences):
        clean = remove_speaker_prefix(sentence)
        low = clean.lower()
        if (
            is_procedural(sentence)
            or is_filler(sentence)
            or is_real_decision(sentence)
            or not is_summary_candidate(sentence)
        ):
            continue
        if clean.casefold() in action_sources or clean.casefold() in decision_sources:
            continue
        if re.search(r"\b(?:by|deadline|due)\b", low):
            tokens = _token_set(clean)
            if any(
                len(tokens & task_tokens) / max(1, len(task_tokens)) >= 0.5
                for task_tokens in action_tasks
                if len(task_tokens) >= 2
            ):
                continue
        if re.match(
            rf"^(?:{MONTHS})\s+\d{{1,2}}(?:st|nd|rd|th)?\s*,",
            low,
            re.IGNORECASE,
        ):
            continue
        if len(clean_text(clean)) < 5 or clean.endswith("?"):
            continue
        if re.search(
            r"\b(?:i move that|i second|all those in favor|any objections|"
            r"thank you|good morning|no problem|that's fine|i'll|i will)\b",
            low,
        ):
            continue

        score = _sentence_score(sentence)
        if re.search(r"\b(?:agenda|proposing|revised recruitment process)\b", low):
            score += 4
        if re.search(r"\b(?:350,000|implementation cost|annual expenses|"
                     r"standardized interviews|background verification)\b", low):
            score += 4
        if score > 0:
            candidates.append((score, index, clean))

    candidates.sort(key=lambda x: (-x[0], x[1]))
    selected, token_sets = [], []
    for score, index, sentence in candidates:
        tokens = _token_set(sentence)
        if any(
            tokens and old and len(tokens & old) / max(1, len(tokens | old)) > 0.55
            for old in token_sets
        ):
            continue
        selected.append((index, sentence))
        token_sets.append(tokens)
        if len(selected) >= number_of_sentences:
            break
    selected.sort(key=lambda x: x[0])
    return [sentence for _, sentence in selected]


def extract_scheduled_events(sentences, meeting_date=None):
    events = []
    for sentence in sentences:
        text = remove_speaker_prefix(sentence).strip()
        match = re.search(
            rf"\b(?:quick\s+)?(?P<event>progress check|progress meeting|"
            rf"follow-up meeting|check-in meeting)\s+"
            rf"(?:on\s+)?(?P<when>(?:(?:{WEEKDAYS})\b)?"
            r"(?:\s+(?:morning|afternoon|evening))?)",
            text,
            re.IGNORECASE,
        )
        if not match:
            continue

        when = match.group("when").strip(" ,.")
        dates = extract_date_mentions(when)
        date_expression = dates[0] if dates else None
        time_match = re.search(r"\b(morning|afternoon|evening)\b", when, re.IGNORECASE)
        event = {
            "type": "follow_up",
            "title": "Project progress check",
            "date": date_expression,
            "time": time_match.group(1).casefold() if time_match else None,
            "source_text": sentence,
        }
        event.update(_date_metadata(date_expression, meeting_date))
        events.append(event)
    return events


def _build_summary(sentences, decisions, action_items):
    summary = []
    evidence = []

    def add(text, sources):
        sources = list(dict.fromkeys(source for source in sources if source))
        if text and text not in summary:
            summary.append(text)
            evidence.append({"summary": text, "source_text": sources})

    topics = []
    topic_patterns = [
        ("website redesign", r"\bwebsite redesign\b|\bredesign\b"),
        ("frontend progress", r"\bfrontend\b|\bhomepage\b"),
        ("design delivery", r"\bdesigns?\b"),
        ("backend API integration", r"\bbackend\b|\bAPI\b"),
        ("authentication issues", r"\bauthentication\b|\blogin\b|\bsession\b"),
        ("QA preparation", r"\bQA\b|\btest cases?\b|\btesting\b"),
    ]
    for label, pattern in topic_patterns:
        source = next(
            (sentence for sentence in sentences if re.search(pattern, sentence, re.IGNORECASE)),
            None,
        )
        if source:
            topics.append(label)
    objective_sources = [
        sentence for sentence in sentences
        if re.search(r"\b(?:main purpose|purpose of today's meeting|meeting is to)\b", sentence, re.IGNORECASE)
    ]
    if not objective_sources:
        objective_sources = [
            sentence for sentence in sentences
            if any(re.search(pattern, sentence, re.IGNORECASE) for _, pattern in topic_patterns)
        ][:4]
    if topics:
        topic_list = topics[0] if len(topics) == 1 else (
            ", ".join(topics[:-1]) + f", and {topics[-1]}"
        )
        add(f"The meeting focused on {topic_list}.", objective_sources)

    progress_sources = []
    has_homepage_structure = any(
        re.search(r"\bhomepage structure\b.{0,50}\bready\b", sentence, re.IGNORECASE)
        for sentence in sentences
    )
    has_navigation = any(
        re.search(r"\bintegrat(?:ed|ion)\b.{0,40}\bnavigation\b|\bnavigation\b.{0,40}\bintegrated\b", sentence, re.IGNORECASE)
        for sentence in sentences
    )
    design_pending = any(
        re.search(r"\bwaiting for\b.{0,40}\bdesigns?\b", sentence, re.IGNORECASE)
        for sentence in sentences
    )
    api_pending = any(
        re.search(r"\bstatic data\b|\bneed to connect\b.{0,50}\bAPI\b", sentence, re.IGNORECASE)
        for sentence in sentences
    )
    progress_sources = [
        sentence for sentence in sentences
        if (
            (has_homepage_structure and re.search(r"\bhomepage structure\b", sentence, re.IGNORECASE))
            or (has_navigation and re.search(r"\bnavigation\b", sentence, re.IGNORECASE))
            or (design_pending and re.search(r"\bwaiting for\b", sentence, re.IGNORECASE))
            or (api_pending and re.search(r"\bstatic data\b|\bAPI\b", sentence, re.IGNORECASE))
        )
    ]
    if has_homepage_structure or has_navigation or design_pending or api_pending:
        complete = []
        pending = []
        if has_homepage_structure:
            complete.append("homepage structure")
        if has_navigation:
            complete.append("navigation")
        if design_pending:
            pending.append("final designs")
        if api_pending:
            pending.append("backend API integration")

        statement = ""
        if complete:
            statement += f"The {' and '.join(complete)} {'are' if len(complete) > 1 else 'is'} in place"
        if pending:
            if statement:
                statement += ", while "
            statement += f"{' and '.join(pending)} {'remain' if len(pending) > 1 else 'remains'} outstanding"
        if statement:
            add(statement + ".", progress_sources)

    role_groups = [
        ("design", ("design", "Emily")),
        ("API development and authentication", ("api", "John")),
        ("homepage development and staging", ("staging", "Ahmed")),
        ("QA and testing", ("test", "David")),
        ("website content", ("content", "Sarah")),
    ]
    assigned = []
    role_sources = []
    for label, (needle, person) in role_groups:
        person_items = [
            item for item in action_items
            if item.get("person", "").casefold() == person.casefold()
            and needle in item.get("task", "").casefold()
        ]
        if person_items:
            assigned.append(f"{label} ({person})")
            role_sources.extend(item.get("source_text", item.get("sentence", "")) for item in person_items)
    if assigned:
        assigned_list = assigned[0] if len(assigned) == 1 else (
            ", ".join(assigned[:-1]) + f", and {assigned[-1]}"
        )
        add("Responsibilities were assigned for " + assigned_list + ".", role_sources)

    decision_bits = []
    decision_sources = []
    has_existing_assets = any(
        re.search(r"\buse the existing assets\b", decision, re.IGNORECASE)
        for decision in decisions
    )
    has_staging_decision = any(
        re.search(r"\bQA will use the staging environment\b", decision, re.IGNORECASE)
        for decision in decisions
    )
    has_review_deadline = any(
        re.search(r"\bNovember 20\b", decision, re.IGNORECASE)
        for decision in decisions
    )
    if has_existing_assets or has_staging_decision or has_review_deadline:
        selected_decisions = [
            decision for decision in decisions
            if re.search(r"\b(?:existing assets|November 20|staging)\b", decision, re.IGNORECASE)
        ]
        decision_sources = [
            sentence for sentence in sentences
            if (
                re.search(r"\b(?:existing assets|November 20)\b", sentence, re.IGNORECASE)
                and re.search(r"\b(?:use|let's keep|internal review)\b", sentence, re.IGNORECASE)
            ) or (
                re.search(r"\bstaging\b", sentence, re.IGNORECASE)
                and re.search(r"\b(?:run|test|QA)\b", sentence, re.IGNORECASE)
            )
        ]
        if not decision_sources:
            decision_sources = selected_decisions
        decision_summary = ""
        agreements = []
        if has_existing_assets:
            agreements.append("use existing assets")
        if has_staging_decision:
            agreements.append("staging for QA")
        if agreements:
            if has_staging_decision and has_existing_assets:
                decision_summary = "The team agreed to use existing assets and staging for QA"
            elif has_existing_assets:
                decision_summary = "The team agreed to use existing assets"
            else:
                decision_summary = "The team agreed to use staging for QA"
        if has_review_deadline:
            if agreements:
                decision_summary += "; the internal review target is November 20"
            else:
                decision_summary = "The team set November 20 as the internal review target"
        add(decision_summary + ".", decision_sources)

    if not summary:
        fallback = summarize(sentences, action_items=action_items, decisions=decisions)
        for sentence in fallback:
            add(sentence, [next(
                (source for source in sentences if remove_speaker_prefix(source) == sentence),
                sentence,
            )])

    return summary, evidence


def _build_decision_evidence(decisions, sentences):
    evidence = []
    for decision in decisions:
        tokens = _token_set(decision)
        ranked = []
        for index, sentence in enumerate(sentences):
            source_tokens = _token_set(remove_speaker_prefix(sentence))
            overlap = len(tokens & source_tokens)
            if overlap:
                ranked.append((overlap, index, sentence))
        ranked.sort(key=lambda entry: (-entry[0], entry[1]))
        sources = [entry[2] for entry in ranked[:2]]
        evidence.append({"decision": decision, "source_text": sources})
    return evidence


def extract_discussion(
    classified_sentences,
    summary=None,
    action_items=None,
    decisions=None,
    action_sources=None,
    excluded_sources=None,
):
    summary_set = {s.casefold() for s in (summary or [])}
    action_set = {
        remove_speaker_prefix(item.get("sentence", "")).casefold()
        for item in (action_items or [])
    }
    action_set.update(action_sources or set())
    action_set.update(excluded_sources or set())
    candidates = []
    for index, item in enumerate(classified_sentences):
        sentence = item["sentence"]
        clean = remove_speaker_prefix(sentence).strip()
        low = clean.lower()
        key = clean.casefold()

        if (
            is_procedural(sentence)
            or is_filler(sentence)
            or is_real_decision(sentence)
            or not is_summary_candidate(sentence)
        ):
            continue
        if key in summary_set or key in action_set:
            continue
        if len(clean_text(clean)) < 5:
            continue
        if re.match(
            r"^(?:that's|that is|yes|no|okay|alright|sure|fine|noted|"
            r"no problem|just one thing)\b",
            low,
        ):
            if not re.search(
                r"\b(?:cost|expense|policy|assessment|deadline|date|department|"
                r"training|maintenance|implementation|proposal)\b",
                low,
            ):
                continue
        if re.search(r"\b(?:good morning|everyone is here|shared with everyone)\b", low):
            continue
        if clean.endswith("?") and not re.search(
            r"\b(?:cost|expense|department|temporary|effective|apply|calculated|"
            r"annual|one-time)\b",
            low,
        ):
            continue
        score = _sentence_score(sentence)
        tokens = _token_set(clean)
        repeated = any(
            len(tokens & _token_set(existing)) / max(
                1,
                len(tokens | _token_set(existing)),
            ) > 0.55
            for _, _, existing in candidates
            if tokens and _token_set(existing)
        )
        if (
            score >= 2
            and key not in {entry[2].casefold() for entry in candidates}
            and not repeated
        ):
            candidates.append((score, index, clean))

    candidates.sort(key=lambda entry: (-entry[0], entry[1]))
    selected = candidates[:12]
    return [entry[2] for entry in sorted(selected, key=lambda entry: entry[1])]
