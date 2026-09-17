# Segment 19Q — Workflow and preview revamp

Three items, closing independently: Prepare absorbs Create invites; the
Previews hub retires into the Invitations drill-in; the Guide catches up.
Item-level `Doc impact` / `Status`, so `tools/close_check.py 19Q.1` reads
Item 1's.

Opened 2026-09-17, after 19P.6 landed the per-reviewer operator view and
19P Item 7 measured when each door to it is open.

---

## Item 1 — Prepare session creates the invitations

### Opportunity

**Create invites commits to nothing.** It mints an `Invitation` row and
discards the raw token (`app/services/invitations.py:167`); no email, no
`EmailOutbox` row, `sent_at` NULL. The first send rotates the token
anyway (`send_invitation:333`). The step's only durable output is the
row's existence.

**The separation is expensive.** Four code sites and three spec rows
exist solely to catch an operator who prepared but did not click:
`_invites.py:203` (`reason="invitations_not_created"`),
`_reminders.py:178` (`no_invitations`), `_workflow_card.py:609` and
`:701` (two amber *"create invitations before then"* captions), and
`spec/lifecycle.md:679`, `spec/architecture.md:700`,
`spec/workflow_card.md:716`. Scheduled auto-send tests `is_prepared`
**and** `has_invitations` (`_invites.py:172-173`) — two preconditions
for one readiness. Author's report, 2026-09-17: it reads as make-work.

### Decision

`generate_invitations` runs inside `workflow_prepare`, immediately after
`mark_validated`, on the validation-clean path only. `Create invites`
retires from the Workflow card and the Next action card.

**Rejected — create at the Generate step, before validate.** A failed
validation would leave invitation rows for a setup the operator is still
fixing, which is exactly what `_require_validated_or_ready` refuses
invitations from `draft` to prevent.

**Rejected — keep the button and auto-create on the schedule path only.**
Leaves both preconditions and all four warning sites standing.

### Semantics

- **Validation fails** → the route returns before `mark_validated`
  (`_workflow.py:157`); session stays `draft`, nothing is created,
  `session.workflow_run_failed` at step `validate` is audited. Confirmed
  as intended by the author, 2026-09-17.
- **Re-Prepare from `validated`** → `mark_validated` is a no-op
  (`session_lifecycle.py:253`); `generate_invitations` still runs,
  additive and idempotent, catching reviewers newly eligible since the
  last run and preserving every existing token and state.
- **Zero eligible reviewers** → nothing created, `has_invitations` stays
  false. See open question 1.
- **A roster edit cannot strand a fresh invitation.** Every setup mutator
  calls `invalidate_if_validated` (52 call sites), so an edit returns the
  session to `draft` and the next Prepare regenerates.
- **Stale residue.** A reviewer invited at an earlier Prepare and since
  made ineligible keeps a `pending` row — lifecycle never deletes them
  (`_invites.py:166`) — and `invitations_send_all` iterates
  `list_invitations_for_session`, which has no eligibility filter
  (`invitations.py:462`). Rung 1 fixes that first.
- `invitations.generated` is still audited, under Prepare's `correlation_id`.

### Judgment calls — decided

- Create after `mark_validated`, not before — a failed validation creates nothing (2026-09-17).
- `generate_invitations` stays a service function — the scheduled path and 7 test files call it (2026-09-17).
- The `has_invitations` skip reasons stay until open question 1 resolves; still reachable in the zero-eligible case (2026-09-17).

### Blast radius (measured)

- `grep -rln "create_invites_visible\|invitations/generate\|Create invites" app/ tests/ spec/ docs/` → **19 files** (6 app, 7 tests, 6 spec/docs)
- `grep -rln "invitations_not_created\|no_invitations" app/ tests/ spec/ docs/` → **12 files**
- `grep -rln "workflow/prepare" tests/` → **12 test files**

### PR ladder

1. **Filter the send set.** `invitations_send_all` iterates
   `reviewers_eligible_for_invitation`, not every pending row. Standalone
   bug fix, defensible today. Must not touch Prepare.
2. **Prepare creates.** `generate_invitations` inside `workflow_prepare`
   after `mark_validated`. Must **not** retire the button — it already
   hides on `invitations_generated`, so it self-conceals for one rung.
3. **Retire the button and collapse the duplicated preconditions** —
   Workflow card, Next action card, the two `_invites.py` /
   `_reminders.py` checks, the two amber captions.
4. **The close** — the specs below, `docs/status.md`, `close_check`,
   `spec-writer`, Status compaction.

### Definition of done

