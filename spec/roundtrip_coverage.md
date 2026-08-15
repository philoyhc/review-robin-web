# Session round-trip coverage

**What survives when a session's configuration is exported and
re-imported — and what silently doesn't.** This is the authoritative
coverage matrix for the three round-trip mechanisms. It exists because
"export the settings and re-import them" is load-bearing for backup /
restore, porting a session between environments, cloning, and the proposed
[rehydrate](../docs/rehydrate.md) feature — and several hand-set settings
do **not** come back.

Companion to `spec/settings_inventory.md` (the full index of every
persisted setting). Where that doc's §10 coverage table and this doc
disagree, **this doc is authoritative** — it was built from a
field-by-field sweep of the serialize/apply/import/clone code and lists
several config surfaces the inventory's matrix omits (view policies,
observer cohort rules, `band1_touched_links`, reviewer `profile_link`).

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

`rehydrate` (proposed) composes the settings CSV + roster CSVs + a new
responses importer; its coverage is the union of the first two columns
below plus responses. See `docs/rehydrate.md`.

**Legend:** ✅ round-trips · ⚠️ partial / asymmetric (see notes) · ❌ lost ·
— not applicable.

## Coverage matrix — configuration

### Session metadata (`sessions`)

| Setting | Settings CSV | Clone | Notes |
|---|:--:|:--:|---|
| `name`, `code`, `description`, `deadline`, `help_contact` | ✅ | ✅ | Settings-CSV applies these only when the target is empty (fallback semantics); clone rewrites name→"Copy of …", derives a unique code, resets deadline |
| `display_timezone`, `self_reviews_active` | ✅ | ✅ | Force-applied |
| `email_template_overrides` (12 keys + `responses_received_enabled`) | ✅ | ✅ | Whole-JSON replace |
| `scheduled_activate_at`, `responses_release_at`, `responses_release_until`, `invite_offsets`, `reminder_offsets`, `archive_offset` | ✅ | ❌ | **Clone drops all scheduling anchors/offsets** (omitted from its constructor) |
| `retention_exception`, `retention_overrides` | ✅ | ❌ | Same — clone drops retention config |
| **`relationships_enabled`, `observers_enabled`** | ❌ | ❌ | **Gap — neither path.** Not serialized; not in clone's constructor. A cloned "all"-mode session copies relationship/observer *rows* but leaves the toggles `False`. Being closed by the [rehydrate prerequisite](../docs/rehydrate.md#prerequisite-extend-the-settings-round-trip) |
| `assignment_mode` | ❌ | ✅ | Settings-CSV defensively drops it (machine-derived); clone copies it |
| `status`, `activated_at`, `created_by_user_id` | — | — | Runtime / identity — intentionally reset |

### Instruments (`instruments`)

| Setting | Settings CSV | Clone | Notes |
|---|:--:|:--:|---|
| `name`, `short_label`, `description`, `responses_visible_when_closed`, `sort_display_fields`, `group_kind`, `rule_set_id` (by name), `column_widths`, `starts_new_page`, `band2_state` | ✅ | ✅ | Full config round-trip both paths |
| `accepting_responses` | ✅ | ❌ | Settings-CSV restores the runtime open/closed flag; clone resets it (fresh draft) |
| `order` | ⚠️ | ✅ | Settings-CSV serializes + parses it but **apply ignores it** — 1-based CSV position wins. Value round-trips only because export order matches position |
| **`band1_touched_links`** | ❌ | ✅ | **Settings-CSV gap.** The Band 1 "set"-pill state isn't serialized; clone copies it |
| `deadline_closed_at`, `cached_group_pair_count/_stamp` | — | — | Runtime / cache |

### Instrument display fields (`instrument_display_fields`)

| Setting | Settings CSV | Clone | Notes |
|---|:--:|:--:|---|
| `source_type`, `source_field`, `visible` | ✅ | ✅ | |
| `label` | ❌ | ⚠️ | Retired from serialize (15A); import tolerates + drops a legacy row → always restored empty. Clone copies the (dead) column |

