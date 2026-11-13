"""The URL map as placeholders (segment AD1, item 2): every page answers
locally, IDs are shape-checked, the gate holds deployed, every link stays
in the mount, and a blind application file names nobody."""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from applydesk import gate, sample_data, stages, workflow
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
    f"/applydesk/operator/exercises/{EX}",
    *(
        f"/applydesk/operator/exercises/{EX}/{section}"
        for section in (
            "process",
            "form",
            "gates",
            "emails",
            "applications",
            "evaluations",
            "extract",
        )
    ),
    f"/applydesk/operator/exercises/{EX}/form/preview",
    f"/applydesk/operator/exercises/{OPEN}",  # open for applications
    f"/applydesk/operator/exercises/{OPEN}/applications",  # only its first stage
    f"/applydesk/operator/exercises/{BLANK}/form/preview",
    f"/applydesk/operator/exercises/{BLIND}",  # in Stage 2; blind review on
    f"/applydesk/operator/exercises/{BLIND}/gates",  # no reviewer pool
    f"/applydesk/operator/exercises/{BLIND}/evaluations",  # blind: the alias key
    f"/applydesk/operator/exercises/{DRAFT}/process",  # the Setup stage is now
    f"/applydesk/operator/exercises/{DRAFT}",  # the Publish step
    f"/applydesk/operator/exercises/{DRAFT}/applications",  # none yet
    f"/applydesk/operator/exercises/{BLANK}",
    *(
        f"/applydesk/operator/exercises/{BLANK}/{section}"
        for section in (
            "process",
            "form",
            "gates",
            "emails",
            "applications",
            "evaluations",
            "extract",
        )
    ),
    "/applydesk/me",
    f"/applydesk/me/exercises/{EX}",
    f"/applydesk/me/exercises/{BLIND}",  # applications have closed
    f"/applydesk/me/exercises/{EX}/applications/m3qx8vkt2n",
    f"/applydesk/me/exercises/{EX}/files/p3bd7kq2wx",
    f"/applydesk/me/exercises/{BLIND}/files/t8nv4hzm2c",
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
        "/applydesk/me/exercises/c4xh2ndv6s",  # a draft is not open to applicants
        f"/applydesk/me/exercises/{BLANK}",
        f"/applydesk/me/exercises/{EX}/applications/zzzzzzzzzz",
        f"/applydesk/me/exercises/{EX}/applications/M3QX8VKT2N",  # an application ID's shape
        f"/applydesk/me/exercises/{EX}/applications/m3qx8vkt2",
        f"/applydesk/me/exercises/{EX}/files/P3BD7KQ2WX",  # a file ID's shape
        f"/applydesk/me/exercises/{EX}/files/p3bd7kq2wx0",
        f"/applydesk/me/exercises/{EX}/files/m3qx8vkt2n",  # an application ID is no file ID
        f"/applydesk/me/exercises/{BLIND}/files/p3bd7kq2wx",  # another exercise's file
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
    samples += [a.file_id for a in sample_data.APPLICATIONS]
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


def test_a_blind_application_file_names_nobody(client: TestClient) -> None:
    app = sample_data.by_file(BLIND, "t8nv4hzm2c")
    assert app is not None
    page = client.get(f"/applydesk/me/exercises/{BLIND}/files/t8nv4hzm2c").text
    for identifying in (app.applicant, app.email, app.public_id):
        assert identifying not in page, identifying
    assert "Redacted" in page


def test_an_open_application_file_names_the_applicant(client: TestClient) -> None:
    page = client.get(f"/applydesk/me/exercises/{EX}/files/p3bd7kq2wx").text
    assert "Aisha Bello" in page


