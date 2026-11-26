"""Sample data for the placeholders (segment AD1, item 2): five exercises,
their applications, panels and dossiers, so every page of the URL
map has something to show. Names and addresses are invented; IDs have the
public-ID shape (`applydesk/ids.py`)."""

from __future__ import annotations

import math
import random
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, TypedDict
from zoneinfo import ZoneInfo

from applydesk import clock

if TYPE_CHECKING:
    from applydesk.form_store import Form


@dataclass(frozen=True)
class Exercise:
    public_id: str
    code: str  # the operator's short code, as an RRW session's (unique)
    name: str
    state: str  # Draft, Published, Closed, Archived
    form_open: bool  # the application form takes applications (rulings 14, 15)
    eligibility: str  # "Open to all signed in", "Invitation only"
    blind: bool
    opens: str
    application_stage_ends: str
    expected_outcome: str
    summary: str
    # Review Robin's help contact and timezone for every gate it runs
    # (AD1G amendment): the exercise's, "" taking the operator settings'
    # defaults below, as Review Robin's sessions take its own.
    help_contact: str = ""
    timezone: str = ""
    # The Operator Lobby's Created and Tags (segment AD1T): sample values
    # until AD2B records them; ``created`` is an ISO time with its UTC
    # offset, shown in the exercise's timezone; "" for none.
    created: str = ""
    tags: tuple[str, ...] = ()


#: Apply Desk's operator settings' defaults for a new exercise (a sample
#: value until AD2 keeps the settings).
DEFAULT_HELP_CONTACT = "applydesk-help@example.edu"
DEFAULT_TIMEZONE = "Asia/Singapore"
#: What Details offers (segment AD1I): the default first, then a few an
#: exercise run from elsewhere would want, until AD2 offers the full list.
TIMEZONES = (
    DEFAULT_TIMEZONE,
    "Asia/Hong_Kong",
    "Asia/Tokyo",
    "Australia/Sydney",
    "Europe/London",
    "America/New_York",
    "UTC",
)


def help_contact(e: Exercise) -> str:
    """The exercise's help contact, or the operator settings' default."""
    return e.help_contact or DEFAULT_HELP_CONTACT


def timezone(e: Exercise) -> str:
    """The exercise's timezone, or the operator settings' default."""
    return e.timezone or DEFAULT_TIMEZONE


