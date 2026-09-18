# Segment 19Q — Workflow and preview revamp

Three items, closing independently. Item-level `Doc impact` / `Status`, so
`tools/close_check.py 19Q.1` reads Item 1's.

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
that grew.**

**What the ladder became.** Rung 1's ladder line named
`invitations_send_all`; building it found the scheduled
`_dispatch_pending_invitations` running its own copy of the same
query with the same defect, and a cold read then found
`invitations_send_one` with a third, looser predicate. All three
share `invitations.list_sendable_invitations` /
`is_reviewer_eligible_for_invitation` now. Fixing one would have left
the unattended half of a live bug standing. Rungs 2–4 landed as
written.

**The bug was sharper than the Opportunity recorded.** The Manage
Invitations table already filtered — `build_invitations_rows` →
`monitoring.per_reviewer_progress`, assigned-and-active — so the
operator saw one row and Send all emailed two people. The page and
the button disagreed, and the one the operator could not see is the
one who got the mail.

**Decisions confirmed at build.**
- Create after `mark_validated`, clean path only. The rejected
  alternative (create at Generate, before validate) is now genuinely
  caught by a test; the first version of that test used an empty
  session, where both orderings agree because nobody is eligible.
- `generate_invitations` stays a service function.
- The `has_invitations` skip reasons and both amber captions stay —
  open question 1 holds. Their *copy* did not: rung 3's first attempt
  named remedies that 409 in the state where they render.
- `?validated=1` keeps its inline flip (author, and see
  `### Judgment calls`).

**The finding worth carrying forward is about the instruments, not
the code.** Every rung, something asserted less than it claimed: a
vacuous identity check reading a key `invitation.sent` has never
carried; a mutant that survived because the test's session had nobody
eligible; five tests that would have gone vacuous when `_ready_session`
started creating invitations; an anti-vacuity control that fired
because two id sequences began advancing in lockstep; a test that had
been skipping itself green for years, whose docstring claimed
creating an invitation "populates email_outbox" when only a *send*
ever has. **None was caught by the suite. All were caught by a
reader.**

**Reads: four.** Rung 1 and rung 2 each took a `diff-reviewer` under
the old per-slice cadence — ten findings and eight — plus a
`spec-writer` pass on rung 2. Rung 3 took the first **per-item
cumulative** read under the cadence introduced mid-item (#2459), at
eleven findings, and it found the one defect that spanned rungs: copy
written in rung 3 that was unreachable because of a state rung 2 had
escalated and rung 3 had not settled. *Recorded per the cadence's own
rule 7, for the next practice audit to weigh.*

**Carried out**, all three now real entries in
`guide/deferred_consolidated.md` rather than claims that they were:
pruning stale invitation rows; the unaudited withheld send
(`counts.sent = 0` has two causes); and
`monitoring._assigned_active_reviewers` duplicating
`invitations._assigned_active_reviewer_ids` — the root cause of the
bug rung 1 fixed, left unfixed because unifying it reaches into the
monitoring layer.

**The close pass found the sweep's own class of miss: deleting a table
row without recomputing what depended on it.** Retiring Create invites
left `spec/workflow_card.md` saying "ten `*_visible` flags" (nine),
"10 conceptual button slots" above a nine-item list, a **Visible
total** row still carrying the old per-state counts, and a "worst case
is 4 (states 4 / 4W / 5)" that had stopped being true. Two sibling
rows were swept in one file and not the other
(`spec/session_home.md`'s `validated` row, `spec/operations_pages.md`'s
caller list).

*Recomputing the totals then surfaced a **pre-existing** error the
retirement had nothing to do with*: the matrix omitted Activate in
state 4Err, though `activate_visible` is `is_validated` alone and 4Err
is `is_validated`. Measured — the button ships in a state whose own
copy says to re-run Prepare first. The spec describes what ships;
whether it should is a design question this item did not open. The
matrix is now arithmetically self-consistent, checked by parsing it.

**Still owed:** dev-slot verification of the Workflow card with one
fewer button and the six rewritten copy strings. The copy is exactly
what the cumulative read caught, so it is the part most worth seeing
rendered.

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

### Decision

One slice per item it follows, landing after that item merges — the Guide
documents shipped behavior, not intent. Screencaps are recaptured in the
agent sandbox with Chromium against a seeded session.

**Rejected — one Guide slice at the end.** It would sit stale on `main`
between Item 1 and Item 2 merging, teaching a workflow that no longer
exists.

### Semantics

- A screencap pair is light + dark; both recapture together or the theme
  toggle shows two different app versions.
- `app/` ships wholesale, so a deleted screencap must also lose every
  reference in the same commit, or the test fails both ways.

### Judgment calls — decided

- Recapture rather than crop or edit existing PNGs — an edited screencap is a claim about the app that nothing checks (2026-09-17).

### Blast radius (measured)

- `ls app/web/static/guide/ | wc -l` → **40 files** (20 light/dark pairs)
- `grep -n "previews\|Create invites\|create-invites" app/web/templates/guide.html` → **7 lines**

### PR ladder

1. **Guide for Item 1** — the Previews paragraph and its screencap pair
   deleted; the drill-in's two jobs documented. Lands after 19Q.1 merges.
2. **Guide for Item 2** — the Prepare narrative, the two workflow
   screencap pairs, the validate-page alt text. Lands after 19Q.2 merges.

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
   surface" step now that the drill-in is the door? **Yes**, but framed
   as an **optional affordance rather than an operational step** — the
   walkthrough's numbered sequence stays the operator's path, and this
   is something to look at along the way (author, 2026-09-18).

### Out of scope

- A Guide sweep beyond the paragraphs these two items falsify. Recorded
  in `guide/segment_20_operator_polish_and_documentation.md`.

### Doc impact

- `docs/status.md` — row when Item 3 lands (Item 3).
- `spec/rrw_functional_spec.md` — the Guide's own contract, if the walkthrough gains a step per open question 1 (Item 3).