@pytest.mark.parametrize("file", ["p3bd7kq2wx", "t8nv4hzm2c"])
def test_a_file_shows_only_the_part_shown_to_reviewers(client: TestClient, file: str) -> None:
    exercise = EX if file == "p3bd7kq2wx" else BLIND
    page = client.get(f"/applydesk/me/exercises/{exercise}/files/{file}").text
    assert "Shown to reviewers" in page and "Not shown to reviewers" not in page
    for hidden in sample_data.NOT_SHOWN_TO_REVIEWERS:
        assert hidden not in page, hidden


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
    """A router that forgot `Depends(placeholders_only)` would pass the
    path checks above; this walks every route the factory builds."""
    routes = list(_gated_routes(create_app().routes))
    assert len(routes) > 1
    missing = [
        r.path for r, calls in routes if r.path != "/health" and gate.placeholders_only not in calls
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
    """Iteration rung 4 (author, 2026-11-12): an Exercise Code column, as
    RRW's Session Code; the public ID is only in each row's link."""
    page = client.get("/applydesk/operator/exercises").text
    assert "<th>Exercise Code</th>" in page and ">ID<" not in page
    for e in sample_data.EXERCISES:
        if e.code:  # a just-created exercise has none yet
            assert f"<code>{e.code}</code>" in page
        assert f"<code>{e.public_id}</code>" not in page
    codes = [e.code for e in sample_data.EXERCISES if e.code]
    assert len(set(codes)) == len(codes)


def test_withdraw_is_destructive(client: TestClient) -> None:
    """The applicant cannot undo a withdrawal (author, 2026-11-12)."""
    page = client.get(f"/applydesk/me/exercises/{EX}/applications/h6zr2tdw9p").text
    assert '<button class="btn btn-destructive" type="button" disabled>Withdraw</button>' in page


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
    assert re.findall(tab, setup) == ["Process", "Form", "Gates", "Emails"]
    assert re.findall(tab, ops) == ["Applications", "Evaluations", "Extract data"]
    assert '<nav class="crumbs" aria-label="Breadcrumb">' in text
    assert "<h1>Undergraduate Research Fellowship 2027</h1>" in text


def test_the_status_row_says_where_each_item_stands(client: TestClient) -> None:
    text = client.get(f"/applydesk/operator/exercises/{EX}/applications").text
    row = text[text.index("data-status>") + len("data-status>") :]
    row = re.sub(r"<[^>]+>", "", row[: row.index("</p>")])
    assert row == (
        "Exercise: Published · Form: Closed · Gates: 2 of 3 done · "
        "Outcomes: 1 of 3 released · Emails: 4 of 6 · Applications: 89 submitted"
    )
    blank = client.get(f"/applydesk/operator/exercises/{BLANK}/process").text
    assert 'Gates: <span class="chip chip-warn">none</span>' in blank


@pytest.mark.parametrize(
    "old",
    ["settings", "assessors", "timeline", "export", "report"]
    + ["setup", "panels", "review", "reports"],  # ruling 14
)
def test_the_retired_sections_are_gone(client: TestClient, old: str) -> None:
    assert client.get(f"/applydesk/operator/exercises/{EX}/{old}").status_code == 404


@pytest.mark.parametrize(
    ("exercise_id", "now"),
    [(DRAFT, "Stage 1"), (OPEN, "Stage 1"), (EX, "Interview"), (BLIND, "Stage 2")],
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
    assert names == ["Call for applications", "Review", "Interview", "Decision"]
    assert len(_stage_cards(text)) == 4
    items = re.findall(r'<div class="pc-item" data-item="(\w+)"', text)
    assert items == ["form", "gate", "gate", "outcome", "gate", "outcome", "outcome"]
    assert "Combined ≥ 4.2 → Shortlisted, else Not shortlisted" in text
    assert 'value="30" inputmode="numeric" aria-label="Peer Review, percent"' in text
    assert "Decided by hand" in text  # Final results
    # Ruling 16: an outcome ticks whom it emails; Emails holds the template.
    assert "data-rel-template" not in text
    assert len(re.findall(r'data-rel="applicants-email" checked', text)) == 3
    assert len(re.findall(r'data-rel="evaluators-email" checked', text)) == 1
    assert "4 stages · 3 gates · 3 outcomes" in full
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


def test_applications_generates_application_files(client: TestClient) -> None:
    text = client.get(f"/applydesk/operator/exercises/{EX}/applications").text
    assert "Generate application files" in text
    # Operators open every application file (author, 2026-11-12).
    assert "/applydesk/me/exercises/wa9juxbc2t/files/p3bd7kq2wx" in text


def test_gates_carries_each_gate_as_a_card_with_its_panel(client: TestClient) -> None:
    """Segment AD1F: a card per gate in timeline order, its panel's chip
    and members, the Outline beside; a sent gate keeps its panel."""
    text = client.get(f"/applydesk/operator/exercises/{EX}/gates").text
    assert re.findall(r'data-kind="gate" data-gate="(\w+)"', text) == ["g1", "g2", "g3"]
    chips = re.findall(r'data-sum="panel">([^<]*)<', text)
    assert chips == ["Panel A · 2 people", "Panel B · 1 person", "Interviewers · 2 people"]
    assert "Prof Ivan Petrov" in text  # the interviewers, on the Interview gate
    assert re.findall(r'data-o-panel="\w+">([^<]*)<', text) == [
        "Panel A",
        "Panel B",
        "Interviewers",
    ]
    # Every gate here is sent: its menu is fixed.
    assert text.count('data-gc-panel disabled title="Sent') == 3
    # A gate picks a panel, never Institution-wide.
    menu = text[text.index("data-gc-panel") : text.index("</select>", text.index("data-gc-panel"))]
    assert ">Institution-wide<" not in menu and ">Reviewer pool<" in menu
    assert ">+ New panel…</option>" in menu


def test_a_gate_with_no_panel_says_so(client: TestClient) -> None:
    """The draft's selection gate was added just in time: no panel yet,
    and it has none to choose from but one it makes."""
    text = client.get(f"/applydesk/operator/exercises/{DRAFT}/gates").text
    assert re.findall(r'data-sum="panel">([^<]*)<', text) == ["No panel"]
    assert '<option value="" selected>No panel yet</option>' in text
    assert "data-gc-panel disabled" not in text
    # A lone card loads open.
    assert 'data-gate="g1" id="gate-g1" data-open' in text


def test_emails_lists_every_template_process_makes_owed(client: TestClient) -> None:
    """Ruling 16: one template per item and audience Process ticks, named
    for its stage, in timeline order; written or owed."""
    text = client.get(f"/applydesk/operator/exercises/{EX}/emails").text
    names = re.findall(r'<section class="card" data-email="([^"]+)">', text)
    assert names == [
        "Call for applications: Receipt - Applicants",
        "Call for applications: Reminder - Applicants",
        "Review: Outcome - Applicants",
        "Interview: Outcome - Applicants",
        "Interview: Outcome - Panel evaluators",
        "Decision: Outcome - Applicants",
    ]
    chips = re.findall(r'<span class="chip chip-\w+">(Written|Owed)</span>', text)
    assert chips == ["Written", "Written", "Written", "Written", "Owed", "Owed"]


def test_evaluations_lists_each_gate_s_progress(client: TestClient) -> None:
    text = client.get(f"/applydesk/operator/exercises/{EX}/evaluations").text
    assert re.findall(r'<tr data-gate="(\w+)">', text) == ["g1", "g2", "g3"]
    assert "18 of 27 interviewed" in text and "Pull results</button>" in text


def test_extract_data_collates_every_evaluation_and_exports(client: TestClient) -> None:
    """Author, 2026-11-12: the evaluation responses, Review Robin's
    included, beside the data export (Reports until ruling 14)."""
    text = client.get(f"/applydesk/operator/exercises/{EX}/extract").text
    assert "<h2>Evaluation responses</h2>" in text
    for column in ("Assessment", "Interview", "Pool reviewer"):
        assert f"<th>{column}" in text
    assert "2 of 2 submitted · mean 4.5 of 5" in text  # from Review Robin
    assert "Received from Dr Hana Ito" in text  # the pool reviewer
    assert "Pull results from Review Robin" in text
    assert "<h2>Export bundle</h2>" in text and "Download export" in text


def test_a_draft_exercise_s_timeline_reads_cleanly(client: TestClient) -> None:
    text = client.get(f"/applydesk/operator/exercises/{DRAFT}").text
    assert "Not set to Not set" not in text and "Expected Not set" not in text
    assert "Dates not set" in text


def test_a_blank_exercise_lists_what_is_still_to_set_up(client: TestClient) -> None:
    """Author, 2026-11-12: one exercise as just created, with only a name."""
    home = client.get(f"/applydesk/operator/exercises/{BLANK}").text
    assert "<h1>Graduate Travel Grant 2027</h1>" in home and "No summary yet." in home
    assert "Still to set up before it can be published:" in home
    missing = home[home.index("Still to set up") :]
    missing = missing[: missing.index("</ul>")]
    base = "/applydesk/operator/exercises/n5wg8tjr3e"
    # Each item links to where it is set: Home's details, Process, Form.
    assert re.findall(r'<li><a href="([^"]+)">([^<]+)</a></li>', missing) == [
        (f"{base}#details", "Exercise Code"),
        (f"{base}#details", "Summary"),
        (f"{base}#details", "Who may apply"),
        (f"{base}/process", "Dates"),
        (f"{base}/form", "Application form"),
    ]
    assert "Dates not set" in home and "(a hard deadline)" not in home
    assert re.findall(r'data-wf-step="([^"]+)" aria-current="step"', home) == ["Application form"]


def test_a_blank_exercise_s_pages_say_what_is_missing(client: TestClient) -> None:
    base = f"/applydesk/operator/exercises/{BLANK}"
    lobby = client.get("/applydesk/operator/exercises").text
    row = lobby[lobby.index("Graduate Travel Grant 2027") :]
    assert '<span class="muted">Not set</span>' in row[: row.index("</tr>")]
    form = client.get(f"{base}/form").text
    cards = form[form.index('id="fb-cards"') : form.index('<template id="fb-new-field">')]
    assert cards.count('data-kind="field"') == 1 and 'placeholder="Untitled form"' in form
    assert "No applications yet." in client.get(f"{base}/applications").text
    assert "<h2>No gates yet</h2>" in client.get(f"{base}/gates").text
    # Ruling 16: a form's receipt is owed until Process says otherwise.
    assert 'data-email="Stage 1: Receipt - Applicants"' in client.get(f"{base}/emails").text
    assert "No submitted applications yet." in client.get(f"{base}/extract").text


def test_a_set_up_draft_lists_only_what_it_lacks(client: TestClient) -> None:
    home = client.get(f"/applydesk/operator/exercises/{DRAFT}").text
    missing = home[home.index("Still to set up") :]
    assert re.findall(r"<a [^>]*>([^<]+)</a></li>", missing[: missing.index("</ul>")]) == ["Dates"]


def test_a_blank_exercise_s_details_and_evaluations_say_not_yet(client: TestClient) -> None:
    base = f"/applydesk/operator/exercises/{BLANK}"
    home = client.get(base).text
    assert home.count('<span class="muted">Not set</span>') >= 3  # code, summary, contact
    assert "fellowships@example.edu" not in home
    review = client.get(f"{base}/evaluations").text
    assert "Nothing to send: the exercise is a draft." in review
    assert "Send to Review Robin</button>" not in review


def test_a_draft_with_nothing_missing_is_ready_to_publish(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sample_data, "setup_missing", lambda e: ())
    home = client.get(f"/applydesk/operator/exercises/{DRAFT}").text
    assert "Ready to publish: the details, the dates and the application form are complete." in home
    assert '<button class="btn btn-primary" type="button" disabled>Publish</button>' in home


def test_the_blank_exercise_is_not_offered_to_applicants(client: TestClient) -> None:
    assert "Graduate Travel Grant 2027" not in client.get("/applydesk/me").text


def test_profile_shows_nowhere_a_reader_sees(client: TestClient) -> None:
    """Ruling 13: what a reviewer opens is the application file. Review
    Robin's `ProfileLink` keeps its name: it is the handoff's field."""
    # The raw page: text, attributes (aria-label, title, placeholder) and
    # the scripts' strings alike.
    for path in PAGES:
        text = client.get(path).text.replace("<code>ProfileLink</code>", "")
        assert "profile" not in text.lower(), path
    assert client.get(f"/applydesk/me/exercises/{EX}/profiles/p3bd7kq2wx").status_code == 404


# --- Segment AD1D rung 3: the Workflow card (ruling 14) ---
def _steps(text: str) -> list[str]:
    return re.findall(r'data-wf-step="([^"]+)"', text)


def test_the_workflow_card_follows_the_timeline(client: TestClient) -> None:
    text = client.get(f"/applydesk/operator/exercises/{EX}").text
    assert _steps(text) == [
        "Application form",
        "Peer Review",
        "Faculty Panel Review",
        "Shortlist for interview",
        "Interview",
        "Finalists",
        "Final results",
        "Close and archive",
    ]
    groups = re.findall(r'<span class="wf-grp">([^<]+)</span>', text)
    assert groups == ["Call for applications", "Review", "Interview", "Decision", "Close"]
    # Next is the earliest step not done: Gate 3, sent, opening Evaluations.
    now = re.findall(r'data-wf-step="([^"]+)" aria-current="step"', text)
    assert now == ["Interview"]
    assert "Next: <strong>Gate 3 · Interview</strong> — 18 of 27 interviewed." in text
    assert f'href="/applydesk/operator/exercises/{EX}/evaluations">Open Evaluations</a>' in text
    assert "Not ready: its email to applicants is not written" in text  # Final results
    # Every action is inert until AD2 (author, 2026-11-13).
    card = text[text.index('aria-labelledby="wf-h"') :]
    card = card[: card.index("</section>")]
    assert "<button" in card and card.count("<button") == card.count("disabled>")


@pytest.mark.parametrize("section", ["applications", "evaluations", "extract"])
def test_the_workflow_card_sits_on_every_operations_page(client: TestClient, section: str) -> None:
    assert (
        'aria-labelledby="wf-h"' in client.get(f"/applydesk/operator/exercises/{EX}/{section}").text
    )


@pytest.mark.parametrize("section", ["process", "form", "gates", "emails"])
def test_setup_pages_carry_no_workflow_card(client: TestClient, section: str) -> None:
    assert (
        'aria-labelledby="wf-h"'
        not in client.get(f"/applydesk/operator/exercises/{EX}/{section}").text
    )


def test_a_draft_s_workflow_starts_at_opening_the_form(client: TestClient) -> None:
    text = client.get(f"/applydesk/operator/exercises/{BLANK}").text
    assert _steps(text) == ["Application form", "Close and archive"]
    assert "Next: <strong>Application form</strong> — Not open yet." in text
    assert "Open form…</button>" in text


# --- Segment AD1D: the cumulative read's fixes ---
def test_an_unnamed_stage_names_its_owed_template(client: TestClient) -> None:
    """Teaching Excellence: its outcome emails applicants, a template owed,
    named for its stage as Process labels it."""
    base = f"/applydesk/operator/exercises/{BLIND}"
    process = client.get(f"{base}/process").text
    assert 'data-rel="applicants-email" checked' in process
    home = client.get(base).text
    assert "Not ready: its email to applicants is not written" in home
    emails = client.get(f"{base}/emails").text
    assert 'data-email="Stage 2: Outcome - Applicants"' in emails


def test_the_breadcrumb_ends_at_the_page(client: TestClient) -> None:
    text = client.get(f"/applydesk/operator/exercises/{EX}/process").text
    crumbs = text[text.index('<nav class="crumbs"') :]
    crumbs = crumbs[: crumbs.index("</nav>")]
    assert re.findall(r">([^<>/]+)</(?:a|span)>", crumbs) == [
        "Exercises",
        "Undergraduate Research Fellowship 2027",
        "Process",
    ]
    assert f'<a href="/applydesk/operator/exercises/{EX}">Undergraduate' in crumbs


def test_every_panel_is_offered_on_gates(client: TestClient) -> None:
    """Teaching Excellence has interviewers but no interview gate: its
    panel is still offered on its one gate's menu (ruling 19)."""
    text = client.get(f"/applydesk/operator/exercises/{BLIND}/gates").text
    assert '<option value="interviewers">Interviewers</option>' in text


def test_a_sent_gate_opens_evaluations_except_from_evaluations(client: TestClient) -> None:
    link = f'href="/applydesk/operator/exercises/{EX}/evaluations">Open Evaluations</a>'
    assert link in client.get(f"/applydesk/operator/exercises/{EX}/applications").text
    assert link not in client.get(f"/applydesk/operator/exercises/{EX}/evaluations").text
    steps = workflow.steps(sample_data.exercise(EX) or sample_data.EXERCISES[0])
    sent = [s for s in steps if s.state == "Sent"]
    assert sent and all(s.action == "" and s.link == "evaluations" for s in sent)


# --- Rung 4's read: stages without an application, the close's date ---
def test_the_close_follows_the_last_stage_with_something_to_decide(client: TestClient) -> None:
    def close_line(exercise_id: str) -> str:
        e = sample_data.exercise(exercise_id)
        assert e is not None
        return workflow.steps(e)[-1].when

    assert close_line(EX) == "After 12 Dec"
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
    assert [s.title for s in workflow.steps(e)][0] == "Peer Review"
    assert workflow.current_stage(e) == "Interview"
    text = client.get(f"/applydesk/operator/exercises/{EX}/applications").text
    assert re.findall(r"<th class=\"ap-first\"[^>]*><b>([^<]+)</b>", text) == ["Applications"]
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
    assert titles.index("Faculty Panel Review") < titles.index("Application form")
    text = client.get(f"/applydesk/operator/exercises/{EX}/applications").text
    groups = re.findall(r"<th class=\"ap-(?:first|r)\"[^>]*><b>([^<]+)</b>", text)
    assert groups == ["Applications", "Review", "Interview", "Decision"]
    assert "From elsewhere" not in text
    assert workflow.current_stage(e) == "Interview"


def test_an_application_stage_later_in_the_timeline_keeps_the_headers_aligned(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An application stage that is not first, holding an outcome: its
    group sits at its place, once, and the group spans match the columns."""
    model = stages._STAGES[EX]  # pyright: ignore[reportPrivateUsage]  -- a sample's shape
    review, decision = model[1], model[3]
    apply = stages.Stage(9, "Apply", "1 Sep – 15 Oct", decision.columns, form=True)
    monkeypatch.setitem(stages._STAGES, EX, (review, apply, model[2]))  # pyright: ignore[reportPrivateUsage]  -- as above
    text = client.get(f"/applydesk/operator/exercises/{EX}/applications").text
    start = text.index('<tr class="ap-groups">')
    head = text[start : text.index("</thead>", start)]
    groups = re.findall(r"<th class=\"ap-(?:first|r)\"[^>]*><b>([^<]+)</b>", head)
    assert groups == ["Applications", "Review", "Apply", "Interview"]
    spans = sum(int(n) for n in re.findall(r'colspan="(\d+)"', head))
    second = head[head.index("</tr>") :]
    assert spans == second.count("<th")


def test_an_owed_email_holds_back_only_a_release_to_come() -> None:
    """Ruling 16: an owed email blocks an outcome not yet released, naming
    every audience owed; one already released is not blocked."""
    ex = sample_data.exercise(EX)
    assert ex is not None
    by_title = {s.title: s for s in workflow.steps(ex)}
    assert by_title["Shortlist for interview"].blocked == ""  # released
    assert by_title["Finalists"].blocked == (
        "Not ready: its email to panel evaluators is not written"
    )
    assert by_title["Final results"].blocked == (
        "Not ready: its email to applicants is not written"
    )


def test_is_operator_follows_the_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ruling 18: until AD2, everyone locally; deployed, the super-admin."""
    from starlette.requests import Request

    request = Request({"type": "http", "headers": []})
    assert gate.is_operator(request)  # a local run
    monkeypatch.setattr(gate, "is_local", lambda: False)
    someone = Identity(principal_id="1", email="someone@example.edu", name="Someone")
    monkeypatch.setattr(gate, "current_identity", lambda request: someone)
    assert not gate.is_operator(request)
    monkeypatch.setattr(gate, "current_identity", lambda request: None)
    assert not gate.is_operator(request)
    monkeypatch.setattr(type(someone), "is_super_admin", property(lambda self: True))
    monkeypatch.setattr(gate, "current_identity", lambda request: someone)
    assert gate.is_operator(request)
