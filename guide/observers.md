# Observers — participant role + collation surface

Standing notes for the **observer** participant role: who they
are, the data model, the surfaces, and the wiring tail that's
still to ship.

## Status

**Paused 2026-06-01, reframed 2026-06-02.** Operator-side
observer plumbing is live (roster Setup page, Quick Setup
slot, Extract Setup row, bundle inclusion, per-session enable
toggle, friendly-label resolver, visibility-policy column)
but the participant-facing collation surface
(`/me/sessions/{id}/collation`) renders only the placeholder
chrome — no body. The reframe below replaces the
collation-table sketch with a download-only model.

## Design reframe (2026-06-02)

### Two scenarios are real

**Scenario A — Universal observers** see the whole session
(department head, auditor, programme admin). The operator
already has Extract data + Zip-all bundles; a participant-
facing surface is mostly redundant. If a surface is wanted,
download-only is the cleanest shape.

**Scenario B — Partitioned observers** see one cohort (tutors
per tutorial group, mentors per cohort). This is the group
that genuinely benefits from a distinct observer role rather
than the operator emailing CSVs.

### Even Scenario B has two focuses

A partitioned observer might be monitoring **either**:

- **Responses about the partition** — what reviewers said
  about *the reviewees in this cohort*. (Tutor monitoring
  their tutees' feedback.)
- **Responses by the partition** — what *the reviewers in
  this cohort* wrote about others. (Peer-review class where
  reviewers are graded on the quality of their feedback.)

A cells-in-a-table surface would need a focus-switcher to
support both, with each switch landing on a differently-
shaped table. That's a lot of UI to maintain for one
participant role.

### Conclusion — observers = download-access role

All lines of reasoning point at the same conclusion:

> **Observers are participants other than the operator who
> get the ability to download a configured range of data
> about the session.**

The `/me/sessions/{id}/collation` surface should be, in the
first instance, a **download index** — a list of the data
the observer is entitled to, with per-file download links.
Not a render surface, not a cells-in-a-table view.

### Configurator lives on the Observers Setup page

The right home for "what does observer X get to download" is
**a dedicated configurator on the Observers Setup page**, not
the Band 3 visibility table.

Reasons:

- The Band 3 chip grid is a per-instrument × per-audience ×
  per-window cell-rendering matrix. It's the right shape for
  reviewer-form transparency + reviewee `/results` mode-
  picking — both of which are cells-on-a-table problems.
  Observer download scope is a different shape (which files
  / which scope / which partitions) and doesn't belong in
  the same primitive.
- An observer's scope is **per-observer**, not per-instrument.
  The Band 3 grid has no per-observer axis.
- The Observers Setup page already has the operator looking at
  the roster, the tags, the status. Adding a "what each
  observer can download" affordance on the same page keeps
  the operator's workflow cohesive.

### Implications for the existing operator surfaces

- **Band 3 visibility editor.** The current 3 × 2 chip grid
  has an `observer` row. Once the new configurator lands,
  that row's role is unclear. Two options:
  (a) drop the observer row from Band 3 entirely (the per-
  instrument cell-render policy is reviewee-only);
  (b) keep it but as the "default mode" for the summarized
  aggregates the observer downloads — orthogonal to the
  per-observer scope.
- **`/me/sessions/{id}/collation`.** Renders the download
  index, not a cross-reviewee table. The route gate stays
  (`require_observer_in_session`), the chrome stays, the
  body becomes a list of files.
- **Observers Setup page.** Adds a per-observer
  configurator — likely a small "scope" cell or expandable
  row carrying: focus (reviewees / reviewers / both),
  partition (whole session / matched by tag), file kinds
  allowed (responses CSV / per-instrument CSVs / shaped
  CSVs / setup bundle / etc.). Concrete shape is a design
  call when this re-opens.
- **W17 + W5 (paused).** The cross-reviewee table sketch is
  retired. The replacement is the download-index +
  configurator above; the supporting service module if
  needed is a thin file-list builder rather than the
  cell-rendering `build_observer_collation_context`
  originally proposed.

## Re-design path

When the work resumes:

1. **Spec the per-observer scope configurator** on the
   Observers Setup page. Decide the shape (focus axis,
   partition axis, file-kinds allowlist).
2. **Reshape the Band 3 observer row** per the implication
   above — drop it or repurpose it.
3. **Wire `/me/sessions/{id}/collation` as a download
   index** — render the list of files the observer can
   download given their configured scope, each file gated
   through a per-observer download route that materialises
   on demand.
4. **Reuse the extract pipeline** — every file kind already
   has an operator-facing serialiser (`reviewers_extract.py`,
   `relationships_extract.py`, `responses_extract.py`, the
   Data shaper output). The per-observer gate is a thin
   permission layer on top.

When that work scopes, fold this file into a
`segment_22_observers.md` plan and link from
`guide/todo_master.md`'s Upcoming list.

## Where the wiring stands

What's shipped (live in production):

- **Schema** — `observers` table, `observer.*` audit events,
  `sessions.observers_enabled` toggle.
- **Roster** — Setup-Observers page (CRUD + bulk + delete-all
  + Upload + Operator-actions row + Danger Zone) shipped
  W10 / PR #1706.
- **Quick Setup Observers slot** — Session Home + new-session
  form both upload a CSV with the same shape as the Setup
  page (W12 / PR #1754). Renders only when
  `observers_enabled` is on.
- **Extract Setup Observers row + bundle** — per-row CSV
  download (`observers.csv`) + inclusion in the Zip-all
  bundle, gated on the same toggle (W13 / PR #1755).
- **Per-instrument visibility policy** — operators can
  author Raw / Anonymized / Summarized for the `observer`
  audience on each instrument's Band 3 visibility editor
  (W15 + the per-window mode pair columns from S14).
- **`/me/sessions/{id}/collation` placeholder route** — page
  renders the reviewer-surface chrome with the caption
  "Observer view of the session"; gated on
  `require_observer_in_session` (W3 / P6, PR #1713). No
  body content yet.
- **Cross-role lobby support** — observers appear on
  `/me/` with the amber `observer` role pill if they're on
  any session's roster (W18, polish through #1715). Their
  role-navigator chip strip links to `/me/sessions/{id}/collation`.

## Paused work items (reshaped by the 2026-06-02 reframe)

- **W17 — Observer collation surface body.** Reshape from a
  cross-reviewee cell-rendering table to a **download index**
  per the reframe above. The original sketch (rows = reviewees
  in the observer's partition, columns = aggregate; cells
  resolved through the visibility policy) is retired.
- **W5 — `app/services/collation.py` service.** The original
  proposed `build_observer_collation_context` is also retired.
  The replacement, if needed, is a thin per-observer
  file-list builder + a download gate layer that calls the
  existing extract serialisers (`reviewers_extract.py`,
  `relationships_extract.py`, `responses_extract.py`, the
  Data shaper) with the observer's configured scope applied.

## Cross-references

- `guide/archive/participant_model_upgrade.md` — design rationale +
  the full audience taxonomy (§3.1 observer scope, §7
  collation render shape).
- `guide/archive/participant_model_remainder.md` — outstanding
  participant-model items overall; observer-side items
  filed here once this stub took ownership.
- `spec/audience_and_identity_model.md` — authoritative
  audience taxonomy.
- `spec/setup_pages.md` — Observers Setup page contract.
- `app/services/visibility_policies.py::resolve_mode` —
  the resolver W17 calls.
- `app/web/views/_reviewee_results.py::_summarize_field` —
  the per-data-type aggregation primitives W5 will reuse.