def utc_offset(zone: str, at: datetime | None = None) -> str:
    """``zone``'s offset from UTC at ``at`` (now by default), as the
    Operator Lobby prints it: "GMT+8", "GMT+5:30", "GMT-4", "GMT"."""
    off = (at or datetime.now(UTC)).astimezone(ZoneInfo(zone)).utcoffset()
    minutes = int(off.total_seconds() // 60) if off else 0
    if not minutes:
        return "GMT"
    sign = "+" if minutes > 0 else "-"
    hours, rest = divmod(abs(minutes), 60)
    return f"GMT{sign}{hours}" + (f":{rest:02d}" if rest else "")


def created_at(e: Exercise) -> datetime | None:
    """When the exercise was created, or None when not recorded."""
    return datetime.fromisoformat(e.created) if e.created else None


def created_label(e: Exercise) -> str:
    """When the exercise was created, in its own timezone, as the Lobby
    prints it ("2026-08-04 09:12"), or "" when not recorded."""
    at = created_at(e)
    return clock.stamp(at, timezone(e)) if at else ""


def newest_first(exercises: Iterable[Exercise]) -> tuple[Exercise, ...]:
    """``exercises`` newest first, as the Lobby's Created arrow says
    (segment AD1T); one not recorded goes last, ties keep their order."""
    oldest = datetime.min.replace(tzinfo=UTC)
    return tuple(sorted(exercises, key=lambda e: created_at(e) or oldest, reverse=True))


def all_tags(exercises: Iterable[Exercise]) -> list[str]:
    """Every tag on ``exercises``, once each, sorted ignoring case."""
    return sorted({t for e in exercises for t in e.tags}, key=str.casefold)


@dataclass(frozen=True)
class Application:
    public_id: str
    exercise_id: str
    applicant: str
    email: str
    title: str
    state: str  # Draft, Submitted, Withdrawn
    submitted: str  # the day it was submitted, else started: "3 Sep 2026"
    dossier_id: str
    #: Stored (segment AD2J): when it was started, and submitted (None for a draft).
    started_at: datetime | None = None
    submitted_at: datetime | None = None


@dataclass(frozen=True)
class Assessor:
    exercise_id: str
    name: str
    email: str
    asked_to_review: tuple[str, ...]  # application public IDs (ruling 9)


@dataclass(frozen=True)
class Evaluator:
    """Someone on a roster that is not an assessment panel: the pool
    applicants choose a reviewer from, or the interviewers."""

    exercise_id: str
    name: str
    email: str
    note: str


@dataclass(frozen=True)
class Member:
    """Someone on a panel: an email, unique in the panel; a name; a note
    (a role or an area)."""

    name: str
    email: str
    note: str = ""


@dataclass(frozen=True)
class Panel:
    """A named roster Apply Desk keeps (rulings 4, 19): an assessment
    panel, the reviewer pool, the interviewers. A Select people question
    and a gate name it by ``key``."""

    exercise_id: str
    key: str
    name: str
    members: tuple[Member, ...]


class Pool(TypedDict):
    """A panel as a Select people question reads it, Institution-wide
    included: its name and its members (name, email)."""

    name: str
    members: list[tuple[str, str]]


EXERCISES: tuple[Exercise, ...] = (
    Exercise(
        public_id="wa9juxbc2t",
        code="RA-2027",
        name="Recruitment and Selection of Residential Assistants",
        state="Published",
        # The model exercise (ruling 30, segment AD1H): the author's RA
        # recruitment, in the middle of Stage 3, its interview pairs being
        # approved (`applydesk/stages.py`).
        form_open=False,
        eligibility="Open to all signed in",
        blind=False,
        opens="1 Sep 2026",
        application_stage_ends="30 Sep 2026, 23:59",
        expected_outcome="December 2026",
        summary=(
            "Residential Assistants look after the residents of their house for"
            " the 2027/28 academic year; current RAs may apply to return."
        ),
        help_contact="ra-recruitment@example.edu",
        created="2026-08-04T09:12+08:00",
        tags=("Residential", "2027"),
    ),
    Exercise(
        public_id="k7mfr3pq8z",
        code="TEA-2026",
        name="Teaching Excellence Award 2026",
        state="Published",
        form_open=False,
        eligibility="Invitation only",
        blind=True,
        opens="1 Sep 2026",
        application_stage_ends="31 Oct 2026, 23:59",
        expected_outcome="December 2026",
        summary="Nominated teachers submit a teaching portfolio; a panel reads it blind.",
        created="2026-07-21T14:30+08:00",
        tags=("Awards",),
    ),
    Exercise(
        public_id="c4xh2ndv6s",
        code="SIS-2027",
        name="Summer Internship Scheme 2027",
        state="Draft",
        form_open=True,
        eligibility="Open to all signed in",
        blind=False,
        opens="Not set",
        application_stage_ends="Not set",
        expected_outcome="Not set",
        summary="Placements with partner organizations over the summer vacation.",
        created="2026-10-30T16:45+08:00",
        tags=(),
    ),
    # Open for applications, now that the model exercise is past its
    # Call for applications (segment AD1C).
    Exercise(
        public_id="r6tm4kq9wz",
        code="PCG-2027",
        name="Postgraduate Conference Grant 2027",
        state="Published",
        form_open=True,
        eligibility="Open to all signed in",
        blind=False,
        opens="1 Nov 2026",
        application_stage_ends="31 Jan 2027, 23:59",
        expected_outcome="Early March 2027",
        summary="Travel and registration for presenting at an international conference.",
        created="2026-10-06T10:02+08:00",
        tags=("Grants", "2027"),
    ),
    # Just created: a name and nothing else, awaiting setup (author,
    # 2026-11-12).
    Exercise(
        public_id="n5wg8tjr3e",
        code="",
        name="Graduate Travel Grant 2027",
        state="Draft",
        form_open=True,
        eligibility="Not set",
        blind=False,
        opens="Not set",
        application_stage_ends="Not set",
        expected_outcome="Not set",
        summary="",
        created="2026-11-12T15:40+08:00",
        tags=("Grants",),
    ),
)

#: The samples' IDs: every other exercise is an ordinary one (segment AD2G).
SAMPLE_IDS: frozenset[str] = frozenset(e.public_id for e in EXERCISES)

_WRITTEN: tuple[Application, ...] = (
    # The model exercise's (ruling 30): Aisha a current RA applying to
    # return, Kenji a new applicant, Wen's still a draft.
    Application(
        "m3qx8vkt2n",
        "wa9juxbc2t",
        "Aisha Bello",
        "aisha.bello@example.edu",
        "RA application · Tembusu House",
        "Submitted",
        "3 Sep 2026",
        "p3bd7kq2wx",
    ),
    Application(
        "h6zr2tdw9p",
        "wa9juxbc2t",
        "Kenji Russo",
        "kenji.russo@example.edu",
        "RA application · Cendana House",
        "Submitted",
        "5 Sep 2026",
        "r9ck4xbm7t",
    ),
    Application(
        "f2ps7nyh4k",
        "wa9juxbc2t",
        "Wen Novak",
        "wen.novak@example.edu",
        "RA application · Saga House",
        "Draft",
        "14 Sep 2026",
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
        "x3vb7ndq5h",
        "r6tm4kq9wz",
        "Lucia Ferrari",
        "lucia.ferrari@example.edu",
        "Presenting at the European Geosciences Union",
        "Submitted",
        "8 Nov 2026",
        "y8kc2mtw4r",
    ),
    Application(
        "z5hp9rkd3m",
        "r6tm4kq9wz",
        "Tomas Herrera",
        "tomas.herrera@example.edu",
        "A poster at the Linguistic Society of America",
        "Draft",
        "11 Nov 2026",
        "a4nw6qxt8c",
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

# The model exercise's other applications, generated with a fixed seed
# so the Dossiers page reads as a real call of about 100 (segment
# AD1C): names, IDs, statuses and dates are the same on every run.
_FIRST = (
    "Aisha",
    "Ben",
    "Chen",
    "Divya",
    "Ethan",
    "Farah",
    "Gabriel",
    "Hana",
    "Ivan",
    "Jia",
    "Kofi",
    "Lena",
    "Mateo",
    "Nadia",
    "Omar",
    "Priya",
    "Quinn",
    "Rosa",
    "Samir",
    "Tara",
    "Umar",
    "Vera",
    "Wei",
    "Xavier",
    "Yuki",
    "Zara",
    "Arjun",
    "Bea",
    "Caleb",
    "Dina",
)
_LAST = (
    "Rahman",
    "Carter",
    "Wei",
    "Nair",
    "Lim",
    "Ismail",
    "Ortiz",
    "Sato",
    "Petrova",
    "Huang",
    "Mensah",
    "Fischer",
    "Silva",
    "Haddad",
    "Farouk",
    "Raman",
    "Byrne",
    "Moreno",
    "Kapoor",
    "Lund",
    "Tanaka",
    "Okafor",
    "Novak",
    "Duarte",
    "Yilmaz",
    "Kowalski",
    "Ng",
    "Abbott",
)
#: The houses an RA may serve in (ruling 30's sample).
RESIDENCES: tuple[str, ...] = ("Cendana House", "Elm House", "Saga House", "Tembusu House")


def _person(n: int, names: set[str]) -> tuple[str, str]:
    """The ``n``-th invented person, a name not yet in ``names``."""
    first, k = _FIRST[n % len(_FIRST)], (n * 7) % len(_LAST)
    while f"{first} {_LAST[k]}" in names:  # one person per name
        k = (k + 1) % len(_LAST)
    name = f"{first} {_LAST[k]}"
    names.add(name)
    return name, f"{first.lower()}.{_LAST[k].lower()}@example.edu"


def _generated() -> tuple[Application, ...]:
    """The model exercise's other applications (ruling 30): one each, 98
    more submitted (100 in all), two drafts and one withdrawn before the
    form closed; names, IDs and dates the same on every run."""
    from applydesk.ids import PUBLIC_ID_ALPHABET, PUBLIC_ID_LENGTH

    rng = random.Random("wa9juxbc2t ra")
    taken = {"m3qx8vkt2n", "h6zr2tdw9p", "f2ps7nyh4k", "b8yd3mkr6v", "q4tw9hcz3x"}

    def new_id() -> str:
        while True:
            value = "".join(rng.choice(PUBLIC_ID_ALPHABET) for _ in range(PUBLIC_ID_LENGTH))
            if value not in taken:
                taken.add(value)
                return value

    states = ["Submitted"] * 98 + ["Draft"] * 2 + ["Withdrawn"]
    rng.shuffle(states)
    names = {"Aisha Bello", "Kenji Russo", "Wen Novak"}
    made: list[Application] = []
    for n, state in enumerate(states):
        name, email = _person(n, names)
        day = 18 if state == "Withdrawn" else rng.randint(2, 30)
        made.append(
            Application(
                new_id(),
                "wa9juxbc2t",
                name,
                email,
                f"RA application · {rng.choice(RESIDENCES)}",
                state,
                f"{day} Sep 2026",
                new_id(),
            )
        )
    return tuple(made)


APPLICATIONS: tuple[Application, ...] = _WRITTEN + _generated()


def _current_ras() -> tuple[Member, ...]:
    """The 30 current RAs (ruling 30): 20 applying to return, Aisha among
    them, and 10 who are not; each with their house."""
    rng = random.Random("wa9juxbc2t current RAs")
    mine = [a for a in APPLICATIONS if a.exercise_id == "wa9juxbc2t" and a.state == "Submitted"]
    returning = [mine[0], *rng.sample([a for a in mine[2:]], 19)]  # Aisha; never Kenji
    names = {a.applicant for a in APPLICATIONS}
    leaving = [_person(200 + n, names) for n in range(10)]
    people = [(a.applicant, a.email) for a in returning] + leaving
    return tuple(
        Member(name, email, RESIDENCES[i % len(RESIDENCES)])
        for i, (name, email) in enumerate(people)
    )


CURRENT_RAS: tuple[Member, ...] = _current_ras()

ASSESSORS: tuple[Assessor, ...] = (
    Assessor("k7mfr3pq8z", "Priya Rao", "priya.rao@example.edu", ("b8yd3mkr6v", "q4tw9hcz3x")),
    Assessor("k7mfr3pq8z", "Mei Chen", "mei.chen@example.edu", ("q4tw9hcz3x",)),
)

# The exercises' panels (ruling 19), one sample each kind: assessment
# panels, the pool an applicant chooses a reviewer from, the interviewers.
# ASSESSORS above keeps only who each assessor is asked to review (AD5,
# AD6); which panel they sit on is here.
PANELS: tuple[Panel, ...] = (
    # The model exercise's three (ruling 30): the current RAs, who review
    # every applicant but themselves; the offices, who check every one;
    # the residential staff, two of whom interview each shortlisted.
    Panel("wa9juxbc2t", "current-ras", "Current RAs", CURRENT_RAS),
    Panel(
        "wa9juxbc2t",
        "office",
        "Office staff",
        (
            Member("Grace Lim", "grace.lim@example.edu", "Housing Office"),
            Member("Daniel Ong", "daniel.ong@example.edu", "Student Conduct"),
            Member("Farida Hassan", "farida.hassan@example.edu", "Counselling"),
            Member("Marcus Wee", "marcus.wee@example.edu", "Finance"),
            Member("Irene Goh", "irene.goh@example.edu", "Student Life"),
        ),
    ),
    Panel(
        "wa9juxbc2t",
        "residential-staff",
        "Residential staff",
        tuple(
            Member(name, f"{name.split()[-2].lower()}.{name.split()[-1].lower()}@example.edu", note)
            for name, note in (
                ("Dr Hana Ito", "Master, Tembusu House"),
                ("Dr Omar Aziz", "Master, Cendana House"),
                ("Dr Ruth Kahn", "Master, Elm House"),
                ("Dr Sara Ng", "Master, Saga House"),
                ("Prof Ivan Petrov", "Resident Fellow"),
                ("Dr Mei Lin", "Resident Fellow"),
                ("Dr Tom Reyes", "Resident Fellow"),
                ("Dr Asha Nair", "Resident Fellow"),
                ("Dr Ken Sato", "Resident Fellow"),
                ("Dr Lucy Park", "Resident Fellow"),
                ("Ms Joy Tan", "Residence Manager"),
                ("Mr Ravi Das", "Residence Manager"),
                ("Ms Nora Lee", "Residential Life"),
            )
        ),
    ),
    # The conference grant, open for applications, has its panels ready
    # (AD1H: the fellowship's four, the builders' sample since the model
    # exercise became the RA recruitment).
    Panel(
        "r6tm4kq9wz",
        "panel-a",
        "Panel A",
        (Member("Zoe Tan", "zoe.tan@example.edu"), Member("Lars Berg", "lars.berg@example.edu")),
    ),
    Panel("r6tm4kq9wz", "panel-b", "Panel B", (Member("Ana Lim", "ana.lim@example.edu"),)),
    Panel(
        "r6tm4kq9wz",
        "pool",
        "Evaluator pool",
        (
            Member("Dr Hana Ito", "hana.ito@example.edu", "Life Sciences"),
            Member("Dr Omar Aziz", "omar.aziz@example.edu", "Engineering"),
            Member("Dr Ruth Kahn", "ruth.kahn@example.edu", "Humanities"),
        ),
    ),
    Panel(
        "r6tm4kq9wz",
        "interviewers",
        "Interviewers",
        (
            Member("Prof Ivan Petrov", "ivan.petrov@example.edu", "Chair"),
            Member("Dr Sara Ng", "sara.ng@example.edu"),
        ),
    ),
    Panel(
        "k7mfr3pq8z",
        "panel-a",
        "Panel A",
        (Member("Priya Rao", "priya.rao@example.edu"), Member("Mei Chen", "mei.chen@example.edu")),
    ),
    Panel(
        "k7mfr3pq8z",
        "interviewers",
        "Interviewers",
        (Member("Prof Ben Ortiz", "ben.ortiz@example.edu", "Chair"),),
    ),
)


def _roster(exercise_id: str, key: str) -> tuple[Evaluator, ...]:
    panel = next((p for p in panels_of(exercise_id) if p.key == key), None)
    if panel is None:
        return ()
    return tuple(Evaluator(exercise_id, m.name, m.email, m.note) for m in panel.members)


# The application form as the Form page builds it (segment AD1B): the
# form's own title and description, then its cards in order. A card is
# a question or text block ("field"), a section's title ("section") or
# a page break ("pagebreak"). The applicant and dossier pages read these
# cards with Extract's answers (``extract.form_answers``, AD-26).
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
    pool: str = "institution"  # Select people: "institution" or a Panel key
    required: bool = False
    shown: bool = False  # shown to evaluators; a new card is not
    # Its handle (segment AD2D; AD-45): ``q<n>``, kept through a rename, so
    # a rule names the question by it. Blank on a card no save has keyed.
    key: str = ""


SAMPLE_FORM: tuple[FormCard, ...] = (
    FormCard("section", label="About the project"),
    FormCard(
        "field",
        "text",
        "Your proposed project",
        help=("Tell us what you will work on and how. Evaluators read the questions marked shown."),
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
        "Preferred evaluator",
        help="If you have a preference.",
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

#: The model exercise's form (ruling 30): the usual fields, whether the
#: applicant is a current RA among them, which its rules read.
_RA_FORM: tuple[FormCard, ...] = (
    FormCard("section", label="About you"),
    FormCard(
        "field",
        "text",
        "Applying to be a Residential Assistant",
        help=(
            "Your name and email come from your sign-in."
            " Evaluators read the questions marked shown."
        ),
        shown=True,
    ),
    FormCard("field", "string", "Preferred name", max="60"),
    FormCard("field", "string", "Matriculation number", min="9", max="9", required=True),
    FormCard(
        "field",
        "list",
        "Year of study",
        options="Year 1, Year 2, Year 3, Year 4, Graduate",
        required=True,
        shown=True,
    ),
    FormCard(
        "field",
        "list",
        "Faculty",
        options=(
            "Arts and Social Sciences, Business, Computing, Engineering, Law, Medicine, Science"
        ),
        required=True,
        shown=True,
    ),
    FormCard(
        "field",
        "list",
        "Currently an RA?",
        help="Yes if you are an RA this year and apply to return.",
        options="Yes, No",
        required=True,
        shown=True,
    ),
    FormCard(
        "field",
        "list",
        "Residence",
        help="The house you would serve in.",
        options=", ".join(RESIDENCES),
        required=True,
        shown=True,
    ),
    FormCard("pagebreak"),
    FormCard("section", label="Your application"),
    FormCard(
        "field",
        "string",
        "Why you want to be an RA",
        help="What you would bring to your house's residents.",
        max="2000",
        required=True,
        shown=True,
    ),
    FormCard(
        "field",
        "string",
        "Relevant experience",
        help="Leadership, peer support or community work.",
        max="2000",
        shown=True,
    ),
    FormCard("field", "photo", "Photo", help="A recent head-and-shoulders photo."),
)
_RA_DESCRIPTION = "Apply to be a Residential Assistant for 2027/28, or to return as one."


def _stored_form(exercise_id: str) -> Form | None:
    """The exercise's form as Form last saved it (segment AD2D), else None:
    never saved, it reads the sample's."""
    from applydesk import form_store  # it builds on this module

    return form_store.stored(exercise_id)


def _blank_form(exercise_id: str) -> bool:
    """An exercise whose form starts with no questions: the sample's empty
    draft, or an ordinary exercise (segment AD2G)."""
    return exercise_id in EMPTY_FORMS or not is_sample(exercise_id)


def form_is_empty(exercise_id: str) -> bool:
    """A form with no questions: as Form last saved it, else the sample's
    empty draft or an ordinary exercise's."""
    own = _stored_form(exercise_id)
    if own is not None:
        return not any(c.kind == "field" for c in own.cards)
    return _blank_form(exercise_id)


def form_cards(exercise_id: str) -> tuple[FormCard, ...]:
    """The Form page's cards, as Form last saved them, else the sample's:
    one empty question for a form with none."""
    own = _stored_form(exercise_id)
    if own is not None:
        cards: tuple[FormCard, ...] = own.cards
    elif _blank_form(exercise_id):
        cards = ()
    else:
        cards = sample_form(exercise_id)
    if not cards:
        return (FormCard("field"),)
    # A pool this exercise has no roster for reads as Institution-wide,
    # so the summary, the card's menu and Preview agree.
    pools = people_pools(exercise_id)
    return tuple(
        replace(c, pool="institution") if c.type == "people" and c.pool not in pools else c
        for c in cards
    )


def sample_form(exercise_id: str) -> tuple[FormCard, ...]:
    """The sample's own cards, keyed ``q1``… in order, the keys its first
    save keeps (segment AD2D); none for an empty draft or an ordinary
    exercise."""
    if _blank_form(exercise_id):
        return ()
    cards = _RA_FORM if exercise_id == "wa9juxbc2t" else SAMPLE_FORM
    return tuple(replace(c, key=f"q{n}") for n, c in enumerate(cards, 1))


def form_heading(exercise_id: str) -> tuple[str, str]:
    """The form's own title and description, as Form last saved them,
    else the sample's."""
    own = _stored_form(exercise_id)
    if own is not None:
        return own.title, own.description
    if _blank_form(exercise_id):
        return "", ""
    return "Application form", (
        _RA_DESCRIPTION if exercise_id == "wa9juxbc2t" else FORM_DESCRIPTION
    )


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
# AD4), or one of the exercise's panels (ruling 19), by its key.
#: The sample institution: everyone below, and two more, stand in for
#: the directory Graph searches.
_ELSEWHERE: tuple[tuple[str, str], ...] = (
    ("Daniel Koh", "daniel.koh@example.edu"),
    ("Priya Raman", "priya.raman@example.edu"),
)
INSTITUTION = "Institution-wide"


def _stored_panels(
    exercise_id: str,
) -> tuple[tuple[Panel, ...], tuple[tuple[Member, frozenset[str]], ...]] | None:
    """The exercise's panels and roster as Panels last saved them (segment
    AD2E), else None: never saved, it reads the sample's."""
    from applydesk import panels_store  # it builds on this module

    found = panels_store.stored(exercise_id)
    return (found.panels, found.roster) if found is not None else None


def panels_of(exercise_id: str) -> tuple[Panel, ...]:
    own = _stored_panels(exercise_id)
    if own is not None:
        return own[0]
    return tuple(p for p in PANELS if p.exercise_id == exercise_id)


def people_pools(exercise_id: str) -> dict[str, Pool]:
    """Each pool a Select people question may use in this exercise:
    Institution-wide first, then its panels in order."""
    everyone = {
        email: (name, email)
        for name, email in [
            *((m.name, m.email) for p in PANELS for m in p.members),
            *((m.name, m.email) for m, _ in (_stored_panels(exercise_id) or ((), ()))[1]),
            *((a.name, a.email) for a in ASSESSORS),
            *_ELSEWHERE,
        ]
    }
    pools: dict[str, Pool] = {
        "institution": {"name": INSTITUTION, "members": sorted(everyone.values())}
    }
    for p in panels_of(exercise_id):
        pools[p.key] = {"name": p.name, "members": [(m.name, m.email) for m in p.members]}
    return pools


def field_key(exercise_id: str, ref: str, of_type: str) -> str | None:
    """The key of the field of type ``of_type`` that ``ref`` names (segment
    AD2D): its key; else, for a reference stored before keys, the key the
    sample's form gave that label while the form still holds it; else the
    first field carrying that label; None if none does."""
    cards = [
        c for c in form_cards(exercise_id) if c.kind == "field" and c.type == of_type and c.key
    ]
    keys = {c.key for c in cards}
    if ref in keys:
        return ref
    sample = {c.label: c.key for c in sample_form(exercise_id) if c.kind == "field"}
    if sample.get(ref) in keys:
        return sample[ref]
    return next((c.key for c in cards if (c.label or "Untitled question") == ref), None)


def nominees(exercise_id: str, application: Application, question: str) -> tuple[str, ...]:
    """Whom an applicant named in a *Select people* question, named by key
    (a label stored before keys is read through it), by email (segment
    AD1G's sample): drawn from the question's pool, up to its max, one
    applicant in five naming no one, seeded by the question's key so a
    rename keeps them. Nothing is stored until AD4."""
    key = field_key(exercise_id, question, "people")
    card = next((c for c in form_cards(exercise_id) if key and c.key == key), None)
    if card is None:
        return ()
    pools = people_pools(exercise_id)
    members = pools.get(card.pool, pools["institution"])["members"]
    rng = random.Random(f"nominee {application.public_id} {card.key}")
    if not members or rng.random() < 0.2:
        return ()
    most = int(card.max) if _DIGITS.fullmatch(card.max) else 1
    return tuple(email for _, email in rng.sample(members, min(max(most, 1), len(members))))


@dataclass(frozen=True)
class ListQuestion:
    """A choose-one *List* question a rule's form condition may read
    (ruling 30): its key (segment AD2D), its label and its options."""

    key: str
    label: str
    options: tuple[str, ...]


def list_questions(exercise_id: str) -> dict[str, ListQuestion]:
    """The form's choose-one *List* questions, by key (segment AD2D, AD-45):
    what a rule's form-answer condition may read (ruling 30)."""
    out: dict[str, ListQuestion] = {}
    for c in form_cards(exercise_id):
        if c.kind == "field" and c.type == "list" and c.exclusive and c.key:
            options = tuple(o.strip() for o in c.options.split(",") if o.strip())
            out[c.key] = ListQuestion(c.key, c.label or "Untitled question", options)
    return out


def answers(exercise_id: str, application: Application) -> dict[str, str]:
    """The application's answers to the form's *List* questions, by key
    (ruling 30's form-answer condition reads them): a choose-one list's
    option, seeded per application and question key. Nothing is stored
    until AD4."""
    out: dict[str, str] = {}
    questions = list_questions(exercise_id)
    for key, q in questions.items():
        if q.options:
            seed = f"answer {application.public_id} {key}"  # a rename keeps it
            out[key] = random.Random(seed).choice(list(q.options))
    if exercise_id == "wa9juxbc2t":  # what the sample knows, not chance
        # By the key the sample's form gave each, so a rename keeps it.
        keys = {c.label: c.key for c in sample_form(exercise_id)}
        ras = {m.email.casefold() for m in CURRENT_RAS}
        if keys.get("Currently an RA?") in questions:
            current = application.email.casefold() in ras
            out[keys["Currently an RA?"]] = "Yes" if current else "No"
        if keys.get("Residence") in questions:
            out[keys["Residence"]] = application.title.split(" · ")[-1]
    return out


def roster(exercise_id: str) -> tuple[tuple[Member, frozenset[str]], ...]:
    """Everyone on the exercise's panels, once each (by email, any case),
    in the order first met, with the keys of the panels they sit on: the
    Panels table's rows (ruling 20). A name or a note left blank where
    first met is taken from a later panel that gives one; a name that is
    only the email counts as blank. Once Panels is saved, its roster as
    saved (segment AD2E), someone on no panel included."""
    own = _stored_panels(exercise_id)
    if own is not None:
        return own[1]
    rows: dict[str, tuple[Member, set[str]]] = {}
    for p in panels_of(exercise_id):
        for m in p.members:
            k = m.email.lower()
            if k not in rows:
                rows[k] = (m, set())
            else:
                seen = rows[k][0]
                if seen.name in ("", seen.email) and m.name not in ("", m.email):
                    seen = replace(seen, name=m.name)
                if not seen.note and m.note:
                    seen = replace(seen, note=m.note)
                rows[k] = (seen, rows[k][1])
            rows[k][1].add(p.key)
    return tuple((m, frozenset(keys)) for m, keys in rows.values())


def panel_pools(exercise_id: str) -> dict[str, Pool]:
    """The exercise's panels alone, in order, as a gate picks from them:
    a gate is evaluated by a panel, never Institution-wide."""
    return {k: p for k, p in people_pools(exercise_id).items() if k != "institution"}


def _people(lo: str, hi: str) -> str:
    """A people span, "person" where its last number is 1."""
    unit = "person" if (hi or lo) == "1" else "people"
    return _span(lo, hi, unit)


def card_summary(c: FormCard, pools: dict[str, Pool] | None = None) -> str:
    """A collapsed card's summary of its settings; the page's script
    computes the same as the card is edited. A Select people card names
    its pool from ``pools`` (the exercise's), else Institution-wide."""
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
        pool = (pools or {}).get(c.pool)
        parts = [p for p in (_people(c.min, c.max), pool["name"] if pool else INSTITUTION) if p]
        return f"Select people · {' · '.join(parts)}"
    return "Title and Description · display only"


#: Exercises whose application form has no questions yet.
EMPTY_FORMS: frozenset[str] = frozenset({"n5wg8tjr3e"})


def setup_missing(e: Exercise) -> tuple[tuple[str, str], ...]:
    """What a draft still lacks before it can be published, each with the
    page that sets it ("" for Home's details, ruling 14): Home's, then
    Process's, then the Form's."""
    missing: list[tuple[str, str]] = []
    if not e.code:
        missing.append(("Exercise code", ""))
    if not e.summary:
        missing.append(("Description", ""))
    if e.eligibility == "Not set":
        missing.append(("Who may apply", ""))
    if "Not set" in (e.opens, e.application_stage_ends):
        missing.append(("Dates", "process"))
    # Only a timeline holding the form owes its questions (segment AD2K):
    # one begun by Populate Dossiers has none to write.
    from applydesk import stages  # it builds on this module

    if stages.plan_of(e.public_id).form_stage is not None and form_is_empty(e.public_id):
        missing.append(("Application form", "form"))
    return tuple(missing)


def is_sample(public_id: str) -> bool:
    """Whether the exercise is one of the fixed samples (segment AD2G):
    every other exercise is an ordinary one, made by *New exercise* or
    *Duplicate*, with no sample stages, form, emails or applications."""
    return public_id in SAMPLE_IDS


def sample(public_id: str) -> Exercise | None:
    """The fixed sample with this ID, else None: no database read, so a
    caller inside a transaction may ask (cold read, AD2G)."""
    return next((e for e in EXERCISES if e.public_id == public_id), None)


def exercise(public_id: str) -> Exercise | None:
    """An exercise by ID: a sample, else an ordinary exercise's row
    (segment AD2G), else None."""
    found = sample(public_id)
    if found is not None:
        return found
    from applydesk import exercises as store  # it builds on this module

    return store.ordinary(public_id)


def exercises() -> tuple[Exercise, ...]:
    """Every exercise on record: the ordinary ones, newest first, then the
    fixed samples (segment AD2G). Deleted ones are left out; archived ones
    are not, for the Archive."""
    from applydesk import exercises as store

    return store.ordinaries() + EXERCISES


#: The signed-in applicant's applications on the /me pages, a submitted one
#: and a draft, until AD2 matches them by email (AD-27).
MINE = ("m3qx8vkt2n", "f2ps7nyh4k")

#: The dossiers the signed-in person reviews on /me (ruling 9), by their
#: applications' IDs, until AD5 pairs them.
MY_REVIEWS = tuple(a.public_id for a in APPLICATIONS[1:5:2])


def my_applications(exercise_id: str | None = None) -> tuple[Application, ...]:
    """The sample applicant's applications, of one exercise or all (AD-27)."""
    from applydesk import applications  # it builds on this module

    return tuple(
        a
        for a in applications.with_ids(MINE)
        if exercise_id is None or a.exercise_id == exercise_id
    )


def sample_applications(exercise_id: str) -> tuple[Application, ...]:
    """A sample exercise's applications as written here: what the seed
    records (segment AD2J). Pages read `applications_of`."""
    return tuple(a for a in APPLICATIONS if a.exercise_id == exercise_id)


def applications_of(exercise_id: str) -> tuple[Application, ...]:
    """The exercise's applications as stored (segment AD2J), in the order
    they came in."""
    from applydesk import applications  # it builds on this module

    return applications.of(exercise_id)


def assessors_of(exercise_id: str) -> tuple[Assessor, ...]:
    return tuple(a for a in ASSESSORS if a.exercise_id == exercise_id)


def pool_of(exercise_id: str) -> tuple[Evaluator, ...]:
    return _roster(exercise_id, "pool")


def interviewers_of(exercise_id: str) -> tuple[Evaluator, ...]:
    return _roster(exercise_id, "interviewers")


def application(exercise_id: str, public_id: str) -> Application | None:
    return next(
        (a for a in applications_of(exercise_id) if a.public_id == public_id),
        None,
    )


def by_dossier(exercise_id: str, dossier_id: str) -> Application | None:
    if not dossier_id:
        return None
    return next(
        (a for a in applications_of(exercise_id) if a.dossier_id == dossier_id),
        None,
    )
