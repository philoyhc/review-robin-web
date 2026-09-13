# Session round-trip coverage

**What survives when a session's configuration is exported and
re-imported — and what silently doesn't.** This is the authoritative
coverage matrix for the three round-trip mechanisms. It exists because
"export the settings and re-import them" is load-bearing for backup /
restore, porting a session between environments, cloning, and the proposed
[rehydrate](../spec/rehydrate.md) feature — and several hand-set settings
do **not** come back.

Companion to `spec/settings_inventory.md` (the full index of every
persisted setting). Where that doc's §10 coverage table and this doc
disagree, **this doc governs** — it is the field-by-field matrix, and it
covers several config surfaces the inventory's matrix does not name (view
policies, observer cohort rules, `band1_touched_links`, reviewer
`profile_link`).

## Scope

- **In scope:** per-session *configuration* and *populations* — everything
  an operator sets by hand.
- **Out of scope, by design:** reviewer-typed **responses** and the
  **audit log** (data, not config); per-operator **UI state** (sort
  cookies, column-width localStorage — see `settings_inventory.md` §7);
  deployer **env vars**; and machine-derived runtime state (`status`,
  `activated_at`, `deadline_closed_at`, `cached_*`).

## The three mechanisms

| Mechanism | Direction | Carries | Entry points |
|---|---|---|---|
| **Settings CSV** | `session_config_io.serialize_session_config` → `apply_session_config` | Config only (no rosters, no data). The `field,value,data_type` file. | Export `GET …/export/settings.csv`; import Quick Setup slot 4 / `POST …/import-config` |
| **Roster CSVs** | `extracts/*_extract.py` → `csv_imports` / `relationships` | Reviewers, reviewees, observers, relationships | Per-entity export routes; Quick Setup / Setup-page uploads |
| **Clone** | `session_clone.clone_session` (in-DB, no CSV) | Config graph; `"all"` mode adds rosters | Lobby row-expander → Duplicate / Duplicate settings only |

`rehydrate` composes the settings CSV + roster CSVs + the responses
importer; its coverage is the union of the first two columns below plus
responses. See `spec/rehydrate.md`.

**Legend:** ✅ round-trips · ⚠️ partial / asymmetric (see notes) · ❌ lost ·
— not applicable.

## Coverage matrix — configuration

### Session metadata (`sessions`)

| Setting | Settings CSV | Clone | Notes |
|---|:--:|:--:|---|
| `name`, `code`, `description`, `deadline`, `help_contact` | ✅ | ✅ | Settings-CSV applies these only when the target is empty (fallback semantics); clone rewrites name→"Copy of …", derives a unique code, resets deadline |
| `display_timezone`, `self_reviews_active` | ✅ | ✅ | Force-applied |
| `email_template_overrides` (12 keys + `responses_received_enabled`) | ✅ | ✅ | Whole-JSON replace |
| `scheduled_activate_at`, `responses_release_at`, `responses_release_until`, `invite_offsets`, `reminder_offsets`, `archive_offset` | ✅ | ❌ *(by design)* | Clone resets the schedule **on purpose** — a clone is a fresh cycle the operator re-schedules, like the deadline. Settings-CSV round-trips these for backup / restore |
| `retention_exception`, `retention_overrides` | ✅ | ✅ | Clone copies retention config |
| **`relationships_enabled`, `observers_enabled`** | ✅ | ✅ | Both paths carry them — a cloned "all"-mode session's copied observer / relationship rows would otherwise be hidden by a `False` toggle |
| `assignment_mode` | ❌ | ❌ | Machine-derived: the Settings CSV drops it, and a clone starts NULL because it copies no assignment rows |
| `status`, `activated_at`, `created_by_user_id` | — | — | Runtime / identity — intentionally reset |

### Instruments (`instruments`)

| Setting | Settings CSV | Clone | Notes |
|---|:--:|:--:|---|
| `name`, `short_label`, `description`, `responses_visible_when_closed`, `sort_display_fields`, `group_kind`, `rule_set_id` (by name), `column_widths`, `starts_new_page`, `band2_state` | ✅ | ✅ | Full config round-trip both paths |
| `accepting_responses` | ✅ | ❌ | Settings-CSV restores the runtime open/closed flag; clone resets it (fresh draft) |
| `order` | ⚠️ | ✅ | Settings-CSV serializes + parses it but **apply ignores it** — 1-based CSV position wins. Value round-trips only because export order matches position |
| **`band1_touched_links`** | ✅ | ✅ | `instruments[n].band1_touched_links` in the Settings CSV; clone copies the column |
| `deadline_closed_at`, `cached_group_pair_count/_stamp` | — | — | Runtime / cache |

### Instrument display fields (`instrument_display_fields`)

