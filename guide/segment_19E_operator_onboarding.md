# Segment 19E — Operator onboarding

**Status: planned 2026-09-06, not started.** Carved out of Segment 20 on
2026-09-05 when that segment was reserved for after the institutional Azure
deployment concludes; absorbed the short-lived 19F the same day. Everything
here needs the app, not the host, so none of it is gated.

Sibling of 19A (docs hygiene), 19B (code consistency) and 19C (behaviour /
contract polish). This one is **operator onboarding** — the theme is new,
which is why it is its own segment rather than a 19C item.

Four pieces of scope — workplan §18 items 1, 2, 4 and 5 — landing as a **six-rung PR ladder**; the Guide and the templates each split in two. Item 3 of that list (validation
explanations) is **already shipped** — `ValidationRule.why` is populated for
all 18 registered rules and renders as a "Why this check?" disclosure. Do not
rebuild it; Item 4 below reuses its pattern.

---

## Opportunity

A first-time operator arrives with no orientation, and every gap compounds the
next.

There is no entry point that says what a session is, what the setup pages do,
or what order to do them in. The setup pages tell them *how to operate the
form* (`.form-help`: "Fill in the new row below, then Save.") but never what
the page is for. At the first upload they must author three roster CSVs from a
written description of the header grammar, with nothing correctly-shaped to
start from — so the first upload is also the first time they find out whether
they understood the format. And nothing lets them look at a populated session
before they have successfully built one.

`docs/quickstart.md` answers all of it in 324 lines, and a first-time operator
does not know it exists. Worse, it is a **document about an app, kept outside
the app**: the 2026-09-05 sweep found it had gone stale once already, and
nothing structural stops that recurring.

Evidence (2026-09-06, tree at `be87b4ba`):

- No route, template or nav entry matching "Start Here" or "Guide" anywhere in
  `app/`.
- The workspace-level chrome carries **5** `chrome-link` entries (Settings ·
  Admin · About · Sign out, plus the theme toggle). Orientation is not among
  them.
- `app/web/templates/operator/sessions_list.html` has **no empty state** — an
  operator with zero sessions sees a table whose only message is "No sessions
  match."
- No downloadable template, blank-CSV route or sample file anywhere in `app/`.
- No seed, demo or fixture session in `app/`, `tools/` or the docs.

---

## Decision

**A single role-aware `/guide` page becomes the canonical operator
documentation, and `docs/quickstart.md` retires into it.** The Guide sits in
the chrome link row beside `/about`, takes the same `?return_to=` treatment,
and serves sections by the viewer's role — operator, reviewer, observer,
reviewee.

*Rejected: keeping `docs/quickstart.md` and adding a page that mirrors it.*
Two hand-maintained copies of the workflow is the drift this segment exists to
stop, and quickstart has already drifted once.

*Rejected: rendering `docs/quickstart.md` at request time.* Attractive — one
source, two surfaces — but there is **no markdown renderer in
`pyproject.toml`**, so it means a new runtime dependency and a `README.md`
update for a page whose content changes a few times a year. The
markdown-as-source shape can be revisited if the Guide ever grows past what a
template comfortably holds.

*Rejected: putting orientation only in the lobby.* It arrives at the right
moment but vanishes once the operator has a session, and there is nothing to
link to from an onboarding email.

**The lobby gets a first-run card**, not instead of the Guide but because the
Guide has to be found. An operator with zero sessions is the one moment
orientation is both most needed and cheapest to place.

**Templates ship as two sets from one location.** A **starter** set — one mock
row per file, for editing — and a **demo** set — populated enough to walk
through. The demo set is the sample session: uploaded through Quick Setup it
builds a working tutorial session **through the real import path**.

*Rejected: a seeded fixture (a `tools/` script or a sys-admin-gated in-app
action).* The Settings CSV already carries instruments
(`app/services/session_config_io/_apply_instrument.py`), and Quick Setup's
submit-all runs reviewers → reviewees → relationships → settings, so the four
porting CSVs can build a complete session with no seeding code at all. That
also removes the risk a seeding action carries: demo data appearing in a
deployed environment by accident.

*Rejected: a header-only "empty" template.* Two variants earn their keep only
if they do different jobs; empty-versus-one-row do not. One row teaches the
format, and it is the row an operator most often forgets to delete either way.
Starter-versus-demo is the split that matters: **edit this** versus **watch
this work**.