### Instrument response fields (`instrument_response_fields`)

| Setting | Settings CSV | Clone | Notes |
|---|:--:|:--:|---|
| `field_key`, `label`, `response_type`, `required`, `help_text`, `help_text_visible`, `data_type`, `min`, `max`, `step`, `list_csv`, `visible` | ✅ | ✅ | Inline bounds carried on the response-field row |
| `validation` (JSON) | ⚠️ | ✅ | Settings-CSV **recomputes** it from the inline bounds on import (derived, not carried); clone copies it verbatim |

### Instrument visibility policies (`instrument_view_policies`)

| Setting | Settings CSV | Clone | Notes |
|---|:--:|:--:|---|
| `audience`, `while_ongoing_granularity/_identification`, `after_release_granularity/_identification`, `observer_tag` | ❌ | ❌ | **Gap — neither path** serializes or copies the Band 3 visibility grid. Reviewee `/results` + observer `/collation` visibility silently reverts to defaults on any round-trip. Being closed by the [rehydrate prerequisite](../docs/rehydrate.md#prerequisite-extend-the-settings-round-trip) |

### Rule sets (`session_rule_sets`)

| Setting | Settings CSV | Clone | Notes |
|---|:--:|:--:|---|
| `name`, `description`, `combinator`, `exclude_self_reviews`, `seed`, `rules_json` | ✅ | ✅ | `exclude_self_reviews` is vestigial (engine hardcodes `False`) |
| `library_origin_id` | ❌ | ✅ | Settings-CSV doesn't carry it (left NULL); clone copies it |

### Field labels (`session_field_labels`)

| Setting | Settings CSV | Clone | Notes |
|---|:--:|:--:|---|
| `reviewer/reviewee.tag_1..3`, `pair_context.1..3` | ✅ | ✅ | The tag-label allowlist |
| labels outside that allowlist | ⚠️ | ✅ | Export emits any label row, but **import rejects** non-allowlist source types (`_ParseError`) — export-without-import. Clone copies all |

### Data shapes (`data_shapes`)

| Setting | Settings CSV | Clone | Notes |
|---|:--:|:--:|---|
| `name`, `axis`, instrument/response-field refs (portable), `column_chip_slots`, `self_review_handling`, `include_empty_rows` | ✅ | ❌ | **Clone drops data shapes entirely** (`DataShape` isn't in its copy set); settings-CSV round-trips them |

### Session tags (`session_tags`)

| Setting | Settings CSV | Clone | Notes |
|---|:--:|:--:|---|
| `tag` | ❌ | ✅ | **Settings-CSV gap** — tags aren't serialized; clone copies them |

### Populations — reviewers / reviewees / observers / relationships

| Setting | Roster CSV | Clone (`all`) | Notes |
|---|:--:|:--:|---|
| Reviewer `name`, `email`, `profile_link`, `tag_1..3` | ✅ | ✅ | |
| Reviewee `name`, `email_or_identifier`, `profile_link`, `tag_1..3` | ✅ | ✅ | |
| Reviewer / Reviewee **`status`** (active vs inactive) | ❌ | ✅ | **Roster CSVs have no `Status` column** — every re-imported reviewer/reviewee becomes `active`. Clone preserves status |
| Reviewee `results_acknowledged_at` | ❌ | ❌ | Participant-set; carried by no CSV and not cloned |
| Observer `email`, `display_name`, `tag_1` | ✅ | ❌ | **Clone copies no observers at all** |
| Observer **`status`** | ⚠️ | ❌ | Export **emits** `Status` but `parse_observer_csv` ignores it → resets to active |
| Observer **`cohort_rule`** (JSON) | ❌ | ❌ | **Gap — neither path.** The observers CSV header is only Email/Name/Tag1/Status; the cohort rule is lost |
| Relationship refs, `tag_1..3`, `status` | ✅ | ✅ | Relationships is the **only** roster path whose `status` round-trips |

### Assignments (`assignments`) — derived

| Setting | Any path | Notes |
|---|:--:|---|
| **Manual per-pair include overrides** (`Assignment.include`, set via the Assignments page's bulk Activate / Inactivate) | ❌ | **Gap — no path, and not reproducible.** Not exported (the coverage CSV emits column labels only, no row data, and has no importer; the manual-assignment CSV was retired 2026-05-11). Clone doesn't copy assignments, and **regenerating from the rule set resets `include=True`**, discarding the override. Confirms the `docs/rehydrate.md` caveat |
| `is_self_review`, `created_by_mode` | — | Engine-derived, not operator overrides |

### Permissions (`session_operators`)

| Setting | Settings CSV | Clone | Notes |
|---|:--:|:--:|---|
| `role` (owner / manager) | ❌ | ❌ | Only the acting operator's owner row is created; co-operator grants aren't carried by any config path |

## Not covered by any round-trip — the gap list

The settings an operator can set that survive **no** export/import path
(and, where relevant, aren't reproducible by regeneration):

1. **Instrument visibility policies** (`instrument_view_policies`) — affects
   `/results` + `/collation`. *Fix underway:* the
   [rehydrate prerequisite](../docs/rehydrate.md#prerequisite-extend-the-settings-round-trip).
2. **`relationships_enabled` / `observers_enabled` toggles** — *same fix.*
3. **Observer cohort rules** (`Observer.cohort_rule`) — the observers CSV
   drops them; clone copies no observers.
4. **Manual per-pair assignment include overrides** — no export, no clone,
   not regenerated.
5. **Observer status** — export-only column the importer ignores.
6. **Session-operator role grants** — co-operators aren't carried.

Covered by **one** path but lost by another (footguns when you pick the
wrong tool):

7. **Scheduling anchors + retention overrides** — settings-CSV ✅, clone ❌.
8. **Data shapes** — settings-CSV ✅, clone ❌.
9. **`band1_touched_links`, session tags, `assignment_mode`,
   `library_origin_id`** — clone ✅, settings-CSV ❌.
10. **Reviewer / reviewee `status`** — clone ✅, roster CSV ❌.

## Asymmetries and footguns

Places where a value *looks* carried but isn't faithfully restored:

- **`instruments[n].order`** — serialized + parsed, but apply ignores it;
  CSV row position is authoritative. Reordering the CSV reorders the
  instruments; the `order` cell is decorative.
- **`display_fields.label`** — serialized no longer; always restored empty.
- **`response_fields.validation`** — recomputed from inline bounds on
  import, not carried (fine as long as inline bounds are present).
- **Field labels outside the tag allowlist** — exported but rejected on
  import.
- **Roster `Status`** — reviewers/reviewees lose it (no column); observers
  have the column but the importer ignores it; only relationships preserve
  it.
- **`status` / `assignment_mode` session rows** — settings-CSV drops them
  on import even if hand-added to the file.

## Recommendations

Ordered by user-visible impact:

1. **Close the visibility-policy + feature-toggle gap in the settings
   round-trip** (gaps 1–2) — already scoped as the
   [rehydrate prerequisite](../docs/rehydrate.md#prerequisite-extend-the-settings-round-trip);
   it also fixes plain export/import and backup/restore, not just rehydrate.
2. **Carry observer `cohort_rule`** (gap 3) — add a column to the observers
   CSV + importer, or serialize observers through `session_config_io`.
3. **Decide the roster-`status` policy** (gap/footgun 10, asymmetry) — add a
   `Status` column to the reviewer/reviewee CSVs (and read it in the
   observer importer), or document that re-import reactivates everyone.
4. **Reconcile clone with settings-CSV** (footguns 7–9) — clone silently
   drops scheduling/retention/data-shapes and settings-CSV silently drops
   tags/`band1_touched_links`. Converging them (or documenting the split)
   removes a class of "why did my duplicate lose X?" surprises.
5. **Manual assignment overrides** (gap 4) — only worth an importer if
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
- Proposed consumer: `docs/rehydrate.md`.
