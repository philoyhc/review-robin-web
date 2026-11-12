"""Sample data for the placeholders (segment AD1, item 2): four exercises,
their applications, panels and profile pages, so every page of the URL
map has something to show. Names and addresses are invented; IDs have the
public-ID shape (`applydesk/ids.py`)."""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Exercise:
    public_id: str
    code: str  # the operator's short code, as an RRW session's (unique)
    name: str
    state: str  # Draft, Published, Closed, Archived
    stage: str  # Application, Review
    eligibility: str  # "Open to all signed in", "Invitation only"
    blind: bool
    opens: str
    application_stage_ends: str
    expected_outcome: str
    summary: str


@dataclass(frozen=True)
class Application:
    public_id: str
    exercise_id: str
    applicant: str
    email: str
    title: str
    state: str  # Draft, Submitted, Withdrawn
    submitted: str
    profile_id: str


@dataclass(frozen=True)
class Assessor:
    exercise_id: str
    name: str
    email: str
    asked_to_review: tuple[str, ...]  # application public IDs (ruling 9)
    panel: str = "Panel A"


@dataclass(frozen=True)
class Evaluator:
    """Someone on a roster that is not an assessment panel: the pool
    applicants choose a reviewer from, or the interviewers."""

    exercise_id: str
    name: str
    email: str
    note: str


EXERCISES: tuple[Exercise, ...] = (
    Exercise(
        public_id="wa9juxbc2t",
        code="URF-2027",
        name="Undergraduate Research Fellowship 2027",
        state="Published",
        stage="Application",
        eligibility="Open to all signed in",
        blind=False,
        opens="3 Nov 2026",
        application_stage_ends="31 Jan 2027, 23:59",
        expected_outcome="Mid-March 2027",
        summary="Funding for a semester of supervised research, with a stipend.",
    ),
    Exercise(
        public_id="k7mfr3pq8z",
        code="TEA-2026",
        name="Teaching Excellence Award 2026",
        state="Published",
        stage="Review",
        eligibility="Invitation only",
        blind=True,
        opens="1 Sep 2026",
        application_stage_ends="31 Oct 2026, 23:59",
        expected_outcome="December 2026",
        summary="Nominated teachers submit a teaching portfolio; a panel reads it blind.",
    ),
    Exercise(
        public_id="c4xh2ndv6s",
        code="SIS-2027",
        name="Summer Internship Scheme 2027",
        state="Draft",
        stage="Application",
        eligibility="Open to all signed in",
        blind=False,
        opens="Not set",
        application_stage_ends="Not set",
        expected_outcome="Not set",
        summary="Placements with partner organizations over the summer vacation.",
    ),
    # Just created: a name and nothing else, awaiting setup (author,
    # 2026-11-12).
    Exercise(
        public_id="n5wg8tjr3e",
        code="",
        name="Graduate Travel Grant 2027",
        state="Draft",
        stage="Application",
        eligibility="Not set",
        blind=False,
        opens="Not set",
        application_stage_ends="Not set",
        expected_outcome="Not set",
        summary="",
    ),
)

APPLICATIONS: tuple[Application, ...] = (
    Application(
        "m3qx8vkt2n",
        "wa9juxbc2t",
        "Aisha Bello",
        "aisha.bello@example.edu",
        "Soil microbes and drought tolerance",
        "Submitted",
        "12 Nov 2026",
        "p3bd7kq2wx",
    ),
    Application(
        "h6zr2tdw9p",
        "wa9juxbc2t",
        "Kenji Russo",
        "kenji.russo@example.edu",
        "Low-cost sensors for air quality",
        "Submitted",
        "10 Nov 2026",
        "r9ck4xbm7t",
    ),
    Application(
        "f2ps7nyh4k",
        "wa9juxbc2t",
        "Wen Novak",
        "wen.novak@example.edu",
        "Oral histories of a fishing village",
        "Draft",
        "",
        "w5jh8ntq3d",
    ),
    Application(
        "b8yd3mkr6v",
        "k7mfr3pq8z",
        "Margaret Liu",
        "margaret.liu@example.edu",
        "Flipped studios for first-year design",
        "Submitted",
        "28 Oct 2026",
        "t8nv4hzm2c",
    ),
    Application(
        "q4tw9hcz3x",
        "k7mfr3pq8z",
        "Ahmed Shah",
        "ahmed.shah@example.edu",
        "Peer instruction in large statistics classes",
        "Submitted",
        "30 Oct 2026",
        "e6xp2rfk9m",
    ),
)

