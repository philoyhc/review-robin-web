# Segment 19Q — Workflow and preview revamp

Seven items, closing independently. Item-level `Doc impact` / `Status`,
so `tools/close_check.py 19Q.1` reads Item 1's. Items 4 and 5 were added
2026-09-18 — 4 after Item 3's own recapture showed the defect, 5 when
the author delivered a new capture set — 6 on 2026-09-19, when a
question about the instrument tints found both the tint and the fallback
label keyed workspace-wide, and 7 later the same day, when a screenshot
of the Assignments table showed one mailbox carrying two names. It opened as two items that day and merged
into one before a rung was cut; see its own note.

Opened 2026-09-17, after 19P.6 landed the per-reviewer operator view and
19P Item 7 measured when each door to it is open.

**Order reversed at planning time, 2026-09-17**, before any rung was cut.
The first draft led with the Prepare/Create-invites fold on the assumption
that it enabled the Previews retirement. It does not: the Invitations
table's row set is `_assigned_active_reviewers`, gated on assignments, not
invitations, so the drill-in was already reachable after Prepare with no
invitations at all (author's dev-slot report, 2026-09-17). The two are
independent, and the preview work leads because it is the one the author
wants to see first.

---

## Item 1 — Email previews move to the drill-in; the Previews page retires

### Opportunity

Two hubs reach one destination. 19P.6 made the reviewer surface reachable
per row from Manage Invitations, which is a better picker than the hub's
own — search, three chip-toggled tag columns, sortable headers,
pagination, a status column — against a datalist and three buttons.

**The hub hosts a second job.** `session_previews.html:31` includes
`_email_preview_region.html`: the invitation / reminder /
responses-received email previews. Retiring the page without a home for
that region loses a capability, not just a door.

**Retiring the hub loses reach.** `build_preview_picker_context`
(`views/_previews.py:132`) selects every `Reviewer`, with no status and
no assignment filter, so the hub reaches three populations the drill-in
cannot: before Prepare (the hub's stated purpose), inactive reviewers,
and reviewers whose assignments are all excluded. Measured in full at
`guide/archive/segment_19P_expander_revamp.md` § *When each door is open*.

### Decision

The email preview region moves onto the per-reviewer drill-in
(`session_invitations_reviewer_detail.html`), then the Previews tab
retires and Operations goes from six tabs to five. The author accepts the
loss of pre-Prepare reach — previews are available for Prepared sessions
(2026-09-17).

The transplant is natural rather than forced: `build_email_preview_body`
already takes `reviewer=` (`views/_previews.py:364`), so the drill-in
supplies what the region needs. The region's only `picker` dependency is
its three tab hrefs.

**Rejected — keep both and cross-link.** The measured difference is
*when*, not *what*; two tabs for one destination is what this item exists
to remove.

**Rejected — move the region to the email template editor.** It renders
for *a named reviewer*, which the editor has no notion of.

### Semantics

- `_email_preview_region.html`'s required-context block changes: `picker`
  out, `reviewer` in; the tab hrefs become the drill-in URL plus
  `?email=<key>#email-previews`. The `#email-previews` fragment stays —
  it exists so a tab switch does not jump the operator to the top.
- `/preview-surface/1?reviewer_email=` returns **200 in every state
  measured**, before Prepare included — `_pages_for_session` walks
  *instruments*, not assignments. The route is not the gate; the doors
  are. Retiring the hub removes a door, not a capability.
- `GET /sessions/{id}/previews` 308s to Manage Invitations, matching the
  19P.6 precedent for the invitation-keyed detail URL. `POST
  /previews/random` retires outright — a POST is not a bookmark.
- `Random` has no equivalent on the table. Dropped unless open question 2
  says otherwise.
- Chrome: the nav item goes from `session_top_nav.html:63`; the six-tab
  assumption in `spec/operator_ui_concept.md` becomes five.

### Judgment calls — decided

- No scaffold rung. `CLAUDE.md`'s scaffold-first rule governs a *new* card; this region is built, shipped and reviewed, and the destination is decided (2026-09-17).
- 308 rather than 404 for `/previews` — a GET hub is a plausible bookmark, and 19P.6 set the precedent (2026-09-17).

### Blast radius (measured)

- `grep -rln "previews" app/web/templates` → **6 templates**
- `grep -rln "preview-surface" app/ tests/ spec/ docs/` → **16 files**
- `grep -rln "previews\b" spec/ docs/` → **17 spec/doc files**
- `grep -rln "previews" tests/` → **6 test files** (excluding `__pycache__`)

### PR ladder

1. **Transplant the region** onto the drill-in: re-point the tab hrefs,
   swap `picker` for `reviewer` in the required context, supply the three
   view calls from the drill-in route. Must not touch the hub — both
   render the region for one rung.
2. **Retire the hub** — nav item, `session_previews.html`,
   `_preview_picker.html`, `GET /previews` → 308, `POST /previews/random`
   deleted.
3. **Chrome** — six tabs to five, and any layout assumption that counted on six. **Absorbed by rung 2:** retiring the hub necessarily removed its nav item, and the flexible strip had no six-column layout rule to change.
4. **The close** — the specs below, `docs/status.md`, `close_check`, `spec-writer`.

### Definition of done

- The drill-in renders all three email tabs for its reviewer, with a test per tab.
- No template references `/previews`; `GET /previews` 308s to Manage Invitations.
- Operations renders five tabs.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19Q.1` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row
  — *the move does not apply: `segment-plan`'s close step 5 archives on a
  segment close or its last item, and Items 2–3 are still open, so the plan
  stays in `guide/`. The line is kept verbatim because the skill exempts
  these five from editing.*

### Status

**Closed 2026-09-18.** Rung 1 moved the three email previews onto the
Invitations per-reviewer drill-in. Rung 2 retired the picker, Random action,
hub template and nav tab; `GET /previews` now 308s to Invitations. That nav
removal also completed rung 3, because the strip has no fixed six-column
layout. The accepted losses are the pre-Prepare and off-table doors; Random
gets no replacement.

**The manifest grew twice at the close, and the second time is the finding.**
Six bullets were added for specs the sweep turned up — `extract_data`,
`visual_style_rrw`, `rrw_functional_spec`, `spec/README`, `README` and the
deployed-slot checklist. Then the cold read measured what the sweep had
actually reached: the ladder's own blast radius said **17 spec/doc files**
and nine had been edited. Six more still described the hub as a shipping
Operations page — `validate_page` (a page-identity table field),
`workflow_card` and `lifecycle` (both enumerating the Operations row),
`settings_inventory` (pointing at the hub for rendered previews, the exact
sibling of the `email_template_editor` pointer the sweep *did* fix),
`ui_elements` (naming the page that hosts the email-tab strip) and
`visual_style_rrw` again, four sections below a line the same sweep edited.

**None of the six was catchable.** Every one is unanchored prose, and
`tests/unit/test_doc_conventions.py` only resolves anchored backticked
paths — so the suite was green throughout with a reader still routed to a
retired tab by four separate specs. *A measured blast radius is only worth
the pass that reconciles it:* the number was in the plan from the start and
the gap was six files wide.

`spec/visual_style_rrw.md`'s third lock-card bullet was **deleted rather
than repointed** — it described a send-test affordance that was never built
(the retired `spec/preview_hub.md` said so) on a page that no longer exists.
The intent survives where it belongs, in
`guide/segment_14B_email_infrastructure.md`.

### Open questions

Both answered by the author, 2026-09-18, and collapsed here at the close.

1. **Do the inactive / all-excluded reviewer populations keep a door?**
   **No — accepted loss.** The mechanism is worth keeping, because the
   obvious rationale is wrong: an inactive reviewer *can* still hold an
   invitation, and their drill-in renders with their invite URL —
   `test_detail_page_keeps_the_invite_url_for_a_reviewer_off_the_table`
   pins exactly that. What they lose is **Open reviewer surface**, because
   the Review Progress card is gated on `row`, which is `None` off the
   table. The surface goes unreachable through a missing card, not a
   missing invitation.
2. **Is `Random` worth keeping** anywhere? **No.** If the need returns it
   gets rebuilt on the Invitations page, against that table's filters
   rather than the picker's datalist. (`spec/operator_button_audit.md`
   §12 cites this answer.)

### Out of scope

- Changing what the Manage Invitations table lists. The row set is
  `per_reviewer_progress`, a monitoring concept; repurposing it as a
  roster is a larger change than this item.

### Doc impact

- `spec/preview_hub.md` — retired; its contract moves to the drill-in (Item 1).
- `spec/operations_pages.md` — the drill-in absorbs the hub's two jobs (Item 1).
- `spec/operator_ui_concept.md` — Operations goes six tabs to five (Item 1).
- `spec/reviewer-surface.md` — "reached from the Previews hub" becomes the Invitations drill-in (Item 1).
- `spec/email_template_editor.md` — where the rendered preview of a template now lives (Item 1).
- `spec/operator_button_audit.md` — the picker's buttons and `Random` retire (Item 1).
- `spec/role_navigator.md` — the Previews entry (Item 1).
- `spec/session_home.md` — any Previews pointer (Item 1).
- `spec/extract_data.md` — Operations-strip diagram loses Previews (Item 1).
- `spec/visual_style_rrw.md` — chrome diagram loses Previews (Item 1).
- `spec/rrw_functional_spec.md` — the user-level preview contract moves to the drill-in (Item 1).
- `spec/README.md` — the spec index marks the hub contract as a retirement boundary (Item 1).
- `README.md` — the route overview marks the hub as a redirect and names the drill-in jobs (Item 1).
- `guide/post_azure_todo_checklist.md` — the deployed-slot hover check drops the retired page (Item 1).
- `spec/validate_page.md` — the Operations-row position field names Previews (Item 1).
- `spec/workflow_card.md` — the Operations-row enumeration the card renders on (Item 1).
- `spec/lifecycle.md` — the same enumeration in the lock-card section (Item 1).
- `spec/settings_inventory.md` — where the rendered email previews live (Item 1).
- `spec/ui_elements.md` — the `.nav-tab` reference example names the hub page (Item 1).
- `docs/status.md` — row when Item 1 lands.

---

## Item 2 — Prepare session creates the invitations

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
retires from the Workflow card and the Next action card, and the card's
copy is rewritten to say what Prepare now does.

**Rejected — create at the Generate step, before validate.** A failed
validation would leave invitation rows for a setup the operator is still
fixing, which is what `_require_validated_or_ready` refuses invitations
from `draft` to prevent.

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
- **`?validated=1` keeps its inline `draft -> validated` flip**
  (author, 2026-09-18). Rung 2 escalated it: `build_workflow_card_context`
  performs a lifecycle mutation on a GET, which is both a layering
  breach and a prefetch hazard, and rung 3 retires the button that
  state used to rely on. Removing it fails **208 tests** across ~30
  files that use the GET as their standard route to `validated`
  (measured). The author's call was to keep the backend — the Workflow
  revamp is about operator experience, and the migration is its own
  piece of work, now filed. *It is also load-bearing for this item's
  tests*: `_ready_session_without_invitations` builds
  "assignments, no invitations" through it, and five tests would be
  vacuous without that state.
- **Prepare stays live from `validated`, so retiring the button opens
  no hole there** (2026-09-18). `prepare_visible` is
  `(is_draft and not is_setup_empty) or is_validated`, so a session
  promoted by any route still has a one-click path to invitations —
  **but not from `ready`**, which is what rung 3's copy got wrong; see
  `### Status`.

### Blast radius (measured)

- `grep -rln "create_invites_visible\|invitations/generate\|Create invites" app/ tests/ spec/ docs/` → **19 files** (6 app, 7 tests, 6 spec/docs)
- `grep -rln "invitations_not_created\|no_invitations" app/ tests/ spec/ docs/` → **12 files**
- `grep -rln "workflow/prepare" tests/` → **12 test files**

### Status

**Closed 2026-09-18. Four rungs as planned; rung 1 was the only one
that grew** — its ladder line named `invitations_send_all`, and the
build found the scheduled dispatcher and then the per-row Send each
carrying their own copy of the predicate. All three share one helper.
Fixing one would have left the unattended half of a live bug standing.

**The bug was sharper than the Opportunity recorded.** The Manage
Invitations table already filtered on assigned-and-active, so the
operator saw one row while Send all emailed two people — the page and
the button disagreed, and the invisible one got the mail.

**Decisions confirmed at build**, beyond `Judgment calls`: creation
sits after `mark_validated` on the clean path (the rejected
before-validate alternative is now genuinely caught — the first test
for it used an empty session, where both orderings agree); the
`has_invitations` skip reasons and both amber captions stay per open
question 1, though their *copy* did not survive rung 3's first
attempt.

**The finding worth carrying is about the instruments.** Every rung,
something asserted less than it claimed: an identity check reading a
key `invitation.sent` has never carried; a mutant surviving because
the test's session had nobody eligible; five tests that would have
gone vacuous once `_ready_session` began creating invitations; an
anti-vacuity control firing because two id sequences began advancing
in lockstep; a test that had been skipping itself green for years; a
button matrix recomputed by eye and wrong twice; and a compaction
edit that anchored on a string appearing in prose before the heading
it meant, deleting `Blast radius` and leaving a bullet cut mid-
sentence — caught by counting sections, not by the suite. **None of
these was caught by a test. All were caught by a reader, or by
measuring rather than looking.**

**Reads: four `diff-reviewer` + two `spec-writer` + Codex.** Rungs 1
and 2 took one each under the old per-slice cadence (ten findings,
eight); rung 3 took the first **per-item cumulative** read (eleven),
which found the only defect spanning rungs — copy written in rung 3
that was unreachable because of a state rung 2 had escalated and rung
3 had not settled. Codex found two more at the close, one factual.
*Recorded per the cadence's rule 7.*

**Carried out** to `guide/deferred_consolidated.md` § *Three carried
out of 19Q Item 2*: stale-row pruning, the unaudited withheld send,
and the `monitoring`/`invitations` duplicate predicate — the root
cause of the bug rung 1 fixed.

**Still owed:** dev-slot verification of the card with one fewer
button and rung 3's six rewritten copy strings.

### PR ladder

1. **Filter the send set.** `invitations_send_all` iterates
   `reviewers_eligible_for_invitation`, not every pending row. Standalone
   bug fix, defensible today. Must not touch Prepare.
2. **Prepare creates.** `generate_invitations` inside `workflow_prepare`
   after `mark_validated`. Must **not** retire the button — it already
   hides on `invitations_generated`, so it self-conceals for one rung.
3. **Retire the button and rewrite the Workflow card copy.** The
   `Create invites` button, its Next action card branch, and
   `POST /invitations/generate` all go. **The `has_invitations` checks
   and both amber captions stay** — open question 1 measured a clean
   Prepare that leaves `has_invitations` false, so they remain
   reachable.
4. **The close** — the specs below, `docs/status.md`, `close_check`, `spec-writer`.

### Definition of done

- A Prepare that validates cleanly leaves one `Invitation` per eligible reviewer; a Prepare that fails validation leaves zero.
- `Create invites` appears in no template; `POST /invitations/generate` resolved per open question 2.
- `invitations_send_all` emails no reviewer outside `reviewers_eligible_for_invitation`.
- The Workflow card's Prepare copy names invitation creation.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19Q.2` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

Both answered, 2026-09-18.

1. **Can a session validate with zero eligible reviewers? Yes** — so
   the `has_invitations` skip reasons and both amber captions stay.
   *The measurement that answered it is not the one that pins it.* OQ1
   measured a roster with every assignment excluded; rung 1 then
   established that `replace_assignments` re-materialises every row
   from the pinned rule set, so **that state cannot survive the
   Prepare that would create the invitations**. The reachable case is
   every reviewer inactive — `reviewers.empty` counts rows regardless
   of status — which validates with *2 included assignments and zero
   warnings*. Pinned by
   `test_invitations_pill_not_created_when_no_invitation_rows`.
2. **Does `POST /invitations/generate` 308 to Prepare, or is it
   deleted? Deleted** — a POST is not a bookmark. It 404s, guarded by
   two tests.

### Out of scope

- **Pruning stale invitation rows on re-Prepare.** Rung 1 makes them
  harmless; deleting one risks removing a *sent* invitation still live in
  a reviewer's inbox. Recorded in `guide/deferred_consolidated.md`.
- **Activate's revalidation asymmetry** — Activate recomputes validation
  before flipping (`_workflow.py:294`), Create invites trusts the status.
  Sound given the invalidation invariant; not a defect.

### Doc impact

- `spec/workflow_card.md` — Prepare's contract gains invitation creation; the Create invites button row and its copy retire (Item 2). *The `invitations_not_created` skip narrative was promised here too and **stays**: open question 1, answered after this bullet was written, established that a clean Prepare can leave `has_invitations` false.*
- `spec/lifecycle.md` — the "Auto-send invites" precondition row collapses to Prepared alone (Item 2).
- `spec/architecture.md` — the `session.scheduled_invites_skipped` reason set drops `invitations_not_created` (Item 2). <!-- doc-impact-waived: open question 1 reversed this. The reason is still emitted, so the set does not drop it and the spec is correct unchanged. -->
- `spec/operator_button_audit.md` — the Create invites row retires (Item 2).
- `spec/operations_pages.md` — Manage Invitations' `not_created` chrome state, and Send all's row set (Item 2).
- `spec/operations_pages.md` — the info-card counters: **Pending invitations** counts the *sendable* set since rung 1 while **Invitations created** still counts every row, so with a stranded invitation the row reads `created 2 · sent 1 · pending 0` and the arithmetic no longer closes. The spec lists the eight counters without defining any of them, so nothing there is false — but the meaning changed and the bullet above would not have prompted a sweep of it (Item 2).
- `spec/operations_pages.md` — the per-row **Send** 409 gate, which moved from `reviewer.status != "active"` to full eligibility at rung 1, with new operator-visible detail text. The spec documents the button's allowed states and has never described the gate at all (Item 2).
- `spec/session_home.md` — the Next action card's create-invites state (Item 2).
- `spec/operator_ui_concept.md` — the Workflow card's ≤4-button budget (Item 2).
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

**Added 2026-09-18, author's call**, found while building rung 1: the
Workflow card's State 2 copy is stale the same way the Guide is.
`next_action_card.html:120` — the only card copy read *before* pressing
Prepare — omits the invitations 19Q Item 2 rung 2 moved into
`workflow_prepare`. That item's definition of done required the Prepare
copy to name invitation creation; States 4 and 7 met it, and the one
state read before Prepare did not.

### Decision

One slice per item it follows, landing after that item merges — the Guide
documents shipped behavior, not intent. Screencaps are recaptured in the
agent sandbox with Chromium against a seeded session.

**Rejected — one Guide slice at the end.** It would sit stale on `main`
between Item 1 and Item 2 merging, teaching a workflow that no longer
exists.

**2026-09-18** — the same rule places the card-copy fix: app copy, so its
own rung **ahead** of the Guide rung. Bundling them would have the Guide
describing a sentence shipping in the same merge.

### Semantics

- A screencap pair is light + dark; both recapture together or the theme
  toggle shows two different app versions.
- `app/` ships wholesale, so a deleted screencap must also lose every
  reference in the same commit, or the test fails both ways.

### Judgment calls — decided

- Recapture rather than crop or edit existing PNGs — an edited screencap is a claim about the app that nothing checks (2026-09-17).
- Seed a warning for the `workflow-after-validation` recapture (2026-09-18): the demo data validates clean but for one info issue, so the shot would not have shown the strip the prose beside it describes. One reviewee under an anonymous identifier supplies one, and the capture frames the card alone.
- Pin the State 2 copy **by effect, not by sentence** (2026-09-18): the test names the three claims and then proves the third, so a rewrite that keeps them passes and a Prepare that stops creating invitations fails. Grepping the sentence would have pinned the wrong thing — the sentence was never the problem, its silence was.

### Blast radius (measured)

- `ls app/web/static/guide/ | wc -l` → **40 files** (20 light/dark pairs)
- `grep -n "previews\|Create invites\|create-invites" app/web/templates/guide.html` → **7 lines**

### Status

**Closed 2026-09-18.** Rungs 1, 1a and 2 landed; the close waited on the
author's dev-slot inspection of the recaptured screencaps, the one gate
the sandbox cannot supply; 19Q Item 5 now supersedes both.

**The ladder grew rung 1a**, the card copy, folded in by the author. Its
finding is the instrument rather than the copy: `ready for prime time`
was quoted verbatim in `spec/workflow_card.md` and asserted in **no
test**, so the sentence 19Q Item 2 rung 2 left incomplete could not go
red. Grepped against `tests/`, States 7/3/1 are pinned by 3/2/1 files;
States 2 and 5 by none.

**Three reads, and two of them found the same defect class** — prose
written from the card's copy rather than from the code. The one
`diff-reviewer` pass this item owed under the per-item cumulative
cadence, at rung 2: four false claims, of which **"Send invites notifies
reviewers"** is the type specimen, since nothing does — no transport is
wired (`app/services/email_send.py`) and `guide.html` says so two cards
down; `docs/status.md` names the other three. A review-bot pass at rung 1
(#2464): two parity claims about the reviewer surface, fixed in
`40e86bf4`. The `spec-writer` close pass found the spec truthful about
everything this item shipped, and one divergence that predates 19Q — the
State 4W cascade, filed as 19O.7 entry 14.

### PR ladder

1. **Guide for Item 1** — the Previews paragraph and its screencap pair
   deleted; the drill-in's two jobs documented. Lands after 19Q.1 merges.
2. **Guide for Item 2** — the Prepare narrative, the two workflow
   screencap pairs, the validate-page alt text. Lands after 19Q.2 merges.

**Inserted 2026-09-18 between 1 and 2.** The original two rungs stand as
written; this is a third, not a rewrite of either.

1a. **The Workflow card's State 2 copy names invitation creation.**
    `next_action_card.html` State 2, the `spec/workflow_card.md` state
    table row that quotes it verbatim, and a test. Must not touch the
    Guide — rung 2 describes what this one ships.

### Definition of done

- `pytest tests/integration/test_guide_screencaps.py` passes.
- No Guide prose names `Create invites` or the Previews page.
- State 2's card copy names invitation creation, pinned by a test that also proves the effect.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19Q.3` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

1. Does the demo walkthrough gain a "look at a reviewer's surface" step?
   **An optional affordance inside step 4, not a numbered step** (author,
   2026-09-18).

### Out of scope

- A Guide sweep beyond the paragraphs these two items falsify. Recorded
  in `guide/segment_20_operator_polish_and_documentation.md`.

### Doc impact

- `docs/status.md` — row when Item 3 lands (Item 3).
- `spec/rrw_functional_spec.md` — the Guide's own contract, if the walkthrough gains a step per open question 1 (Item 3). <!-- doc-impact-waived: both conditions failed. That spec documents no Guide page at all — its only "guide" mentions are its own reading-guide section and pointers to plan files — and the walkthrough gained a sentence inside step 4 rather than a step. The Sample session card's contract lives in `spec/operator_ui_concept.md` and `spec/csv_contracts.md` §5a, and the four-step summary there is still accurate. --> <!-- cites: spec/operator_ui_concept.md, spec/csv_contracts.md -->
- `spec/workflow_card.md` — the State 2 row quotes the card copy verbatim, so it changes with rung 1a (Item 3).

---

## Item 4 — Four button slots, and the one that is not

### Opportunity

Reported from the author's reading of Item 3 rung 2's recaptured
screencap: the Workflow card's buttons "go haywire when the RHS column
is populated". There should be up to four equal-width slots on the left.

**The grid is not the problem.** Measured in Chromium at a 957px
viewport, `.next-action-buttons-row` (`base.html:3494`) computes four
equal tracks of **103.188px**, and three of the four buttons measure
exactly 103.2px. The fourth measures **137.2px** and overflows its own
track:

```
['BUTTON 103.2', 'BUTTON 103.2', 'BUTTON 103.2', 'A 137.2']
```

**The difference is the element.** `<button>` inherits
`box-sizing: border-box` from the UA stylesheet; `<a>` does not, and
this sheet has no global reset — its own comment says so at
`base.html:1645` ("sheet has no global box-sizing reset; five other
rules set it"). The `.btn` rule (`base.html:2591-2593`) sets 16px
horizontal padding and a 1px border and **no** `box-sizing`, so
`width: 100%` on a grid item means the border box for a `<button>` and
the *content* box for an `<a>`:

```
103.188 + 16 + 16 + 1 + 1 = 137.2   ← the measurement, exactly
```

**Why it correlates with the right-hand column, which is the part worth
recording.** Activate renders as an anchor only on the
warnings-acknowledgement detour
(`next_action_card.html:315`). Warnings are also what fills the right
column with count pills and the issue list. One cause, two symptoms; the
columns never interact. The report's correlation is real and its obvious
explanation is wrong, which is why this is an Opportunity and not a
one-line fix.

**Added 2026-09-19, author's call: the right column enumerates where it
should point.** The same screenshot shows it listing every validation
issue in full — each with its own per-issue *Fix* deep link, so a
session with several assignment warnings renders "Assignments" over and
over. The Validate page already holds the authoritative table.

`_next_action_issue_list.html` renders **all** issues across all three
severities, uncapped. Its own header comment already describes the
intended design — *"the right column is a compact summary, not the
authoritative diagnostic surface. Operators who want the full report
still navigate to the Validate page"* — so this is the comment and the
code disagreeing, not a design that was never settled. And the card
carries **no link to Validate at all**: the comment says operators get
there "via the chrome top-nav".

**The four-button case, by precondition rather than by number:**
`is_validated` + `can_activate` + `needs_acknowledge`, with invitations
generated and not sent. The canonical cascade (`spec/workflow_card.md`)
tests `needs_acknowledge` *before* invitation state, so it numbers this
**4W**; there is no "State 5 with warnings". Worth a second's care when
building the fixture, because the body copy that renders is State 5's
("Invitations are ready to send") above 4W's help-line — the template's
body cascade tests invitations first. Which of the two the spec's tables
should describe is not this item's question; it is noted so the fixture
is built from the preconditions and not from a number.

**Answered 2026-09-19, after the above was written** (19O Item 7 entry
14, the author's ruling): the spec was wrong, not the template. `W` is an
overlay on States 4, 5 and 6, so this case is **`5W`** — State 5's body
above the overlay's help-line, four buttons. `spec/workflow_card.md` says
so now. The fixture is unchanged; only its name was ever in question.

### Decision

**`box-sizing: border-box` on the base `.btn` rule** (author,
2026-09-19: *"buttons should not be going beyond their card in
general"*). The intent is general, so the rule is general — scoping it to
`.next-action-buttons-row > a.btn` would fix this card and leave the same
trap set for the next author. It takes the fourth button to 103.2px and
all four then match, probed in Chromium.

The blast radius was the question and is now measured (below): the rule
changes the rendered width of **exactly one** selector's matches, the
overflowing one.

**Rejected — the global `box-sizing` reset.** It would fix the class of
bug rather than this instance, but it is a whole-sheet change against a
sheet that has declined it ten times, and this item is not the place to
settle that. Not recorded as deferred anywhere yet, deliberately: it is
a question for a sheet-wide pass, not an owed slice.

**The right column summarizes and links** (author, 2026-09-19). Counts
by severity stay; the per-issue enumeration goes, replaced by one link
to the Validate page, which renders the same issues in a table with the
"Why this check?" disclosure the card deliberately omits. What the card
keeps is the decision — *is there anything to look at* — and hands off
the diagnosis.

**Rejected — cap the list at N.** It keeps two surfaces rendering the
same rows and adds an arbitrary constant to argue about; the Validate
page is not a fallback for a long list, it is where the list lives.

### Semantics

- A `.btn` with no width set is unaffected either way: with no `width`,
  content-box and border-box shrink-to-fit identically.
- Only a `.btn` given an explicit `width` / `min-width` / `max-width`,
  or stretched by a grid or flex track, can change. That set is what
  the blast radius has to enumerate.
- The four-slot contract is `spec/operator_ui_concept.md`'s ≤4-button
  budget; this item does not change the budget, only whether the slots
  are honored.
- **A residual the box model cannot reach, established out of scope at
  rung 1.** `min-width: 0` cannot take a grid item below its min-content
  contribution — here the longest first-line word. Measured on the real
  `5W` page: **0px overflow across 500–960px**, the whole range the sheet
  has breakpoints for, and the first overflow at a **400px** viewport.
  `spec/visual_style_general.md` puts narrow-viewport support in a
  separate spec, and the sheet's narrowest breakpoint is 500px, so 400px
  is below what the app claims. Not fixed: a wrapping rule would be
  scope the contract has not asked for.
- The right column with no issues is unchanged: `_has_any` already
  guards the list, and the severity pills are rendered by
  `next_action_card.html`, not by the partial — so retiring the loop
  empties the partial rather than changing any zero-issue state.
- The Validate link renders wherever the list rendered — States 3 and
  4Err, and the `W` overlay's inline block (`spec/workflow_card.md`
  "Right-column content by state") — one link per block, not per
  severity.
- The per-issue `fix_url` / `fix_anchor` / `fix_page_label` stamps stay
  on the rule registry; the card stops reading them. The Validate page
  is their only consumer after this.

### Judgment calls — decided

- Recorded as an item rather than fixed in place when found (2026-09-18, author): the one-line fix is tempting and the 80-occurrence blast radius is exactly the kind of thing a drive-by does not measure.

### Blast radius (measured)

At `a08b4750`:

- `grep -rn '<a class="btn' app/web/templates/ | wc -l` → **80**
- `grep -rln '<a class="btn' app/web/templates/ | wc -l` → **31 templates**
- `grep -c "box-sizing" base.html` within the `.btn` rule → **0**
- `grep -c "box-sizing:" app/web/templates/base.html` → **10** rules set
  it by hand. The comment at `base.html:1645` says "five other rules",
  which was true when it was written and is not now — nine others hold
  today. *Counted here rather than quoted, because the first draft of
  this bullet quoted it: a stale comment inside a section headed
  **measured** is the failure this repository keeps finding.*

**The question the count above asks wrong, settled 2026-09-19 at
`8aa30224`.** Only an *explicit* width can overflow a content box — flex
and grid compute padding and border themselves, measured identical under
both box models in Chromium. So the 79 anchors are not the blast radius;
the width-setting rules are, and the sheet has two. One is
`#danger-zone button.btn`, a `<button>`, already border-box from the UA
sheet. The other is `.next-action-buttons-row > a.btn { width: 100% }` —
the defect itself.

**The base rule therefore changes exactly one selector's matches**, and
no template can widen that: **0** of the 79 anchors carry an inline
`style` attribute. Rung 1's PR body carries the enumeration in full.

- The probe: every `<a …>` tag parsed for the bare `btn` class → 79 in
  30 templates, 0 styled; the four sizing cases rendered side by side
  under both box models → `width: 100%` overflows by **34px** (2 × 16
  padding + 2 × 1 border) as content-box and **0px** as border-box, all
  four children on the 104px track. Kept out of the tree: a
  measurement, not a fixture.

### Status — intended vs done

**Three rungs as planned, in order, none struck.** Two divergences from
what the plan assumed:

- **The blast-radius question was asked wrong** — the 79 anchors were
  never the blast radius. Corrected in `Blast radius` above, which owns
  it; the wrong question is the finding.
- **Rung 1's render test was already written.**
  `test_workflow_card_w_overlay.py` pins the `5W` markup, so the rung's
  test became the CSS contract instead.

**Counts were short four times, and the fourth was the correction
itself.** Doc impact named four specs and the cold read found a fifth.
The `spec/workflow_card.md` bullet said four passages, the read made it
five, the close sweep found eight. The `spec/session_home.md` bullet said
three passages where there are two. And the close's own commit message
claimed the first of those was already fixed when it was not — caught by
re-reading the bullet rather than trusting the message. Which is the
lesson `base.html:1645`'s retired "five other rules" comment had just
taught, relearned three times inside the item that taught it: **a count
nothing derives is a count that rots, and a count in prose derives from
nothing.**

**The item kept committing its own defect class**, and something other
than the author caught it each time:

- Two guards passed for the wrong reason — a `min-width: 0` that
  satisfied a "has a width" regex, and a "clean session" control that
  exercised the *absence of the include* rather than the guard inside it.
  Both found by mutants. The negative-lookahead repair for the first
  failed too, the whitespace around the colon backtracking to empty.
- **Rung 2 rewrote the partial's misleading comment and created three
  fresh ones one file up**, one flatly false, in a file its own test
  opens and reads. Found by the cold read.
- The `content-box` guard scanned only `.btn`-subject rules, so a `> *`
  selector would have reopened the defect.

**Reads: one `diff-reviewer`** (rung 2, the last build rung, cumulative
from `ddf640d8`) **and one `spec-writer`** at this close. The cold read
returned five findings, all real, all fixed; it falsified nothing in the
blast-radius claim and extended it — no `.btn` carries a height or
explicit `flex-basis`, and the one `<span class="btn">` in the tree is
reached by no width rule. **Fifteen mutants, fifteen caught**, including
the one the read predicted would survive.

**Found on the way past:** `var(--font-size-sm)`, the sheet's only use of
a token it has never defined, so the retired fix links rendered at
inherited size all along.

**Carried out of the item**, both needing the dev slot and neither a
defect against the call: the `W` overlay now names Validate in both
columns, and the pointer has no fragment, so it lands above a second copy
of the card the operator just left (no suitable anchor id exists).

**Not verified end-to-end** — both rungs are UI-visible.

### PR ladder

1. **The base rule.** `box-sizing: border-box` on the `.btn` rule, with
   the enumeration above in the PR body and a render test pinning the
   four slots at one track width in the `5W` case. Retire the stale
   "five other rules" comment at `base.html:1645` while in the file.
2. **The right column points instead of enumerating.** Severity counts
   stay; `_next_action_issue_list.html`'s per-issue loop retires behind
   a single Validate link. Must not touch the button row — rung 1 owns
   that, and the two are separable even though one screenshot found
   both.
3. **The close** — specs below, `docs/status.md`, `close_check`,
   `spec-writer`.

### Definition of done

- All four buttons measure one track width in the `5W` case above, verified in Chromium.
- The enumeration of width-sized `a.btn` is in the PR body, not asserted to be empty.
- A session with several assignment warnings renders severity counts and one Validate link, not one row per issue.
- `_next_action_issue_list.html`'s header comment and what it renders agree.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19Q.4` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

1. ~~Base rule or scoped?~~ **Base rule** — author, 2026-09-19: the
   intended behavior is general, so the rule is. See `Decision`.
2. ~~Does `spec/ui_elements.md` §6 need to state the box model?~~ **Yes,
   as the intent rather than the mechanism** — §6 says a `.btn` never
   exceeds its container, with `box-sizing: border-box` named as how.
   Read out of the same ruling, which stated a *behavior* and not a
   declaration; flagged to the author as a reading rather than a
   quotation.

### Out of scope

- The `≤4` budget itself. It is correct here; only the slot width is
  wrong.
- ~~The right column's content.~~ Struck 2026-09-19: rung 2 changes it,
  per the author's call in `Decision`.
- The empty left-column gap visible in the same capture, where the issue
  list makes the aside taller than the button row. That is the grid
  behaving as specified, and a separate question if the author wants it
  raised.

### Doc impact

- `docs/status.md` — row when Item 4 lands (Item 4).
- `spec/ui_elements.md` — §6 gains the no-overflow intent for `.btn` and names `box-sizing: border-box` as its mechanism (Item 4).
- `spec/workflow_card.md` — **eight** passages describing the right column's per-issue list: "Right-column content by state" rows 3 and 4Err, the `W`-overlay paragraph under it, the §"`4W` is an overlay" mention, the Prepare chain's error branch, the right column's structural description, the workflow-failure signal's note on what it does not suppress, and the `## Source-of-truth pointers` entry. This bullet first said four, a cold read made it five, and the close sweep found eight — the count is recorded here as the finding it is (Item 4).
- `spec/session_home.md` — **two** passages: the "Status pills + per-issue list live in the right column" bullet and the State 3 row of the lifecycle table. **Undeclared at planning time**, found at rung 2 (Item 4).
- `spec/rrw_functional_spec.md` — the "right-hand column" bullet, which says the column carries "a validation issue list wherever validation has findings to show". **Undeclared at planning time**, found by the cold read at rung 2; it matters because `spec/README.md` makes this file the entry point a new reader starts from (Item 4). <!-- cites: spec/README.md -->

---

## Item 7 — One mailbox, two names: the check exists and the Add form skips it

### Opportunity

The author's screenshot of the Assignments table, 2026-09-19: a row
pairing reviewer **Aisha Haddad** with reviewee **Aisha Haddadx**, both
on `aisha.haddad@example.edu`. One mailbox, two names, two rosters.

**The rule is already written and already correct.**
`csv_imports.check_cross_table_identity` states it in its own docstring:
same email + same name across tables is allowed (the person is both
reviewer and reviewee, common in peer review), same email + different
name is a blocking error. It is wired to **two** call sites, both CSV
uploads (`_shared.py:799`, `_quick_setup.py:687`), and to none of the
four create/edit services that write the same row. Measured against the
running app, one session, one input:

| path | result | rows written |
| --- | --- | --- |
| reviewer CSV, existing reviewee's email, different name | **400**, "names must match" | 0 |
| the Add form, same input | **303** | 1 |

Nothing catches it afterwards: Validate has no cross-roster rule, so a
row that arrives by hand is never flagged again.

**It is not cosmetic.** `assignments/_self_review.py:27` classifies a
pair on `normalize_email` alone, so that row *is* a self-review to the
engine — counted, filtered, excluded as one — while the table shows the
operator two different people. The only visible signal points the wrong
way.

**A second gap, found looking for the first.** Within one roster,
duplicate email is blocked at CSV, create and edit, and — for reviewers
and reviewees — again at Validate. **Observers have no Validate rule**,
the only roster without that backstop. They carry the sole DB-level
guarantee (`uq_observer_session_email`), so a duplicate cannot persist;
what is missing is the *report*, on the page whose job is to list what
is wrong before activation.

### Decision

**Call the existing check from the services rather than write a second
copy**, and add the two missing Validate rules. Three pieces, in the
order a reader meets them:

1. `create_reviewer` / `update_reviewer` / `create_reviewee` /
   `update_reviewee` consult `check_cross_table_identity` the way the
   CSV paths do, raising the roster's own `*OperationError` so the Add
   and Edit forms re-render at 400 with the message, exactly as the
   within-roster duplicate already does.
2. A Validate rule for cross-roster identity, which is what catches the
   rows already sitting in a session from before piece 1.
3. A Validate rule for `observers.duplicate_email`, closing the one hole
   in the within-roster table.

**Rejected — a new service-layer check.** The rule would then exist
twice and could drift, which is the defect this item is fixing one level
up: a rule written once and reachable from only some of its callers.

**Rejected — making the DB constraint the answer.** A constraint on
`(session_id, email)` across two tables is not expressible, and the
reviewer/reviewee overlap is legitimate whenever the names agree.

### Semantics

- **Same email + same name across rosters stays legal** — the
  self-review case, which the app has machinery for. Unchanged.
- Comparison is `normalize_email` (strip + `str.lower`, not casefold —
  19N Item 2); name comparison is **exact**, inherited from the CSV path
  and reopened as open question 2.
- A reviewee identifier with no `@` is skipped, as in the CSV path:
  anonymous handles cannot collide with a mailbox by construction.
- Both new rules are **errors**, matching their within-roster siblings.
- Piece 1 governs new writes only, so a session already holding a
  conflicting pair keeps it until someone edits that row. Piece 2 is
  what tells them it is there.

### Blast radius (measured)

At `81c46014`:

- `grep -rn "check_cross_table_identity" app/ --include=*.py` → **3**:
  the definition and its two CSV callers.
- Create/edit services that can write a roster row: **6**
  (`create_`/`update_` × reviewers / reviewees / observers). **4** are in
  scope for piece 1; the observer pair is not, cross-table identity being
  reviewer↔reviewee (open question 1).
- `grep -c "ValidationRule(" app/services/validation.py` → **18** rules
  today; this item adds 2.
- `grep -rln "check_cross_table_identity\|duplicate_email\|duplicate_id" tests/`
  → **8** test files, including `test_observers_crud_dedup.py`, which
  already pins observer dedup at the CRUD layer — so piece 3 adds the
  report, not the behaviour.
- `spec/validate_page.md` mentions the two duplicate rules **5** times.

### PR ladder

1. **The services consult the existing check.** Pieces 1. Four call
   sites, one helper each side, and the tests that prove the Add form
   now matches the CSV path — the asymmetry measured in `Opportunity`
   becomes a regression test.
2. **The two Validate rules.** Pieces 2 and 3, with their `why` copy and
   `fix_anchor` deep links.
3. **The close** — specs below, `docs/status.md`, `close_check`,
   `spec-writer`.

### Definition of done

- The Add form and the CSV path give the same verdict on the same input, asserted by one test that drives both.
- A session holding a pre-existing conflicting pair reports it on Validate.
- `observers.duplicate_email` reports on Validate; the DB constraint stays as the guarantee.
- Same email + same name across rosters still creates cleanly, and still classifies as a self-review.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19Q.7` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

1. **Do observers join the cross-roster check?** Today it is
   reviewer↔reviewee only. An observer sharing a mailbox with a reviewer
   under a different name is the same defect, but observers are a
   different audience (`spec/audience_and_identity_model.md`) and may be
   deliberately separate. Author's.
2. **Is the name comparison exact, trimmed, or case-insensitive?** The
   CSV path compares exactly, so `"Aisha Haddad "` and `"aisha haddad"`
   both fail today. Inherited rather than chosen; worth choosing now
   that a form posts into it. Author's.

### Out of scope

- The Assignments table's own display. Whether a self-review row should
  be visually marked more strongly than it is belongs with that page.
- Retrofitting existing sessions. Piece 2 reports; nothing rewrites a
  row an operator has not touched.

### Doc impact

- `docs/status.md` — row when Item 7 lands (Item 7).
- `spec/validate_page.md` — the rule registry gains two entries; the per-rule table and the counts that quote it (Item 7).
- `spec/setup_pages.md` — the roster create/edit contracts gain the cross-roster rejection alongside the within-roster one (Item 7).

---

## Item 5 — The author's capture set

### Opportunity

The author delivered **12 light/dark pairs** as a captionless `.docx`
(`Guide_v2`, 2026-09-18), shot from a slot carrying 19Q Items 1–3. Each
was identified by reading it against the page it shows:

| pair | replaces |
|---|---|
| 1 | `session-home-chrome-and-workflow` |
| 2 | `reviewer-tag-labels` **and** `roster-upload-card` — two figures become one |
| 3–6 | the four `instrument-card-*` bands |
| 7, 8 | `workflow-prepare-session`, `workflow-after-validation` |
| 9–12 | `assignments-page`, `validate-page`, `extract-data-page`, `invitations-page` |

Six stay as they are: the three `create-session-*`,
`lobby-add-new-session`, `responses-page` and `workflow-activated`.

**Three of the twelve are not like-for-like re-shoots**, and the prose
beside them is what makes that matter:

- **Pair 2 collapses two figures into one.** The Unlock panel now holds
  what were separate tag-label and upload captures, so the Reviewers
  prose is rewritten rather than repointed.
- **`validate-page` is now clean** — 0 errors, 0 warnings, 1 info. 19K.8
  shot it mid-setup on purpose, because the section's copy is about the
  find-and-fix loop: *"if the sentence is about a loop, the image has to
  be taken inside it"* (`docs/status.md`, 2026-09-12).
- **`workflow-after-validation` is clean too**, so its right column reads
  only `Status — Setup validated.` Item 3 rung 2's prose beside it says
  warnings and blocking issues are listed there.

**The session is also much larger** — 154 reviewers, 856 assignments —
against the six-student demo behind the six pairs not re-shot.

**Pair 12 arrived mismatched**, caught by a 167px height gap: the light
half carried the info-counter card and the dark half did not — a
different page state, not a different theme. That is 19H.3's
`instrument-card-preview` defect, and no test in
`test_guide_screencaps.py` can see it. Re-shot on request to 1757×975
against the light half's 1760×972, inside 19H.3's ±4px tolerance.

### Decision

**The captures are the source of truth and the prose refines to match**
(author, 2026-09-18: *"Much of the prose need refining, for sure"*).

**Rejected — re-shooting to preserve the existing prose.** The author
shot these from a real slot at real scale; asking for retakes so the
words can stand unchanged inverts which of the two is evidence.

### Semantics

- A pair is light + dark of **one app state**. Comparing heights is the
  only cheap check for that, and it is done by hand: no test compares
  the two images' content.
- `app/` ships wholesale, so a replaced capture keeps its filename or
  loses every reference in the same commit.
- The narrow family goes **6 → 3**, still satisfying
  `test_both_capture_families_are_present` — which only asserts each
  family is non-empty, so it cannot notice the change. The counts were
  retired from that file's comment rather than restated (they had gone
  stale twice), so nothing there needs updating as pairs land.

### Judgment calls — decided

- Identify each capture by reading it against the running page, not by matching file sizes to the existing set (2026-09-18): two pairs are near-identical in size to captures they do not replace.

### Blast radius (measured)

At `ac6d0832`:

- `ls app/web/static/guide/ | grep -v dark | wc -l` → **19** pairs today; **18** after, since pair 2 absorbs two
- `grep -c '<figure class="guide-figure' app/web/templates/guide.html` → **19** figures, going to 18
- narrow-family pairs → **6** today, 3 after (measured by PNG width < 1000)
- `pytest tests/integration/test_guide_screencaps.py --collect-only` → **161** cases, parametrized per file

### PR ladder

1. **The eight like-for-like pairs** — session home, the four instrument
   bands, assignments, extract data, invitations. File swaps and alt-text
   refresh, no prose restructuring.
2. **The Reviewers panel** — pair 2, two figures to one, prose rewritten
   around the Unlock panel.
3. **Validate and the two Workflow states** — however open questions 1
   and 2 are answered, prose and captures land together.
4. **The close** — specs below, `docs/status.md`, `close_check`,
   `spec-writer`.

### Definition of done

- Every pair is one app state, checked by height and by reading both halves.
- No Guide prose describes a control or a condition its adjacent capture does not show.
- `pytest tests/integration/test_guide_screencaps.py` passes.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19Q.5` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

1. **Does the Validate section keep its find-and-fix framing?** The new
   capture is clean, documenting the end state rather than the activity
   the copy describes — what 19K.8 re-shot to avoid. Either the copy
   stops describing a loop or this capture is the wrong one. Author's.
2. **Does the post-validation Workflow prose keep its warnings
   sentence?** That capture has no warnings, so its right column is a
   status line. Author's, and it meets Item 4: the four-slot defect needs
   a warning to render, so a clean capture cannot show it either way.
3. Is the two-session look worth resolving, or does it go on the register
   until the remaining six are re-shot?

### Out of scope

- Re-shooting the six pairs the author did not supply. They are correct
  for what they show; only their scale differs.
- `spec/ui_elements.md`'s capture-family rules. The 6 → 3 narrowing stays
  inside them.

### Doc impact

- `docs/status.md` — row when Item 5 lands (Item 5).
- `spec/setup_pages.md` — the Reviewers page prose, if pair 2's collapse changes what the Guide says the Unlock panel holds (Item 5).
- `spec/ui_elements.md` — the capture-family counts, if the 6 → 3 narrowing is worth stating (Item 5).

---


## Item 6 — An instrument's per-session identity

**Revised at planning time, 2026-09-19, before any rung was cut** — same
shape as the segment's own 2026-09-17 reversal. The author's three
requirements: least code change, per-session numbering, and **creation
order rather than on-screen order**, because instrument drag-and-drop
already ships (`_instruments_pagination.py:107`), so a position-based
number moves under the drag. The first draft was two items keyed on
display position; the tint cannot land before the label's column exists,
so they are one.

### Opportunity

An instrument's identity is keyed on `Instrument.id`, a workspace-wide
autoincrement PK, and shown on a per-session page. It surfaces twice:

- **The fallback label.** Author's screenshot, 2026-09-19: two
  instruments in one session titled *Instrument_1* and *Instrument_7*.
  `_state.py::_instrument_label` returns `short_label` or
  `f"Instrument_{instrument.id}"`.
- **The card tint.** `instruments_index.html:693` keys the background on
  `instrument_palette[(instrument.id - 1) % instrument_palette | length]`,
  so ids 47, 48, 51 render tints 5, 6, 3 and two sessions with identical
  instruments differ by insertion date.
- **The delete confirmation** (`:4779`), author's screenshot: "Yes,
  delete **Instrument #1** and its associated assignments…". A third
  spelling: it keys on `loop.index` so it moves under the drag, it
  ignores `short_label` so a named instrument is confirmed under a name
  nobody chose, and its `#` is the prefix the operator-identifier policy
  reserves for reviewer-facing headings.

**The rule has two implementations.** `_state.py::_instrument_label` is
the Python copy; `:780` inlines `short_label or "Instrument_" ~ id` for
the card title the screenshots show. They agree only because both read
`id`. Measuring the function rather than the rendered text is how 19O.7
entry 13's sweep missed two strings, and nearly did again here.

Three numbers already describe an instrument and none is a per-session
identity: `Instrument.id` is workspace-wide, and `Instrument.order` and
the reviewer's `#N` are per-session but **move on drag**.

### Decision

Add **`Instrument.session_seq`** — an integer set once at creation,
never updated. The label becomes `f"Instrument_{session_seq}"`; the tint
keys on the same value. *Instrument_3* then means "the third instrument
I created in this session", permanently.

**Zero of the label's 44 call sites change.** `_instrument_label`
takes the instrument and reads a column, so its signature is untouched
and every caller — including the six audit-summary sites and the three
reviewer-facing ones — is untouched with it.

**Rejected — derive the rank inside `_instrument_label`.** Smaller and
migration-free, which is what requirement 1 asks for, and still wrong:
the number moves on delete instead of on drag, and it moves
*retroactively inside stored copy* — `audit_events.summary` is a
persisted `String(500)` with the label baked in at emit time, so a
summary naming `Instrument_3` would come to mean another instrument.

**Rejected — display position**, this plan's first draft: reorder ships,
so the number moves whenever the operator drags.

### Semantics

- **Gaps after delete are accepted** (author, 2026-09-19). Delete the
  second instrument and the labels read 1, 3, 4. That is what a handle
  that never moves costs, and closing the gap is renumbering.
- **Reorder never touches `session_seq`.** Display order stays
  `Instrument.order`; the two are independent by construction.
- **Clone preserves the source's sequence** (author, 2026-09-19): 1, 3, 2
  clones to 1, 3, 2. Needs **no code** — `session_clone.py:167` builds the
  row with `**_column_values(instrument, skip=…)`, copying every mapped
  column but `id` / `created_at` / `updated_at`. The rung asserts it.
- **Config import mints a fresh sequence**: the payload keys instruments
  by `short_label` and carries no ordinal, and adding one to the CSV
  contract is wider than requirement 1 allows. Recorded so the
  divergence from clone reads as a decision.
- **The reviewer's `#N` is unchanged**, still display position via
  `instrument_heading`. The two mean different things on purpose: `#N` is
  where you are in the form, `session_seq` is which instrument this is.
- `short_label` still wins, still muted italic so the fallback reads as
  a placeholder (`spec/instruments.md:274-284`); tints still wrap at six.
- **The delete confirmation says what the card title says** — the
  `short_label` when there is one, `Instrument_{session_seq}` otherwise —
  so the operator confirms the thing they recognise. Its `#` retires
  with the change, which is the operator-identifier policy applied
  rather than a new rule.

### Judgment calls — decided

- One item rather than two (2026-09-19): the tint reads a column the label's rung creates, so the tint cannot ship first and a shared migration serves both.
- Stored rather than derived (2026-09-19), accepting the larger diff, because only a stored value is stable in copy that was already written.
- Backfill with a correlated `COUNT` rather than the planned `ROW_NUMBER() OVER (...)` (revised at build): landing a window function's result needs `UPDATE ... FROM`, which SQLite only gained in 3.33, while the correlated form is plain SQL-92 and runs the same on both.

### Blast radius (measured)

Run 2026-09-19:

- `grep -rn "_instrument_label(" app/ --include=*.py | grep -v "def " | wc -l` → **44** across **18** files — **all unchanged**
- of those, `grep -ci "summary="` → **6** audit summaries; three are reviewer-facing
- `grep -rn "Instrument_" tests/ --include=*.py | wc -l` → **13** assertions to update
- `grep -rn 'Instrument_" ~\|Instrument #' app/web/templates/` → **2** rendered spellings outside `_instrument_label` (`:780` the card title, `:4779` the delete confirm) plus one comment
- `grep -rn "instrument.id - 1" app/ | wc -l` → **1** — the tint
- `grep -rln "surface-tint\|instrument_palette" tests/ | wc -l` → **0** — the tint is unpinned
- creation paths needing a line: **4** — `_instrument_crud.py` (`ensure_default_instrument`, `create_instrument`, `replicate_instrument`) and `session_config_io/_apply_instrument.py:296`. `session_clone.py` needs none, per Semantics.

### Status

**Built 2026-09-19, four rungs as planned** (#2474 → #2475 → #2476 and
the close). The ladder held; one rung's *method* did not.

**Rung 1 replaced the plan's approach within a minute of trying it.**
Wiring `session_seq` at the four creation paths left **417 tests
failing**, because 75 of them construct `Instrument(...)` directly.
Editing 75 fixtures to satisfy a requirement reading *as little code
change as possible* is backwards, so a context-sensitive column default
took over: zero creation paths edited, zero fixtures edited, one file
changed, and no path *can* forget it. The clone needed no code at all —
`session_clone` copies every mapped column — so that rung asserts the
behaviour rather than implementing it.

**Three defects were found by something other than me, and each names
what my own gate cannot see.**

- `ci-postgres` caught three tests keyed on `instrument.id`. They were
  green on SQLite, where every test gets a fresh id space, and red on a
  shared one — *the item's own defect, wearing a test's clothes*. Any
  assertion keyed on a primary key is a false green in this sandbox.
- The cumulative cold read caught a **fifth implementation of the label,
  in SQL**: `_coverage.py::_instrument_label_sql` is the Assignments
  page's sort key and stayed on `id` when rung 2 moved the Python form,
  so the server sorted by a string the page no longer displayed. Its
  docstring claimed a test pinned the two together; that file has never
  contained the word *instrument*. The measurement that missed it —
  "44 call sites, all unchanged" — was true and beside the point,
  because a SQL expression is not a call site.
- The same read caught **a false claim of mine**: `max + 1` reuses the
  number after a *trailing* delete. The sibling test pinned the interior
  case and passed while that one was unwritten. Now open question 1.

**Four reads**: one `diff-reviewer` cumulative pass (13 findings), one
`spec-writer` close pass, and review-bot passes on the PRs. The
cumulative read is the one that paid — it found the only defect that
spanned rungs, which is the cadence's whole argument.

**Scope that moved.** `spec/assignments.md` and `spec/architecture.md`
joined the manifest at the close, neither anticipated: the first because
the SQL sort key turned out to be a documented surface, the second
because the column default puts a query in the model layer and a reader
auditing "no logic in models" will find it. `docs/database.md` is waived
— it documents constraints, not column lists.

### PR ladder

1. **The column.** `session_seq` on the model, the migration with its
   backfill, the four creation paths, and a test that the clone carries
   the source's values. Nothing visible changes yet.
2. **The label, in all three places it is spelled.**
   `_instrument_label` reads `session_seq`; `:780`'s inline copy follows
   it; `:4779`'s confirm drops `loop.index` and the `#` and says what
   the title says. The 13 test assertions move with them. Must not touch
   the tint.
3. **The tint.** `:693` keys on `session_seq`, with the id-keyed order
   as its mutant — the first guard this palette has ever had.
4. **The close.**

### Definition of done

- A two-instrument session labels them 1 and 2, whatever their ids.
- Dragging either one changes neither its label, its tint, nor its delete confirmation.
- No template spells the fallback independently of `_instrument_label`.
- Deleting the first leaves the second reading 2.
- Cloning a session whose sequence reads 1, 3, 2 reproduces 1, 3, 2.
- `grep -rn "instrument.id - 1" app/` returns only the comment recording what the tint keying replaced.
- `alembic downgrade base && alembic upgrade head` round-trips on Postgres 16.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19Q.6` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

1. ~~**A trailing delete hands the number back** — make it monotonic?~~
   **Accepted as it behaves** (author, 2026-09-19): a trailing slot has
   no successor, so recycling there disturbs nobody's sense of order,
   and monotonic would cost a column on `sessions`, a migration, and
   undoing rung 1's column-default allocation — the residual harm is
   only an audit summary about an instrument deleted while newest.
   Pinned by `test_a_trailing_delete_hands_the_number_back`, whose
   failure message tells whoever reverses this what to update.

The three that existed at planning time were answered the same day:
creation order over display order, gaps accepted, clone preserves.

### Out of scope

- `short_label`, and the operator-identifier policy reserving `#` for reviewer-facing headings. This item changes what the *fallback* says, not who may use which prefix.
- The palette's six values and their dark-mode variants — `spec/color_tokens.md` holds them and only *which instrument gets which* moves here.
- The extracts' `Instrument_{position}` fallback — already per-session, and nothing here reads it.

### Doc impact

- `docs/status.md` — row when Item 6 lands (Item 6).
- `spec/instruments.md` — the Title bullet's fallback (`:274-284`), the operator-identifier restatement (`:722`), and the "Card background colour" paragraph, whose id-keying rationale this item reverses (Item 6).
- `spec/operator_ui_concept.md` — the fallback mention at `:318` (Item 6).
- `spec/setup_pages.md` — the delete-confirmation pattern it holds up as the exemplar for four other pages' copy, which still quotes the retired `Instrument #1` (Item 6).
- `docs/database.md` — the new column (Item 6). <!-- doc-impact-waived: that file documents constraints and indexes, not per-table column lists — `grep -in instrument docs/database.md` finds one composite-key mention and no instruments column table, so there is nothing there to add a row to. The column's semantics went to `spec/instruments.md` "The per-session ordinal" instead. -->
- `spec/assignments.md` — the Instrument column's label and its server-side sort key, which the cold read found drifted from it (Item 6).
- `spec/architecture.md` — the model layer's one querying column default, recorded rather than hidden (Item 6).