**Inline per-page guidance reuses the shipped `<details>` disclosure** — the
Validate page's "Why this check?"
(`app/web/templates/operator/partials/validation_results.html:51`).

*Rejected: tooltips.* They cannot hold a sentence, and they are invisible to
touch and awkward for keyboard.

*Rejected: the `.banner` family.* Segment 19C Item 8 established that it is
specced **behaviourally** as transient page-level feedback — redirect-back,
`.banner-scroll-target`, `margin-bottom`. Persistent explanation is not that.

---

## Semantics

**Guide role resolution.** The page renders the sections a viewer's role
entitles them to, not a role switcher. An operator who is also a reviewee sees
both. A signed-in user with no role sees the reviewer/reviewee material plus
the access help `/about` already carries — the "signed-in stranger" case 18R
Item 6 introduced. The Guide never 404s for a signed-in user; the worst case
is a short page.

**Guide and `/about` stay separate.** `/about` is identity and access — what
this software is, who to contact. `/guide` is how to run a session. The chrome
carries both; neither absorbs the other.

**quickstart retirement.** The file moves to `docs/archive/` rather than being
deleted, so the sweep's dead-reference pass finds a retired file rather than a
missing one. Every **live** inbound reference is repointed at `/guide`; archive
references stay as history.

**Lobby card trigger.** Shown when the signed-in operator has **zero** sessions
visible to them — not "has never had one". An operator who archives everything
sees it again, which is correct: they are back at the start.

**Template derivation.** Both sets are generated from the serializers that
already emit these shapes (`app/services/extracts/reviewers_extract.py`,
`reviewees_extract.py`, `relationships_extract.py`, and
`serialize_session_config` in `app/services/session_config_io/`), never
hand-authored. A hand-maintained CSV is a second source of truth for
`spec/csv_contracts.md` and will drift from the parser that reads it.

**Template contents.** All addresses use `example.edu` — already the
established convention at 1,845 uses against 88 `example.org` and 11
`example.com`. The demo set must be large enough that assignments, the
Responses grid and observer collation all show something; a one-reviewer
session demonstrates none of them.

**Demo set round-trip.** The demo set must survive its own import: download →
Quick Setup submit-all → a session that reaches `validated` with no
validation errors. That is the item's acceptance test, and it exercises the
real path rather than a fixture's.

**Inline guidance placement.** One `<details>` per setup page, page-level,
above the existing per-form `.form-help` — which stays. Mechanics and purpose
are different registers and should not merge.

---

## Judgment calls — decided

- **`/guide` not `/start-here`** (2026-09-06). The page serves returning
  operators looking something up as much as first-timers; "Start Here" names
  only the first visit.
- **Role-aware sections, not separate per-role pages** (2026-09-06). One URL
  to link from an email, and the roles overlap in practice.
- **Item 4 sequenced last** (2026-09-06). Per-page guidance has to speak the
  Guide's vocabulary; writing them in parallel guarantees two voices.
- **Role-filtering is wired from rung 2 but resolves to "all" until rung 7**
  (2026-09-06). The alternative — leave the seam out and add it at rung 7 —
  means the filter arrives untested against real content. Running it from the
  start with a constant audience set keeps the code path exercised by every
  rung's tests, so rung 7 changes one resolver rather than introducing a
  mechanism.
- ~~**Template downloads live in the Workflow card, as a "Download setup
  templates" row after the Setup checklist**~~ *(decided and then reversed the
  same day — 2026-09-06. Kept because the reason for the reversal is the
  argument for the shape that replaced it.)* The Workflow card put the
  templates in the operator's field of view at the moment they are useful, and
  made them **session-aware**: roster headers carry each renamed tag column's
  friendly label (`ReviewerTagN.<label>`, 19C Item 1), so a template generated
  inside a session matches that session's importer exactly. What killed it: the
  Quick Setup card renders on `session_new.html` as well as
  `session_detail.html`, so an operator can upload rosters **before any session
  exists** — and a Workflow-card template cannot reach them there.