- A Prepare that validates cleanly leaves one `Invitation` per eligible reviewer; a Prepare that fails validation leaves zero.
- `Create invites` appears in no template; `POST /invitations/generate` resolved per open question 2.
- `invitations_send_all` emails no reviewer outside `reviewers_eligible_for_invitation`.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19Q.1` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

1. Can a session validate with **zero** eligible reviewers? If not, the
   `has_invitations` skip reasons are dead code and rung 3 deletes rather
   than keeps them. Decided by a test against `validate_session_setup`.
2. Does `POST /invitations/generate` 308 to Prepare, or is it deleted? A
   POST is an unlikely bookmark. Decided by the author.

### Out of scope

- **Pruning stale invitation rows on re-Prepare.** Rung 1 makes them
  harmless; deleting one risks removing a *sent* invitation still live in
  a reviewer's inbox. Recorded in `guide/deferred_consolidated.md`.
- **Activate's revalidation asymmetry** — Activate recomputes validation
  before flipping (`_workflow.py:294`), Create invites trusts the status.
  Sound given the invalidation invariant; not a defect.

### Doc impact

- `spec/workflow_card.md` — Prepare's contract gains invitation creation; the Create invites button row and the `invitations_not_created` skip narrative retire (Item 1).
- `spec/lifecycle.md` — the "Auto-send invites" precondition row collapses to Prepared alone (Item 1).
- `spec/architecture.md` — the `session.scheduled_invites_skipped` reason set drops `invitations_not_created` (Item 1).
- `spec/operator_button_audit.md` — the Create invites row retires (Item 1).
- `spec/operations_pages.md` — Manage Invitations' `not_created` chrome state, and Send all's row set (Item 1).
- `spec/session_home.md` — the Next action card's create-invites state (Item 1).
- `spec/operator_ui_concept.md` — the Workflow card's ≤4-button budget (Item 1).
- `docs/status.md` — row when Item 1 lands.

---

## Item 2 — Retire the Previews page

### Opportunity

Two hubs reach one destination. 19P.6 made the reviewer surface
reachable per row from Manage Invitations, which is a better picker than
the hub's own — search, three chip-toggled tag columns, sortable headers,
pagination, a status column — against a datalist and three buttons.

**Item 1 does not help this item.** The Invitations table's row set is
`_assigned_active_reviewers`, gated on assignments, not invitations; the
drill-in was already reachable after Prepare with no invitations at all
(author's dev-slot report, 2026-09-17). The two items are independent.

**Retiring the hub loses reach.** `build_preview_picker_context`
(`views/_previews.py:145-151`) selects every `Reviewer`, with no status
and no assignment filter, so the hub reaches three populations the
drill-in cannot: before Prepare (the hub's stated purpose), inactive
reviewers, and reviewers whose assignments are all excluded. Measured in
full at `guide/segment_19P_expander_revamp.md` § *When each door is open*.

**And the page hosts a second job.** `session_previews.html:31` includes
`_email_preview_region.html` — the invitation / reminder /
responses-received email previews, which the drill-in does not do.

### Decision

Retire the tab; Operations goes from six tabs to five. The author accepts
the loss of pre-Prepare reach — previews are available for Prepared
sessions (2026-09-17). Populations 2 and 3, and the email preview
region's new home, are open questions 1 and 2 below.

**Rejected — keep both and cross-link.** The measurement shows the
surfaces differ in *when*, not *what*; two tabs for one destination is
the thing this item exists to remove.

### Semantics

- `/preview-surface/1?reviewer_email=` returns **200 in every state
  measured**, before Prepare included — `_pages_for_session` walks
  *instruments*, not assignments. The route is not the gate; the doors
  are. Retiring the hub removes a door, not a capability, so any
  replacement is a link.
- `GET /sessions/{id}/previews` and `POST /previews/random` retire.
  `/previews` 308s to Manage Invitations, matching the 19P.6 precedent
  for the invitation-keyed detail URL.
- `Random` has no equivalent on the table. Dropped unless open question 3
  says otherwise.
- The nav item goes from `session_top_nav.html:63`; the six-tab layout
  assumption in `spec/operator_ui_concept.md` moves to five.

### Judgment calls — decided

- 308 rather than 404 for `/previews` — a GET hub is a plausible
  bookmark, and 19P.6 set the precedent (2026-09-17).

### Blast radius (measured)

- `grep -rln "previews" app/web/templates` → **6 templates**
- `grep -rln "preview-surface" app/ tests/ spec/ docs/` → **16 files**
- `grep -rln "previews\b" spec/ docs/` → **17 spec/doc files**
- `grep -rln "previews" tests/` → **6 test files** (excluding `__pycache__`)

### PR ladder

1. **Scaffold the replacement door(s)** for whatever open questions 1–3
   decide, on the Invitations page — inert if the destination needs one.
2. **Move the email preview region** to its decided home.
3. **Retire the hub** — nav item, route, `session_previews.html`,
   `_preview_picker.html`, the 308.
4. **The close** — specs, `docs/status.md`, `close_check`, `spec-writer`.

### Definition of done

- No template references `/previews`; `GET /previews` 308s to Manage Invitations.
- The email preview region is reachable and tested at its new home.
- `spec/preview_hub.md` retired or rewritten per open question 2.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19Q.2` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

