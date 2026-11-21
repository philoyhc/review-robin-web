"""The URL map as placeholders (segment AD1, item 2): every page answers
locally, IDs are shape-checked, the gate holds deployed, every link stays
in the mount, and a blind dossier names nobody."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from html.parser import HTMLParser
from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from applydesk import extract, gate, locks, paging, sample_data, stages, workflow
from applydesk.ids import PUBLIC_ID_ALPHABET, PUBLIC_ID_LENGTH, generate_public_id, is_public_id
from applydesk.main import create_app
from applydesk.tests._host import host_with
from cordware.identity import Identity

EX = "wa9juxbc2t"  # the model exercise: not blind, its Interview stage under way
OPEN = "r6tm4kq9wz"  # open for applications
BLIND = "k7mfr3pq8z"  # blind, in its unnamed Stage 2
DRAFT = "c4xh2ndv6s"  # not published
BLANK = "n5wg8tjr3e"  # just created: a name, nothing else

PAGES = (
    "/applydesk/",
    "/applydesk/operator/exercises",
    "/applydesk/admin/operators",  # the super-admin's (segment AD2A)
    f"/applydesk/operator/exercises/{EX}",
    *(
        f"/applydesk/operator/exercises/{EX}/{section}"
        for section in (
            "process",
            "form",
            "panels",
            "emails",
            "dossiers",
            "evaluations",
            "extract",
        )
    ),
    f"/applydesk/operator/exercises/{EX}/form/preview",
    f"/applydesk/operator/exercises/{EX}/evaluations/gate_1",  # a gate's own page (AD1H)
    f"/applydesk/operator/exercises/{EX}/dossiers/p3bd7kq2wx",  # a dossier, the operator's (AD1P)
    f"/applydesk/operator/exercises/{EX}/evaluations/gate_2?q=lim&offset=200",
    f"/applydesk/operator/exercises/{OPEN}",  # open for applications
    f"/applydesk/operator/exercises/{OPEN}/dossiers",  # only its first stage
    f"/applydesk/operator/exercises/{BLANK}/form/preview",
    f"/applydesk/operator/exercises/{BLIND}",  # in Stage 2; blind review on
    f"/applydesk/operator/exercises/{BLIND}/process",  # a panel no gate uses
    f"/applydesk/operator/exercises/{BLIND}/evaluations",  # blind: the alias key
    f"/applydesk/operator/exercises/{BLIND}/evaluations/gate_1",
    f"/applydesk/operator/exercises/{DRAFT}/process",  # the Setup stage is now
    f"/applydesk/operator/exercises/{DRAFT}",  # the Publish step
    f"/applydesk/operator/exercises/{DRAFT}/dossiers",  # none yet
    f"/applydesk/operator/exercises/{BLANK}",
    *(
        f"/applydesk/operator/exercises/{BLANK}/{section}"
        for section in (
            "process",
            "form",
            "panels",
            "emails",
            "dossiers",
            "evaluations",
            "extract",
        )
    ),
    "/applydesk/me",
    f"/applydesk/me/exercises/{EX}",
    f"/applydesk/me/exercises/{BLIND}",  # applications have closed
    f"/applydesk/me/exercises/{EX}/applications/m3qx8vkt2n",
    f"/applydesk/me/exercises/{EX}/dossiers/p3bd7kq2wx",
    f"/applydesk/me/exercises/{BLIND}/dossiers/t8nv4hzm2c",
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(host_with(("applydesk",))[0])


@pytest.mark.parametrize("path", PAGES)
def test_every_page_of_the_map_answers_locally(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 200, path
    assert "Placeholder." in response.text


@pytest.mark.parametrize(
    "path",
    [
        "/applydesk/operator/exercises/WA9JUXBC2T",  # uppercase is not the alphabet
        "/applydesk/operator/exercises/wa9juxbc2",  # nine characters
        "/applydesk/operator/exercises/wa9juxbc2t0",  # eleven
        "/applydesk/operator/exercises/wa9juxbc1t",  # a look-alike
        "/applydesk/operator/exercises/zzzzzzzzzz",  # well formed, unknown
        f"/applydesk/operator/exercises/{EX}/bogus",
        f"/applydesk/operator/exercises/{EX}/applications",  # Dossiers since ruling 25
        "/applydesk/me/exercises/c4xh2ndv6s",  # a draft is not open to applicants
        f"/applydesk/me/exercises/{BLANK}",
        f"/applydesk/me/exercises/{EX}/applications/zzzzzzzzzz",
        f"/applydesk/me/exercises/{EX}/applications/M3QX8VKT2N",  # an application ID's shape
        f"/applydesk/me/exercises/{EX}/applications/m3qx8vkt2",
        f"/applydesk/me/exercises/{EX}/dossiers/P3BD7KQ2WX",  # a dossier ID's shape
        f"/applydesk/me/exercises/{EX}/dossiers/p3bd7kq2wx0",
        f"/applydesk/me/exercises/{EX}/dossiers/m3qx8vkt2n",  # an application ID is no dossier ID
        f"/applydesk/me/exercises/{BLIND}/dossiers/p3bd7kq2wx",  # another exercise's dossier
    ],
)
def test_a_malformed_or_unknown_id_is_a_404(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 404, path


def test_public_ids_have_rrw_s_shape() -> None:
    assert PUBLIC_ID_ALPHABET == "23456789abcdefghjkmnpqrstuvwxyz" and PUBLIC_ID_LENGTH == 10
    for _ in range(50):
        assert is_public_id(generate_public_id())
    samples = [e.public_id for e in sample_data.EXERCISES]
    samples += [a.public_id for a in sample_data.APPLICATIONS]
    samples += [a.dossier_id for a in sample_data.APPLICATIONS]
    assert all(is_public_id(s) for s in samples)
    assert len(set(samples)) == len(samples)


def test_deployed_only_the_super_admin_reaches_a_placeholder(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gate, "is_local", lambda: False)
    someone = Identity(principal_id="1", email="someone@example.edu", name="Someone")
    monkeypatch.setattr(gate, "current_identity", lambda request: someone)
    for path in PAGES:
        assert client.get(path).status_code == 404, path
    assert client.get("/applydesk/health").status_code == 200
    monkeypatch.setattr(gate, "current_identity", lambda request: None)
    assert client.get("/applydesk/me").status_code == 404


def test_deployed_the_super_admin_reaches_them(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gate, "is_local", lambda: False)
    client = TestClient(host_with(("applydesk",))[0])
    assert client.get("/applydesk/me").status_code == 200  # the conftest's fake super-admin


_LINK = re.compile(r'\b(?:href|action|src)="([^"]*)"')


@pytest.mark.parametrize("path", PAGES)
def test_every_link_stays_in_the_mount(client: TestClient, path: str) -> None:
    """Every link sits under the mount; only the host's landing and Easy
    Auth's sign-out leave it. (That templates write them through `url()`
    is held by rendering under another prefix, below.)"""
    for link in _LINK.findall(client.get(path).text):
        if link.startswith("data:") or link.startswith("#"):
            continue
        assert link.startswith("/applydesk/") or link in ("/", "/.auth/logout"), (path, link)


def test_the_tabs_mark_the_current_page(client: TestClient) -> None:
    page = client.get(f"/applydesk/operator/exercises/{EX}/form").text
    assert (
        f'<a class="xnav-tab on" href="/applydesk/operator/exercises/{EX}/form"'
        ' aria-current="page">Form</a>'
    ) in page
    assert '<span class="xnav-label xnav-l-setup on">Setup</span>' in page
    assert '<span class="xnav-label xnav-l-ops">Operations</span>' in page
    # The tab, the breadcrumb's last step, and Exercises in the switcher.
    assert page.count('aria-current="page"') == 3
    home = client.get(f"/applydesk/operator/exercises/{EX}").text
    assert '<a class="xnav-home on"' in home and 'class="xnav-tab on"' not in home


def test_a_blind_dossier_names_nobody(client: TestClient) -> None:
    app = sample_data.by_dossier(BLIND, "t8nv4hzm2c")
    assert app is not None
    page = client.get(f"/applydesk/me/exercises/{BLIND}/dossiers/t8nv4hzm2c").text
    for identifying in (app.applicant, app.email, app.public_id):
        assert identifying not in page, identifying
    assert "Redacted" in page


def test_an_open_dossier_names_the_applicant(client: TestClient) -> None:
    page = client.get(f"/applydesk/me/exercises/{EX}/dossiers/p3bd7kq2wx").text
    assert "Aisha Bello" in page


@pytest.mark.parametrize("dossier", ["p3bd7kq2wx", "t8nv4hzm2c"])
def test_a_dossier_shows_only_the_part_shown_to_reviewers(client: TestClient, dossier: str) -> None:
    exercise = EX if dossier == "p3bd7kq2wx" else BLIND
    page = client.get(f"/applydesk/me/exercises/{exercise}/dossiers/{dossier}").text
    assert "Shown to evaluators" in page and "Not shown to evaluators" not in page
    app = next(a for a in sample_data.APPLICATIONS if a.dossier_id == dossier)
    found = sample_data.exercise(exercise)
    assert found is not None
    shown, hidden = extract.form_answers(found, app)
    for label, _ in hidden:
        assert f"<dt>{label}</dt>" not in page, label
    for label, value in shown:
        assert f"<dt>{label}</dt><dd>{value}</dd>" in page, label
    if exercise == BLIND:  # no title against a field, nor anywhere (cold read)
        assert app.title not in page


def test_the_application_reads_its_form_and_answers(client: TestClient) -> None:
    """AD-26: the Form's questions in order with the seeded answers, "—"
    where none; no hand-kept list, no title against the first field."""
    page = client.get("/applydesk/me/exercises/wa9juxbc2t/applications/m3qx8vkt2n").text
    assert "<dt>Year of study</dt><dd>Year 4</dd>" in page
    assert "<dt>Residence</dt><dd>Tembusu House</dd>" in page
    # The same answers Extract writes, so the two never disagree.
    app = next(a for a in sample_data.APPLICATIONS if a.public_id == "m3qx8vkt2n")
    found = sample_data.exercise("wa9juxbc2t")
    assert found is not None
    shown, hidden = extract.form_answers(found, app)
    for label, value in shown + hidden:
        assert f"<dt>{label}</dt><dd>{value}</dd>" in page, label
    assert "<dt>Photo</dt><dd>" in page and "Expected graduation" not in page

    assert not hasattr(sample_data, "form_of")


def test_the_bar_s_icon_is_the_favicon(client: TestClient) -> None:
    page = client.get("/applydesk/me").text
    (favicon,) = re.findall(r'<link rel="icon" type="image/svg\+xml"\s+href="([^"]+)"', page)
    assert f'url("{favicon}")' in page


def test_no_inline_style_attributes(client: TestClient) -> None:
    """New visual primitives are classes in `base.html`, never `style=`."""
    for path in PAGES:
        assert " style=" not in client.get(path).text, path


def _gated_routes(routes: Any, gates: tuple[object, ...] = ()) -> Iterator[tuple[Any, set[object]]]:
    """Every route under ``routes`` with the dependencies that guard it,
    an enclosing include's too (FastAPI nests an included router behind
    its include context), as Residential's gate test walks them."""
    for route in routes:
        context = getattr(route, "include_context", None)
        if context is not None:
            outer = tuple(d.dependency for d in context.dependencies or ())
            yield from _gated_routes(context.included_router.routes, gates + outer)
            continue
        calls: set[object] = set(gates)
        pending = list(route.dependant.dependencies if hasattr(route, "dependant") else ())
        while pending:
            dependant = pending.pop()
            calls.add(dependant.call)
            pending.extend(dependant.dependencies)
        yield route, calls


def test_every_route_but_health_carries_the_gate() -> None:
    """A router that forgot its gate would pass the path checks above; this
    walks every route the factory builds: the operator's carry the
    operator check (segment AD2A), the rest the placeholders' gate."""
    routes = list(_gated_routes(create_app().routes))
    assert len(routes) > 1
    missing = [
        r.path
        for r, calls in routes
        if r.path != "/health"
        and (
            gate.require_exercise_operator
            if r.path.startswith("/operator/exercises")
            else gate.require_super_admin
            if r.path.startswith("/admin/")
            else gate.placeholders_only
        )
        not in calls
    ]
    assert missing == []


def test_links_follow_the_mount_s_prefix() -> None:
    """Mounted elsewhere, every link moves with it: none is written with
    `/applydesk` spelled out, so each went through `url()`."""
    from fastapi import FastAPI

    from applydesk.main import create_app as factory

    host = FastAPI()
    host.mount("/elsewhere", factory())
    client = TestClient(host)
    for path in PAGES:
        page = client.get(path.replace("/applydesk/", "/elsewhere/", 1)).text
        for link in _LINK.findall(page):
            assert not link.startswith("/applydesk"), (path, link)


def test_health_answers_with_no_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    """No sign-in at all, fake auth off and deployed: health still answers,
    and nothing else does."""
    from cordware.settings import identity_settings

    monkeypatch.setattr(identity_settings, "allow_fake_auth", False)
    monkeypatch.setattr(identity_settings, "app_env", "production")
    monkeypatch.setattr(gate, "is_local", lambda: False)
    client = TestClient(host_with(("applydesk",))[0])
    assert client.get("/applydesk/health").json() == {"status": "ok"}
    assert client.get("/applydesk/me").status_code == 404


def test_the_lobby_names_exercises_by_code_not_id(client: TestClient) -> None:
    """Iteration rung 4 (author, 2026-11-12): an Exercise code column, as
    RRW's Session Code; the public ID is only in each row's link."""
    page = client.get("/applydesk/operator/exercises").text
    assert "<th>Exercise code</th>" in page and ">ID<" not in page
    for e in sample_data.EXERCISES:
        if e.code:  # a just-created exercise has none yet
            assert f"<code>{e.code}</code>" in page
        assert f"<code>{e.public_id}</code>" not in page
    codes = [e.code for e in sample_data.EXERCISES if e.code]
    assert len(set(codes)) == len(codes)