- **Template downloads live on the two pre-session surfaces: the Guide's
  "Create and set up a session" card, and the lobby first-run card**
  (2026-09-06, author, superseding the above). An operator may reasonably want
  the templates *while* creating a session, filling them for Quick Setup on
  `session_new.html`, rather than after. Both surfaces exist before any session
  does, and both are already where a new operator is looking — the Guide is the
  canonical documentation and the first-run card is what an empty lobby shows.

  **This forces the templates to be truly generic**, which is the trade the
  reversal buys and costs:

  - **Cost: bare headers clear friendly labels on re-import.** A generic
    template cannot carry `ReviewerTagN.<label>` suffixes, and a bare tag header
    is not neutral — `field_labels.apply_captured_labels` **clears** every
    in-scope slot the header does not name (`app/services/field_labels.py`;
    mirrors how an absent tag *value* re-imports as NULL). So an operator who
    renamed `ReviewerTag1` to `Tutor`, then filled a generic template and
    uploaded it into that session, would silently lose the rename. Harmless in
    the case this decision optimises for — a fresh session has no overrides —
    and the existing per-session roster **export** already serves labeled
    headers for anyone re-uploading. The Guide's card copy must say so; that is
    a rung 4 content obligation, not a footnote.
  - **Benefit: one artefact, no session dependency.** The four files are
    identical for every operator, so they can be generated from the serializers'
    `HEADER` tuples with no `review_session` in hand, and served from a route
    that needs no session scope.

- **One segment-level `Doc impact`, tagged by PR rung rather than by item**
  (2026-09-06). The four pieces of scope split unevenly across six PRs, so
  item-level manifests would have needed `## Item n` headings that do not match
  the ladder. Rung tags are documentation for the reader; every bullet takes the
  segment window.

---

## Blast radius (measured)

Taken 2026-09-06 at `be87b4ba`, before the first slice.

| What | Count | Command |
|---|---|---|
| Live files referencing `quickstart` (archives excluded) | **11** | `grep -rln quickstart --include=*.md --include=*.py --include=*.html . \| grep -v '^./.git\|/archive/'` |
| `chrome-link` entries in `base.html` | **5** | `grep -c 'chrome-link' app/web/templates/base.html` |
| Setup-page templates for Item 4 | **5** | `ls app/web/templates/operator/ \| grep -E 'session_(reviewers\|reviewees\|relationships\|observers)\|instruments_index'` |
| Tests touching `/about` or the lobby | **9** | `grep -rln "/about\|sessions_list" tests/ \| grep -v __pycache__` |
| Serializers the templates derive from | **4** | `reviewers_extract.py`, `reviewees_extract.py`, `relationships_extract.py`, `serialize_session_config` |

Named, not counted:

- `app/web/routes_guide.py` is a **new routing module**, so it must be added to
  `SPEC_COVERAGE` in `app/web/spec_registry.py` or
  `tests/unit/test_spec_coverage.py` fails — the 19A Item 3 gate. `routes_about`
  maps to `spec/operator_ui_concept.md` (`spec_registry.py:134`); the Guide
  needs its own spec entry.
- `app/web/routes_operator/_lobby.py:102` renders `sessions_list.html` — the
  first-run card's host.
- `tools/close_check.py:107` uses `docs/quickstart.md §4c` as a docstring
  example of the section-reference regex; retirement makes it stale.
- `app/services/extracts/zip_bundle.py` is the existing zip pattern the
  template download reuses.

---

## Status

