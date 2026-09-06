# Segment 19E — Operator onboarding

**Status: ⏸ paused 2026-09-06, rungs 1–6 shipped.** The ladder is complete
through rung 6b plus the author's copy pass; **rung 7 (role-awareness) is
the only build item outstanding**, and the close sequence has not been run.
Paused by the author with the segment mostly done — not blocked, and not
abandoned. What that means for anyone picking it up:

- `guide/page_help_text.md` has **retired early** to
  `guide/archive/` (2026-09-06, once the wording settled) rather than
  waiting for the close. See `## Status`.
- `visible_audiences()` still returns every audience for every viewer.
  `spec/audience_and_identity_model.md` is the one outstanding `Doc impact`
  path, and it is committed but unhonoured until rung 7 lands — so
  `tools/close_check.py 19E` will fail today, correctly.
- Rung 7 is slightly smaller than planned: the Guide shed two sections in
  the copy pass, so there are eleven to gate rather than thirteen.

Carved out of Segment 20 on
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

- **Page guidance is a half-width card, not an inline disclosure**
  (2026-09-06, author, superseding the rung 6a pilot's shape). Closed, it is
  one line — a chevron and `What this page is for`; open, the card grows
  downwards in place. The card form gives the guidance a slot in each page's
  existing grid rather than a full-width band above it, so it reads as one of
  the page's cards rather than as a preamble to them. Width comes from the
  grid slot, not the macro, so a page composes it without fighting a
  hard-coded size.

- **Per-page placements, decided together rather than page by page**
  (2026-09-06, author):

  | Page | Placement |
  |---|---|
  | Reviewers / Reviewees / Relationships | `Fields with data` card drops to half width; guidance card to its right, same row |
  | Observers | Half width, top right, in its own row above `Cohort match rule` |
  | Email Template | Half width, above `Merge tags` in the right column |
  | Instruments | The `Expand all` / `Collapse all` buttons move into the `Session deadline (auto-close)` card; the card they vacate becomes the guidance card |

  The Instruments move is the only one that changes something other than the
  guidance: a card holding nothing but two bulk toggles was the page's
  cheapest half to reclaim, and the toggles read better beside the counts they
  act on than alone in their own card.

  **This supersedes rung 6a's "above the tab strip" placement** on Email
  Template. The pilot reasoned that page-level guidance should precede the
  page's own sub-navigation; the card form answers the same worry differently,
  by making the guidance visibly one of the page's cards rather than a banner
  over them. The rung 6a test that pinned the old ordering is replaced, not
  deleted — it now pins the new one.

- **The top half-width cards are column stacks, not a row**
  (2026-09-06, author, after seeing the scaffold). `.card-columns` —
  `1fr 1fr`, `align-items: start`, each child a column stacking its own
  cards. A row grid makes the two halves share a height, so opening the
  guidance dragged its neighbour taller; columns confine the growth to
  the column that grew. The guidance card also gets `align-self: start`
  and tighter padding so it is one line tall when closed.

  **Observers' guidance moves to the top left**, above the cohort editor
  and in the same column — which is what the empty top-left slot the
  scaffold left was telling us. Opening it now pushes the cohort editor
  down and leaves `Operator actions` alone in the right column.

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

**2026-09-06 — rung 6b, first slice: placements scaffolded.** All six Setup
pages now carry the guidance card in the position `## Judgment calls` records;
five hold placeholder bodies. Copy follows in the next slice, from
`guide/page_help_text.md`.

Scaffold-first per `CLAUDE.md` → "Working approach", and the author's
instruction: agree the layout across six pages before six lots of copy are
attached to it. Landing the placements alone also means the Instruments
button move is reviewable on its own rather than buried under prose.

**Two consequences to look at on the slot rather than reason about here:**

- **Observers has an empty top-left slot.** The card is specified top right,
  in a row above the cohort editor, which is itself left-aligned — so the two
  are diagonal rather than stacked. Implemented as specified; if the gap reads
  wrong the fix is to move the card, not to fill the gap with something.
- **An open card may stretch its row neighbour.** `.bottom-grid` and
  `.page-grid` stretch, so opening the guidance can grow the card beside it.
  Whether that is fine or distracting is a looking question.

**Test corrections at build**, both from asserting against markup rather than
behaviour:

- Counting the bare string `page-guidance` counted **base.html's stylesheet**
  — nine CSS rules plus one card, so the "exactly one per page" assertion read
  10. The tests now count `<details class="card page-guidance`, which only
  markup matches.
- The all-pages loop 404'd on **Relationships**, which is gated on
  `relationships_enabled` exactly as Observers is on `observers_enabled`. I
  had it in the ungated list. Both are now covered by one gated-pages test
  that sets the flag and asserts a 200 before asserting the card.

Mutation-checked: adding `open` to the macro fails the closed-by-default test
and nothing else.

**2026-09-06 — rung 6b tweaks: column stacks, minimal closed height, Observers
to the left.** The scaffold answered the questions it was landed to ask, and
all three answers were changes.

**A silent bug the whole suite missed, and the check that now catches it.**
Rewrapping cards in column stacks means hand-balancing `<div>`s across Jinja
conditionals. My edit to the three roster pages left one `</div>` unclosed —
an `if` branch with no `else`, so the closing replacement never ran — and
**2782 tests passed**. The pages returned 200 and still contained every string
the content tests look for; only the layout was wrong. An HTML-nesting test
now parses all six Setup pages and asserts nothing is closed out of order or
left open. Mutation-checked by deleting a `</div>`.

That is the general shape of the risk here: markup structure is invisible to
tests that assert on strings, and every test in this file was a string
assertion.

**The same string-versus-markup trap, twice more.** An ordering assertion
using the bare class name `operator-actions-card` compared against
**base.html's stylesheet**, not the card — the CSS rule sits ~88 KB earlier in
the response than the markup, so the assertion failed while the layout was
correct. Both new ordering assertions now use markup markers
(`class="card operator-actions-card"`, `id="observers-cohort-heading"`). This
is the third instance of the same mistake in this rung; the rule is that any
assertion naming a class must include enough of the tag to exclude the
stylesheet.

**Observers' empty top-left slot resolved itself.** The scaffold flagged it as
a looking question; moving the guidance there is the answer, and it also makes
the column stack meaningful — guidance above the editor it explains, with the
actions card untouched beside them.

**2026-09-06 — rung 6b: the roster pages' top region merged into one column
container** (author: the two-column layout "still not putting the top cards in
2 columns properly").

They were right, and the first fix was half a fix. Each roster page has **two**
row grids above the preview table — `Fields with data` + guidance, then the
tag-label editor + `Operator actions` — and I had converted only the first. Two
`.card-columns` containers look identical while everything is closed, and still
lose the point of the change: growth in the upper container pushes **both**
columns of the lower one down. Column independence only holds inside one
container.

**The full-width lock card was what split them in the first place.**
`.card-columns` has no spanning slot, so an Activated-session lock card cannot
sit between the two pairs. It moves above the container — where a "you cannot
edit this while the session is ongoing" notice reads better anyway.

The merged shape: left column `Fields with data` → tag-label editor, right
column guidance → `Operator actions`, each card keeping the side it already
had.

**Pinned by a test that asserts source order, not appearance.** Left column in
full then right column in full is the flattening only a single two-stack
container produces; two stacked grids interleave. It also asserts the first
`.bottom-grid` in the document comes *after* those four cards — the Upload /
Danger Zone pair below the table is still legitimately a row grid, so the test
asserts position rather than absence.

Two boundary attempts failed before that: slicing the page at `<table` breaks
on an empty roster (no rows, no table, so "above the table" is the whole page),
and slicing at `id="upload-csv"` still includes the grid's own opening tag a
few characters earlier. Asserting relative order needs no boundary at all.

**2026-09-06 — roster pages: guidance and `Fields with data` swap columns**
(author). Left column is now guidance then the tag-label editor; right is
`Fields with data` then `Operator actions`. Opening the guidance therefore
grows the *left* column.

Only the two leading cards moved; the tag-label editor and `Operator actions`
keep their sides. The ordering test inverts with them rather than being
loosened — it still asserts one column in full then the other, which is what
distinguishes a single two-stack container from two stacked row grids.

**2026-09-06 — Instruments swap, and Email Template off the row grid**
(author). Instruments now matches the roster pages: guidance left,
`Session deadline` right.

**Email Template's gap was the row grid, not spacing.** Its three-slot
`.page-grid` had the composer spanning both rows, which meant the right
column's cards were aligned to the *left* column's row boundaries — so the
merge-tag card began at row 2, level with the composer's midpoint, leaving a
gap under the guidance card and bottom-aligning merge tags with the composer.
Column stacks have no rows to align against, so each card sits directly under
the one above. Same primitive as every other Setup page now.

**`slot_class` retired.** The macro took a grid-position argument for exactly
one caller — Email Template's `card-tr`. That page is on column stacks now, so
the argument had no users; removed rather than left as a knob nothing turns
(`constitution.md` Article VI).

The bulk-toggle test kept its substantive assertion — the `Expand all` /
`Collapse all` buttons still live *inside* the deadline card — and inverted
only the ordering half, which the swap reverses. Losing the buttons would still
be silent, so that half stays.

**2026-09-06 — the disclosure glyph, and a customizer facet renamed**
(author).

**Confirmed: the guidance card uses the shared `--card-help-*` tokens**, the
same set `.rs-help-card` has used since 19C Item 8 — so those tokens now have
two callers, and the theme customizer's facets named `Instrument help card` /
`Instrument help card with edit box` misdescribed what editing them changes.
Renamed to **`Help card`** / `Help card with edit box`, at the generator
(`tools/theme_customizer.gen.py`, `tools/_harness_common.py`) with all three
generated pages re-run — editing the HTML directly would have been undone by
the next regeneration. `Help-card edit box` was already named without the
prefix, which is the consistency the rename restores.

**The chevron became the instrument cards' solid triangle** (U+25BE,
`rotate(180deg)` when open — down closed, up expanded). The pilot invented a
rotating `›` when the app already had a disclosure glyph; one glyph across the
app means an operator learns the control once. Pinned by a test that asserts
the code point, the rotation, *and* both native-marker suppressions — engines
disagree about which one works, and losing either would show two markers.

**2026-09-06 — theme adjustments from the customizer** (author, exported as
JSON and diffed against `base.html` rather than described). Six changes, five
light and one dark:

| Token | Was | Now |
|---|---|---|
| `--green-wash` *(primitive)* | `#f0fdf4` | `#ddf4e3` |
| `--nav-strip-setup-bg` (light) | `--blue-wash` | `--blue-pale` |
| `--nav-home-bg` (light) | `--blue-wash` | `--blue-pale` |
| `--card-help-bg` (light) | `--gray-wash` | `--gray-mist` |
| `--card-help-border` (light) | `--gray-wash` | `--gray-soft` |
| `--card-help-border` (dark) | `--ink-muted` | `--slate-deeper` |

The nav changes are one move: both strips gain saturation — `--green-wash` has
exactly one consumer, `--nav-strip-ops-bg`, so deepening the primitive moves
the Ops strip and nothing else — and the Session Home anchor is repointed to
match the Setup strip beside it.

**The help-card border reverses 19C Item 8, and the spec said so explicitly.**
`spec/color_tokens.md` carried the rule "resolves to the same primitive as
`--card-help-bg`, **on purpose**", because the slab then sat *inside* another
card and an edge there would have been `.card`'s 2px `--border-default`
cutting across a nested block. That stopped being true at rung 6b, when
`.page-guidance` made the help card a card **of its own** in a column, where
an edgeless card reads as unanchored. The token did not change meaning; the
thing it paints did. Rule rewritten in `spec/color_tokens.md` and
`spec/ui_elements.md` rather than left contradicting the code.

The first exported values used `--gray` light and left dark untouched, which
would have given the card an edge in light and none in dark; the author
revised to `--gray-soft` / `--slate-deeper`, landing both themes at ~1.47:1
and ~1.50:1 against the page. A soft edge, not an outline, and symmetric.

**Contrast, checked rather than assumed.** Nothing that passed now fails.
Inactive nav-tab text (`--text-dim` on the strips) goes 2.33 → 2.08 light
Setup and 2.43 → 2.19 Ops, and the Session Home anchor's `--text-subtle` goes
4.44 → 3.96 — all three were **already below AA before this change**, so the
strips deepen an existing problem rather than create one. Worth a separate
look at `--text-dim` / `--text-subtle` on tinted strips; not this change's to
fix.

All three generated theme tools re-run from their generators.

**2026-09-06 — the guidance summary reads as a card heading** (author). Set in
`--fs-h2` / weight 600, matching `body.ui-v2 h2`, with the triangle moved from
`::before` to `::after`.

Both halves are the same point. The summary *is* this card's heading, so it
should look like every other card heading on the page; and a leading glyph
indents the text out of line with those neighbours, which is precisely the
alignment the type change is buying. Margin stays 0 — closed, the heading is
the whole card, and `.page-guidance-body` brings its own top margin when open.

The h2 rule is **mirrored rather than inherited**: a `<summary>` is not an
`<h2>`, so `body.ui-v2 h2` does not reach it. The test now asserts the type
alongside the glyph, so the two cannot drift apart silently.

**2026-09-06 — two Operations pages get an inline note, not a help card**
(author, after asking whether Operations and Session Home want guidance cards).

I proposed cards for Invitations, Assignments and Responses. The author took
the first two and **rejected Responses**, correctly: the release-and-visibility
rule I wanted to put there is set on **Instruments**, and that page is the
*operator's* view of responses, not the reviewee's. A fact stated on the page
that does not own it is how two sources of truth start.

They also chose the lighter form. Neither page gets a `.page-guidance` card;
each gets one `.muted` line inside the card it concerns:

- **Assignments**, under `Per-instrument status` — *"Pairs are materialised
  from each instrument's rule and appear at Prepare."* The page's one invisible
  fact: pairs are a derivative, so an operator hunting for an add/remove
  control will not find one.
- **Invitations**, above the counters — *"Note: Invitation and reminder columns
  are inactive until email sending is switched on."* Without it, four of eight
  counters that never move read as broken rather than not-yet-switched-on.

**Guidance cards stay a Setup-page affordance.** A card is for a page whose
*whole purpose* needs explaining; a sentence about one card's own table is not
that, and scattering the card idiom across pages that need one line would
dilute the thing an operator has just learned to look for.

**The Invitations note has an expiry, and it is wired to fail loudly.** It
becomes false the moment 14B ships. `guide/segment_14B_email_infrastructure.md`
now opens its `## Status` with the three surfaces that must be retired then,
and two of the three carry test assertions — a red test when email lands beats
a comment nobody greps for. The Guide's own version of the claim is listed
there too, unpinned.

Also fixed at build: both assertions normalise whitespace. The templates wrap
mid-sentence, so a literal match tripped on the newline — and would have
tripped again on any re-wrap.

**2026-09-06 — rung 6b copy: the Observers draft was inverted, and that is
the finding worth keeping** (author-directed slice; the correction is mine,
caught by checking the draft's own flag).

`guide/page_help_text.md` shipped its Observers draft with an explicit
warning that one sentence — *"an observer with no rule set sees every
reviewee in the session"* — was my reading of the default and had **not**
been verified against `app/services/`. It was wrong, and wrong in the
direction the draft note predicted would matter more.
`observer_cohort.observer_has_rule` returns `False` for a null
`cohort_rule` or an empty `rules` list; `materialize_cohort_assignments`
returns `EMPTY_COHORT` on that test, and
`_observer_collation.build_observer_collation_context` short-circuits to
`cohort_empty=True`. **No rule means no access.**

Why the inversion makes the sentence more important rather than less:
"sees everything" is a privacy bug, and an operator who hit it would
report it within the hour. "Sees nothing" is a silent failure — the
observer is saved, the roster shows `—` in the Cohort column, nothing
warns anyone, and the first sign is a course leader saying their page is
blank. That is precisely the class of fact page guidance exists to carry,
and the page's own controls say none of it.

Three things followed from it, beyond the corrected sentence:

- The claim is **pinned to the behaviour it describes**.
  `test_the_observers_copy_matches_the_empty_cohort_default` asserts the
  service's default alongside the copy, so a flipped default fails a test
  rather than turning shipped prose into a lie. A copy assertion that only
  greps the template would have passed the whole way through this mistake.
- `spec/setup_pages.md` gains the rule under "Cohort match rule editor" —
  the behaviour was documented only in a service docstring, which is not
  where anyone specifying the operator surface would look. No new
  doc-impact path: that spec was already committed at PR 6.
- `test_no_setup_page_still_carries_the_scaffold_placeholder` exists
  because every structural test in the file passed happily against five
  bodies reading *"Guidance to follow"*. The placement slice was green and
  incomplete at the same time, which is the failure mode the rung split
  invited.

**The `create_and_set_up` anchor question, answered.** Four pages point at
one Guide card, flagged at drafting as a signal to watch. Writing the five
bodies did not produce a sentence wanting a more precise target, because
each links at the *end* of a paragraph that has already made its point —
the link says "there is more about sessions over there", not "the answer is
over there". It would stop holding the moment a body needs to send an
operator to a *particular* explanation; the fix then is splitting the Guide
card, not lengthening the guidance.

**19E is not closed.** The author is reviewing the wording and expects to
tweak it, so `guide/page_help_text.md` stays in `guide/` rather than
retiring to `guide/archive/`, and the close sequence has not been run.
*(Half superseded 2026-09-06: the wording settled and the drafting doc
retired early. The segment is still open — see the entry below.)*

**2026-09-06 — the Guide loses two sections in the author's copy pass, and
both losses are moves** (author-directed, on their reading of the shipped
page).

`Before you start` went to `/about`. The author's reason is the one that
settles it: *if you can read this, you were already able to log in.* Three
bullets on how to reach the app and sign in are advice for someone outside
it, and the Guide is a page you get to by being inside. On `/about` — the
page whose subject is identity and access — the same facts answer a
question someone is actually asking, so the material folds into the Access
card rather than becoming a card of its own.

One clause did not travel: *"An empty lobby is expected — you have not made
a session yet."* Rung 3 put a first-run card on the lobby that says this
where an operator meets it, and repeating it on `/about`, which nobody with
an empty lobby is looking at, would restore the drift the segment exists to
stop. Called out here rather than done silently, because the instruction was
"move".

`Getting help` folded into `Tips and troubleshooting` as its last bullet.
It was one sentence pointing at the Validate page, which is a
troubleshooting tip; a card is the wrong unit for it, and a whole section
that says "ask your administrator" reads as the page having run out of
answers.

**Both removals are asserted in both directions.**
`test_guide_renders_every_committed_section` only checks that every *listed*
heading is present, so dropping two names from `SECTION_HEADINGS` would let
a stale card go on rendering unnoticed — and a deletion and a move look
identical from the Guide's side. So `test_the_retired_sections_are_gone`
pins the headings' absence and
`test_the_retired_content_landed_where_it_was_moved_to` pins the content on
`/about` and in the Tips list. The template-gating test moved off
`getting_help` to `for_observers`, which also makes it a better test: it now
narrows to a section whose audience is *not* the operator.

`For reviewers` also lost its "open the link and sign in" step in the same
pass, for the same reason as `Before you start`.

**2026-09-06 — the drafting doc retires early, and takes a wrong turn on
the way** (author-directed).

`guide/page_help_text.md` is in `guide/archive/`, ahead of the close.
The wording had settled, so the condition this plan set for keeping it
live was met.

The route there is the part worth recording. The instruction was first
to update it to the shipped copy and promote it to
`spec/page_help_text.md`, and that is what I built — a spec reproducing
all six pages' copy, plus a test binding the blocks to the templates so
the pair could not drift. The author then asked whether retiring it and
keeping the code as the source of truth would be better. It is, and the
built version is the argument: **the binding test makes drift loud, not
free.** Every wording tweak becomes a two-file edit, and this segment
produced five such tweaks in a single afternoon. The file's own opening
paragraph had said as much from the day it was written — *"rather than
becoming a second place where the copy appears to live"* — so the
correct move was the one it had already called.

What survives is the half that was never copy. `spec/setup_pages.md` §0
gains a **copy contract**: the five rules an edit is held to, a table of
the one fact each page's card must carry, the Guide-anchor convention
with the reasoning for why one card serves five pages, the sanctioned
rule-5 exception, and the Instruments paragraph order. Rule 2 now points
at `test_every_setup_page_states_its_own_invisible_fact`, which already
pins those facts — so the spec describes a rule a test enforces, which
is the repo's idiom rather than a new one.

Nothing reproduces the copy, so nothing can drift from it, and no
binding test is needed. The archived file opens with a note saying
where the contract went and that it is no longer canonical.

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
  §2 page contract (PR 6).
- `spec/assignments.md` — the inline note under `Per-instrument status` saying
  pairs are materialised at Prepare (added 2026-09-06; see `## Status`).
- `spec/operations_pages.md` — the Invitations counters note (same). **Added 2026-09-06 at build**: the rung's original
  bullet named only the shared Setup-pages spec, but the Setup pages are not
  all governed by it — `spec_registry.py` maps `_setup_invite` here, and this
  is where the Email Template page's contract lives. See `## Status`.
- `docs/README.md` — `quickstart.md` retires to `docs/archive/`; the index
  points at `/guide` (PR 2).
- `docs/known_limitations.md` — repoint its quickstart reference (PR 2).
- `docs/status.md` — a row per rung as it lands.