| Setting | Settings CSV | Clone | Notes |
|---|:--:|:--:|---|
| `source_type`, `source_field`, `visible` | ✅ | ✅ | |
| `label` | ❌ | ⚠️ | Not serialized; import tolerates + drops the row if a bundle carries one → always restored empty. Clone copies the (dead) column |

### Instrument response fields (`instrument_response_fields`)

| Setting | Settings CSV | Clone | Notes |
|---|:--:|:--:|---|
| `field_key`, `label`, `response_type`, `required`, `help_text`, `help_text_visible`, `data_type`, `min`, `max`, `step`, `list_csv`, `visible` | ✅ | ✅ | Inline bounds carried on the response-field row |
| `validation` (JSON) | ⚠️ | ✅ | Settings-CSV **recomputes** it from the inline bounds on import (derived, not carried); clone copies it verbatim |

### Instrument visibility policies (`instrument_view_policies`)

| Setting | Settings CSV | Clone | Notes |
|---|:--:|:--:|---|
| `audience`, `while_ongoing_granularity/_identification`, `after_release_granularity/_identification`, `observer_tag` | ✅ | ❌ | Settings-CSV carries the Band 3 grid (`instruments[n].view_policies[<audience>].*`, recreated in the instrument rebuild). Clone does **not** copy it — a clone reverts to default visibility. **The import validates each `(audience, window)` cell** against the same table the editor uses and rejects the whole apply on an illegal one (`spec/visibility_policy.md` §3.1). A round-trip of an editor-authored session is unaffected: the serializer emits all four cells for every audience, so a forbidden cell exports as two empty strings and parses back to `None`, which is that cell's legal mode |

### Rule sets (`session_rule_sets`)

| Setting | Settings CSV | Clone | Notes |
|---|:--:|:--:|---|
| `name`, `description`, `combinator`, `exclude_self_reviews`, `seed`, `rules_json` | ✅ | ✅ | `exclude_self_reviews` is vestigial (engine hardcodes `False`) |

### Field labels (`session_field_labels`)

The **roster CSV header** is the sole round-trip carrier (see
`spec/csv_contracts.md` §1a): a tag friendly label rides on its column
as a `ReviewerTag1.<label>` suffix, import ↔ export **symmetric**. The
Settings CSV carries no `field_labels.*` row, and one in an older bundle
is silently ignored on apply rather than failing the import.