**2026-09-06 — rung 1 shipped** (PR #2131). The `/guide` scaffold: route,
twelve section shells, chrome link beside About, `?return_to=`, and the
`SPEC_COVERAGE` entry the 19A Item 3 gate requires. One test assumption
corrected at build — Jinja's `urlencode` leaves `/` unescaped, so the chrome
link renders `return_to=/about`, as the existing Settings and About links in
the same row already did. Two inaccuracies in the adjacent `/about` spec entry
were fixed rather than left beside a new correct one: `.chrome-app-identity` is
a `<span>`, not a link, and "currently a stub" predated 18R Item 6.

**2026-09-06 — rung 2 shipped.** `docs/quickstart.md`'s material moved into
`app/web/templates/guide.html`; the file retired to `docs/archive/quickstart.md`
with a header naming its successor and forbidding edits. All live references
repointed — `docs/README.md`'s index row, `docs/known_limitations.md`,
`docs/status.md` (twice), `guide/segment_20_*`, `guide/todo_master.md`,
`guide/segment_14B_*`, `guide/deferred_consolidated.md`, and the
`docs/quickstart.md §4c` docstring example in `tools/close_check.py`. Dated
history in `todo_master`'s Done rows and `docs/practice-audit-2026-09-04.md`
was left alone: those record what was true then.

The audience seam landed as planned — `app/web/views/_guide.py` owns the
section→audience map and `visible_audiences()`, the template gates each card
on its key, and `visible_audiences()` returns everything until rung 7. It is
**exercised, not merely present**: a mutation test strips the `{% if %}` gates
from the template and exactly one test fails. That test was the reason for
landing the filter early, so it earns its place.

**Answering the open question "how much of `docs/quickstart.md` survives the
move".** Its ten numbered sections became eight operator cards: §3 and §4
merged into "Create and set up a session" (creating a session and setting it up
are one continuous act, and splitting them put a card boundary mid-task), and
§9 "What your reviewers experience" was folded into a reviewer-addressed "For
reviewers" card rather than kept as operator-facing description. Two cards are
new, with no quickstart source: **For observers** and **For reviewees**. They
had to be written, because the doc only ever addressed operators — which is
itself the argument for the Guide being role-aware.

**What did not survive: the nineteen `📷 Screenshot —` placeholders and the
checklist at the foot of the file.** They were never-taken TODOs, and an
in-app page carrying "screenshot goes here" callouts is worse than one
carrying none. The intent is real and is not lost — it is recorded here, and
the archived file still holds the full list of nineteen filenames and the
suggested location. Whether the Guide should carry screenshots at all is a
better question once there is a deployed host to capture, so it belongs with
Segment 20's currency pass rather than with 19E.

**2026-09-06 — role-awareness moved out of rung 2 to a new rung 7, after the
content is settled** (author decision). The original ladder put role-filtering
in the same slice as the quickstart move. Separating them, because they fail
differently: the content is a long editorial pass that will take several
iterations to get right, and role-filtering is a query problem with a
correctness risk — showing someone the wrong sections, or hiding sections they
need. Bundling them means every copy edit re-opens the gating question, and the
gating cannot be reviewed on its own.

The app is not openly available, so an ungated Guide costs nothing meanwhile.

**Rungs 2–6 wire for it and leave it inert**, in the specific sense that the
*filter runs* from rung 2 onward — each section declares its audience and the
template renders only sections whose audience is in a `visible_audiences` set —
but the set is a constant containing every audience. The seam is therefore live
and covered by tests from the moment it exists; rung 7 replaces the constant
with a real resolver and nothing else. A seam that is built but never executed
is worse than no seam: it rots unobserved, which is the failure mode this shape
avoids.

Rung 7's actual work is the resolver, not the template. Noted at rung 1's
close: **role membership is not a property of `AuthenticatedUser`.**
`is_sys_admin` / `is_super_admin` are, but "is this person a reviewer /
observer / reviewee" is a function of their rows in some session's roster,
resolved per-session today by `require_reviewee_in_session` and its siblings.
A workspace-level "does this person have any such row anywhere" query does not
exist yet.

**2026-09-06 — rung 3 shipped.** The lobby first-run card. It replaces the
plain empty state in `sessions_list.html` rather than sitting beside it: the
existing card already occupied that slot, and two onboarding cards in an empty
lobby is one too many. `id="lobby-first-run"` is the handle the tests gate on.

**The trigger needed no new mechanism.** The template's `{% if sessions %}`
already branches on the *non-archived* subset, which is exactly the
zero-visible-sessions rule `## Semantics` specifies — so the archive-everything
case falls out of the existing structure rather than being coded for. Confirmed
by a test that archives the only session and asserts the card returns.

**The card reuses the Guide's section headings verbatim** — "Create and set
up", "Prepare and launch", "Give reviewers access" — and a test asserts all
three appear on *both* surfaces. The alternative, writing fresh copy for the
card, gives the same workflow two vocabularies and no way to notice when they
diverge.

**Judgment call at build: the card's Guide link is byte-identical to the
chrome's** on this page (both `/guide?return_to=/operator/sessions`, the chrome
deriving `return_to` from the current path). The first version of the test
substring-matched the link and passed on the chrome's alone — proving nothing.
The tests now count occurrences: two at first run, one thereafter. Left
identical rather than differentiated with a marker attribute, since a test-only
hook in the markup is a worse trade than a counting assertion.