1. **Where does the email preview region go?** Candidates: the Invitations
   page as its own card, or `spec/email_template_editor.md`'s editor
   surface. Decided by the author.
2. **Do the inactive / all-excluded reviewer populations keep a door?**
   Widening the Invitations table's row set changes a monitoring concept
   (`per_reviewer_progress`), so the likelier answer is a link elsewhere
   or accepted loss. Decided by the author.
3. **Is `Random` worth keeping** anywhere? Decided by the author.

### Out of scope

- Changing what the Manage Invitations table lists. The row set is
  `per_reviewer_progress`, a monitoring concept; repurposing it as a
  roster is a larger change than this item.

### Doc impact

- `spec/preview_hub.md` — retired or rewritten as the drill-in's contract per open question 2 (Item 2).
- `spec/operator_ui_concept.md` — Operations goes six tabs to five (Item 2).
- `spec/operations_pages.md` — the drill-in absorbs the hub's job (Item 2).
- `spec/reviewer-surface.md` — "reached from the Previews hub" becomes the Invitations drill-in (Item 2).
- `spec/operator_button_audit.md` — the picker's buttons and `Random` retire (Item 2).
- `spec/email_template_editor.md` — the email preview region's new home (Item 2).
- `spec/role_navigator.md` — the Previews entry (Item 2).
- `spec/session_home.md` — any Previews pointer (Item 2).
- `docs/status.md` — row when Item 2 lands.

---

## Item 3 — The Guide catches up

### Opportunity

`app/web/templates/guide.html` teaches the workflow Items 1 and 2
change. `tests/integration/test_guide_screencaps.py` fails on a
referenced-but-missing file **and** on a committed-but-unreferenced one,
so the screencaps must move with the prose in the same slice.

Affected, measured 2026-09-17:

- `:405-416` — the Previews paragraph and both `previews-page*.png` images.
- `:381`, `:385` — alt text naming *"the create-invites and activate actions"*.
- `:635` — the demo walkthrough's Prepare step, which stops at "assignments generated".
- `previews-page{,-dark}.png` delete; `workflow-prepare-session{,-dark}.png`,
  `workflow-after-validation{,-dark}.png` recapture.

### Decision

One slice per item it follows, landing after that item merges — the Guide
is documentation of shipped behavior, not of intent. Screencaps are
recaptured in the agent sandbox with Chromium against a seeded session.

**Rejected — one Guide slice at the end.** It would sit stale on `main`
between Item 1 and Item 2 merging, teaching a workflow that no longer
exists.

### Semantics

- A screencap pair is light + dark; both recapture together or the theme
  toggle shows two different app versions.
- `app/` ships wholesale, so a deleted screencap must also lose every
  reference in the same commit, or the test fails both ways.

### Judgment calls — decided

- Recapture rather than crop or edit existing PNGs — an edited screencap
  is a claim about the app that nothing checks (2026-09-17).

### Blast radius (measured)

- `ls app/web/static/guide/ | wc -l` → **40 files** (20 light/dark pairs)
- `grep -n "previews\|Create invites\|create-invites" app/web/templates/guide.html` → **7 lines**

### PR ladder

1. **Guide for Item 1** — the Prepare narrative, the two workflow
   screencap pairs, the validate-page alt text. Lands after 19Q.1 merges.
2. **Guide for Item 2** — the Previews paragraph and its screencap pair
   deleted; the drill-in documented. Lands after 19Q.2 merges.

### Definition of done

- `pytest tests/integration/test_guide_screencaps.py` passes.
- No Guide prose names `Create invites` or the Previews page.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19Q.3` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

1. Does the demo walkthrough (`:628-640`) gain a "look at a reviewer's
   surface" step now that the drill-in is the door? Decided by the author.

### Out of scope

- A Guide sweep beyond the paragraphs these two items falsify. Recorded
  in `guide/segment_20_operator_polish_and_documentation.md`.

### Doc impact

- `docs/status.md` — row when Item 3 lands (Item 3).
- `spec/rrw_functional_spec.md` — the Guide's own contract, if the walkthrough gains a step per open question 1 (Item 3).