| Setting | Roster CSV | Settings CSV | Clone | Notes |
|---|:--:|:--:|:--:|---|
| `reviewer/reviewee.tag_1..3`, `pair_context.1..3` | ✅ | ❌ | ✅ | Roster header suffix (import upserts, bare header / absent column clears — mirrors the roster's wipe-and-replace). Clone copies all |

### Data shapes (`data_shapes`)

| Setting | Settings CSV | Clone | Notes |
|---|:--:|:--:|---|
| `name`, `axis`, instrument/response-field refs (portable), `column_chip_slots`, `self_review_handling`, `include_empty_rows` | ✅ | ✅ | Clone copies data shapes (scope chips re-pointed at the clone's instrument + response field); settings-CSV round-trips them via portable refs |

### Session tags (`session_tags`)

| Setting | Settings CSV | Clone | Notes |
|---|:--:|:--:|---|
| `tag` | ✅ | ✅ | `session_tags[i].tag` in the Settings CSV, wipe-and-replace; clone copies them |

### Populations — reviewers / reviewees / observers / relationships

| Setting | Roster CSV | Clone (`all`) | Notes |
|---|:--:|:--:|---|
| Reviewer `name`, `email`, `profile_link`, `tag_1..3` | ✅ | ✅ | |
| Reviewee `name`, `email_or_identifier`, `profile_link`, `tag_1..3` | ✅ | ✅ | |
| Reviewer / Reviewee **`status`** (active vs inactive) | ✅ | ✅ | The roster CSVs carry a `Status` column (blank/absent → active); clone preserves status |
| Reviewee `results_acknowledged_at` | ❌ | ❌ | Participant-set; carried by no CSV and not cloned |
| Observer `email`, `display_name`, `tag_1` | ✅ | ❌ | **Clone copies no observers at all** |
| Observer **`status`** | ✅ | ❌ | `parse_observer_csv` reads back the `Status` the extract emits. Clone copies no observers |
| Observer **`cohort_rule`** (JSON) | ✅ | ❌ | Round-trips via the observers CSV's `CohortRule` column, re-validated through `CohortRuleSet` on import. Clone copies no observers |
| Relationship refs, `tag_1..3`, `status` | ✅ | ✅ | Relationships is the **only** roster path whose `status` round-trips |

### Assignments (`assignments`) — derived

| Setting | Any path | Notes |
|---|:--:|---|
| **Manual per-pair include overrides** (`Assignment.include`, set via the Assignments page's bulk Activate / Inactivate) | ❌ | **Gap — no path, and not reproducible.** Not exported: the coverage CSV emits column labels only, no row data, and there is no assignments importer at all. Clone doesn't copy assignments, and **regenerating from the rule set resets `include=True`**, discarding the override. Matches the `spec/rehydrate.md` caveat |
| `is_self_review`, `created_by_mode` | — | Engine-derived, not operator overrides |

### Permissions (`session_operators`)

| Setting | Settings CSV | Clone | Notes |
|---|:--:|:--:|---|
| `role` (owner / manager) | ❌ | ❌ | Only the acting operator's owner row is created; co-operator grants aren't carried by any config path |

## Not covered by any round-trip — the gap list

The settings an operator can set that survive **no** export/import path
(and, where relevant, aren't reproducible by regeneration):

1. **Instrument visibility policies under clone** (`instrument_view_policies`)
   — the Settings CSV carries them; `session_clone` does not, so a clone
   reverts to default visibility. Affects `/results` + `/collation`.
2. **Observers under clone** — `session_clone` copies **no observer rows at
   all**, so `email` / `display_name` / `tag_1` / `status` / `cohort_rule`
   are all lost on that path. The observers CSV carries every one of them.
3. **Assignment row status does not round-trip** (`Assignment.include`,
   the Assignments page's bulk Activate / Inactivate) — no export, no
   clone, and regenerating resets it to `True`. **This is the one place
   the author's contract is knowingly unmet**: *"individual rows can be
   turned inactive, and that's the extent of operator manual work and
   export import round trip."* Inactivation is the whole manual surface,
   and it is the part that does not survive a round trip.
   **Carrying it is future work** — deferred 2026-09-13, recorded here
   rather than left to be rediscovered as a bug.
4. **Session-operator role grants** — co-operators aren't carried by any
   config path; only the acting operator's own owner row is created.

Covered by **one** path but lost by another (footguns when you pick the
wrong tool):

5. **Scheduling anchors** stay clone-reset **by design** — a clone is a
   fresh cycle the operator re-schedules. The Settings CSV round-trips
   them, so use it, not clone, for backup / restore.
6. **`assignment_mode`** travels by neither mechanism. The Settings CSV
   drops it as machine-derived, and a clone starts NULL rather than
   copying it: a clone carries no `Assignment` rows, and NULL is how
   this codebase says *never Generated* — the state the delete-all path
   restores, and the one three validation rules skip on. There is no
   `library_origin_id` to carry — that column, its FK and its index were
   dropped with the rule-set library, so neither mechanism has anything
   to omit.

## Asymmetries and footguns

Places where a value *looks* carried but isn't faithfully restored:

- **`instruments[n].order`** — serialized + parsed, but apply ignores it;
  CSV row position is authoritative *by design* (`spec/csv_contracts.md`
  §3.3). Reordering the CSV reorders the instruments; the `order` cell is
  informational.
- **`display_fields.label`** — a dead column: not serialized, import
  tolerates + drops it, always restored empty (`spec/csv_contracts.md`
  §3.3).
- **`response_fields.validation`** — recomputed from inline bounds on
  import, not carried (fine as long as inline bounds are present).
- **Field labels outside the tag allowlist** — only the nine labelable tag
  columns take a label suffix on export (`field_label_csv._LABELABLE_COLUMNS`),
  so nothing is exported that import would reject.
- **Roster `Status`** — all four roster CSVs (reviewers, reviewees,
  observers, relationships) round-trip `status`; blank/absent → active.
- **`status` / `assignment_mode` session rows** — settings-CSV drops them
  on import even if hand-added to the file.

## Recommendations

Ordered by user-visible impact:

1. **Clone's observer and visibility-policy gaps** (gaps 1–2) — the CSV
   paths carry both, so a clone is the wrong tool for a session whose
   observers or Band 3 grid matter until clone copies them.
2. **Manual assignment overrides** (gap 3) — only worth an importer if
   field use shows operators rely on hand-toggling pairs; otherwise
   document that assignments always regenerate from rules.

## References

- Settings CSV: `app/services/session_config_io/` (`_serialize.py`,
  `_apply*.py`, `_rows.py`).
- Roster CSVs: `app/services/extracts/{reviewers,reviewees,observers,relationships}_extract.py`,
  `app/services/csv_imports.py`, `app/services/relationships.py`.
- Clone: `app/services/session_clone.py`.
- Assignments: `app/services/assignments/` (`_generate.py`,
  `_coverage.py`), `app/web/routes_operator/_assignments.py`.
- Full setting index: `spec/settings_inventory.md`.
- Consumer: `spec/rehydrate.md`.