ASSESSORS: tuple[Assessor, ...] = (
    Assessor("wa9juxbc2t", "Zoe Tan", "zoe.tan@example.edu", ("m3qx8vkt2n", "h6zr2tdw9p")),
    Assessor("wa9juxbc2t", "Lars Berg", "lars.berg@example.edu", ("m3qx8vkt2n",)),
    Assessor("wa9juxbc2t", "Ana Lim", "ana.lim@example.edu", ("h6zr2tdw9p",), panel="Panel B"),
    Assessor("k7mfr3pq8z", "Priya Rao", "priya.rao@example.edu", ("b8yd3mkr6v", "q4tw9hcz3x")),
    Assessor("k7mfr3pq8z", "Mei Chen", "mei.chen@example.edu", ("q4tw9hcz3x",)),
)

# The pool an applicant chooses a reviewer from, and the interviewers.
REVIEWER_POOL: tuple[Evaluator, ...] = (
    Evaluator("wa9juxbc2t", "Dr Hana Ito", "hana.ito@example.edu", "Life Sciences"),
    Evaluator("wa9juxbc2t", "Dr Omar Aziz", "omar.aziz@example.edu", "Engineering"),
    Evaluator("wa9juxbc2t", "Dr Ruth Kahn", "ruth.kahn@example.edu", "Humanities"),
)
INTERVIEWERS: tuple[Evaluator, ...] = (
    Evaluator("wa9juxbc2t", "Prof Ivan Petrov", "ivan.petrov@example.edu", "Chair"),
    Evaluator("wa9juxbc2t", "Dr Sara Ng", "sara.ng@example.edu", ""),
    Evaluator("k7mfr3pq8z", "Prof Ben Ortiz", "ben.ortiz@example.edu", "Chair"),
)

# The applicant form's two sections, as an applicant fills them in
# (spec §5.1): the profile page shows the first only.
SHOWN_TO_REVIEWERS: tuple[tuple[str, str], ...] = (
    ("Project title", ""),
    (
        "Summary",
        "What the project asks, why it matters, and what the semester will produce.",
    ),
    ("Methods", "How the work will be done, with a timeline by month."),
    ("Relevant experience", "Courses, projects or work that prepare the applicant."),
)
NOT_SHOWN_TO_REVIEWERS: tuple[str, ...] = (
    "Preferred reviewer (from the reviewer pool)",
    "Matriculation number",
    "Expected graduation",
    "Financial aid held",
)


# Evaluation responses by application, from every source (author,
# 2026-11-12: Reports collates them): Review Robin's assessments, the
# interviews, and the reviewer an applicant chose from the pool.
RESPONSES: dict[str, dict[str, str]] = {
    "m3qx8vkt2n": {
        "assessment": "2 of 2 submitted · mean 4.5 of 5",
        "interview": "Not yet",
        "pool": "Received from Dr Hana Ito",
    },
    "h6zr2tdw9p": {
        "assessment": "1 of 2 submitted",
        "interview": "Not yet",
        "pool": "Awaited from Dr Omar Aziz",
    },
}


# The application form as the Form page builds it (segment AD1B): the
# form's own title and description, then its cards in order. A card is
# a question or text block ("field"), a section's title ("section") or
# a page break ("pagebreak"). The applicant pages still read the two
# lists above until AD4 renders a stored form.
# ASCII digits only, as the page's /^\d+$/: str.isdecimal() takes others.
_DIGITS = re.compile(r"[0-9]+")

CARD_TYPES: tuple[tuple[str, str], ...] = (
    ("string", "String"),
    ("integer", "Integer"),
    ("decimal", "Decimal"),
    ("list", "List"),
    ("photo", "Photo"),
    ("people", "Select people"),
    ("text", "Title and Description"),
)


@dataclass(frozen=True)
class FormCard:
    kind: str  # field, section, pagebreak
    type: str = "string"  # a CARD_TYPES key, for a field
    label: str = ""  # the question, a text block's title, a section's title
    help: str = ""  # help text, or a text block's description
    min: str = ""
    max: str = ""
    step: str = ""
    options: str = ""  # a list's, comma-separated
    exclusive: bool = True  # a list: choose one, else choose any
    ratio_w: str = "4"
    ratio_h: str = "5"
    pool: str = "institution"  # Select people: a PEOPLE_POOLS key
    required: bool = False
    shown: bool = False  # shown to reviewers; a new card is not