def test_withdraw_is_outline_amber(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ruling 45 (2026-11-18, over the 2026-11-12 Destructive): Withdraw is
    Outline-amber, with a confirm once AD4 builds it."""
    monkeypatch.setattr(workflow, "gate_sent", lambda _e, _k: ("Ready", ""))
    page = client.get(f"/applydesk/me/exercises/{EX}/applications/h6zr2tdw9p").text
    assert 'class="btn btn-destructive"' not in page and 'class="btn btn-alert"' in page


def test_the_chrome_follows_the_operator_s_workflow(client: TestClient) -> None:
    """Ruling 14: Exercise Home, then a Setup row and an Operations row."""
    text = client.get(f"/applydesk/operator/exercises/{EX}").text
    grid = text[text.index('<nav class="xnav-grid"') :]
    grid = grid[: grid.index("</nav>")]
    home = re.findall(r'<a class="xnav-home[^"]*"[^>]*>([^<]+)</a>', grid)
    setup = grid[grid.index("xnav-setup") : grid.index("xnav-l-ops")]
    ops = grid[grid.index('class="xnav-row xnav-ops"') :]
    tab = r'<a class="xnav-tab[^"]*"[^>]*>([^<]+)</a>'
    assert home == ["Exercise Home"]
    assert re.findall(tab, setup) == ["Process", "Form", "Panels", "Emails"]  # ruling 20
    assert re.findall(tab, ops) == ["Dossiers", "Evaluations", "Extract data"]  # ruling 25
    assert '<nav class="crumbs" aria-label="Breadcrumb">' in text
    assert "<h1>Recruitment and Selection of Residential Assistants</h1>" in text


def test_the_status_row_says_where_each_item_stands(client: TestClient) -> None:
    text = client.get(f"/applydesk/operator/exercises/{EX}/dossiers").text
    row = text[text.index("data-status>") + len("data-status>") :]
    row = re.sub(r"<[^>]+>", "", row[: row.index("</p>")])
    assert row == (
        "Exercise: Published · Form: Closed · Gates: 2 of 3 done · "
        "Outcomes: 1 of 2 released · Emails: 3 of 5 · Applications: 100 submitted · 3 drafts"
    )
    blank = client.get(f"/applydesk/operator/exercises/{BLANK}/process").text
    assert 'Gates: <span class="chip chip-warn">none</span>' in blank


@pytest.mark.parametrize(
    "old",
    ["settings", "assessors", "timeline", "export", "report"]
    + ["setup", "review", "reports"]  # ruling 14 (Panels came back, ruling 20)
    + ["gates"],  # folded into Process, ruling 20
)
def test_the_retired_sections_are_gone(client: TestClient, old: str) -> None:
    assert client.get(f"/applydesk/operator/exercises/{EX}/{old}").status_code == 404


@pytest.mark.parametrize(
    ("exercise_id", "now"),
    [(DRAFT, "Stage 1"), (OPEN, "Stage 1"), (EX, "Interviews"), (BLIND, "Stage 2")],
)
def test_the_lobby_names_each_exercise_s_current_stage(
    client: TestClient, exercise_id: str, now: str
) -> None:
    """Ruling 15: the stage holding the exercise's next step."""
    e = sample_data.exercise(exercise_id)
    assert e is not None and workflow.current_stage(e) == now
    lobby = client.get("/applydesk/operator/exercises").text
    row = lobby[lobby.index(e.name) :]
    assert f"<td>{now}</td>" in row[: row.index("</tr>")]


def _page(text: str) -> str:
    """The Process page without the templates its script clones from."""
    cut = text.find('<template id="pc-new-stage">')
    return text if cut < 0 else text[:cut]


def _stage_cards(text: str) -> list[str]:
    return re.findall(r'<article class="fc pc" data-kind="stage" data-stage="\d+"', _page(text))


def test_process_is_a_stack_of_stage_cards(client: TestClient) -> None:
    """Segment AD1E rung 2, the scaffold: Form's pattern, a card per stage
    holding its items, the Outline beside them."""
    full = client.get(f"/applydesk/operator/exercises/{EX}/process").text
    text = _page(full)
    names = re.findall(r'<span class="fc-q" data-sum="name">([^<]+)</span>', text)
    assert names == ["Applications", "Review", "Interviews"]
    assert len(_stage_cards(text)) == 3
    items = re.findall(r'<div class="pc-item" data-item="(\w+)"', text)
    assert items == ["form", "gate", "gate", "outcome", "gate", "outcome"]
    # Ruling 30's rules, branched, as the Dossiers page's headers.
    assert "Shortlisting is Re-appointment → Selected; else if Shortlisting is Interview" in text
    # Ruling 16: an outcome ticks whom it emails; Emails holds the template.
    assert "data-rel-template" not in text
    assert len(re.findall(r'data-rel="applicants-email" checked', text)) == 2
    assert len(re.findall(r'data-rel="evaluators-email" checked', text)) == 1
    assert "3 stages · 3 gates · 2 outcomes" in full
    assert "announcement" not in text.lower()  # the exercise's own setup (author)
    # Ruling 15's shape, as the inert buttons say it.
    assert 'disabled title="A stage holding the form holds no gate">+ Gate' in text
    assert 'disabled title="A stage holding gates holds no form">+ Form' in text
    assert 'disabled title="A stage holds one outcome at most">+ Outcome' in text
    # The buttons ruling 15 refuses say why; the rest work in the
    # browser. Cards load collapsed, as Form's.
    assert not re.findall(r"<article [^>]*data-open", text)
    assert (
        '<button type="button" class="btn btn-secondary" data-fc-act="new">+ Stage</button>' in text
    )
    assert re.findall(r'data-pc-act="gate" disabled', text)


def test_a_blank_exercise_s_process_is_one_stage_holding_the_form(client: TestClient) -> None:
    text = _page(client.get(f"/applydesk/operator/exercises/{BLANK}/process").text)
    assert len(_stage_cards(text)) == 1
    assert 'placeholder="Stage 1"' in text
    assert re.findall(r'<div class="pc-item" data-item="(\w+)"', text) == ["form"]
    assert 'disabled title="The last stage cannot be deleted">Delete' in text


def test_dossiers_returns_to_draft_by_row_and_ticked(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rulings 45, 49: no Generate dossiers; Return to draft on a submitted
    row until a gate holding its dossier completes, and for the ticked rows,
    gates or none."""
    text = client.get(f"/applydesk/operator/exercises/{EX}/dossiers").text
    assert "Generate dossiers" not in text and ">Return ticked to draft</button>" in text
    # wa9's Gate 1 has results in: every entered dossier is past returning.
    assert 'aria-label="Return p3bd7kq2wx to draft"' not in text
    monkeypatch.setattr(workflow, "gate_sent", lambda _e, _k: ("Ready", ""))
    open_ = client.get(f"/applydesk/operator/exercises/{EX}/dossiers").text
    assert 'aria-label="Return p3bd7kq2wx to draft">Return to draft</button>' in open_
    assert 'aria-label="Return f2ps7nyh4k to draft"' not in open_  # a draft
    # Ruling 49: a sent gate, opened or not, keeps it open until it completes.
    for sent in (("Sent", ""), ("Sent", "3 of 5 reviewed")):
        monkeypatch.setattr(workflow, "gate_sent", lambda _e, _k, s=sent: s)
        assert workflow.withdrawal_closed_by(EX, "m3qx8vkt2n") == ""
    monkeypatch.setattr(workflow, "gate_sent", lambda _e, _k: ("Results in", "done"))
    assert workflow.withdrawal_closed_by(EX, "m3qx8vkt2n") == "Peer review"
    nogates = client.get("/applydesk/operator/exercises/r6tm4kq9wz/dossiers").text
    assert ">Return ticked to draft</button>" in nogates
    # Operators open every dossier (author, 2026-11-12), on their own page
    # under Dossiers (ruling 64, U20).
    assert "/applydesk/operator/exercises/wa9juxbc2t/dossiers/p3bd7kq2wx" in text


def test_a_gate_item_carries_its_evaluators(client: TestClient) -> None:
    """Ruling 27 (AD1G): each gate item's head reads its sources and Total,
    as stages.sources_summary; Evaluators lists the panel sources'
    members; a sent gate keeps its sources. (The Outline's are the
    script's: Chromium.)"""
    text = client.get(f"/applydesk/operator/exercises/{EX}/process").text
    chips = re.findall(r"data-pi-panel>([^<]*)<", text)
    assert chips[:3] == [
        "Current RAs 29–30 · Total 29–30",
        "Office staff 5 · Total 5",
        "Residential staff 2 · Total 2",
    ]
    assert "data-pc-members" not in text  # members are on Panels, not listed (author)
    # The Review stage's gates have opened: their panel menus are fixed; the
    # staff interview, not yet sent, is still set here (ruling 29).
    assert text.count('data-pc-panel data-ps="panel" disabled title="Its session has opened') == 2
    # A gate picks a panel, never Institution-wide.
    at = text.index("data-pc-panel")
    menu = text[at : text.index("</select>", at)]
    assert ">Institution-wide<" not in menu and ">Residential staff<" in menu
    assert ">+ New panel…</option>" in menu
    # No gate page to send anyone to.
    assert "/gates" not in text


def test_a_gate_with_no_panel_has_no_evaluators(client: TestClient) -> None:
    """The draft's selection gate was added just in time: no sources yet,
    and + Source to add one."""
    text = client.get(f"/applydesk/operator/exercises/{DRAFT}/process").text
    assert re.findall(r"data-pi-panel>([^<]*)<", text)[:1] == ["No evaluators"]
    gate = text[text.index('data-item="gate"') : text.index('data-pc-act="remove-gate"')]
    assert "data-ps-row" not in gate and ">No sources<" in gate
    assert 'data-ps-act="add">+ Source<' in gate


def test_emails_lists_every_template_process_makes_owed(client: TestClient) -> None:
    """Ruling 16: one template per item and audience Process ticks, named
    for its stage, in timeline order; written or owed."""
    text = client.get(f"/applydesk/operator/exercises/{EX}/emails").text
    names = re.findall(r'<section class="card em-card" id="em-[\w-]+" data-email="([^"]+)"', text)
    assert names == [
        "Applications: Receipt · Applicants",
        "Applications: Reminder · Applicants",
        "Review: Outcome · Applicants",
        "Interviews: Outcome · Applicants",
        "Interviews: Outcome · Evaluators",
    ]
    chips = re.findall(r'<span class="chip chip-\w+" data-em-chip>(Written|Owed)</span>', text)
    assert chips == ["Written", "Written", "Written", "Owed", "Owed"]
    # The side card (author, 2026-11-19): an Outline linking each email,
    # its chip beside it, and the counts; then the merge tags.
    outline = re.findall(
        r'<a class="fb-o-item" href="#(em-[\w-]+)">([^<]+)</a> <span[^>]*>(\w+)</span>', text
    )
    # Each id names its email (ruling 65), as Process's Template → links do.
    emails = workflow.emails(EX)
    assert [(a, b) for a, _, b in outline] == [
        (e.anchor, "Written" if e.ok else "Owed") for e in emails
    ]
    assert [b for _, _, b in outline] == ["Written", "Written", "Written", "Owed", "Owed"]
    assert all(f'id="{e.anchor}"' in text for e in emails)
    assert [n for _, n, _ in outline] == names
    assert "5 emails · 3 written · 2 owed" in text
    assert re.findall(r'data-em-tag="(\w+)"', text) == list(workflow.TAG_HELP)
    # Ruling 23: a Save on each template card, none for the page.
    cards = text.split(" data-email=")[1:]
    assert all(c.split("</section>")[0].count(">Save</button>") == 1 for c in cards)
    assert text.count(">Save</button>") == len(cards)
    # Segment AD1L: a written sample template shows its kind's default; an
    # owed one starts empty, offering the default.
    subject = workflow.DEFAULT_TEMPLATES["receipt"][0]
    assert f'data-em-subject value="{subject}"' in cards[0]
    assert 'data-em-subject value=""' in cards[3] and ">Start from the default</button>" in cards[3]
    # Preview's sample: an evaluator's email has no applicant field.
    assert (
        "evaluator_name&#34;" in cards[4].split("data-em-sample")[1][:400]
        and "applicant_name" not in cards[4].split("data-em-sample")[1][:400]
    )


def test_evaluations_lists_each_gate_s_progress(client: TestClient) -> None:
    text = client.get(f"/applydesk/operator/exercises/{EX}/evaluations").text
    assert re.findall(r'<tr data-gate="(\w+)">', text) == ["g1", "g2", "g3"]
    # Mid-stage (ruling 29): the Interview gate is ready, not yet sent.
    assert "100 of 100 reviewed" in text
    # Each row links to its gate's Review Robin card (segment AD1M); the
    # link reads the same whatever the gate's state (ruling 64, U10).
    assert re.findall(r'href="([^"]+)#ev-rr">([^<]+)</a>', text) == [
        (f"/applydesk/operator/exercises/{EX}/evaluations/gate_{n}", "Review Robin card →")
        for n in (1, 2, 3)
    ]


def test_a_gate_page_s_review_robin_card_is_a_scaffold(client: TestClient) -> None:
    """Segment AD1M rung 2: the card in its real layout, the session's
    name and code derived (ruling 56), every control off until its
    script has run."""
    base = f"/applydesk/operator/exercises/{EX}/evaluations"
    ready = client.get(f"{base}/gate_3").text
    card = ready.split('id="ev-rr"')[1].split("</section>")[0]
    assert f'value="{EX}-g3" data-rr-code disabled' in card
    assert "data-rr-name disabled" in card
    assert "Not linked: nothing sent yet" in card
    # Off until the card's script has run (segment AD1M rungs 4 and 5).
    for act in ("send", "resend", "pull", "invite", "remind"):
        assert re.search(f'data-rr-act="{act}"[^>]* disabled data-rr-wait', card)
    for kind in ("Reviewers", "Reviewees", "Relationships", "Settings"):
        assert f'<div class="rr-file"><h4>{kind}</h4>' in card  # a tile each (ruling 65)
    assert "<th>Evaluator</th><th>Pairs</th><th>Done</th>" in card
    assert 'href="#ev-rr">Review Robin ↓</a>' in ready
    done = client.get(f"{base}/gate_1").text.split('id="ev-rr"')[1].split("</section>")[0]
    assert "Linked; its results are in" in done and "Sent (sample)" in done


def test_extract_data_is_download_cards_and_shows_no_data(client: TestClient) -> None:
    """Segment AD1J: Review Robin's Extract data, cards that cut the data
    into files; the old collation table goes (Dossiers and the gate pages
    show the data)."""
    text = client.get(f"/applydesk/operator/exercises/{EX}/extract").text
    assert re.findall(r'data-xd-card="(\w+)"', text) == [
        "all",
        "applications",
        "gates",
        "outcomes",
        "alias",
        "setup",
    ]
    for h in (
        "Extract all data",
        "Applications",
        "By gate",
        "Outcomes",
        "Alias key",
        "Extract setup",
    ):
        assert f"<h2>{h}</h2>" in text
    assert "Evaluation responses" not in text and "Record interview scores" not in text
    assert re.search(
        r"ra_2027_extract_\d{4}-\d\d-\d\d\.zip: <span>manifest\.csv</span> "
        r'<span data-xd-part="applications">· applications\.csv</span> '
        r'<span data-xd-part="gates">· gate_1_peer_review\.csv</span>',
        text,
    )
    # A confidential gate: Extract all data starts on Dossier IDs, saying why.
    assert "Dossier IDs to start with: a gate is confidential." in text
    # A gate not sent has no file; a confidential one says so.
    gate3 = text[text.index('data-xd-gate="3"') :]
    assert "Not sent" in gate3[: gate3.index("</tr>")]
    gate2 = text[text.index('data-xd-gate="2"') :]
    assert "Confidential" in gate2[: gate2.index("</tr>")] and "500 pairs" in gate2
    assert "dossier_id, evaluator, evaluator_email, Score, Comment" in text
    assert "dossier_id, application_id, applicant, email" in text  # the alias key
    assert "form.csv · process.csv · panels.csv · emails.csv" in text  # CSV (author)
    assert "No submitted applications yet." not in text
    assert ".xd-grid { display: grid;" in text  # two to a row (base.html)


def test_extract_s_files_follow_the_exercise(client: TestClient) -> None:
    ra = sample_data.exercise(EX)
    assert ra is not None
    x = extract.of(ra)
    assert x.application_columns[:6] == extract.APPLICATION_KEYS
    # A column per question, in the form's order; no section or text block.
    assert x.application_columns[6:9] == ("Preferred name", "Matriculation number", "Year of study")
    assert "About you" not in x.application_columns
    assert [(g.name, g.pairs, g.sent) for g in x.gates] == [
        ("gate_1_peer_review.csv", 2980, True),
        ("gate_2_office_checks.csv", 500, True),
        ("gate_3_staff_interview.csv", 80, False),
    ]
    assert x.outcome_columns[:5] == (
        "dossier_id",
        "applicant",
        "email",
        "Peer review: Mean score",
        "Peer review: Comments",
    )
    assert "Shortlisting released" in x.outcome_columns
    assert extract.slug("Staff interview / Panel 2") == "staff_interview_panel_2"
    draft = sample_data.exercise(DRAFT)
    assert draft is not None
    assert not any(g.sent for g in extract.of(draft).gates)  # a draft sent nothing


def test_a_draft_exercise_s_timeline_reads_cleanly(client: TestClient) -> None:
    text = client.get(f"/applydesk/operator/exercises/{DRAFT}").text
    assert "Not set to Not set" not in text and "Expected Not set" not in text
    draft = sample_data.exercise(DRAFT)
    assert draft is not None
    assert workflow.steps(draft)[0].when == "Dates not set"


def test_a_blank_exercise_lists_what_is_still_to_set_up(client: TestClient) -> None:
    """Author, 2026-11-12: one exercise as just created, with only a name."""
    home = client.get(f"/applydesk/operator/exercises/{BLANK}").text
    assert "<h1>Graduate Travel Grant 2027</h1>" in home
    assert (
        '<dt>Description</dt><dd data-dt-show="description"><span class="muted">Not set</span>'
        in home
    )
    # Its stage's blockers, in the timeline's operator part (AD1K, at the
    # author's check), each linked to where it is set.
    assert "Blocking publication" in home
    missing = home[home.index("data-tl-blocking") :]
    missing = missing[: missing.index("</ul>")]
    base = "/applydesk/operator/exercises/n5wg8tjr3e"
    assert re.findall(r'<li><a href="([^"]+)">([^<]+)</a> not set</li>', missing) == [
        (f"{base}#details", "Exercise code"),
        (f"{base}#details", "Description"),
        (f"{base}#details", "Who may apply"),
        (f"{base}/process", "Dates"),
        (f"{base}/form", "Application form"),
    ]
    assert "(a hard deadline)" not in home
    blank = sample_data.exercise(BLANK)
    assert blank is not None
    assert workflow.steps(blank)[0].when == "Dates not set"


def test_a_blank_exercise_s_pages_say_what_is_missing(client: TestClient) -> None:
    base = f"/applydesk/operator/exercises/{BLANK}"
    lobby = client.get("/applydesk/operator/exercises").text
    row = lobby[lobby.index("Graduate Travel Grant 2027") :]
    assert '<span class="muted">Not set</span>' in row[: row.index("</tr>")]
    form = client.get(f"{base}/form").text
    cards = form[form.index('id="fb-cards"') : form.index('<template id="fb-new-field">')]
    assert cards.count('data-kind="field"') == 1 and 'placeholder="Untitled form"' in form
    assert "<h2 data-empty-title>No applications yet</h2>" in client.get(f"{base}/dossiers").text
    # Ruling 16: a form's receipt is owed until Process says otherwise.
    assert 'data-email="Stage 1: Receipt · Applicants"' in client.get(f"{base}/emails").text
    xd = client.get(f"{base}/extract").text
    assert "<h2 data-empty-title>No submitted applications yet</h2>" in xd
    assert "<p>A draft exercise: only its setup can be extracted" in xd
    assert "No gates yet: Process adds them." in xd


def test_a_set_up_draft_lists_only_what_it_lacks(client: TestClient) -> None:
    home = client.get(f"/applydesk/operator/exercises/{DRAFT}").text
    missing = home[home.index("data-tl-blocking") :]
    assert re.findall(r"<a [^>]*>([^<]+)</a> not set", missing[: missing.index("</ul>")]) == [
        "Dates"
    ]


def test_evaluations_shows_each_gate_s_assignments(client: TestClient) -> None:
    """Ruling 27, and AD1H's page per gate: Evaluations keeps a short card
    per gate (mode, counts, load) linking to the gate's page, which holds
    a row per pair, its source and its state; a sent gate's operations
    disabled, saying why."""
    text = client.get(f"/applydesk/operator/exercises/{EX}/evaluations").text
    assert re.findall(r'data-ev-gate="(\w+)" data-mode="(\w+)"', text) == [
        ("g1", "automatic"),
        ("g2", "automatic"),
        ("g3", "suggested"),
    ]
    g1 = text[text.index('data-ev-gate="g1"') : text.index('data-ev-gate="g2"')]
    assert "100 dossiers · 100 filled" in g1
    assert re.search(r"Current RAs: Aisha Bello \d+ · ", g1)
    link = f'href="/applydesk/operator/exercises/{EX}/evaluations/gate_1">Pairs (2,980)'
    assert link in g1
    assert "data-ev-row" not in text  # the rows are the gate's page's
    page = client.get(f"/applydesk/operator/exercises/{EX}/evaluations/gate_1").text
    assert "<title>Gate 1 · Peer review · Recruitment and Selection of Residential" in page
    # A row per pair (author, 2026-11-17), 200 to a page.
    assert page.count("data-ev-row=") == 200 == page.count('data-ev-source="Current RAs"')
    assert (
        'data-ev-act="add"  disabled title="Its session has opened' in page
    )  # no Re-run (ruling 48)
    assert 'data-ev-act="rerun"' not in page
    assert "Showing 1–200 of 2,980 pairs" in page
    g3 = client.get(f"/applydesk/operator/exercises/{EX}/evaluations/gate_3").text
    # Not sent (ruling 29): its pairs suggested, still the operator's.
    assert g3.count("data-ev-row=") == 80 and g3.count(">Suggested<") == 80
    assert (
        'data-ev-act="approve-all" disabled data-ev-wait>Approve all' in g3
    )  # the operator's (AD1G 6b)
    assert 'id="ev-data"' in g3 and 'id="ev-data"' not in page  # a sent gate's are not
    assert 'data-ev-act="remove" aria-label="Remove ' in g3 and "Its session has opened" not in g3


def test_a_gate_s_page_shows_200_rows_at_a_time(client: TestClient) -> None:
    """Segment AD1H: Gate 1's 2,980 pairs, 200 at a time, as Review
    Robin's rosters; the offset snapped to a page and clamped to the last;
    the steps and the range menu keep the filter."""
    base = f"/applydesk/operator/exercises/{EX}/evaluations/gate_1"
    first = client.get(base).text
    assert f'href="{base}?offset=200#ev-table-card" aria-label="Next page"' in first
    assert 'is-inactive" aria-disabled="true" aria-label="Previous page"' in first
    ranges = re.findall(r"<li>(?:<a [^>]*>|<span [^>]*>)([^<]+)<", first)
    # The pager again below the table (AD-108): the same 15 ranges twice.
    assert len(ranges) == 30 and ranges[:15] == ranges[15:]
    assert ranges[0] == "1–200" and ranges[14] == "2,801–2,980"
    last = client.get(f"{base}?offset=99999").text
    assert last.count("data-ev-row=") == 180 and "2,801–2,980 of 2,980" in last
    assert "201–400 of 2,980" in client.get(f"{base}?offset=250").text  # snapped to its page
    assert client.get(f"{base}?offset=-5").text.count("data-ev-row=") == 200
    found = client.get(f"{base}?q=example.edu").text  # every row: the filter kept
    assert f'href="{base}?q=example.edu&amp;offset=200#ev-table-card"' in found


def test_a_gate_s_page_finds_a_candidate_or_an_evaluator(client: TestClient) -> None:
    base = f"/applydesk/operator/exercises/{EX}/evaluations/gate_1"
    one = client.get(f"{base}?q=KENJI").text
    # Kenji's 30 reviewers; Kenji reviews no one, not being an RA.
    assert one.count('data-ev-row="h6zr2tdw9p"') == 30 == one.count("data-ev-row=")
    assert "matching “KENJI”" in one
    assert f'<a class="btn btn-secondary" href="{base}">Clear</a>' in one
    aisha = client.get(f"{base}?q=aisha.bello@example.edu").text
    # Hers: 29 reviewing her, and the 99 others she reviews.
    assert aisha.count('data-ev-row="m3qx8vkt2n"') == 29
    assert aisha.count('data-ev-pair="aisha.bello@example.edu"') == 99
    assert "Showing 1–128 of 128 pairs matching" in aisha
    none = client.get(f"{base}?q=nobody-at-all").text
    assert "Showing 0 of 2,980 pairs matching" in none and "data-ev-row=" not in none


def test_a_gate_s_page_reads_a_bad_offset_as_the_first_page(client: TestClient) -> None:
    base = f"/applydesk/operator/exercises/{EX}/evaluations/gate_1"
    for offset in ("abc", "1.5", ""):
        page = client.get(f"{base}?offset={offset}")
        assert page.status_code == 200 and "1–200 of 2,980" in page.text, offset


def test_a_blind_gate_s_page_finds_a_candidate_only_by_the_dossier(client: TestClient) -> None:
    """Codex on #3958: a blind page shows the dossier ID, so a search by
    the applicant's name, email or application ID must not find them."""
    base = f"/applydesk/operator/exercises/{BLIND}/evaluations/gate_1"
    app = sample_data.applications_of(BLIND)[0]
    for q in (app.applicant.split()[0], app.email, app.public_id):
        assert "data-ev-row=" not in client.get(f"{base}?q={q}").text, q
    assert f'data-ev-row="{app.public_id}"' in client.get(f"{base}?q={app.dossier_id}").text


def test_a_sent_suggested_gate_s_pairs_are_approved_and_fixed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Once its session opens (ruling 29), a Suggested gate's pairs read
    Approved and its operations are Review Robin's."""
    monkeypatch.setitem(workflow._GATES[EX], "g3", ("Sent", "12 of 80 reviewed"))  # pyright: ignore[reportPrivateUsage]  -- a sample's state
    page = client.get(f"/applydesk/operator/exercises/{EX}/evaluations/gate_3").text
    assert page.count(">Approved<") == 80 and ">Suggested<" not in page
    assert 'data-ev-act="approve-all" disabled title="Its session has opened' in page
    assert "Its session has opened: its pairs are Review Robin's to change." in page


def test_a_gate_s_page_is_only_a_gate_s(client: TestClient) -> None:
    base = f"/applydesk/operator/exercises/{EX}/evaluations"
    for tail in ("gate_9", "gate_0", "gate_x", "g1", "gate_01"):
        assert client.get(f"{base}/{tail}").status_code == 404, tail
    # A draft sends nothing, so it has no assignments to show.
    draft = client.get(f"/applydesk/operator/exercises/{DRAFT}/evaluations/gate_1")
    assert draft.status_code == 404
    blind = client.get(f"/applydesk/operator/exercises/{BLIND}/evaluations/gate_1").text
    assert '>Dossier<a class="ev-sort-btn"' in blind and ">Applicant<a" not in blind


def test_a_dossier_with_no_evaluator_is_one_row() -> None:
    app = sample_data.applications_of(EX)[0]
    none = stages.Assignment(app, (), 2, ())
    two = stages.Assignment(app, (("A", "a@x", "Panel A"), ("B", "b@x", "Panel A")), 0, ())
    pairs = stages.pairs_of((none, two))
    assert [(p.name, p.source) for p in pairs] == [("", ""), ("A", "Panel A"), ("B", "Panel A")]
    assert stages.matching(pairs, "B@X") == pairs[2:]
    assert stages.matching(pairs, app.public_id.upper()) == pairs


def test_a_gate_s_table_sorts_as_review_robin_s_tables() -> None:
    """Author, 2026-11-17: a click sorts by a column, again reverses, again
    clears; shift-click adds to the cascade (three at most), then
    reverses, then drops the column; unknown keys are dropped."""
    up, down = (("evaluator", False),), (("evaluator", True),)
    assert paging.plain_click((), "evaluator") == up
    assert paging.plain_click(up, "evaluator") == down
    assert paging.plain_click(down, "evaluator") == ()
    both = (("candidate", False), ("evaluator", False))
    assert paging.plain_click(both, "evaluator") == up  # replaces the cascade
    assert paging.shift_click(up, "candidate") == (("evaluator", False), ("candidate", False))
    assert paging.shift_click(both, "evaluator") == (("candidate", False), ("evaluator", True))
    assert paging.shift_click((("candidate", False), ("evaluator", True)), "evaluator") == (
        ("candidate", False),
    )
    three = (*both, ("source", False))
    assert paging.shift_click(three, "state") == three  # three at most
    assert paging.parse_sort("-state,bogus,state,evaluator") == (
        ("state", True),
        ("evaluator", False),
    )
    assert paging.sort_text((("state", True), ("evaluator", False))) == "-state,evaluator"
    assert [paging.sort_badge(both, k) for k in ("candidate", "evaluator", "state")] == [
        "1↑",
        "2↑",
        "↕",
    ]
    assert paging.sort_badge(down, "evaluator") == "1↓"


def test_a_gate_s_page_sorts_every_page_on_the_server(client: TestClient) -> None:
    base = f"/applydesk/operator/exercises/{EX}/evaluations/gate_1"
    first = client.get(f"{base}?sort=evaluator").text
    evaluators = re.findall(r'data-ev-pair="([^"]+)"', first)
    names = [n for n in re.findall(r'<td><span title="[^"]+">([^<]+)</span></td>', first)]
    assert names == sorted(names, key=str.casefold) and len(evaluators) == 200
    last = client.get(f"{base}?sort=-evaluator&offset=2800").text
    tail = re.findall(r'<td><span title="[^"]+">([^<]+)</span></td>', last)
    # Reversed, the last page ends with the name the first began with.
    assert tail[-1] == names[0]
    assert '<th class="ev-sortable" data-sort-key="evaluator" aria-sort="descending">' in last
    # The pager, the range menu and the search keep the sort; a new order
    # starts at the first page and keeps the filter.
    assert f'href="{base}?sort=-evaluator&amp;offset=2600#ev-table-card"' in last
    assert '<input type="hidden" name="sort" value="-evaluator">' in last
    found = client.get(f"{base}?q=kenji&sort=candidate&offset=0").text
    assert f'href="{base}?q=kenji&amp;sort=-candidate#ev-table-card" data-shift-href' in found
    assert f'data-shift-href="{base}?q=kenji&amp;sort=candidate%2Cevaluator#ev-table-card"' in found
    assert f'<a class="btn btn-secondary" href="{base}?sort=candidate">Clear</a>' in found


def test_a_blind_gate_sorts_by_the_dossier(client: TestClient) -> None:
    base = f"/applydesk/operator/exercises/{BLIND}/evaluations/gate_1"
    text = client.get(f"{base}?sort=candidate").text
    shown = re.findall(
        r"<tr data-ev-row=\"\w+\"[^>]*>\s*<td>(?:<input [^>]*>)?<code>(\w+)</code></td>", text
    )
    assert shown == sorted(shown) and shown
    # The sample's IDs and names fall in one order, so the rule itself:
    # by the ID when blind, by the name otherwise.
    zed, abe = _pair("Abe Ng", "z9", "Dr A"), _pair("Zed Ong", "a1", "Dr B")
    order = (("candidate", False),)
    gate = cast(stages.Gate, None)  # read only by the State column
    assert stages.sorted_pairs((zed, abe), order, gate, False, blind=True) == (abe, zed)
    assert stages.sorted_pairs((abe, zed), order, gate, False) == (zed, abe)


def test_a_blind_gate_s_page_data_names_no_candidate() -> None:
    """AD1G rung 6b: the script's data on a blind page carries dossier
    IDs and evaluators, never a candidate's name or email."""
    gate = stages.gate_numbered(stages.plan_of(BLIND), 1)
    assert gate is not None
    rows, _ = stages.assignments(BLIND, gate)
    data = json.dumps(stages.page_data(BLIND, gate, rows, blind=True))
    for a in rows:
        assert a.application.applicant not in data
        assert a.application.email.lower() not in data
        assert a.application.dossier_id in data


def _pair(applicant: str, dossier: str, evaluator: str, source: str = "") -> stages.Pair:
    app = SimpleNamespace(applicant=applicant, dossier_id=dossier)
    of = cast(stages.Assignment, SimpleNamespace(application=app))
    return stages.Pair(of=of, name=evaluator, source=source)


def test_a_gate_s_sort_puts_empty_cells_last_and_numbers_as_numbers() -> None:
    """As Review Robin's tables: a dossier with no evaluator yet sorts
    last up or down, and *Panel 2* before *Panel 10*."""
    none_yet, b, a = _pair("C", "c", ""), _pair("B", "b", "Bo"), _pair("A", "a", "Al")
    gate = cast(stages.Gate, None)  # read only by the State column
    for desc, want in ((False, (a, b, none_yet)), (True, (b, a, none_yet))):
        got = stages.sorted_pairs((none_yet, b, a), (("evaluator", desc),), gate, False)
        assert got == want, desc
    ten, two = _pair("X", "x", "E", "Panel 10"), _pair("Y", "y", "F", "Panel 2")
    assert stages.sorted_pairs((ten, two), (("source", False),), gate, False) == (two, ten)


def test_pages_snap_and_clamp() -> None:
    assert paging.page(0, 50) == paging.Page(0, 0)
    assert paging.page(450, 399).offset == 200
    assert paging.page(450, 10_000).offset == 400
    p = paging.page(450, 200)
    assert (p.end, p.last, p.previous, p.following) == (400, 400, 0, 400)
    assert paging.page(450, 400).following is None
    assert paging.page(3_000, 0).ranges[-1] == (2_800, "2,801–3,000", False)


def test_a_blank_exercise_s_details_and_evaluations_say_not_yet(client: TestClient) -> None:
    base = f"/applydesk/operator/exercises/{BLANK}"
    home = client.get(base).text
    assert home.count('<span class="muted">Not set</span>') >= 2  # code, summary
    # The help contact and timezone start as the operator settings'
    # defaults (AD1G amendment); the model exercise sets its own contact.
    assert (
        '<dd data-dt-show="contact">applydesk-help@example.edu'
        ' <span class="muted">· the default</span>' in home
    )
    assert (
        '<dd data-dt-show="timezone">Asia/Singapore <span class="muted">· the default</span>'
        in home
    )
    model = client.get("/applydesk/operator/exercises/wa9juxbc2t").text
    assert '<dd data-dt-show="contact">ra-recruitment@example.edu</dd>' in model
    review = client.get(f"{base}/evaluations").text
    assert "<h2 data-empty-title>Nothing to send yet</h2>" in review
    assert "The exercise is a draft: once it is published" in review
    assert "#ev-rr" not in review


def test_a_draft_with_nothing_missing_is_ready_to_publish(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sample_data, "setup_missing", lambda e: ())
    home = client.get(f"/applydesk/operator/exercises/{DRAFT}").text
    # Its first stage's own checks still name its dates (segment AD1K).
    assert "<li>Stage 1 has no start and end.</li>" in home
    assert home.count("Blocking publication") == 2  # and Selection's


def test_the_blank_exercise_is_not_offered_to_applicants(client: TestClient) -> None:
    assert "Graduate Travel Grant 2027" not in client.get("/applydesk/me").text


def test_profile_shows_nowhere_a_reader_sees(client: TestClient) -> None:
    """Rulings 13 and 25: what a reviewer opens is the dossier. Review
    Robin's `ProfileLink` keeps its name: it is the handoff's field."""
    # The raw page: text, attributes (aria-label, title, placeholder) and
    # the scripts' strings alike.
    for path in PAGES:
        text = client.get(path).text.replace("<code>ProfileLink</code>", "")
        assert "profile" not in text.lower(), path
    assert client.get(f"/applydesk/me/exercises/{EX}/profiles/p3bd7kq2wx").status_code == 404


# --- Segment AD1D rung 3: the timeline, step by step (ruling 14). The
# Workflow card that drew it is gone (author, 2026-11-15); the steps
# still name the current stage. ---
def test_the_timeline_steps_follow_the_stages() -> None:
    e = sample_data.exercise(EX)
    assert e is not None
    all_steps = workflow.steps(e)
    assert [s.title for s in all_steps] == [
        "Application form",
        "Peer review",
        "Office checks",
        "Shortlisting",
        "Staff interview",
        "Selection",
        "Close and archive",
    ]
    # Next is the earliest step not done: Gate 3, its pairs still to be
    # approved, so derived Not ready (ruling 29; AD-33).
    now = workflow.next_step(all_steps)
    assert now is not None and (now.title, now.state, now.line, now.action) == (
        "Staff interview",
        "Not ready",
        "40 dossiers to approve",
        "Send…",
    )
    assert workflow.current_stage(e) == "Interviews"
    final = next(s for s in all_steps if s.title == "Selection")
    assert final.blocked == "Not ready: its emails to applicants and evaluators are not written"


@pytest.mark.parametrize(
    "section",
    ["", "/process", "/form", "/panels", "/emails", "/dossiers", "/evaluations", "/extract"],
)
def test_no_page_carries_a_workflow_card(client: TestClient, section: str) -> None:
    text = client.get(f"/applydesk/operator/exercises/{EX}{section}").text
    assert 'aria-labelledby="wf-h"' not in text and "data-wf-step" not in text


def test_a_blank_exercise_s_timeline_starts_at_opening_the_form() -> None:
    e = sample_data.exercise(BLANK)
    assert e is not None
    all_steps = workflow.steps(e)
    assert [s.title for s in all_steps] == ["Application form", "Close and archive"]
    now = workflow.next_step(all_steps)
    assert now is not None and (now.title, now.line, now.action) == (
        "Application form",
        "Not open yet",
        "Open form…",
    )


# --- Segment AD1D: the cumulative read's fixes ---
def test_an_unnamed_stage_names_its_owed_template(client: TestClient) -> None:
    """Teaching Excellence: its outcome emails applicants, a template owed,
    named for its stage as Process labels it."""
    base = f"/applydesk/operator/exercises/{BLIND}"
    process = client.get(f"{base}/process").text
    assert 'data-rel="applicants-email" checked' in process
    blind = sample_data.exercise(BLIND)
    assert blind is not None
    blocked = [s.blocked for s in workflow.steps(blind) if s.blocked]
    assert blocked == ["Not ready: its email to applicants is not written"]
    emails = client.get(f"{base}/emails").text
    assert 'data-email="Stage 2: Outcome · Applicants"' in emails


def test_the_breadcrumb_ends_at_the_page(client: TestClient) -> None:
    text = client.get(f"/applydesk/operator/exercises/{EX}/process").text
    crumbs = text[text.index('<nav class="crumbs"') :]
    crumbs = crumbs[: crumbs.index("</nav>")]
    assert re.findall(r">([^<>/]+)</(?:a|span)>", crumbs) == [
        "Operator Lobby",
        "Recruitment and Selection of Residential Assistants",
        "Process",
    ]
    assert f'<a href="/applydesk/operator/exercises/{EX}">Recruitment' in crumbs


def test_every_panel_is_offered_to_a_gate(client: TestClient) -> None:
    """Teaching Excellence has interviewers but no interview gate: its
    panel is still offered on its one gate's menu (ruling 19)."""
    text = client.get(f"/applydesk/operator/exercises/{BLIND}/process").text
    assert '<option value="interviewers">Interviewers</option>' in text


def test_a_sent_gate_points_to_evaluations() -> None:
    steps = workflow.steps(sample_data.exercise(BLIND) or sample_data.EXERCISES[0])
    sent = [s for s in steps if s.state == "Sent"]
    assert sent and all(s.action == "" and s.link == "evaluations" for s in sent)


# --- Rung 4's read: stages without an application, the close's date ---
def test_the_close_follows_the_last_stage_with_something_to_decide(client: TestClient) -> None:
    def close_line(exercise_id: str) -> str:
        e = sample_data.exercise(exercise_id)
        assert e is not None
        return workflow.steps(e)[-1].when

    assert close_line(EX) == "After 4 Dec"
    assert close_line(OPEN) == "After the last outcome"  # only the application yet
    assert close_line(BLANK) == "After the last outcome"
    assert "After Dates not set" not in client.get(f"/applydesk/operator/exercises/{BLANK}").text


def test_an_exercise_whose_applications_came_from_elsewhere(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ruling 15: no stage holds the application; the table is loaded
    upstream, so the timeline starts at its first gate."""
    upstream = stages._STAGES[EX][1:]  # pyright: ignore[reportPrivateUsage]  -- a sample's shape
    monkeypatch.setitem(stages._STAGES, EX, upstream)  # pyright: ignore[reportPrivateUsage]  -- as above
    e = sample_data.exercise(EX)
    assert e is not None
    assert [s.title for s in workflow.steps(e)][0] == "Peer review"
    assert workflow.current_stage(e) == "Interviews"
    text = client.get(f"/applydesk/operator/exercises/{EX}/dossiers").text
    assert re.findall(r"<th class=\"ap-first\"[^>]*><b>([^<]+)</b>", text) == ["Dossiers"]
    assert "From elsewhere" in text


def test_applicants_see_whether_applications_are_open(client: TestClient) -> None:
    text = client.get("/applydesk/me").text
    e = sample_data.exercise(OPEN)
    assert e is not None
    row = text[text.index(e.name) :]
    assert "Applications open" in row[: row.index("</p>")]


def test_a_gate_stage_may_come_before_the_application(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Author, 2026-11-13: a gate first, its outcome deciding who may apply."""
    model = stages._STAGES[EX]  # pyright: ignore[reportPrivateUsage]  -- a sample's shape
    monkeypatch.setitem(stages._STAGES, EX, (model[1], model[0], *model[2:]))  # pyright: ignore[reportPrivateUsage]  -- as above
    e = sample_data.exercise(EX)
    assert e is not None
    titles = [s.title for s in workflow.steps(e)]
    assert titles.index("Office checks") < titles.index("Application form")
    text = client.get(f"/applydesk/operator/exercises/{EX}/dossiers").text
    groups = re.findall(r"<th class=\"ap-(?:first|r)\"[^>]*><b>([^<]+)</b>", text)
    assert groups == ["Dossiers", "Review", "Interviews"]
    assert "From elsewhere" not in text
    assert workflow.current_stage(e) == "Interviews"


def test_an_application_stage_later_in_the_timeline_keeps_the_headers_aligned(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An application stage that is not first, holding an outcome: its
    group sits at its place, once, and the group spans match the columns."""
    model = stages._STAGES[EX]  # pyright: ignore[reportPrivateUsage]  -- a sample's shape
    review, interviews = model[1], model[2]
    selection = stages.Stage(4, "Later", None, interviews.columns[1:])
    interview = stages.Stage(3, "Interviews", None, interviews.columns[:1])
    when = stages.span(stages.day(2026, 9, 1), stages.day(2026, 10, 15))
    apply = stages.Stage(9, "Apply", when, selection.columns, form=True)
    monkeypatch.setitem(stages._STAGES, EX, (review, interview, apply))  # pyright: ignore[reportPrivateUsage]  -- as above
    text = client.get(f"/applydesk/operator/exercises/{EX}/dossiers").text
    start = text.index('<tr class="ap-groups">')
    head = text[start : text.index("</thead>", start)]
    groups = re.findall(r"<th class=\"ap-(?:first|r)\"[^>]*><b>([^<]+)</b>", head)
    assert groups == ["Dossiers", "Review", "Interviews", "Apply"]
    spans = sum(int(n) for n in re.findall(r'colspan="(\d+)"', head))
    # The information row and the headers row (ruling 52) each match.
    info = head[head.index('<tr class="ap-info">') : head.index('<tr class="ap-heads">')]
    heads = head[head.index('<tr class="ap-heads">') :]
    assert spans == info.count("<th") == heads.count("<th")


def test_an_owed_email_holds_back_only_a_release_to_come() -> None:
    """Ruling 16: an owed email blocks an outcome not yet released, naming
    every audience owed; one already released is not blocked."""
    ex = sample_data.exercise(EX)
    assert ex is not None
    by_title = {s.title: s for s in workflow.steps(ex)}
    assert by_title["Shortlisting"].blocked == ""  # released
    assert by_title["Selection"].blocked == (
        "Not ready: its emails to applicants and evaluators are not written"
    )


def test_is_operator_follows_the_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    """Segment AD2A: the super-admin, or someone on the allowlist; a local
    run no longer makes everyone one (`test_gate.py` has the rest)."""
    from starlette.requests import Request

    def request() -> Request:
        return Request({"type": "http", "headers": [], "state": {}})

    assert gate.is_operator(request())  # the conftest's fake super-admin
    someone = Identity(principal_id="1", email="someone@example.edu", name="Someone")
    monkeypatch.setattr(gate, "current_identity", lambda request: someone)
    assert not gate.is_operator(request())  # no tenant: cannot be bound
    monkeypatch.setattr(gate, "current_identity", lambda request: None)
    assert not gate.is_operator(request())


# --- Segment AD1F rung 4d: Panels, one table (ruling 20) ---
def test_panels_is_one_table_a_column_per_panel(client: TestClient) -> None:
    text = client.get(f"/applydesk/operator/exercises/{EX}/panels").text
    heads = re.findall(
        r'<th scope="col" class="pn-col" id="panel-[\w-]+" data-panel="([\w-]+)"', text
    )
    assert heads == ["current-ras", "office", "residential-staff"]
    assert re.findall(r'<span class="pn-h" data-pn-name>([^<]+)</span>', text) == [
        "Current RAs",
        "Office staff",
        "Residential staff",
    ]
    # Each person once, ticked on the panels they sit on.
    body = text[text.index("data-pn-body") : text.index("</tbody>")]
    assert body.count("<tr data-pn-row>") == 48
    row = text[text.index('value="Aisha Bello"') :]
    row = row[: row.index("</tr>")]
    ticks = re.findall(r'data-pn-panel="([\w-]+)"( checked)?', row)
    assert [k for k, on in ticks if on] == ["current-ras"]
    # Used by, worked out from the gates.
    assert "Gate 1 · Peer review" in text and "Gate 3 · Staff interview" in text
    assert "data-pn-people>48<" in text and "data-pn-inuse>· 3 in use<" in text


def test_a_panel_nothing_uses_may_be_retired(client: TestClient) -> None:
    """Teaching Excellence's interviewers sit on no gate: not used yet,
    so Retire carries no reason against it."""
    text = client.get(f"/applydesk/operator/exercises/{BLIND}/panels").text
    item = text[text.index('<li data-panel="interviewers">') :]
    item = item[: item.index("</li>")]
    assert "Not used yet" in item and 'title="In use' not in item
    assert "data-pn-people>3<" in text and "data-pn-inuse>· 1 in use<" in text
    assert sample_data.roster(BLIND)[0][0].name == "Priya Rao"


def test_an_exercise_with_no_panels_says_so(client: TestClient) -> None:
    text = client.get(f"/applydesk/operator/exercises/{BLANK}/panels").text
    assert "data-pn-empty>\n  <h2 data-empty-title>No panels yet</h2>" in text
    # No header-only table (AD-79): it waits, out of view, for a first row.
    assert '<div class="table-wrap pn-wrap" data-pn-wrap hidden>' in text


_EMPTY = re.compile(
    r'<section class="ad-empty"[^>]*>\s*<h2 data-empty-title>([^<]+)</h2>'
    r"\s*<p>(.*?)</p>\s*</section>",
    re.S,
)


def _empties(text: str) -> list[tuple[str, list[str]]]:
    """Each empty-state block: its title and the links in its line."""
    return [(t, re.findall(r'<a href="([^"]+)">', line)) for t, line in _EMPTY.findall(text)]


def test_a_blank_draft_s_empty_states_are_one_block(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AD-79 (segment AD1R): Evaluations, Emails, Extract, Dossiers and
    Panels say they are empty in one block, a muted card with a title, one
    line and a link to the page that fixes it, where they had five shapes."""
    base = f"/applydesk/operator/exercises/{BLANK}"
    assert _empties(client.get(f"{base}/evaluations").text) == [("Nothing to send yet", [base])]
    assert _empties(client.get(f"{base}/extract").text) == [
        ("No submitted applications yet", [base])
    ]
    assert _empties(client.get(f"{base}/panels").text) == [("No panels yet", [f"{base}/process"])]
    dossiers = client.get(f"{base}/dossiers").text
    assert _empties(dossiers) == [("No applications yet", [base])]
    assert '<div class="ap-wrap" hidden>' in dossiers and "<td colspan=" not in dossiers
    # One empty message: the no-gates foot line waits for rows (AD1R read).
    assert 'class="ap-foot"' not in dossiers
    monkeypatch.setattr(workflow, "emails", lambda ex: ())
    assert _empties(client.get(f"{base}/emails").text) == [("No emails yet", [f"{base}/process"])]
    # A draft that has gates but no applications links its own pages.
    assert _empties(client.get(f"/applydesk/operator/exercises/{DRAFT}/dossiers").text) == [
        ("No applications yet", [f"/applydesk/operator/exercises/{DRAFT}"])
    ]


def test_controls_over_nothing_are_off_saying_why(client: TestClient) -> None:
    """AD-79 (U16): Dossiers' Unlock with no applications, and Extract's
    chips on a card whose download is off, are disabled in place, each
    with a title saying why; Extract setup's stay live."""
    base = f"/applydesk/operator/exercises/{BLANK}"
    dossiers = client.get(f"{base}/dossiers").text
    assert 'data-ap-lock disabled title="No applications to change yet">Unlock<' in dossiers
    live = client.get(f"/applydesk/operator/exercises/{EX}/dossiers").text
    assert 'data-ap-lock title="Unlock the table to change it">Unlock<' in live
    xd = client.get(f"{base}/extract").text
    why = 'disabled title="No submitted applications to extract yet"'
    for card in ("all", "applications", "gates", "outcomes"):
        body = xd[xd.index(f'data-xd-card="{card}"') :]
        body = body[: body.index("</section>")]
        chips = re.findall(r"<button type=\"button\"[^>]*data-xd-[vt]=[^>]*>", body)
        assert chips and all(why in c for c in chips), card
        assert all(why in b for b in re.findall(r"<button class=\"btn[^>]*>", body)), card
    setup = xd[xd.index('data-xd-card="setup"') :]
    assert "disabled" not in setup[: setup.index("</section>")]
    full = client.get(f"/applydesk/operator/exercises/{EX}/extract").text
    assert "No submitted applications to extract yet" not in full


# --- Segment AD1F 4d-4e cold read: roster, uses, sent panels ---
def test_the_roster_lists_each_person_once_taking_a_later_name_and_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    p = sample_data.Panel
    m = sample_data.Member
    panels = (
        p("x", "a", "A", (m("xu@y.edu", "xu@y.edu"), m("Ann", "ann@y.edu"))),
        p("x", "b", "B", (m("Xu Yi", "XU@y.edu", "Chair"), m("Other", "ann@y.edu", "Lead"))),
    )
    monkeypatch.setattr(sample_data, "PANELS", panels)
    rows = sample_data.roster("x")
    assert [(r.name, r.email, r.note, sorted(k)) for r, k in rows] == [
        ("Xu Yi", "xu@y.edu", "Chair", ["a", "b"]),
        ("Ann", "ann@y.edu", "Lead", ["a", "b"]),
    ]


def test_what_uses_each_panel_and_what_was_sent_with_it() -> None:
    assert stages.panel_uses(EX) == {
        "current-ras": ("Gate 1 · Peer review",),
        "office": ("Gate 2 · Office checks",),
        "residential-staff": ("Gate 3 · Staff interview",),
    }
    assert workflow.panels_sent(EX) == {  # the staff interview not yet sent
        "current-ras": ("Gate 1",),
        "office": ("Gate 2",),
    }
    assert stages.panel_uses(OPEN) == {"pool": ("Form: Preferred evaluator",)}
    assert workflow.panels_sent(DRAFT) == {}


def test_every_panel_source_of_a_gate_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    """AD-49: a second-rank panel source is used by its gate and kept with
    it once the gate's session opens; a gate merely sent keeps nothing."""
    import dataclasses

    plan = stages.plan_of(EX)
    g1 = next(c for c in plan.columns if isinstance(c, stages.Gate) and c.number == 1)
    two = (stages.Source("panel", "current-ras", 1, 2), stages.Source("panel", "office", 0, 1))
    g1b = dataclasses.replace(g1, sources=two)
    assert stages.gate_panels(EX, g1b) == ("current-ras", "office")
    sts = tuple(
        dataclasses.replace(st, columns=tuple(g1b if c is g1 else c for c in st.columns))
        for st in plan.stages
    )
    monkeypatch.setattr(stages, "plan_of", lambda _id: dataclasses.replace(plan, stages=sts))
    assert stages.panel_uses(EX)["office"] == ("Gate 1 · Peer review", "Gate 2 · Office checks")
    assert workflow.panels_sent(EX)["office"] == ("Gate 1", "Gate 2")
    monkeypatch.setattr(workflow, "gate_sent", lambda _e, _k: ("Sent", ""))  # not yet opened
    assert workflow.panels_sent(EX) == {}


def test_panels_says_a_sent_gate_keeps_its_roster(client: TestClient) -> None:
    text = client.get(f"/applydesk/operator/exercises/{EX}/panels").text
    note = "Gate 1 has opened with the roster as it then stood, and keeps it."
    assert f'<span class="pn-sent">{note}</span>' in text  # under Manage panels
    assert f'title="{note}">Opened</span>' in text  # and as its column's chip
    item = text[text.index('<li data-panel="residential-staff">') :]
    assert "sent" not in item[: item.index("</li>")]  # the staff interview: not yet sent


# --- Segment AD1F rung 5b: a gate's results (ruling 21) ---
F, R = stages.Field, stages.GateResult
LIKERT = F("integer", "1", "5", "1")


RESULT_CASES: list[tuple[stages.GateResult, str]] = [
    (R("r1", "Rating", LIKERT, "mean"), "Integer 1 to 5, step 1 · Mean → Decimal 1 to 5"),
    # Ruling 30: a 0 that means *no view* left out.
    (
        R("r1", "Score", F("integer", "0", "5", "1"), "mean", ignore_zero=True),
        "Integer 0 to 5, step 1 · Mean, ignoring 0 → Decimal 0 to 5",
    ),
    (
        R("r1", "Score", F("integer", "0", "5", "1"), "median", at_least=2, ignore_zero=True),
        "Integer 0 to 5, step 1 · Median, ignoring 0, from 2 or more → Decimal 0 to 5",
    ),
    (
        R("r1", "Rating", LIKERT, "median", at_least=2),
        "Integer 1 to 5, step 1 · Median, from 2 or more → Decimal 1 to 5",
    ),
    (R("r1", "Low", LIKERT, "min"), "Integer 1 to 5, step 1 · Lowest → Integer 1 to 5, step 1"),
    (
        R("r1", "Total", F("decimal", "0"), "sum"),
        "Decimal at least 0 · Sum → Decimal, n × at least 0",
    ),
    (
        R("r1", "N", LIKERT, "count"),
        "Integer 1 to 5, step 1 · Count of responses → Integer, from 0",
    ),
    (
        R("r1", "Rec", F("list", options="Fund, Do not fund"), "share"),
        "List: Fund, Do not fund · Share choosing Fund → Decimal 0 to 100 (%)",
    ),
    (
        R("r1", "Rec", F("list", options="Fund, Do not fund"), "share", "Fund"),
        "List: Fund, Do not fund · Share choosing Fund → Decimal 0 to 100 (%)",
    ),
    (
        R("r1", "Rec", F("list", options="A,B"), "mode"),
        "List: A, B · Most common → List: A, B",
    ),
    (
        R("r1", "Notes", F("string", max="500"), "join"),
        "String, up to 500 characters · All, joined → String, for reading",
    ),
    (
        R("r1", "X", F("list"), "mode"),
        "List, no options yet · Most common → List, no options yet",
    ),
]


@pytest.mark.parametrize(("result", "summary"), RESULT_CASES)
def test_a_result_reads_its_field_derivation_and_type(
    result: stages.GateResult, summary: str
) -> None:
    assert stages.result_summary(result) == summary


def test_a_mean_or_median_may_leave_out_the_0s() -> None:
    """Ruling 30: a 0 that means *no view* is not a score; all 0s give no
    result, and the count taken says how many scored."""
    assert stages.averaged((4, 0, 5, 0, 3), "mean", True) == (4.0, 3)
    assert stages.averaged((4, 0, 5, 0, 3), "mean", False) == (2.4, 5)
    assert stages.averaged((0, 0), "mean", True) == (None, 0)
    assert stages.averaged((5, 0, 1, 2), "median", True) == (2, 3)
    assert stages.averaged((5, 0, 1, 2, 4), "median", True) == (3.0, 4)
    assert stages.averaged((), "mean", False) == (None, 0)
    # Only a mean or a median offers it; another derivation reads as before.
    count = stages.GateResult(
        "r1", "N", stages.Field("integer", "0", "5"), "count", ignore_zero=True
    )
    assert stages.derivation_text(count) == "Count of responses"


def test_every_derivation_a_field_allows_is_known() -> None:
    known = dict(stages.DERIVATIONS)
    for kind, allowed in stages.ALLOWED.items():
        assert kind in dict(stages.FIELD_TYPES)
        assert all(d in known for d in allowed)


def test_a_gate_item_lists_its_results_and_what_review_robin_asks(client: TestClient) -> None:
    text = client.get(f"/applydesk/operator/exercises/{EX}/process").text
    g1 = text[text.index('data-key="g1"') : text.index('data-key="g2"')]
    assert re.findall(r'class="pr-name" data-pr-name>([^<]+)<', g1) == ["Mean score", "Comments"]
    # A result names the field it collates (ruling 28), its 0s left out (30).
    assert "From Score · Mean, ignoring 0 → Decimal 0 to 5" in g1
    assert '<option value="score" selected>Score</option>' in g1
    assert 'data-r="ignore_zero" checked' in g1
    assert "data-pi-results>2 results<" in g1
    # Review Robin asks the response fields, a required one saying so.
    assert (
        "For Review Robin, each evaluator answers: <strong>Score</strong> (Integer 0 to 5,"
        " step 1, required; help: “0 = Don&#39;t know enough about this applicant”);"
        " <strong>Comment</strong> (String, up to 2000 characters)."
    ) in g1
    # What will be sent (AD1G amendment): the instrument, its stage's
    # window in the exercise's timezone, the help contact, the tag.
    assert (
        "Review Robin receives <strong>Peer review</strong>: Every current RA scores every"
        " applicant, never themselves, open 1 Oct to 31 Oct (Asia/Singapore); help contact"
        " ra-recruitment@example.edu; tagged <code>applydesk</code>."
    ) in g1
    assert "Help contact <strong>ra-recruitment@example.edu</strong> · Timezone" in g1
    assert (
        'data-pr-send data-tz="Asia/Singapore" data-contact="ra-recruitment@example.edu"'
        " data-fixed>" in g1
    )
    # Each response field's key, read-only: what Review Robin reports under.
    assert re.search(r'Key<input class="fc-in" data-rf-key value="\w+" readonly', g1)
    # Every gate runs in Review Robin (ruling 28): the draft's too, its
    # derivations a decimal field's, none entered here.
    draft = client.get(f"/applydesk/operator/exercises/{DRAFT}/process").text
    assert "From Score · Mean → Decimal 0 to 10" in draft
    assert "For Review Robin, each evaluator answers: <strong>Score</strong>" in draft
    # A stage whose dates say they are not set has no window yet.
    assert "open when its stage&#39;s dates are set (Asia/Singapore)" in draft
    at = draft.index('data-r="derive"')
    menu = draft[at : draft.index("</select>", at)]
    assert menu.count("<option") == len(stages.ALLOWED["decimal"]) and "Entered here" not in menu


# --- Segment AD1F rung 5d: rules and weights read a named result (ruling 21) ---
def test_a_key_names_a_gate_s_result() -> None:
    plan = stages.plan_of(EX)
    assert stages.split_key("g2.r2") == ("g2", "r2")
    assert stages.split_key("g2") == ("g2", "r1")  # a bare gate reads its first
    assert stages.result_label(plan, "g2.r2") == "Minor concerns at Office checks"
    assert stages.result_label(plan, "g2.r9") == "Result at Office checks"
    assert stages.result_label(plan, "gone.r1") == "Result at (removed)"
    list_rule = stages.Rule((("res", "g2.r1", "is", "Fund"),), "Yes", "No")
    with_list = stages.Outcome("ox", 9, "X", (), None, "", rule=list_rule)
    assert stages.rule_text(plan, with_list).startswith("Major concerns at Office checks is Fund")


def test_what_a_rule_may_do_with_a_result() -> None:
    assert stages.comparable(R("r1", "x", LIKERT, "mean")) == "number"
    assert stages.comparable(R("r1", "x", F("list", options="A"), "share", "A")) == "number"
    assert stages.comparable(R("r1", "x", F("list", options="A"), "mode")) == "list"
    assert stages.comparable(R("r1", "x", F("string"), "count")) == "number"
    assert stages.comparable(R("r1", "x", F("string"), "join")) == ""
    assert stages.comparable(R("r1", "x", F("decimal"), "min")) == "number"


def test_a_combined_result_reads_named_results_and_skips_a_0_weight() -> None:
    plan = stages.plan_of(EX)
    o1 = next(c for c in plan.columns if c.key == "o1")
    assert isinstance(o1, stages.Outcome)
    row = next(r for r in plan.rows if dict(r.cells["g2"].extra).get("r2", "0") != "0")
    g1, g2 = row.cells["g1"].result, row.cells["g2"].result
    assert g1 is not None and g2 is not None
    weighed = stages.Outcome("ox", 9, "X", (), None, "", (("g1.r1", 0.3), ("g2.r1", 0.7)))
    assert stages.combined(row, weighed) == round(0.3 * g1 + 0.7 * g2, 2)
    minor = float(dict(row.cells["g2"].extra)["r2"])
    on_minor = stages.Outcome("ox", 9, "X", (), None, "", (("g2.r2", 1.0), ("g1.r1", 0.0)))
    assert stages.combined(row, on_minor) == minor
    # Process draws every numeric result in scope, 0 for one not weighed:
    # the Shortlisting weighs none, its rule reading the results alone.
    assert stages.weight_rows(plan, o1) == (("g1.r1", 0), ("g2.r1", 0), ("g2.r2", 0))


def test_applications_carries_a_gate_s_other_results(client: TestClient) -> None:
    text = client.get(f"/applydesk/operator/exercises/{EX}/dossiers").text
    assert re.search(r'data-result="[\d.]+" data-r2="\d+"', text)
    assert "Interview score at Staff interview 100%" in text


def test_a_0_weight_on_an_unknown_result_leaves_the_combined_result_known() -> None:
    """The 5b-5d cold read: only an unknown result tells the skip apart."""
    app = sample_data.applications_of(EX)[0]
    row = stages.Row(
        app,
        {"g1": stages.Cell("Entered", "", None), "g2": stages.Cell("Entered", "", 4.0)},
    )
    o = stages.Outcome("ox", 9, "X", (), None, "", (("g2.r1", 1.0), ("g1.r1", 0.0)))
    assert stages.combined(row, o) == 4.0
    # A bare key, "g1", is drawn as its first result, as combined reads it.
    import dataclasses

    plan = stages.plan_of(EX)
    o1 = next(c for c in plan.columns if c.key == "o1")
    assert isinstance(o1, stages.Outcome)
    bare = dataclasses.replace(o1, weights=(("g1", 0.3), ("g2", 0.7)))
    swapped = tuple(
        dataclasses.replace(st, columns=tuple(bare if c.key == "o1" else c for c in st.columns))
        for st in plan.stages
    )
    with_bare = stages.Plan(swapped, plan.rows)
    assert stages.weight_rows(with_bare, bare) == (("g1.r1", 30), ("g2.r1", 70), ("g2.r2", 0))


def test_count_is_any_field_s() -> None:
    """Author, 2026-11-14: how many responded is offered for a list or a
    string as for a number, an integer from 0 that a rule may compare."""
    for kind in ("integer", "decimal", "list", "string"):
        assert "count" in stages.ALLOWED[kind]
    said = stages.GateResult("r2", "Comments", stages.Field("string", max="2000"), "count")
    assert stages.result_type(said) == "Integer, from 0"
    assert stages.comparable(said) == "number"


def test_a_gate_card_follows_ruling_28(client: TestClient) -> None:
    """Ruling 28 (AD1G rung 4c, scaffold): a gate's own fields and its
    evaluators sit in two cards, shut, each saying what it holds; Type is
    fixed at Review Robin; then Response fields, then Results; no Runs as."""
    text = client.get(f"/applydesk/operator/exercises/{EX}/process").text
    gate = text[text.index('data-item="gate"') : text.index('data-pc-act="remove-gate"')]
    assert re.findall(r'<details class="gsec" data-gsec="(\w+)"', gate) == ["gate", "evaluators"]
    assert '<details class="gsec" data-gsec="gate" open' not in gate  # shut on load
    sums = re.findall(r"data-gsec-sum>([^<]*)<", gate)
    assert sums[0].startswith("Review Robin session · Enters: Status is Submitted")
    assert sums[1] == "Current RAs 29–30 · Total 29–30 · Automatic"
    assert '<select class="fc-in" data-pc="type" disabled' in gate
    assert ">Review Robin session</option>" in gate
    assert "Every current RA scores every applicant" in gate  # its description
    assert 'data-pc="confidential"' in gate and ">Confidential<" in gate
    order = [
        gate.index(m)
        for m in ('data-gsec="gate"', 'data-gsec="evaluators"', ">Response fields<", ">Results<")
    ]
    assert order == sorted(order)
    assert re.findall(r'data-rf="(\w+)"', gate) == ["score", "comment"]
    assert "Integer 0 to 5, step 1 · Required · Help: 0 = Don" in gate
    assert "Runs as" not in text and "Entered here" not in text
    head = gate[gate.index("data-ps-headrow>") :]
    head = head[: head.index("</div>")]
    assert re.findall(r"<span>([^<]*)</span>", head) == [
        "Order",
        "Kind",
        "Source",
        "Min",
        "Max",
        "All",
        "",
    ]


def test_a_confidential_gate_says_so_when_shut(client: TestClient) -> None:
    from applydesk import stages

    gate = stages.Gate("g9", 9, "x", "RRW", confidential=True)
    plan = stages.plan_of(EX)
    assert (
        stages.gate_summary(plan, gate)
        == "Review Robin session · Confidential · Entry decided by hand"
    )
    fields = stages.fields_of(
        stages.Gate(
            "g9", 9, "x", "RRW", (stages.GateResult("r1", "Score", stages.Field(), "mean"),)
        )
    )
    assert [(f.key, f.label) for f in fields] == [("f1", "Score")]


def test_a_gate_card_shows_no_progress_and_says_what_evaluators_read(
    client: TestClient,
) -> None:
    """The author, 2026-11-17 (rung 4e): progress is Evaluations', not
    Process's; what evaluators read sits under Response fields, redacted
    in a blind exercise."""
    text = client.get(f"/applydesk/operator/exercises/{EX}/process").text
    assert "Progress:" not in text and "Panel sees" not in text
    fields = text[text.index("data-pc-fields") : text.index("data-pc-results")]
    assert "Evaluators read the dossier's <em>Shown to evaluators</em> part." in fields
    blind = client.get(f"/applydesk/operator/exercises/{BLIND}/process").text
    assert "<em>Shown to evaluators</em> part, redacted." in blind


def test_a_gate_lists_its_evaluator_sources(client: TestClient) -> None:
    """Ruling 27 (AD1G rungs 3-4): a gate's Evaluators are ranked sources,
    each a kind, its question or panel, a min and max, a Total within
    them and the assignment mode; a sent gate's are fixed."""
    text = client.get(f"/applydesk/operator/exercises/{EX}/process").text
    gate = text[text.index('data-item="gate"') : text.index('data-pc-act="remove-gate"')]
    rows = re.findall(r'data-ps-row data-kind="(\w+)"', gate)
    assert rows == ["panel"]
    assert '<option value="current-ras" selected>Current RAs</option>' in gate
    assert re.findall(r'data-ps="(?:min|max)" value="(\d*)"', gate) == ["29", "30"]
    assert re.findall(r'data-ps="total-(?:min|max)" value="(\d*)"', gate) == ["29", "30"]
    assert "within 29–30" in gate
    assert '<option value="automatic" selected>Automatic</option>' in gate
    assert '<select class="fc-in" data-ps="mode" disabled' in gate
    for control in ('data-ps="kind"', 'data-ps-act="up"', 'data-ps-act="add"', 'data-ps="min"'):
        at = gate.index(control)
        assert "disabled" in gate[at : gate.index(">", at)], control


def test_a_new_source_is_a_panel_of_one(client: TestClient) -> None:
    """+ Source adds the page's blank source: a panel, none chosen yet,
    one per dossier; its controls live (not sent)."""
    text = client.get(f"/applydesk/operator/exercises/{DRAFT}/process").text
    tpl = text[text.index('<template id="pc-new-source">') :]
    tpl = tpl[: tpl.index("</template>")]
    assert re.findall(r'data-ps-row data-kind="(\w+)"', tpl) == ["panel"]
    assert '<option value="" selected>No panel yet</option>' in tpl
    assert re.findall(r'data-ps="(?:min|max)" value="(\d*)"', tpl) == ["1", "1"]
    assert "disabled title" not in tpl


def test_process_names_what_keeps_each_stage_from_publishing(client: TestClient) -> None:
    """Segment AD1K, AD-20: a draft stage lists its publish problems; a
    published one its status, Revert, and the lock's reason."""
    draft = client.get("/applydesk/operator/exercises/c4xh2ndv6s/process").text
    assert "Before it can be published:" in draft
    assert "<li>Gate 1 · Placement interview has no evaluators.</li>" in draft
    assert "<li data-pc-prev>Stage 1 is not published yet.</li>" in draft
    model = client.get("/applydesk/operator/exercises/wa9juxbc2t/process").text
    assert "data-pc-status>Published</span>" in model
    assert 'data-locked="Interviews is published: revert it to draft to change this"' in model
    assert "Interviews is published: what it holds is fixed until it is reverted to draft." in model


def test_home_and_the_lobby_say_each_stage_s_status(client: TestClient) -> None:
    """Segment AD1K: the timeline's operator part names each stage's
    status; the lobby and the status row the exercise's, from its stages."""
    home = client.get("/applydesk/operator/exercises/wa9juxbc2t").text
    rows = re.findall(r'data-tl-status><b>Stage <span class="chip chip-\w+">(\w+)</span>', home)
    assert rows == ["Completed", "Completed", "Published"]
    lobby = client.get("/applydesk/operator/exercises").text
    assert '<span class="chip chip-warn">Draft</span>' in lobby
    assert '<span class="chip chip-info">Published</span>' in lobby  # as a stage's


def test_a_stage_with_nothing_blocking_is_ready_to_publish(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AD1K, at the author's check: a draft stage nothing blocks says so
    in the timeline's operator part."""
    monkeypatch.setattr(locks, "publish_problems", lambda e, st: ())
    monkeypatch.setattr(sample_data, "setup_missing", lambda e: ())
    home = client.get(f"/applydesk/operator/exercises/{DRAFT}").text
    assert home.count("Ready to publish.") == 2 and "Blocking publication" not in home


def test_pages_say_what_works_and_what_is_not_built(client: TestClient) -> None:
    """The register's copy rows (AD-06, 10-13, 19, 29): one banner, honest
    copy, and a reason on every inert control."""
    home = client.get("/applydesk/operator/exercises/wa9juxbc2t").text
    assert "what you do here works on screen, but nothing is saved, and a reload" in home
    extract = client.get("/applydesk/operator/exercises/wa9juxbc2t/extract").text
    assert "the files are built from the sample, not from edits made on other pages" in extract
    assert "Keep it apart from the files above." in extract and "logged" not in extract
    emails = client.get("/applydesk/operator/exercises/wa9juxbc2t/emails").text
    assert "come from Apply Desk; Review Robin sends none" in emails
    assert "and Dossiers' <em>Released</em> still read the sample's templates" in emails
    evaluations = client.get("/applydesk/operator/exercises/wa9juxbc2t/evaluations").text
    assert "Results come back by dossier" in evaluations
    lobby = client.get("/applydesk/operator/exercises").text
    # New exercise works (segment AD1N): a scratch exercise, its form hidden
    # until asked for, saying what a scratch exercise is.
    assert 'data-nx-open aria-expanded="false" aria-controls="nx-form">New exercise<' in lobby
    assert "never saved, gone after a restart" in lobby
    # A draft on an exercise whose form has closed says so (AD-29).
    draft = client.get("/applydesk/me/exercises/wa9juxbc2t/applications/f2ps7nyh4k").text
    assert "Applications closed on 30 Sep 2026, 23:59." in draft and ">Submit<" not in draft


def test_crumbs_and_headings_after_the_register(client: TestClient) -> None:
    """AD-100, 101, 103: the /me pages and the gate page carry a crumb
    just under the bar; card and section titles are h2."""
    me = "/applydesk/me/exercises/wa9juxbc2t"
    for path, current in ((me, ""), (f"{me}/applications/f2ps7nyh4k", "Your application")):
        page = client.get(path).text
        assert 'class="crumbs" aria-label="Breadcrumb"' in page and 'class=" crumbed"' in page
        assert '<a href="/applydesk/me">User Lobby</a>' in page
        # The separator is drawn before each later crumb, so a wrapped
        # name strands none (AD-102; ruling 64, F11): no "/" in the markup.
        assert '<span class="crumb"><a href="/applydesk/me">User Lobby</a></span>' in page
        assert 'aria-hidden="true">/</span>' not in page
        assert f'aria-current="page">{current}' in page
    app = client.get(f"{me}/applications/f2ps7nyh4k").text
    assert "<h3" not in app.split('class="page"', 1)[-1].split("<footer", 1)[0]
    gate = client.get(f"/applydesk/operator/exercises/{EX}/evaluations/gate_1").text
    crumb = gate[gate.index('class="crumbs"') : gate.index("</nav>", gate.index('class="crumbs"'))]
    assert "/evaluations" in crumb and 'aria-current="page">Gate 1 · ' in crumb
    assert crumb.count('<span class="crumb">') == 3  # root, exercise, Evaluations (AD-102)
    assert ">Operator Lobby</a>" in crumb
    assert "← Evaluations" not in gate
    assert '<h2 id="ev-pairs-h">Pairs</h2>' in gate
    # The pager twice on a long table, its count once (AD-108).
    assert gate.count("data-ev-pager-foot") == 1 + gate.count(".ev-pager[data-ev-pager-foot]")
    assert gate.count("data-ev-showing") == 1
    # The gate's state and its Review Robin action in its head (AD-23).
    head = gate[gate.index('class="ev-head"') : gate.index("</div>", gate.index('class="ev-head"'))]
    assert "data-gate-state>Results in<" in head  # done: no action left
    g2 = client.get(f"/applydesk/operator/exercises/{EX}/evaluations/gate_3").text  # not sent
    head = g2[g2.index('class="ev-head"') : g2.index("</div>", g2.index('class="ev-head"'))]
    assert "data-gate-state" in head and 'href="#ev-rr">Review Robin ↓</a>' in head
    # AD-33: why it is not ready, as saved, beside the chip.
    assert "data-gate-state>Not ready<" in head and ">40 dossiers to approve</span>" in head


def test_the_applicant_reaches_each_of_their_applications(client: TestClient) -> None:
    """AD-27: the lobby and the exercise page list each of the applicant's
    applications, the draft included."""
    me = "/applydesk/me/exercises/wa9juxbc2t"
    lobby = client.get("/applydesk/me").text
    page = client.get(me).text
    for app in ("m3qx8vkt2n", "f2ps7nyh4k"):
        assert f'href="{me}/applications/{app}"' in lobby
        assert f'href="{me}/applications/{app}"' in page


def test_one_count_of_applications_everywhere(client: TestClient) -> None:
    """AD-41: the lobby, Home and the status row count the same submitted
    applications, drafts and the withdrawn one apart; "draft" pluralized."""
    c = workflow.counts_of(EX)
    assert (c.submitted, c.drafts) == (100, 3)
    assert workflow.plural(1, "draft") == "1 draft" and workflow.plural(3, "draft") == "3 drafts"
    lobby = client.get("/applydesk/operator").text
    assert "<th>Submitted</th>" in lobby and "<td>100</td>" in lobby
    home = client.get(f"/applydesk/operator/exercises/{EX}").text
    assert "100 submitted · 3 drafts" in home


def test_an_applicant_reads_their_released_result(client: TestClient) -> None:
    """Ruling 41, AD-28: once an outcome is released to applicants, the
    applicant's own value shows on the exercise and application pages."""
    me = "/applydesk/me/exercises/wa9juxbc2t"
    page = client.get(me).text
    assert "Your result, Shortlisting: <strong>Re-appointment</strong>" in page
    app = client.get(f"{me}/applications/m3qx8vkt2n").text
    assert "<h2>Your results</h2>" in app and "Re-appointment" in app
    draft = client.get(f"{me}/applications/f2ps7nyh4k").text
    assert "Your results" not in draft  # nothing decided for a draft


def test_a_closed_exercise_stays_on_me_read_only(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ruling 41, AD-37: Closed stays on /me with its results; Archived and
    Draft do not."""
    import dataclasses

    ex = sample_data.exercise("wa9juxbc2t")
    assert ex is not None
    closed = dataclasses.replace(ex, state="Closed")
    monkeypatch.setattr(
        sample_data,
        "EXERCISES",
        tuple(closed if e.public_id == ex.public_id else e for e in sample_data.EXERCISES),
    )
    monkeypatch.setattr(sample_data, "exercise", lambda i: closed if i == ex.public_id else None)
    lobby = client.get("/applydesk/me").text
    assert "Closed: its released results stay here" in lobby
    page = client.get("/applydesk/me/exercises/wa9juxbc2t").text
    assert "This exercise is closed." in page and "Your result, Shortlisting" in page
    archived = dataclasses.replace(ex, state="Archived")
    monkeypatch.setattr(sample_data, "exercise", lambda i: archived)
    assert client.get("/applydesk/me/exercises/wa9juxbc2t").status_code == 404


def test_a_confidential_gate_s_page_shows_dossier_ids(client: TestClient) -> None:
    """Ruling 42, AD-65: a confidential gate's page shows Dossier IDs, not
    names, as its files do; a gate that is not confidential names them."""
    base = f"/applydesk/operator/exercises/{EX}/evaluations"
    conf = client.get(f"{base}/gate_2").text
    assert '>Dossier<a class="ev-sort-btn"' in conf
    assert "Aisha Bello" not in conf
    assert re.search(r"<td>(?:<input [^>]*>)?<code>\w{10}</code></td>", conf)
    named = client.get(f"{base}/gate_1").text
    assert '>Applicant<a class="ev-sort-btn"' in named


def test_blind_review_starts_outcomes_csv_with_dossier_ids() -> None:
    """AD-65: outcomes.csv names applicants by default only without blind
    review; Extract all data follows sensitive()."""
    import dataclasses

    ex = sample_data.exercise(EX)
    assert ex is not None
    assert extract.names_by_default(ex, "outcomes.csv")
    blind = dataclasses.replace(ex, blind=True)
    assert not extract.names_by_default(blind, "outcomes.csv")
    assert extract.names_by_default(blind, "applications.csv")


def test_another_application_s_page_shows_no_results(client: TestClient) -> None:
    """Cold read: Your results is the applicant's own, never another's."""
    other = client.get("/applydesk/me/exercises/wa9juxbc2t/applications/h6zr2tdw9p").text
    assert "Your results" not in other


def test_archived_closes_the_application_and_dossier_pages(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Author, 2026-11-18: an Archived exercise's application and dossier
    pages close with it; a Closed one's stay."""
    import dataclasses

    ex = sample_data.exercise("wa9juxbc2t")
    assert ex is not None
    me = "/applydesk/me/exercises/wa9juxbc2t"
    for state, code in (("Archived", 404), ("Draft", 404), ("Closed", 200)):
        moved = dataclasses.replace(ex, state=state)
        monkeypatch.setattr(sample_data, "exercise", lambda i, m=moved: m)
        assert client.get(f"{me}/applications/m3qx8vkt2n").status_code == code, state
        assert client.get(f"{me}/dossiers/p3bd7kq2wx").status_code == code, state


def test_a_hidden_applicant_on_a_panel_is_never_their_own_evaluator() -> None:
    """Author, 2026-11-18: a blind or confidential gate's data names no
    applicant, but gives each dossier the panel member it may not take."""
    plan = stages.plan_of(EX)
    gate = next(c for c in plan.columns if isinstance(c, stages.Gate) and c.number == 1)
    rows, _ = stages.assignments(EX, gate)
    data = stages.page_data(EX, gate, rows, blind=True)
    dossiers = cast(list[list[str]], data["dossiers"])
    panel = {
        e.lower()
        for p in cast(list[list[Any]], data["panels"])
        for _, e in cast(list[list[str]], p[1])
    }
    assert all(d[2] == "" for d in dossiers)  # no email for who they are
    selfs = [d[3] for d in dossiers if d[3]]
    assert selfs and all(s in panel for s in selfs)  # current RAs reapplying


def test_the_outcomes_card_follows_its_file_under_blind_review(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cold read: blind, the Outcomes card starts on Dossier IDs, says
    why, lists no applicant columns, and lets the operator choose Names."""
    import dataclasses

    ex = sample_data.exercise(EX)
    assert ex is not None
    blind = dataclasses.replace(ex, blind=True)
    monkeypatch.setattr(sample_data, "exercise", lambda i: blind)
    page = client.get(f"/applydesk/operator/exercises/{EX}/extract").text
    card = page[page.index('data-xd-card="outcomes"') : page.index('data-xd-card="alias"')]
    assert "Dossier IDs to start with: blind review is on." in card
    assert 'data-xd-v="ids" aria-pressed="true"' in card and "applicant, email" not in card


def test_withdrawal_closes_once_a_gate_holding_the_dossier_completes(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rulings 45, 49: an applicant may withdraw (Outline-amber, AD4) until
    a gate holding their dossier completes, Sent included; then the page
    says which."""
    page = client.get("/applydesk/me/exercises/wa9juxbc2t/applications/m3qx8vkt2n").text
    assert workflow.withdrawal_closed_by("wa9juxbc2t", "m3qx8vkt2n") == "Peer review"
    assert "your application has gone to Peer review" in page and ">Withdraw</button>" not in page
    for state in ("Ready", "Sent"):
        monkeypatch.setattr(workflow, "gate_sent", lambda _e, _k, s=state: (s, ""))
        open_page = client.get("/applydesk/me/exercises/wa9juxbc2t/applications/m3qx8vkt2n").text
        withdraw = 'disabled title="Withdrawing is not built yet">Withdraw'
        assert f'class="btn btn-alert" type="button" {withdraw}' in open_page, state


def test_extract_s_many_of_chips_are_pills(client: TestClient) -> None:
    """Ruling 47, AD-68: Carries and Extract setup's pages are .pn-show
    pills, never Primary-looking buttons."""
    page = client.get(f"/applydesk/operator/exercises/{EX}/extract").text
    chips = re.findall(r'<button type="button" class="([^"]+)" data-xd-t=', page)
    assert chips and set(chips) == {"pn-show"}


def test_dossiers_rows_are_named_by_dossier_id(client: TestClient) -> None:
    """AD-89, ruling 25: a Dossiers row is named by its Dossier ID, linking
    to the dossier, its Application ID under it; the dossier page shows
    its ID."""
    page = client.get(f"/applydesk/operator/exercises/{EX}/dossiers").text
    assert (
        'aria-label="Tick every row in view"><button type="button" class="ap-sort" '
        'data-ap-sort="dossier">Dossier<' in page
    )
    assert (
        f'href="/applydesk/operator/exercises/{EX}/dossiers/p3bd7kq2wx"><code>p3bd7kq2wx</code></a>'
        '<span class="ap-app">Application <code>m3qx8vkt2n</code></span>'
    ) in page
    # The search box is labelled where it stands (ruling 64, U17).
    assert 'data-ap-app="m3qx8vkt2n"' in page and '<label class="ap-f">Search<input' in page
    dossier = client.get(f"/applydesk/me/exercises/{EX}/dossiers/p3bd7kq2wx").text
    assert "<dt>Dossier ID</dt><dd><code>p3bd7kq2wx</code></dd>" in dossier


def test_a_gate_page_s_pairs_take_ticks_off_until_the_script_runs(client: TestClient) -> None:
    """Ruling 51: a tick per pair and one in the header, rendered off until
    the page's script runs; on a gate whose session has opened, off and
    saying why."""
    base = f"/applydesk/operator/exercises/{EX}/evaluations"
    g3 = client.get(f"{base}/gate_3").text
    rows = g3.count("data-ev-pair=")
    assert rows and g3.count("data-ev-tick ") == rows
    assert 'data-ev-tick-all aria-label="Tick every pair on this page" disabled data-ev-wait' in g3
    g1 = client.get(f"{base}/gate_1").text
    assert (
        'data-ev-tick-all aria-label="Tick every pair on this page" disabled '
        'title="Its session has opened: its pairs are Review Robin\'s to change"' in g1
    )


def test_preview_s_sample_values_follow_each_kind() -> None:
    """Segment AD1L: the first submitted application fills an applicant's
    fields, the outcome's value in its row (or its tally, to evaluators),
    and the evaluator is the first member of that stage's gate panel."""
    e = sample_data.exercise(EX)
    assert e is not None
    mails = {m.name: m for m in workflow.emails(EX)}
    receipt = workflow.sample_values(e, mails["Applications: Receipt · Applicants"])
    assert receipt == {
        "applicant_name": "Aisha Bello",
        "exercise_name": e.name,
        "application_id": "m3qx8vkt2n",
        "exercise_url": f"/me/exercises/{EX}",
        "help_contact": sample_data.help_contact(e),
    }
    review = workflow.sample_values(e, mails["Review: Outcome · Applicants"])
    assert (review["stage_name"], review["outcome"]) == ("Review", "Re-appointment")
    panel = workflow.sample_values(e, mails["Interviews: Outcome · Evaluators"])
    assert (panel["evaluator_name"], panel["outcome"]) == ("Dr Hana Ito", "55 pending")
    assert "applicant_name" not in panel


def test_every_merge_tag_has_its_description_and_every_default_its_own_tags() -> None:
    """Ruling 54: each kind's tags each carry a description, and each
    default names only its own kind's tags."""
    tags = {t for fields in workflow.EMAIL_FIELDS.values() for t in fields}
    assert tags == set(workflow.TAG_HELP)
    for kind, (subject, body) in workflow.DEFAULT_TEMPLATES.items():
        named = set(re.findall(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)", subject + body))
        assert named <= set(workflow.EMAIL_FIELDS[kind]), kind


def test_a_state_has_one_tone_everywhere() -> None:
    """Ruling 64, U1: one map, RRW's palette: Draft amber, Closed red,
    Completed green; the stage chip, the status row and Home's rows agree."""
    from applydesk import locks, tones

    assert (tones.tone("Draft"), tones.tone("Closed"), tones.tone("Completed")) == (
        "warn",
        "bad",
        "ok",
    )
    assert locks.STATUS_CHIP == {s: tones.tone(s) for s in locks.STATUS_CHIP}
    page = (
        TestClient(host_with(("applydesk",))[0])
        .get("/applydesk/operator/exercises/n5wg8tjr3e")
        .text
    )
    # The draft's status row and its stage chip: both amber.
    assert 'chip-mute">Draft' not in page and 'chip-warn">Draft' in page


def test_a_dossier_has_an_operator_page_under_dossiers(client: TestClient) -> None:
    """Ruling 64, U20: the page sits under Dossiers, its breadcrumb back
    there; it shows the application, the row's gates and outcomes and what
    evaluators read; View as applicant opens the applicant's page in a new
    tab; Dossiers' ID links come here."""
    page = client.get(f"/applydesk/operator/exercises/{EX}/dossiers/p3bd7kq2wx").text
    crumb = page[page.index('class="crumbs"') : page.index("</nav>", page.index('class="crumbs"'))]
    assert f'href="/applydesk/operator/exercises/{EX}/dossiers">Dossiers</a>' in crumb
    assert 'aria-current="page">Dossier p3bd7kq2wx' in crumb
    for card in ("application", "progress", "shown"):
        assert f'data-od-card="{card}"' in page
    assert "Aisha Bello" in page and "<code>m3qx8vkt2n</code>" in page
    assert "Gate 1 · Peer review" in page and ">Entered</span>" in page
    evaluators = f'href="/applydesk/me/exercises/{EX}/dossiers/p3bd7kq2wx" target="_blank"'
    assert evaluators in page and "data-od-as-evaluators>View as evaluators see it" in page
    dossiers = client.get(f"/applydesk/operator/exercises/{EX}/dossiers").text
    assert f'href="/applydesk/operator/exercises/{EX}/dossiers/p3bd7kq2wx"' in dossiers
    assert client.get(f"/applydesk/operator/exercises/{EX}/dossiers/nope").status_code == 404
    # A draft has no dossier yet (ruling 32), so no page.
    assert client.get(f"/applydesk/operator/exercises/{EX}/dossiers/w5jh8ntq3d").status_code == 404


def test_every_operator_section_has_one_intro_under_its_h1(client: TestClient) -> None:
    """F1, AD-85: a `pc-intro` line under the h1 on every section page,
    Dossiers', Evaluations' and Extract's included."""
    for section in ("process", "form", "panels", "emails", "dossiers", "evaluations", "extract"):
        text = client.get(f"/applydesk/operator/exercises/{EX}/{section}").text
        assert text.count('class="muted pc-intro"') == 1, section
        assert text.index("</h1>") < text.index('class="muted pc-intro"'), section
    # Dossiers' intro says where its columns come from; its key stays below.
    dossiers = client.get(f"/applydesk/operator/exercises/{EX}/dossiers").text
    assert "come from Process" not in dossiers[dossiers.index("ap-help") :]


def test_evaluations_says_what_the_link_is_in_words(client: TestClient) -> None:
    """AD-92: Evaluations' copy describes the dossier's link, not the
    handoff's field name (that stays in the gate page's file list)."""
    text = client.get(f"/applydesk/operator/exercises/{EX}/evaluations").text
    assert "ProfileLink" not in text
    assert "each dossier with a link to its page here" in text


def test_one_label_and_role_creates_a_panel(client: TestClient) -> None:
    """U8 and U6, AD-72: + Panel, Secondary, on Panels and in the inline
    box on Form and Process; Form's add is + Question."""
    panels = client.get(f"/applydesk/operator/exercises/{EX}/panels").text
    assert (
        '<button type="button" class="btn btn-secondary" data-pn-act="create">+ Panel</button>'
        in panels
    )
    for section in ("form", "process"):
        text = client.get(f"/applydesk/operator/exercises/{DRAFT}/{section}").text
        assert (
            '<button type="button" class="btn btn-secondary" data-np-act="create">+ Panel</button>'
            in text
        ), section
        assert "Create panel" not in text, section
    form = client.get(f"/applydesk/operator/exercises/{EX}/form").text
    assert 'data-fc-act="new">+ Question</button>' in form and ">+ New</button>" not in form


# --- Segment AD1S rung 3: the copy sweep ---
CITATION = re.compile(r"ruling \d+|\(R\d+\)|segment AD|\bAD-?\d+|\(G\d+\)", re.IGNORECASE)


_JS_TOKEN = re.compile(
    r"""//[^\n]*|/\*.*?\*/|"(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*'|`(?:[^`\\]|\\.)*`""", re.DOTALL
)


def _js_strings(code: str) -> list[str]:
    """A script's string literals, its comments skipped: what it may write
    on screen. A regex literal holding a quote would throw it; none does."""
    return [t[1:-1] for t in _JS_TOKEN.findall(code) if t[0] in "\"'`"]


class _Visible(HTMLParser):
    """A page's visible text, its tooltips and placeholders included; its
    scripts' string literals apart, since a script puts them on screen."""

    def __init__(self) -> None:
        super().__init__()
        self.text: list[str] = []
        self.said: list[str] = []
        self._in: str = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self._in = tag
        self.text += [v for k, v in attrs if k in ("title", "placeholder", "aria-label") and v]

    def handle_endtag(self, tag: str) -> None:
        if tag == self._in:
            self._in = ""

    def handle_data(self, data: str) -> None:
        if self._in == "script":
            self.said += _js_strings(data)
        elif not self._in:
            self.text.append(data)


def _swept_pages(client: TestClient) -> list[str]:
    """Every operator page and /me page of every sample exercise: Home,
    each section, the preview, each gate's page and a dossier's."""
    pages = list(PAGES)
    for e in sample_data.EXERCISES:
        base = f"/applydesk/operator/exercises/{e.public_id}"
        sections = ("process", "form", "panels", "emails", "dossiers", "evaluations", "extract")
        pages += [base, f"{base}/form/preview", *(f"{base}/{s}" for s in sections)]
        pages += sorted(
            set(re.findall(rf"{base}/evaluations/gate_\d+", client.get(f"{base}/evaluations").text))
        )
        pages += re.findall(
            rf"{base}/dossiers/[a-z0-9]{{10}}", client.get(f"{base}/dossiers").text
        )[:1]
    me = client.get("/applydesk/me").text
    pages += sorted(set(re.findall(r"/applydesk/me/exercises/[a-z0-9/]+", me)))
    return list(dict.fromkeys(pages))


def test_no_page_cites_a_ruling_a_segment_or_an_ad_number(client: TestClient) -> None:
    """AD1S's copy sweep: no visible text, tooltip or scripted message on
    an operator or /me page cites a ruling, a segment or an AD number.
    Template comments are not copy, and stay."""
    pages = _swept_pages(client)
    assert len(pages) > len(PAGES)
    for path in pages:
        response = client.get(path)
        assert response.status_code == 200, path
        seen = _Visible()
        seen.feed(response.text)
        for line in seen.text + seen.said:
            assert not CITATION.search(line), (path, " ".join(line.split()))


def test_details_says_only_what_the_operator_needs(client: TestClient) -> None:
    """AD1S: Details no longer explains Invitation only or Blind review in
    the words of the spec; the fields say what each does."""
    for e in (EX, BLIND, DRAFT, BLANK):
        home = client.get(f"/applydesk/operator/exercises/{e}").text
        assert "Invitation only hides the exercise" not in home, e
        assert "On, evaluators' dossiers redact" not in home, e
        assert "Blind review" in home, e
