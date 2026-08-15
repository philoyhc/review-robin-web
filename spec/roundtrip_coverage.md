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

`rehydrate` (shipped, Segment 18P Group 2) composes the settings CSV +
roster CSVs + the responses importer; its coverage is the union of the
first two columns below plus responses. See `docs/rehydrate.md`.

**Legend:** ✅ round-trips · ⚠️ partial / asymmetric (see notes) · ❌ lost ·
— not applicable.

## Coverage matrix — configuration

### Session metadata (`sessions`)

| Setting | Settings CSV | Clone | Notes |
|---|:--:|:--:|---|
| `name`, `code`, `description`, `deadline`, `help_contact` | ✅ | ✅ | Settings-CSV applies these only when the target is empty (fallback semantics); clone rewrites name→"Copy of …", derives a unique code, resets deadline |
| `display_timezone`, `self_reviews_active` | ✅ | ✅ | Force-applied |
| `email_template_overrides` (12 keys + `responses_received_enabled`) | ✅ | ✅ | Whole-JSON replace |
| `scheduled_activate_at`, `responses_release_at`, `responses_release_until`, `invite_offsets`, `reminder_offsets`, `archive_offset` | ✅ | ❌ *(by design)* | Clone resets the schedule **on purpose** (18P PR D1 documents it) — a clone is a fresh cycle the operator re-schedules, like the deadline. Settings-CSV still round-trips these for backup / restore |
| `retention_exception`, `retention_overrides` | ✅ | ✅ | Clone copies retention config as of **18P PR D1** |
| **`relationships_enabled`, `observers_enabled`** | ✅ | ✅ | Settings-CSV carries them as of **18P PR A1**; clone copies them as of **18P PR D1** (so a cloned "all"-mode session's copied observer / relationship rows aren't hidden by a `False` toggle) |
| `assignment_mode` | ❌ | ✅ | Settings-CSV defensively drops it (machine-derived); clone copies it |
| `status`, `activated_at`, `created_by_user_id` | — | — | Runtime / identity — intentionally reset |

### Instruments (`instruments`)

| Setting | Settings CSV | Clone | Notes |
|---|:--:|:--:|---|
| `name`, `short_label`, `description`, `responses_visible_when_closed`, `sort_display_fields`, `group_kind`, `rule_set_id` (by name), `column_widths`, `starts_new_page`, `band2_state` | ✅ | ✅ | Full config round-trip both paths |
| `accepting_responses` | ✅ | ❌ | Settings-CSV restores the runtime open/closed flag; clone resets it (fresh draft) |
| `order` | ⚠️ | ✅ | Settings-CSV serializes + parses it but **apply ignores it** — 1-based CSV position wins. Value round-trips only because export order matches position |
| **`band1_touched_links`** | ✅ | ✅ | Settings-CSV carries it as of **18P PR D2** (`instruments[n].band1_touched_links`); clone already copied it |
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
| `audience`, `while_ongoing_granularity/_identification`, `after_release_granularity/_identification`, `observer_tag` | ✅ | ❌ | Settings-CSV carries the Band 3 grid as of **18P PR A2** (`instruments[n].view_policies[<audience>].*`, recreated in the instrument rebuild). Clone still doesn't copy it — a clone reverts to default visibility |

### Rule sets (`session_rule_sets`)

| Setting | Settings CSV | Clone | Notes |
|---|:--:|:--:|---|
| `name`, `description`, `combinator`, `exclude_self_reviews`, `seed`, `rules_json` | ✅ | ✅ | `exclude_self_reviews` is vestigial (engine hardcodes `False`) |
| `library_origin_id` | ❌ | ✅ | Settings-CSV doesn't carry it (left NULL); clone copies it |

### Field labels (`session_field_labels`)

| Setting | Settings CSV | Clone | Notes |
|---|:--:|:--:|---|
| `reviewer/reviewee.tag_1..3`, `pair_context.1..3` | ✅ | ✅ | The tag-label allowlist |
| labels outside that allowlist | ✅ | ✅ | As of **18P PR E** export **filters to the allowlist**, so it never emits a row import would reject (was export-without-import). Clone copies all |

### Data shapes (`data_shapes`)