**Blast-radius correction: `Go to Archive` is unreachable in exactly this
state.** The only in-app link to `/operator/sessions/archived` lives in the
Search card, inside the populated branch, so an operator who archives every
session loses the route to their own archive — and the `N archived` stats pill
goes with it. Found while reading the branch this rung hangs off; **not fixed
here**, since it is a pre-existing defect independent of the card and
`CLAUDE.md` → "Working approach" rules out bundling one into this PR. Recorded
as a Known gap in `spec/sessions_overview.md` and raised with the author for
its own slice.

**2026-09-06 — rung 4 shipped.** The starter template set:
`GET /templates/starter.zip`, generated by `app/services/setup_templates.py`,
linked from the Guide's "Create and set up a session" card and the lobby
first-run card.

**The plan said four serializers; the set ships four files, but not the four
the plan named.** Two corrections at build:

- **Observers is in.** Quick Setup has *five* slots, not four —
  `app/web/views/_quick_setup.py` appends an `observers` slot when the
  session-level toggle is on, and `observers_extract.HEADER` already exists.
  A generic set has no session whose toggle it could consult, so the file
  ships unconditionally and an operator not using observers ignores it.
- **Settings is out** (author decision, put at build). The Settings CSV is a
  `field,value,data_type` dump of a whole live session — instruments, response
  fields, rule sets, email overrides — not a row-shaped roster, so "one mock
  row per file" has no meaning for it. Deriving even a minimal one meant either
  reaching into `session_config_io`'s private row builders or hand-authoring
  rows, and hand-authoring is exactly what `## Semantics` forbids. An operator
  sets those values in the form and builds instruments on the Instruments page;
  the worked `settings.csv` arrives with the rung 5 demo set.

**Derivation is by reference, and tested as such.** Each template holds the
extract's `HEADER` tuple itself rather than a copy, so a column added to an
extract reaches the template with no edit here. The test asserts *identity*
(`is`), not equality — a copied tuple would compare equal today and drift
silently later. The one authored part, the mock row, is authored per column:
`SAMPLES` maps column name → cell, and a header column with no entry raises on
the request rather than emitting a short row. Two tests bracket that mapping in
both directions, so neither a new column nor a stale sample survives.

**The strongest check is that the templates survive the real importers.**
`test_setup_template_download.py` runs the generated files through
`parse_reviewer_csv` / `parse_reviewee_csv` / `parse_observer_csv` and asserts
zero issues, and parses `relationships.csv` against rosters built from the other
two files — so the four are verified as one coherent set, not four files that
each parse alone. That is rung 4's affordable share of the round-trip; rung 5
owns the full download → Quick Setup → `validated` path.

**One artefact, not four links** (build judgment). Both offering surfaces are
prose — a Guide paragraph and a first-run card — and four download links would
crowd each. A zip also keeps rung 5's demo set to one more link rather than
four.

**Consequence worth naming: the lobby's download leaves with the first-run
card.** It rides in that card, so an operator with a session no longer sees it
there and must use the Guide. That is the correct trade for rung 3's gating
rather than a regression, and a test pins it so it cannot change unnoticed.

**2026-09-06 — rung 4 follow-up: the templates carry a worked scenario and
worked labels** (author, after reviewing the shipped set). Two changes, and the
second reverses a decision the rung had just documented.

**The mock data is now one scenario rather than four generic rows.** Symmetrical
peer review: two students in tutorial group `TW01` reviewing each other, sharing
a tutor and an interest group, with the tutor as the observer. The original rows
were shaped as a supervisor reviewing a supervisee, which is not the case the app
is most often used for and made the relationships file read as hierarchy rather
than pairing.

**The headers now carry friendly-label suffixes** — `ReviewerTag1.Tutor`,
`ReviewerTag2.Group`, `PairContextTag1.Interest Group` — where rung 4 shipped
them bare. The argument that changed: the suffix grammar is the one thing about
roster CSVs an operator cannot guess, so a template that demonstrates it teaches
more than one that avoids it. Tag 3 stays bare on both rosters so the set shows
labelling as per column and optional.

That inverts the caveat, and the inverted form is the more useful one. Bare
headers *cleared* an existing override, which bites an operator re-uploading
into a configured session — a case the Guide had to warn about in the abstract.
Labelled headers *set* the override, which is visible in the file the operator
is editing: they see `Tutor` in the header and change it to their own word. The
Guide card now states both directions, because both are live.

