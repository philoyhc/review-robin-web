# Warnings updates

**Opened:** 2026-10-17 · **Theme:** a Save that clears group answers asks
first · **Related:** `spec/assignments.md` "Group-scoped fan-out",
`spec/lifecycle.md` §3.2, `spec/setup_pages.md`

A standalone plan, not a `segment_*.md`, in the shape of
`guide/import_error_reporting.md`: one item, its `### Doc impact` checked
by hand at its close (`tools/close_check.py` reads only `segment_*`
files).

---

## Item 1 — Saves that clear group answers ask first

### Opportunity

A group instrument's subject is the group, so a change that adds a
member to a group clears every answer in it; a group that only shrinks
keeps its answer (author's rulings 2026-10-17; #3098, #3099, #3100). Prepare counts these clears before it runs. Nothing
else does. These Saves can clear answers without asking: the Instrument
card's unit of review and boundary tags (a merge, Individual to
Grouped), a reviewee tag edit into an answered group, and every
relationship change that moves a pair into an answered group (add,
edit, CSV import, Delete all, Inactivate, Reactivate, bulk Delete: an
inactive or missing relationship reads as empty tags, so a pair can
land in the empty-tag group). The 2026-10-03 ruling that relationship
changes ask nothing predates the clear, which now loses a whole group
rather than one copy.

### Decision

**The author ruled on 2026-10-17: refuse, then re-offer, on every
surface.** A Save that would clear any group answer does nothing.
Instead, the page re-shows the operator's input with a banner: *"This
change clears N saved responses on groups whose members it changes."*
It also shows a `Yes, clear them` tick, sent as
`acknowledge_response_loss=true`. Ticking it and saving again goes
through.

`clear_changed_groups` gains `acknowledged: bool`. Unacknowledged, it
raises `GroupAnswersWouldClear(count)` before deleting anything. The
route catches it, rolls the transaction back, and re-renders. The
mutation never commits, so no change has to be dry-run separately.

**Rejected:**
- A browser `confirm()`: it covers only the JS Instrument card, and it
  cannot name a count without a second round trip.
- Warning after the fact: the loss cannot be undone.

### Semantics

- **Count.** The count is the `Response` rows that would be deleted,
  as Prepare's banner counts them. If the count is zero, the Save
  never asks, so an unchanged Save or an unanswered instrument is never
  stopped.
- **Service default.** Services take `acknowledged=True` by default, so
  imports, Duplicate, Rehydrate and tests keep their behavior. The
  routes listed above pass the form's value. A route that forgets to
  pass it fails open. That is the reason for the per-route tests.
- **Deletes.** A reviewee delete only shrinks groups, so it clears
  nothing and keeps its existing gate unchanged.
- **Instrument card.** The card saves through a JS fetch. A refusal
  answers 422 `{"ok": false, "confirm_group_clear": N}`. The card's
  error banner shows the line and the tick, and the next Save sends the
  tick. Nothing reloads, so the card's edits stay.
- **Relationships CSV import.** The upload card's banner carries the
  line and the tick beside `confirm_replace`. The file must be chosen
  again, as on every refused upload.

### Judgment calls — decided

- One field name, `acknowledge_response_loss`, for every response
  loss. A second name would let one tick satisfy the wrong gate.
- `Inactivate` and `Reactivate` gain the tick inline in the row
  expander, as Delete has.

### Blast radius (measured)

Taken 2026-10-17 at `df32ff26`.

| What | Count | Command |
|---|---|---|
| Clear call sites | 12 | `grep -rn "clear_changed_groups(\|clear_redrawn_groups(\|_reconcile_regrouped(" app --include=*.py \| grep -v "def " \| wc -l` |
| Routes to gate | 10 | `grep -rn` for the eleven route paths in `app/web/routes_operator`, less `/reviewees/bulk-delete`, which no longer clears |
| Templates | 3 | `instruments_index.html`, `session_reviewees.html`, `session_relationships.html` |
| Specs naming the acknowledgement | 9 | `grep -rln "response-loss acknowledgement\|acknowledge_response_loss" spec docs \| grep -v archive` |
| Tests posting to those routes | 53 | `grep -rln "relationships/create\|relationships/import\|reviewees/.*/update\|instruments/.*/save" tests \| wc -l` |

### PR ladder

1. **PR 1 — this plan.** Lands the plan, its README row and the
   `todo_master.md` entry. Must not touch `app/`.
2. **PR 2 — the gate, on the Instrument card.** Lands the `acknowledged`
   flag and the exception, the card's 422 and its banner tick, and
   tests. Must not touch Reviewees or Relationships.
3. **PR 3 — Reviewees.** Lands the tag-edit refusal in the row editor.
   Must not touch Relationships.
4. **PR 4 — Relationships.** Lands add, edit, import, Delete all,
   Inactivate, Reactivate and bulk Delete. This is the last build rung,
   so it takes the item's cumulative `diff-reviewer` read from
   `df32ff26`.
5. **PR 5 — close.** Lands the specs, the `spec-writer` pass and
   `Status`.

### Definition of done

- Each of the 10 routes refuses an unacknowledged clear with the count,
  keeps the operator's input, and goes through when acknowledged. Each
  route has a test.
- An unchanged Save on each surface never asks.
- `spec/lifecycle.md` §3.2 lists the group-clear gate, and
  `spec/assignments.md` "Group-scoped fan-out" says every clear asks.
- `## Doc impact` section present and current
- Doc impact checked by hand (no `close_check.py` for a non-segment plan)
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entry deleted; plan moved to `guide/archive/` + index row

### Open questions

None open. The pattern and the scope were ruled by the author on
2026-10-17.

### Out of scope

- Quick Setup's relationships slot. The card is locked whenever the
  session has responses (`views/_quick_setup.py`), so it cannot reach a
  clear.
- Settings import and Rehydrate. They rebuild a session's instruments
  rather than redraw its groups.

### Doc impact

- `spec/assignments.md` — "Group-scoped fan-out": every clear asks.
- `spec/lifecycle.md` — §3.2: the group-clear gate and the routes it
  covers.
- `spec/setup_pages.md` — the Reviewees and Relationships refusals,
  ticks and counts.
- `spec/instruments.md` — the card's group-clear refusal on Save.
- `spec/rrw_functional_spec.md` — the losses outside regeneration now
  ask.
- `spec/operator_button_audit.md` — the Relationships rows that gain
  the tick.
