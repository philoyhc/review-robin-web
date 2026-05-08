# Segment 13A-1 — Rule Based editor revamp

Implementation plan for the **single-card, self-sufficient Rule
Builder page** that supersedes Segment 13A's two-column editor
(seed view + Personal editable view + Library panel + preview).
Everything an operator does to a RuleSet — pick from any seeded
or Personal RuleSet, copy, edit, save, delete, or start blank —
happens on one page without ever bouncing back to the session
assignments page.

> **Relationship to Segment 13A.** 13A landed the full ruleset
> machinery (schemas, engine, seeds, library service, audit
> events, the assignments-page Rule Based card). This sub-
> segment only revamps the editor surface — no new domain
> primitives, no new services beyond thin route plumbing. The
> existing `/operator/sessions/{id}/assignments/rule-based/edit/{rule_set_id}`
> route stays alive in parallel until the new surface is proven,
> then a follow-on PR retires it. The Rule Based Assignment card
> on the main assignments page is **not** linked to the new
> route in this segment — operators reach it by typing the URL
> or via a future card update.

## Status

Planning. Sized as **4 PRs** in dependency order. Each PR ships
independently on top of `main`; PRs 1–3 build the new surface
behind its own URL, PR 4 retires the old editor.

1. **PR 1 — New route + dropdown selector + read-only seed view.**
   Adds `GET /operator/sessions/{id}/assignments/rule-based-editor`
   with breadcrumbs and the new single-card "Rule Builder"
   surface. Top dropdown lists all visible RuleSets (seeds first,
   then Personal, then a sentinel "+ New blank RuleSet" entry).
   On first paint and on dropdown change, the card renders the
   selected RuleSet **read-only**: a sentence-shaped text view
   (no inputs) reusing the existing seed-view rule renderer.
   Only Copy is enabled. No Save / Cancel / Delete yet — those
   land in PR 2.
2. **PR 2 — Copy / Save / Cancel / Delete + form editing.**
   Personal RuleSets render as the existing PR 5b/5c indented
   inline-composite **editable** form. Action row: Copy / Save /
   Cancel / Delete. Cancel reverts to last-saved state. Delete
   soft-deletes and reloads the next visible RuleSet (first seed
   fallback). Copy creates a new Personal with auto-generated
   name (e.g. "Copy of Intra-group peer review") and selects it
   in-place (form switches to the new draft, no redirect, draft
   not persisted until Save).
3. **PR 3 — "New blank RuleSet" entry.** The sentinel dropdown
   option loads a truly blank draft (zero rules, default top-
   level combinator AND, auto-name "New RuleSet"). Save is gated
   server-side until at least one rule exists (route returns 422
   with inline message; client-side button stays disabled until
   the rules_json hidden field encodes ≥1 rule).