**Observer tags stay bare and that is now asserted.** They are outside
`field_label_csv`'s nine-column labelable set by design, so the tutor's role
travels as the cell value. A suffix there would survive generation, fail to
split on import, and be read as an unknown column — the tag lost silently. The
test round-trips **every** generated header cell through the public
`split_header` and asserts it comes back as its column plus its expected label,
which catches a suffix on any non-labelable column rather than only the one
that prompted the check.

**2026-09-06 — rung 5 shipped.** The demo set: `GET /templates/demo.zip`, a
"Sample session" card on the Guide between "Tips and troubleshooting" and
"For reviewers", and the round-trip test the rung exists for.

**The demo set needs no `settings.csv`, and neither set has one.** This was
the rung's open risk — the plan's Decision leaned on the Settings CSV carrying
instruments, which would have meant authoring the one artefact here that
cannot be derived. It turns out not to be needed: `create_session` calls
`ensure_default_instrument`, and a new-model instrument defaults to Full
Matrix, so the four roster files alone carry a session to `validated`.
**Verified by probe before designing anything** — a throwaway test that ran
rung 4's starter set through Quick Setup and Prepare and printed the status.
The answer arrived in one run, and it removed the largest unknown in the rung.

**"Must not change the derivation code rung 4 lands, only its inputs" — a
deliberate, minimal deviation.** Rung 4's generator held one row per file, in
a flat column→cell mapping shared across files. Two sets of different sizes
cannot both be inputs to that, so the generator generalised: a `TemplateSet`
carries per-file row tuples, and the starter set is the one-row case. This is
the ladder's intent rather than a breach of it — after the change both sets
*are* inputs, and there is one mechanism instead of a second one bolted
alongside. Every structural test is now parameterised over both sets, so the
starter set is checked by strictly more than before.

**Rows are generated, not listed.** Twelve within-group pairs across two
groups, hand-listed, is where a typo would hide — and a wrong address there is
a row the importer silently rejects as an unknown reviewer. So addresses derive
from names (`"Alex Student"` → `alex.student@example.edu`), pairs come from a
`_peer_pairs` comprehension, and one `_student_row` builder serves both rosters
since their headers are identical but for the `Reviewer`/`Reviewee` stem.

**The acceptance test asserts more than `validated`.** Two things a naive
version would have missed:

- Quick Setup's submit-all **skips a failing slot and redirects with a
  `quick_setup_error` flag**, so a session can reach `validated` on the
  remaining rosters while one file was rejected. The test asserts the redirect
  carries no flag.
- `validated` alone is satisfied by a one-pair session, which is exactly what
  the demo set exists not to be. A second test asserts the roster counts landed
  and that assignments outnumber the reviewers.

Mutation-checked: pointing the relationships file at addresses no roster
defines fails five tests across both files, including the round trip.

**Card name: "Sample session".** Rejected *Test data* — "test" reads as
verifying the software or as throwaway QA data, when the operator's purpose is
learning, and it invites the reading that they should test their own setup with
it. Rejected *Tutorial set* — "set" names the artefact rather than what the
operator gets, and "tutorial" promises step-by-step instruction that the Guide
above the card already provides. "Sample session" is the plan's own phrase in
`## Decision` ("the demo set **is** the sample session"), and it names the
outcome rather than the download.

**The rung-2 seam earned itself here.** Adding the section to
`app/web/views/_guide.py` without adding its heading to the test's list failed
`test_headings_and_audience_mapping_stay_in_step` immediately — the check
written at rung 2 catching exactly the drift it was written for.

**2026-09-06 — rung 6a shipped: the guidance scaffold, piloted on Email
Template.** Split from rung 6 by the author, so the shape can be adjusted
before it is repeated five times rather than after.

**What the scaffold is.** `partials/_page_guidance.html` — a macro taking body
content through `{% call %}`, wrapping it in
`<details class="page-guidance">` with a **fixed** summary,
`What this page is for`. Fixed rather than a parameter: this is a repeated
affordance, and an operator learns a control faster when it reads identically
everywhere. A page that genuinely needs different wording is a finding about
the scaffold, which is what the pilot is for.

**Two scaffold decisions the pilot settled**, neither of which the plan
anticipated:

- **Placement is above any page-internal tab strip**, not merely "above the
  cards". The Email Template page has three tabs choosing *which* email; the
  guidance is about the page, so under the tabs it would read as commentary on
  the selected tab. A test pins the ordering.
