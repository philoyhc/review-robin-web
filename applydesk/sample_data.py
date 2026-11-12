"""Sample data for the placeholders (segment AD1, item 2): three exercises,
their applications, panels and profile pages, so every page of the URL
map has something to show. Names and addresses are invented; IDs have the
public-ID shape (`applydesk/ids.py`)."""

from __future__ import annotations

from dataclasses import dataclass


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
    "Matriculation number",
    "Expected graduation",
    "Financial aid held",
)


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
