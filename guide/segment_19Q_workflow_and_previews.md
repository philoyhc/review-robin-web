# Segment 19Q — Workflow and preview revamp

Five items, closing independently. Item-level `Doc impact` / `Status`, so
`tools/close_check.py 19Q.1` reads Item 1's. Items 4 and 5 were added
2026-09-18 — 4 after Item 3's own recapture showed the defect, 5 when
the author delivered a new capture set.

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
`next_action_card.html:119` — the only card copy read *before* pressing
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

**Rungs 1, 1a and 2 landed 2026-09-18**; the close remains. Rung 1 needed
a corrective push for two false parity claims (#2464).

**The ladder grew rung 1a**, the card copy, folded in by the author. Its
finding is the instrument rather than the copy: `ready for prime time`
was quoted verbatim in `spec/workflow_card.md` and asserted in **no
test**, so the sentence 19Q Item 2 rung 2 left incomplete could not go
red. Grepped against `tests/`, States 7/3/1 are pinned by 3/2/1 files;
States 2 and 5 by none.

**One cumulative cold read, and it paid.** Four defects, all in rung 2's
prose, all claims about the app: Prepare's steps in the wrong order and
unconditional, where invitations come last and only on a clean
validation; the eligibility rule missing *included*; Activate credited
with sending; and **"Send invites notifies reviewers"**, which nothing
does — no transport is wired (`app/services/email_send.py`) and
`guide.html` says so two cards down. All four: the card's copy read
instead of the code.

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
   **Yes, as an optional affordance and not a numbered step** (author,
   2026-09-18) — it rides inside step 4's "look around" rather than
   extending the sequence.

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
(`next_action_card.html:312`). Warnings are also what fills the right
column with count pills and the issue list. One cause, two symptoms; the
columns never interact. The report's correlation is real and its obvious
explanation is wrong, which is why this is an Opportunity and not a
one-line fix.

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

### Decision

*Not yet decided — see Open questions.* The fix is known and the
**blast radius is the question**: `box-sizing: border-box` on the `.btn`
rule takes the fourth button to 103.2px and all four then match, probed
in Chromium. But 80 `<a class="btn">` across 31 templates currently size
as content boxes, and any that carry an explicit width would move.

### Semantics

- A `.btn` with no width set is unaffected either way: with no `width`,
  content-box and border-box shrink-to-fit identically.
- Only a `.btn` given an explicit `width` / `min-width` / `max-width`,
  or stretched by a grid or flex track, can change. That set is what
  the blast radius has to enumerate.
- The four-slot contract is `spec/operator_ui_concept.md`'s ≤4-button
  budget; this item does not change the budget, only whether the slots
  are honored.

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

### PR ladder

1. **Enumerate, then fix.** Measure which of the 80 anchors are sized by
   anything other than shrink-to-fit, decide base-rule versus scoped per
   open question 1, land it with the enumeration in the PR body.
2. **The close** — specs below, `docs/status.md`, `close_check`,
   `spec-writer`.

### Definition of done

- All four buttons measure one track width in the 4W-with-generated-invitations case above, verified in Chromium.
- The enumeration of width-sized `a.btn` is in the PR body, not asserted to be empty.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19Q.4` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

1. **Base rule or scoped?** `box-sizing` on `.btn` fixes every `a.btn`
   the codebase will ever stretch; scoping to
   `.next-action-buttons-row > a.btn` fixes this card and leaves the
   same trap set for the next author. A third option is the global reset
   the sheet has declined so far — **10** rules now set it by hand
   (measured; the comment at `base.html:1645` still says five), which is
   an argument either way. Author's.
2. Does anything in `spec/ui_elements.md` §6 need to state the box model
   for `.btn`, or is it an implementation detail? Only worth asking
   because a contract nobody wrote down is what produced this.

### Out of scope

- The `≤4` budget itself, and the right column's content. Both are
  correct here; only the slot width is wrong.
- The empty left-column gap visible in the same capture, where the issue
  list makes the aside taller than the button row. That is the grid
  behaving as specified, and a separate question if the author wants it
  raised.

### Doc impact

- `docs/status.md` — row when Item 4 lands (Item 4).
- `spec/ui_elements.md` — the `.btn` box model, if open question 2 says it belongs in the contract (Item 4).

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