- **"It links there" needed somewhere to link to.** The Guide's cards had no
  ids, so the only possible link was the whole page. Each card now carries
  `id="guide-<section key>"`, derived from the key the view already gates on,
  so a renamed section fails a test rather than becoming a dead link. Links
  carry `?return_to=`, and the test asserts the Guide's Back link names the
  originating session — an unallowlisted path falls back to the lobby silently,
  so asserting the URL was *sent* would prove nothing.

**The pilot page's copy names something the page never did.** Its three tabs
let an operator carefully compose emails the app does not send: Segment 14B is
still `Planning`. Verified against `guide/segment_14B_email_infrastructure.md`
rather than taken from the Guide's own rung-2 prose, which is where I would
have got it second-hand. The guidance says so, and says that access does not
depend on it.

**Undeclared spec impact, caught by the manifest.** `## Doc impact` named only
`spec/setup_pages.md` for this rung. But the Setup pages are not all governed
by it: `spec_registry.py` maps `_setup_invite` to
`spec/email_template_editor.md`, which carries this page's contract. Bullet
added rather than the edit made quietly.

**The plan's page count was wrong.** `## Definition of done` said five Setup
pages; `spec/setup_pages.md` lists **six** — the omitted one is Instruments.
Corrected in place, and it makes rung 6b a five-page rollout rather than four.

---

## PR ladder

**1 — Guide scaffold.** `routes_guide.py`, the `/guide` template with every
section as a static placeholder (real headings and layout, no real copy), the
chrome link, `?return_to=` plumbing, the `spec_registry.py` entry. Must not
move any quickstart content. Scaffold-first per `CLAUDE.md` → "Working
approach": this adds both a page and a navigation affordance.

**2 — Guide content + quickstart retirement.** Move the material in, ~~add
role-awareness,~~ *(moved to rung 7 on 2026-09-06 — see `## Status`; rung 2
lands the audience declarations and the filter, with the audience set held at
"all")*, move `docs/quickstart.md` to `docs/archive/`, repoint the 11 live
references. Must not touch the lobby or templates.

**3 — Lobby first-run card.** Scaffold and wiring together — one card on an
existing page, no new nav. Must not change the lobby's table or filters.

**4 — Starter template set.** Derivation from the four serializers, the
download location, one mock row per file. Must not add a demo set.
*(Download location decided 2026-09-06: the Guide's "Create and set up a
session" card and the lobby first-run card — both pre-session surfaces, so the
templates are generic. A Workflow-card row was decided first and reversed the
same day; see `## Judgment calls — decided` for why.)*

**5 — Demo template set.** The fuller data plus the round-trip test (download
→ Quick Setup → `validated`). Must not change the derivation code rung 4
lands, only its inputs.

**6 — Inline page guidance.** One `<details>` per setup page, written against
the Guide's settled vocabulary. Must not restate the Guide; it links there.
*(Split into two stages 2026-09-06, author: **6a** pilots the scaffold on one
page — Email Template — so its shape can be adjusted before repetition; **6b**
rolls it out to the remaining five.)*

**7 — Activate role-awareness** *(added 2026-09-06)*. Replace the
all-audiences constant with a real resolver: a workspace-level query for
whether the signed-in user holds any reviewer / observer / reviewee row, plus
their operator status. Must not touch Guide copy — if a section turns out to be
addressed to the wrong audience, that is a rung 2 correction landing before
this rung, not a change made while activating the filter.

---

## Definition of done

- `/guide` renders for every role, and for a signed-in user with none
  (**rung 7**; before it, every signed-in user sees every section — see
  `## Status`).
- `docs/quickstart.md` is under `docs/archive/`; `grep -rln quickstart` over
  live files returns only the archive pointer and the Guide's own references.
- `app/web/spec_registry.py` maps `app.web.routes_guide`, and
  `tests/unit/test_spec_coverage.py` passes.
- An operator with zero sessions sees the first-run card; one with a session
  does not.
- Both template sets download from one location and are byte-generated by the
  serializers — no CSV literal in the repo. *(Rung 5: "one location" became the
  Guide — starter in the "Create and set up a session" card and also on the
  lobby first-run card, demo in "Sample session". Headers are byte-derived from
  the extracts' `HEADER` tuples; rows are constants rendered through the CSV
  writer, never a checked-in `.csv`.)*
