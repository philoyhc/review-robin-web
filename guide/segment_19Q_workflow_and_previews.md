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

### Blast radius (measured)

- `grep -rln "create_invites_visible\|invitations/generate\|Create invites" app/ tests/ spec/ docs/` → **19 files** (6 app, 7 tests, 6 spec/docs)
- `grep -rln "invitations_not_created\|no_invitations" app/ tests/ spec/ docs/` → **12 files**
- `grep -rln "workflow/prepare" tests/` → **12 test files**

### Status

**Rung 1 landed 2026-09-18, across two send paths rather than one.**

The ladder named `invitations_send_all`. Building it found
`_dispatch_pending_invitations`
(`app/services/scheduled_events/_invites.py`) running its own copy of
the same query with the same defect — and that is the **unattended**
path, firing from a timer with no operator present. Fixed both;
splitting them would have left a known live bug in the worse of the
two. *The register names the instance somebody noticed, not the class.*

**The bug is sharper than the Opportunity records.** The Manage
Invitations table already filters: `views.build_invitations_rows` goes
through `monitoring.per_reviewer_progress`, which is assigned-and-active.
So the operator saw one row and the button emailed two people — the page
and the button disagreed about who is in the session, and the one the
operator could not see is the one who got the mail.

**One definition, not a third spelling.** `list_sendable_invitations`
reuses `_assigned_active_reviewer_ids`, the predicate
`generate_invitations` already enrols on, so a row is sendable exactly
when a fresh Prepare would have created it.
`monitoring._assigned_active_reviewers` is a *second* spelling of the
same idea and is how these two surfaces came to disagree in the first
place; unifying it is not this rung's (it would touch the monitoring
layer) but it is the root and should be recorded as such.

`spec/workflow_card.md`'s *"Iterates every pending invitation"* became
false the moment this landed, so it is corrected now rather than at
rung 4 — the file was already in `Doc impact`.

**The cold read found two residues the rung itself created**, both now
fixed here:

- The **"Pending invitations" pill** counted every pending row while
  the button stopped sending every pending row, so an ineligible
  reviewer's invitation would read amber forever with no control on
  the page able to clear it. The rung had moved its own defect from
  the button to the counter. It counts the sendable set.
- **`invitations_send_one` was the third send path** and still gated on
  `status == "active"` alone, so a direct POST could mail someone the
  two bulk paths refuse. Its comment claimed to "match the bulk
  send-path's active-only gate" — true when the bulk path had no gate,
  a half-truth in the other direction afterwards. Gated on eligibility
  only, deliberately not on `pending` as well: that would be a second,
  unrelated behavior change riding this rung.

**And three defects in the tests, which is the pattern this segment
keeps meeting.** The scheduled test's identity assertion read
`context.to_email` off `invitation.sent`, which has never carried it
(`context={"trigger": trigger}`) — **vacuously true**, and would have
passed if the scheduler mailed the stranded reviewer. It reads
`EmailOutbox.to_email` now, verified by inverting it. The
"leaves it pending" test asserted two things a total no-op satisfies.
And `_strand_an_invitation` never checked the session came back to
`validated`, though `workflow_prepare` answers 303 on a failed
validation too.

**The untested half of eligibility had a wrong lever, and finding out
was worth more than the test.** Nothing covered *active reviewer, no
included assignment*. The first attempt used
`POST /assignments/bulk-inactivate` then re-Prepared, and failed:
`workflow_prepare` runs `replace_assignments`, which re-materialises
every row from the pinned rule set, so **a per-row exclusion does not
survive the Prepare that makes the session sendable**. Measured, not
read. In the field that state comes from a rule the regeneration
reproduces; the test sets the column directly and says why.

**Observability gap, recorded not fixed.** `counts.sent = 0` on
`session.scheduled_invites_fired` now has two causes — all already
sent, or all pending rows ineligible — and nothing is audited for the
withheld rows, on either send path. A skip event means a new
`EVENT_SCHEMAS` entry, so it belongs to a later rung or to
`guide/deferred_consolidated.md`, not here.

**`spec-writer` (pre-push, since the slice touches `spec/`) came back
clean on this slice** and raised one phrase of mine — *"the four
surfaces cannot drift"*, where the test actually has five call sites.
Rewritten to name them; a count is the part that goes stale.

**It also found a contradiction that predates this segment**, and it
needs an author ruling rather than a fix here:
`spec/operations_pages.md:127-129` and `:304` both say the Invitations
page's per-row **Send** and **Regenerate** are *"live from `validated`
onward"*, and `:306` adds that all three render disabled outside their
allowed state. The template gates both on `is_ready`
(`session_invitations.html:309,327`), which is `lifecycle.is_ready`
alone (`_workflow_card.py:110`) — so both buttons are disabled in
`validated`, the state the spec says they are live in. Verified at
`file:line`. Either the template should gate on
`is_validated or is_ready`, matching the route's own
`_require_validated_or_ready`, or the spec was never true. Out of this
rung's scope and not in Item 2's `Doc impact`; filed here so the
segment can adjudicate it.

Six mutants, all caught: route reverted to the unfiltered listing;
eligibility filter dropped; `pending` filter dropped; scheduled path
back to its own query; the eligibility test reduced to its status limb;
and the scheduled identity assertion inverted. *The `pending`-filter
mutant is caught by a pre-existing test
(`test_scheduled_invites.py`'s second-fire `counts.sent == 0`), not by
any of the new ones — the first write-up implied otherwise.*

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

1. Can a session validate with **zero** eligible reviewers? **Yes** —
   measured: a full roster with every assignment excluded gives 0
   eligible reviewers, **0 blocking errors** and `can_activate: True`,
   on two warnings (`assignments.no_included_pairs`,
   `instruments.zero_included`). `reviewers.empty` is an error, but
   `assignments.no_included_pairs` is only a warning. Author: *"warning
   is enough; the session is set up, just that there are no eligible
   invites."* **So rung 3 keeps the `has_invitations` skip reasons and
   both amber captions** — a clean Prepare can still leave
   `has_invitations` false.
2. Does `POST /invitations/generate` 308 to Prepare, or is it deleted?
   **Deleted.** A POST is not a bookmark.

### Out of scope

- **Pruning stale invitation rows on re-Prepare.** Rung 1 makes them
  harmless; deleting one risks removing a *sent* invitation still live in
  a reviewer's inbox. Recorded in `guide/deferred_consolidated.md`.
- **Activate's revalidation asymmetry** — Activate recomputes validation
  before flipping (`_workflow.py:294`), Create invites trusts the status.
  Sound given the invalidation invariant; not a defect.

### Doc impact

- `spec/workflow_card.md` — Prepare's contract gains invitation creation; the Create invites button row, its copy, and the `invitations_not_created` skip narrative retire (Item 2).
- `spec/lifecycle.md` — the "Auto-send invites" precondition row collapses to Prepared alone (Item 2).
- `spec/architecture.md` — the `session.scheduled_invites_skipped` reason set drops `invitations_not_created` (Item 2).
- `spec/operator_button_audit.md` — the Create invites row retires (Item 2).
- `spec/operations_pages.md` — Manage Invitations' `not_created` chrome state, and Send all's row set (Item 2).
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