SAMPLE_FORM: tuple[FormCard, ...] = (
    FormCard("section", label="About the project"),
    FormCard(
        "field",
        "text",
        "Your proposed project",
        help=(
            "Tell us what you will work on and how. Assessors read the "
            "questions marked shown on your applicant profile."
        ),
        shown=True,
    ),
    FormCard("field", "string", "Project title", min="1", max="120", required=True, shown=True),
    FormCard(
        "field",
        "string",
        "Summary",
        help="What the project asks, why it matters, and what the semester will produce.",
        max="2000",
        required=True,
        shown=True,
    ),
    FormCard(
        "field",
        "string",
        "Methods",
        help="How the work will be done, with a timeline by month.",
        max="2000",
        shown=True,
    ),
    FormCard(
        "field",
        "integer",
        "Months the project will run",
        help="From 1 to 6, in whole months.",
        min="1",
        max="6",
        step="1",
        required=True,
        shown=True,
    ),
    FormCard(
        "field",
        "list",
        "Field of study",
        help="Choose the closest.",
        options="Life Sciences, Engineering, Humanities",
        required=True,
        shown=True,
    ),
    FormCard("pagebreak"),
    FormCard("section", label="About you"),
    FormCard(
        "field",
        "people",
        "Preferred reviewer",
        help="One person from the reviewer pool.",
        min="1",
        max="1",
        pool="pool",
    ),
    FormCard("field", "string", "Matriculation number", min="9", max="9", required=True),
    FormCard(
        "field",
        "decimal",
        "Cumulative GPA",
        help="As on your latest transcript.",
        min="0.00",
        max="5.00",
        step="0.01",
        required=True,
    ),
    FormCard("field", "photo", "Photo", help="A recent head-and-shoulders photo."),
)

FORM_DESCRIPTION = "Tell us about the project you propose for the semester."


def form_cards(exercise_id: str) -> tuple[FormCard, ...]:
    """The Form page's cards: one empty question for a form with none."""
    if exercise_id in EMPTY_FORMS:
        return (FormCard("field"),)
    return SAMPLE_FORM


def form_heading(exercise_id: str) -> tuple[str, str]:
    """The form's own title and description."""
    if exercise_id in EMPTY_FORMS:
        return "", ""
    return "Application form", FORM_DESCRIPTION


def form_snapshot(exercise_id: str) -> dict[str, object]:
    """The form as the preview tab draws it, when the builder that opened
    it cannot hand over its own: a field card has the same keys as the
    page's ``applydeskFormSnapshot()`` (a section or page break more than
    the page sends, read only for ``kind`` and ``label``), a photo's kept
    size worked out here."""
    title, description = form_heading(exercise_id)
    return {
        "exercise": exercise_id,
        "title": title,
        "description": description,
        "cards": [
            {**asdict(c), "kept": kept_size(c.ratio_w, c.ratio_h)} for c in form_cards(exercise_id)
        ],
    }


def kept_size(ratio_w: str, ratio_h: str) -> tuple[int, int] | None:
    """A photo's kept size: 600 px on its longer side, the other by the
    ratio; None for a ratio that is not two positive whole numbers."""
    if not (_DIGITS.fullmatch(ratio_w) and _DIGITS.fullmatch(ratio_h)):
        return None
    w, h = int(ratio_w), int(ratio_h)
    if w <= 0 or h <= 0:
        return None
    # Half up, as the page's Math.round: Python's round() takes a half
    # to the even side (16:7 is 262.5, kept 263 on both).
    if w >= h:
        return 600, math.floor(600 * h / w + 0.5)
    return math.floor(600 * w / h + 0.5), 600


def _span(lo: str, hi: str, unit: str = "") -> str:
    suffix = f" {unit}" if unit else ""
    if lo and hi:
        return f"exactly {lo}{suffix}" if lo == hi else f"{lo} to {hi}{suffix}"
    if hi:
        return f"up to {hi}{suffix}"
    if lo:
        return f"at least {lo}{suffix}"
    return ""


# Who a Select people question may name (segment AD1B): everyone in the
# institution (looked up in Entra ID through Graph once forms are live,
# AD4), or a roster on the Panels page. Keys: "institution", "pool",
# "interviewers", or "panel:" and an assessment panel's name.
#: The sample institution: everyone below, and two more, stand in for
#: the directory Graph searches.
_ELSEWHERE: tuple[tuple[str, str], ...] = (
    ("Daniel Koh", "daniel.koh@example.edu"),
    ("Priya Raman", "priya.raman@example.edu"),
)


def pool_label(key: str) -> str:
    """A pool's name on the card and in its summary."""
    if key.startswith("panel:"):
        return key.removeprefix("panel:")
    return {"pool": "Reviewer pool", "interviewers": "Interviewers"}.get(key, "Institution-wide")