- The demo set uploaded through Quick Setup produces a session that reaches
  `validated` with zero validation errors, asserted by a test.
- Every address in both sets is `example.edu`.
- Each of the ~~five~~ **six** setup pages carries one page-level `<details>`.
  *(Corrected 2026-09-06: `spec/setup_pages.md` lists six — Reviewers,
  Reviewees, Relationships, Observers, **Instruments**, Email Template. The
  plan's count omitted Instruments.)*
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19E` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` records intended vs done
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

---

## Open questions

- **Should `/guide` be viewable without signing in?** Not decided, and
  **deferred to Segment 20**: `resolve_current_user` raises
  `HTTP_401_UNAUTHORIZED` today, so an anonymous Guide would be the app's first
  unauthenticated surface — a change to `docs/security_posture.md` that also
  needs Easy Auth configured to allow anonymous on that path, which is host
  work. 19E ships the authenticated Guide; the public question travels with the
  deployment. Decided by: the author, once the host exists.
- ~~**Where exactly does the template download live** — a card on the Guide, or a
  tile in Extract Data? Leaning Guide, since that is where a newcomer is, but an
  experienced operator refetching a template may look in Extract Data. Decided
  by: the author at rung 4.~~ **Decided 2026-09-06: the Guide's "Create and
  set up a session" card and the lobby first-run card** — the Guide half of the
  original leaning, plus the surface rung 3 had just built. See `## Judgment
  calls — decided`.
- **How much of `docs/quickstart.md` survives the move.** Ten sections written
  as a document may not map one-to-one onto a page. Decided at rung 2, recorded
  in `## Status`.

---

## Out of scope

- **Participant-facing onboarding beyond the Guide's own sections.** The
  reviewer `/me` and observer `/collation` surfaces have their own first-time
  gaps; those are their specs' business, not this segment's.
- **The administrator guide, institutional troubleshooting, and the docs
  currency pass** — Segment 20, gated on the deployment.
- **Validation explanations** (workplan §18 item 3) — already shipped.
- **A markdown rendering pipeline.** Rejected in `## Decision`; revisit only if
  the Guide outgrows a template.
- **Operator-authored guide content.** The Guide is code-side copy. Anything
  operator-editable is a different feature and belongs in
  `guide/deferred_consolidated.md` if it is ever wanted.

---

## Doc impact

Tags name **PR-ladder rungs**, not `## Item n` blocks — this segment plans as
one whole with a ladder rather than independently-closing items, so there are
no item headings for the close check to date a bullet from. Every bullet takes
the segment window.

- `spec/operator_ui_concept.md` — the `/guide` page: chrome placement beside
  `/about`, role-aware sections, and the `?return_to=` treatment (PR 1); the
  template downloads in its "Create and set up a session" card (PR 4, added
  2026-09-06 with the download location).
- `spec/audience_and_identity_model.md` — which roles see which Guide sections,
  including the signed-in-no-role case (**PR 7**, retagged from PR 2 on
  2026-09-06 when role-awareness moved; see `## Status`).
- `spec/sessions_overview.md` — the lobby's first-run card and its
  zero-sessions trigger (PR 3); the template-download links the card gains
  (PR 4, added 2026-09-06 when the download location was decided).
- `spec/csv_contracts.md` — the two template sets, that they are derived from
  the serializers rather than authored, and the `example.edu` convention
  (PRs 4 + 5). Includes that the templates are **generic** — bare headers, no
  `<Column>.<label>` suffixes — and therefore clear friendly-label overrides on
  re-import into a session that has them (added 2026-09-06).
- `spec/setup_pages.md` — the page-level `<details>` guidance in the shared body
  shape (PR 6).
- `spec/email_template_editor.md` — the pilot page's own guidance copy in its
  §2 page contract (PR 6). **Added 2026-09-06 at build**: the rung's original
  bullet named only the shared Setup-pages spec, but the Setup pages are not
  all governed by it — `spec_registry.py` maps `_setup_invite` here, and this
  is where the Email Template page's contract lives. See `## Status`.
- `docs/README.md` — `quickstart.md` retires to `docs/archive/`; the index
  points at `/guide` (PR 2).
- `docs/known_limitations.md` — repoint its quickstart reference (PR 2).
- `docs/status.md` — a row per rung as it lands.