4. **PR 4 — Retire the old editor.** Delete the `_rule_based_card.html`
   "Edit ruleset" link's old target; rewire it to the new route.
   Delete `session_rule_based_editor.html`, the `_rule_based_*_panel*`
   partials that the new surface doesn't use, and the routes
   `GET /edit/{rule_set_id}` + `POST /copy` + `POST /save-as` (the
   route handlers that the new flow doesn't need). Retire
   integration tests pinned to the old surface; port any still-
   relevant assertions onto the new tests.

Sequencing rationale:

- **PR 1 is read-only.** Lets the new URL exist, the dropdown be
  exercised, and the seed-view rendering land without any write
  path. Shippable on its own — the operator just can't edit yet,
  and falls back to the old `/edit/{id}` for editing.
- **PR 2 is the meat.** Makes the new surface usable end-to-end
  for any seeded or Personal RuleSet that already exists.
- **PR 3 adds the empty-state path.** Independent of PR 2 in
  code (just a new dropdown sentinel + a blank-form template
  branch), but PR 2 ships first because copy-from-seed is the
  90% path.
- **PR 4 deletes the old surface.** Held to last so PRs 1–3 can
  ship behind the new URL while the old `/edit/{id}` keeps
  working as a fallback. Retiring it is cheap once the new
  surface is proven on the dev slot.

## Locked decisions

The user-visible behaviour was nailed down in planning Q&A; pin
these so PR review can focus on plumbing rather than re-litigating
UX:

1. **Page is self-sufficient.** No redirect back to the
   assignments page on Save / Save As / Delete / Cancel. All
   actions return to the same URL with the new selection loaded
   in-card.
2. **Switching the dropdown silently auto-discards unsaved edits.**
   No `window.confirm`, no inline guard. Operators are expected
   to Save / Cancel before switching; the page reload after
   switching is the discard signal. Mirrors the silent-reload
   posture the assignments-page Rule Based card already takes.
3. **Action row depends on selection state.**
   - **Seeded RuleSet (read-only):** Copy only.
   - **Saved Personal RuleSet (editable):** Copy + Save + Cancel
     + Delete.
   - **Unsaved draft (Copy from seed/Personal, or "New blank"):**
     Save + Cancel only. No Delete (nothing to delete yet); no
     second Copy until the draft is saved.
4. **Cancel reverts to last-saved state of the currently-selected
   RuleSet.** For an unsaved draft (Copy / New blank), Cancel
   discards the draft and reverts the dropdown to the previous
   selection (i.e. whichever RuleSet was loaded before the draft
   was started).
5. **Placeholder name is auto-generated from source.**
   - Copy of seeded `Intra-group peer review` → `"Copy of Intra-group peer review"`.
   - Copy of Personal `My team's review` → `"Copy of My team's review"`.
   - New blank → `"New RuleSet"`.
   The name is editable inline (same affordance as PR 5b's name
   field). DB unique-by-owner constraint surfaces a friendly
   422 on Save collision; the route appends ` (n)` suffix on
   Save only if the literal source-derived default would collide
   (saves the operator a rename round-trip).
6. **Seed read-only is a text view.** No disabled form inputs;
   render the selected seed using the existing seed-view rule
   renderer (sentence-shaped predicates, plain text). The Copy
   button is the only affordance.
7. **URL stays at `/assignments/rule-based-editor` regardless of
   selection.** No `?rule_set_id=` query param, no per-RuleSet
   sub-path. Refresh returns to the default selection (first
   seed). Back/forward don't restore RuleSet selection — that's
   an explicit non-goal for this revamp. (If shareable URLs
   become a request later, add `?rule_set_id=` as a future PR.)
8. **"New blank" produces a truly empty draft, Save gated to ≥1
   rule.** Combinator picker present; rules list empty. Save
   button is `disabled` client-side until the inline-JS
   serializer reports ≥1 rule; the route still validates
   server-side and returns 422 with `?rule_based_error=empty_rules`.
9. **Rule-builder body reuses existing editor partials.** The
   indented inline-composite rule list, predicate sentence
   editor (verbs), combinator picker, and `rules_json` indent-
   stack serializer from PR 5b/5c are lifted unchanged into
   the new card. No new rule-shape primitives in this segment.
10. **Audit emission is unchanged.** This segment doesn't touch
    `rule_set.created` / `.updated` / `.deleted` event types, the
    `via=` vocabulary, or the envelope shape. Whatever the
    library service already emits for `copy_rule_set` /
    `save_in_place` / `save_as_rule_set_from_schema` /
    `soft_delete_rule_set` carries through.

## Page surface

```
Operator → Sessions → <session> → Assignments → Rule Builder

[breadcrumb]   ← /operator/sessions/{id}/assignments

╔════════════════════════════════════════════════════════════════╗
║ Rule Builder                                                   ║
║ ──────────────────────────────────────────────────────────────  ║
║                                                                 ║
║   RuleSet  [ Intra-group peer review            ▾ ]            ║
║            (seeded — read-only. Copy to edit.)                  ║
║                                                                 ║
║   ┌─────────────────────────── read-only seed view ─────────┐  ║
║   │ Match: reviewer tag1 is the same as reviewee tag1.       │  ║
║   │ Filter: reviewer email is not empty.                     │  ║
║   └──────────────────────────────────────────────────────────┘  ║
║                                                                 ║
║                                          [ Copy ]               ║
╚════════════════════════════════════════════════════════════════╝
```

When the operator selects a Personal RuleSet from the dropdown:

```
   RuleSet  [ My team's review                    ▾ ]
            Name [ My team's review                  ]  (inline edit)

   Top-level combinator: ( • AND  ○ OR )

   1. Match — reviewer tag1 [is the same as ▾] reviewee tag1   [×]
   2. Filter — reviewer email [is not empty ▾]                 [×]
      [+ Add filter]  [+ Add match]  [+ Add quota]  [+ Add composite]

                              [ Copy ]  [ Cancel ]  [ Save ]  [ Delete ]
```

When the operator picks **+ New blank RuleSet** from the dropdown:

```
   RuleSet  [ + New blank RuleSet                  ▾ ]
            Name [ New RuleSet                        ]

   Top-level combinator: ( • AND  ○ OR )

   (no rules yet)

      [+ Add filter]  [+ Add match]  [+ Add quota]  [+ Add composite]

                                       [ Cancel ]  [ Save (disabled until ≥1 rule) ]
```

## Routes

New (PR 1 + PR 2 + PR 3, all under `/operator/sessions/{id}/assignments/rule-based-editor`):

- `GET  /` — Rule Builder card. Query param `rule_set_id`
  optional; if absent, loads the first seed (or the New-blank
  sentinel if explicitly `?new=1`). The URL bar stays clean
  regardless — `rule_set_id` is only honoured on the server
  side and stripped from the canonical href.
- `POST /copy` — body `from_rule_set_id`. Creates a Personal
  RuleSet (auto-name "Copy of …"), redirects 303 back to the
  same URL with the new RuleSet selected (server-side; URL bar
  stays clean).
- `POST /save` — body `rule_set_id` + `name` + `rules_json` +
  `combinator`. Save in place (Personal only). For an unsaved
  draft (no `rule_set_id`), creates the row first (Save-As-
  semantics — replaces PR 5b's separate `/save-as`).
- `POST /delete` — body `rule_set_id` + `confirm=true`. Soft-
  delete; redirect 303 back to the same URL with the next-
  visible RuleSet selected.

The existing `POST /preview` from PR 5c is **not** carried over —
the new card has no preview slot per the brief.

Old routes that PR 4 retires:

- `GET  /assignments/rule-based/edit/{rule_set_id}`
- `POST /assignments/rule-based/edit/{rule_set_id}/copy`
- `POST /assignments/rule-based/edit/{rule_set_id}/save-as`
- `POST /assignments/rule-based/edit/{rule_set_id}/save`
- `POST /assignments/rule-based/edit/{rule_set_id}/rename`
- `POST /assignments/rule-based/edit/{rule_set_id}/delete`
- `POST /assignments/rule-based/edit/{rule_set_id}/preview`

The `POST /assignments/rule-based/generate` route on the
assignments page is **untouched** — it runs the engine against
whichever RuleSet the assignments-page card has selected, which
is independent of the editor surface.

## View-shape adapter

Add a new dataclass in `app/web/views.py`:

```python
@dataclass(frozen=True)
class RuleBuilderContext:
    options: list[RuleSetOption]          # dropdown entries (seeds + personal + new-blank sentinel)
    selected_id: str | None               # None when the new-blank sentinel is selected
    selected: RuleSetSchema | None        # None for new-blank
    selected_is_seed: bool                # drives read-only vs. editable rendering
    selected_is_draft: bool               # True for new-blank (no row in DB yet)
    name: str                             # current draft name (auto-generated when draft)
    combinator: Literal["AND", "OR"]
    rules_json: str                       # initial form value for the hidden field
    editable_rules: list[EditableRule]    # only populated when editable
    seed_rule_lines: list[str]            # only populated when seeded (read-only sentences)
    can_save: bool                        # derived from selected_is_seed + rules count
    can_delete: bool                      # True only for saved Personal
```

Builder: `build_rule_builder_context(session, current_user, db, *,
selected_id: str | None, draft: bool = False) -> RuleBuilderContext`.
Reuses the existing `EditableRule` dataclass and
`_flatten_editable_rules` walker from PR 5b — no domain-shape
changes.

## Templates

New:

- `app/web/templates/operator/session_rule_builder.html` — the
  single-card page. Extends `base.html`, breadcrumbs via
  `operator_session_child(session, "Rule Builder")`.
- `app/web/templates/operator/partials/_rule_builder_card.html` —
  the card body. Branches on `selected_is_seed`,
  `selected_is_draft`, and `can_save` to render the right
  surface. Reuses `_rule_based_editor_js.html` (the indent-
  stack serializer + add/remove buttons) for the editable
  branches.

Reused unchanged from Segment 13A:

- `_rule_based_editor_js.html` — the indent-stack `rules_json`
  serializer.
- The seed-view rule sentence renderer (the
  sentence-shaped text rendering used by the read-only seed
  partial).

Retired in PR 4:

- `session_rule_based_editor.html`
- `partials/_rule_based_library_panel*.html`
- `partials/_rule_based_copy_picker_js.html`
- `partials/_rule_set_preview.html`

## Tests

PR 1:

- `tests/integration/test_rule_builder_page.py`
  - GET renders, dropdown lists all 5 seeds + 0 personal + 1
    "New blank" sentinel.
  - First-paint loads first seed read-only (no inputs in form).
  - Switching dropdown to a different seed updates the read-only
    body (server-side render path; no JS in tests).
  - 404 / 403 for non-operator and unknown session.

PR 2:

- `tests/integration/test_rule_builder_copy_save_delete.py`
  - Copy from seed creates a Personal with auto-name "Copy of …".
  - Save in place mutates `rules_json` + name; second Save with
    same name no-ops cleanly.
  - Cancel revert: the route doesn't actually need a Cancel
    handler (it's a client-side form reset to initial values),
    but assert that GET after Cancel shows the saved state.
  - Delete soft-deletes, reloads next-visible RuleSet.
  - Inline rename via the name field on Save.
  - 422 on duplicate-name collision; auto-suffix on Copy
    collision.

PR 3:

- `tests/integration/test_rule_builder_new_blank.py`
  - "New blank" sentinel selectable; renders empty rules list
    with combinator picker.
  - Save with zero rules returns 422 / `?rule_based_error=empty_rules`.
  - Save with one rule succeeds, creates Personal "New RuleSet".

PR 4:

- Delete `tests/integration/test_rule_based_editor.py`. Port
  any unique assertions (e.g. predicate verb rendering) to the
  PR 1–3 test files first.

No new unit tests — the schema, engine, predicates, quotas,
fields, seeds, and library service are all unchanged.

## Risks

- **Dropdown is the only navigation primitive.** If the Personal
  list grows past ~30 rulesets the dropdown gets unwieldy. Out
  of scope here — the assumption is operators have at most a
  handful of saved rulesets per session. Revisit if the field
  reports otherwise; a search/filter row above the dropdown
  would be the natural next step.
- **Silent auto-discard on dropdown change.** Operators can
  lose unsaved work. Mitigation: Cancel + Save buttons sit
  immediately under the form, and the dropdown is at the top
  (visually separated). If field feedback shows accidental
  discards, revisit with a `window.confirm` guard like the
  retired Library panel had.
- **Old editor still works during PRs 1–3.** Two surfaces exist
  in parallel; if the assignments-page card's "Edit ruleset"
  link is followed in dev-slot smoke testing, the operator
  ends up on the old page, not the new one. PR 4 closes that
  by rewiring the link. Document this in the PR-1 and PR-2 PR
  descriptions.
- **PR 4 churn.** Retiring the old editor touches the
  assignments-page Rule Based card link target and deletes
  ~3 partials + 1 template + 6 routes + 1 test file. Diff is
  bigger than PRs 1–3 individually. If reviewer load is a
  concern, split PR 4 into 4a (rewire link, keep old route as
  no-op redirect) + 4b (delete dead code).

## Out of scope

- Linking the assignments-page Rule Based card to the new editor
  (kept as old link until PR 4).
- Preview pane, sampled-pairs distribution, or Library panel.
- Rule-shape changes (e.g. new combinators, new predicate
  operators, new field paths).
- Shareable per-RuleSet URLs (`?rule_set_id=`).
- Drag-and-drop rule reordering (the existing dropdown reorder
  affordance from PR 5c carries through).
- Multi-tab edit conflict detection (last-write-wins, same as
  Segment 13A).