def people_pools(exercise_id: str) -> dict[str, list[tuple[str, str]]]:
    """Each pool a Select people question may use in this exercise, with
    its members (name, email), Institution-wide first."""
    pools: dict[str, list[tuple[str, str]]] = {}
    for a in assessors_of(exercise_id):
        pools.setdefault(f"panel:{a.panel}", []).append((a.name, a.email))
    if pool := pool_of(exercise_id):
        pools["pool"] = [(e.name, e.email) for e in pool]
    if interviewers := interviewers_of(exercise_id):
        pools["interviewers"] = [(e.name, e.email) for e in interviewers]
    everyone = {
        email: (name, email)
        for name, email in [
            *((a.name, a.email) for a in ASSESSORS),
            *((e.name, e.email) for e in (*REVIEWER_POOL, *INTERVIEWERS)),
            *_ELSEWHERE,
        ]
    }
    panels = sorted(k for k in pools if k.startswith("panel:"))
    order = [*panels, *(k for k in ("pool", "interviewers") if k in pools)]
    return {"institution": sorted(everyone.values()), **{k: pools[k] for k in order}}


def _people(lo: str, hi: str) -> str:
    """A people span, "person" where its last number is 1."""
    unit = "person" if (hi or lo) == "1" else "people"
    return _span(lo, hi, unit)


def card_summary(c: FormCard) -> str:
    """A collapsed card's summary of its settings; the page's script
    computes the same as the card is edited."""
    if c.type == "string":
        span = _span(c.min, c.max, "characters")
        return f"String · {span}" if span else "String"
    if c.type in ("integer", "decimal"):
        name = "Integer" if c.type == "integer" else "Decimal"
        parts = [p for p in (_span(c.min, c.max), f"step {c.step}" if c.step else "") if p]
        return f"{name} · {', '.join(parts)}" if parts else name
    if c.type == "list":
        options = ", ".join(o.strip() for o in c.options.split(",") if o.strip())
        choose = "choose one" if c.exclusive else "choose any"
        return f"List · {choose} · {options or 'no options yet'}"
    if c.type == "photo":
        size = kept_size(c.ratio_w, c.ratio_h)
        if size is None:
            return "Photo · ratio not set"
        return f"Photo · {c.ratio_w}:{c.ratio_h}, kept {size[0]} × {size[1]}"
    if c.type == "people":
        parts = [p for p in (_people(c.min, c.max), pool_label(c.pool)) if p]
        return f"Select people · {' · '.join(parts)}"
    return "Title and Description · display only"


#: Exercises whose application form has no questions yet.
EMPTY_FORMS: frozenset[str] = frozenset({"n5wg8tjr3e"})


def form_of(exercise_id: str) -> tuple[tuple[tuple[str, str], ...], tuple[str, ...]]:
    """The application form's two sections: shown to reviewers, not shown."""
    if exercise_id in EMPTY_FORMS:
        return (), ()
    return SHOWN_TO_REVIEWERS, NOT_SHOWN_TO_REVIEWERS


def setup_missing(e: Exercise) -> tuple[tuple[str, str], ...]:
    """What a draft still lacks before it can be published, each with the
    tab that sets it: Setup's, in its order, then the Form's."""
    missing: list[tuple[str, str]] = []
    if not e.code:
        missing.append(("Exercise Code", "setup"))
    if not e.summary:
        missing.append(("Summary", "setup"))
    if "Not set" in (e.opens, e.application_stage_ends):
        missing.append(("Dates", "setup"))
    if e.eligibility == "Not set":
        missing.append(("Who may apply", "setup"))
    if e.public_id in EMPTY_FORMS:
        missing.append(("Application form", "form"))
    return tuple(missing)


def exercise(public_id: str) -> Exercise | None:
    return next((e for e in EXERCISES if e.public_id == public_id), None)


def applications_of(exercise_id: str) -> tuple[Application, ...]:
    return tuple(a for a in APPLICATIONS if a.exercise_id == exercise_id)


def assessors_of(exercise_id: str) -> tuple[Assessor, ...]:
    return tuple(a for a in ASSESSORS if a.exercise_id == exercise_id)


def pool_of(exercise_id: str) -> tuple[Evaluator, ...]:
    return tuple(e for e in REVIEWER_POOL if e.exercise_id == exercise_id)


def interviewers_of(exercise_id: str) -> tuple[Evaluator, ...]:
    return tuple(e for e in INTERVIEWERS if e.exercise_id == exercise_id)


def application(exercise_id: str, public_id: str) -> Application | None:
    return next(
        (a for a in applications_of(exercise_id) if a.public_id == public_id),
        None,
    )


def by_profile(exercise_id: str, profile_id: str) -> Application | None:
    return next(
        (a for a in applications_of(exercise_id) if a.profile_id == profile_id),
        None,
    )