| Setting | Settings CSV | Clone | Notes |
|---|:--:|:--:|---|
| `name`, `axis`, instrument/response-field refs (portable), `column_chip_slots`, `self_review_handling`, `include_empty_rows` | ✅ | ✅ | Clone copies data shapes as of **18P PR D1** (scope chips re-pointed at the clone's instrument + response field); settings-CSV round-trips them via portable refs |

### Session tags (`session_tags`)

| Setting | Settings CSV | Clone | Notes |
|---|:--:|:--:|---|
| `tag` | ✅ | ✅ | Settings-CSV carries tags as of **18P PR D2** (`session_tags[i].tag`, wipe-and-replace); clone already copied them |

### Populations — reviewers / reviewees / observers / relationships

| Setting | Roster CSV | Clone (`all`) | Notes |
|---|:--:|:--:|---|
| Reviewer `name`, `email`, `profile_link`, `tag_1..3` | ✅ | ✅ | |
| Reviewee `name`, `email_or_identifier`, `profile_link`, `tag_1..3` | ✅ | ✅ | |
| Reviewer / Reviewee **`status`** (active vs inactive) | ✅ | ✅ | Roster CSVs gained a `Status` column in **18P PR C** (blank/absent → active); clone already preserved status |
| Reviewee `results_acknowledged_at` | ❌ | ❌ | Participant-set; carried by no CSV and not cloned |
| Observer `email`, `display_name`, `tag_1` | ✅ | ❌ | **Clone copies no observers at all** |
| Observer **`status`** | ✅ | ❌ | `parse_observer_csv` reads the `Status` it exports as of **18P PR C** (was export-only). Clone still copies no observers |
| Observer **`cohort_rule`** (JSON) | ✅ | ❌ | Round-trips via the observers CSV's `CohortRule` column as of **18P PR B** (re-validated through `CohortRuleSet` on import). Clone still copies no observers |
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
   `/results` + `/collation`. Settings-CSV **done (18P PR A2)**; clone still
   omits them (a clone reverts to default visibility).
2. **`relationships_enabled` / `observers_enabled` toggles** — settings-CSV
   **done (18P PR A1)**; clone still omits them (Part D1).
3. **Observer cohort rules** (`Observer.cohort_rule`) — roster-CSV **done
   (18P PR B)** (the `CohortRule` column); clone still copies no observers.
4. **Manual per-pair assignment include overrides** — no export, no clone,
   not regenerated.
5. **Observer status** — **done (18P PR C)**; `parse_observer_csv` now reads
   the `Status` it exported.
6. **Session-operator role grants** — co-operators aren't carried.

Covered by **one** path but lost by another (footguns when you pick the
wrong tool):

7. **Retention overrides** — **done (18P PR D1)**: clone now copies them.
   **Scheduling anchors** stay clone-reset **by design** (a clone is a fresh
   cycle); settings-CSV still round-trips them.
8. **Data shapes** — **done (18P PR D1)**: clone now copies them.
9. **`band1_touched_links`, session tags** — **done (18P PR D2)**: both now
   round-trip through the settings CSV. `assignment_mode` (machine-derived)
   and `library_origin_id` (niche) remain clone-only by design.
10. **Reviewer / reviewee `status`** — **done (18P PR C)**: both paths now
    carry it (roster CSV gained a `Status` column; clone already did).

## Asymmetries and footguns

Places where a value *looks* carried but isn't faithfully restored:

- **`instruments[n].order`** — serialized + parsed, but apply ignores it;
  CSV row position is authoritative *by design* (documented in
  `spec/csv_contracts.md`, 18P PR E). Reordering the CSV reorders the
  instruments; the `order` cell is informational.
- **`display_fields.label`** — a dead column: not serialized, import
  tolerates + drops it, always restored empty (documented, 18P PR E).
- **`response_fields.validation`** — recomputed from inline bounds on
  import, not carried (fine as long as inline bounds are present).
- ~~**Field labels outside the tag allowlist**~~ — fixed in **18P PR E**:
  export now filters to the allowlist, so nothing is exported that import
  would reject.
- **Roster `Status`** — as of **18P PR C** all four roster CSVs (reviewers,
  reviewees, observers, relationships) round-trip `status`; blank/absent →
  active.
- **`status` / `assignment_mode` session rows** — settings-CSV drops them
  on import even if hand-added to the file.

## Recommendations

Ordered by user-visible impact:

1. ~~**Close the visibility-policy + feature-toggle gap** (gaps 1–2)~~ —
   **done (18P A1 + A2)**; both round-trip through `settings.csv`.
2. ~~**Carry observer `cohort_rule`** (gap 3)~~ — **done (18P PR B)** (the
   observers-CSV `CohortRule` column).
3. ~~**Decide the roster-`status` policy** (gap/footgun 10)~~ — **done (18P
   PR C)**: `Status` preserved on all four roster CSVs (blank/absent →
   active).
4. ~~**Reconcile clone with settings-CSV** (footguns 7–9)~~ — **done (18P
   D1 + D2)**: D1 gave clone retention config + toggles + data shapes (and
   documented the deliberate schedule reset); D2 gave the settings CSV
   session tags + `band1_touched_links`. Only the by-design splits remain
   (clone resets the schedule; `assignment_mode` / `library_origin_id` stay
   clone-only).
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
- Consumer: `docs/rehydrate.md` (shipped, Segment 18P Group 2).
