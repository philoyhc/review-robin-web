# Response visibility policy

Per-instrument, per-audience grants controlling **who** can see this instrument's responses, **in what form**, and **during which window**. The schema lives on `instrument_view_policies`; the resolver consumes one row per (instrument, audience) pair at view time (no materialisation onto `assignments`).

This spec is the operator-facing functional contract. The cross-cutting participant-model design lives in `guide/participant_model_upgrade.md`; the per-page operator UI sits in `spec/instruments.md` (Band 3 of the instrument card).

---

## 1. Audiences

Three audiences are configurable per instrument. The **operator** is not a configurable audience — the operator always sees everything, identified and per-line. That is the baseline, not a policy.

| Audience | Stored as |
|---|---|
| Peer reviewer (reviewers viewing their own work + peers') | `audience = "peer_reviewer"` |
| Reviewee | `audience = "reviewee"` |
| Observer | `audience = "observer"` |

### 1.1 Audience scope

The audience name implies a **scope rule** the resolver applies in addition to the policy lookup. Scope is intrinsic to the audience identity; the schema does not store it.

| Audience | Scope of "responses they may see" |
|---|---|
| Peer reviewer | The reviewer's **own** submitted responses on this instrument — **never** responses keyed in by another reviewer. The schema name `peer_reviewer` is historical; the policy governs a reviewer viewing their own work post-submit / across pages of the review. |
| Reviewee | Responses **about this reviewee** — or about a group this reviewee is a member of, for group-scoped instruments. Never about another reviewee or another group. |
| Observer | All responses by all reviewers about all reviewees on the session, on instruments this observer is granted (subject to `observer_tag`). Observers are the only audience whose grant is cross-cohort. |

---

## 2. Form axes (what they see)

Two orthogonal columns on `instrument_view_policies` encode the form:

| Column | Values |
|---|---|
| `granularity` | `row` (each reviewer's response shown as its own line) / `aggregated` (summarised across reviewers) |
| `identification` | `identified` (reviewer name shown) / `deidentified` (reviewer name hidden) |

Of the four combinations, three are coherent for participant audiences and one is reserved as incoherent:

| Operator-facing mode | granularity | identification | Notes |
|---|---|---|---|
| **Raw** | `row` | `identified` | Each reviewer's response, attributed. |
| **Anonymized** | `row` | `deidentified` | Each reviewer's response, attribution stripped. |
| **Summarized** | `aggregated` | `deidentified` | Per-data-type aggregate stats; no individual rows. |
| *(reserved)* | `aggregated` | `identified` | Incoherent — "averaging Alice" isn't a thing. The service rejects this combination. |

### 2.1 Per-data-type "Summarized" semantics

"Summarized" needs a per-data-type interpretation:

| Data type | Summarized rendering |
|---|---|
| Integer / Decimal | Mean, median, distribution, count. |
| List (enum) | Per-option count + percentage. |
| String (free-text) | Falls back to the **Anonymized** render — show each de-identified row as a list. Free-text can't be averaged; hiding the content behind a count would erase qualitative feedback. Operators who want a count-only view explicitly pick Anonymized. |

This fallback is the resolver's responsibility; the policy row carries `aggregated` regardless of data type. The Reviewee / Observer surfaces present the same UI either way.

### 2.2 Peer reviewer special case

The peer-reviewer audience's form is **fixed at Raw** (`granularity = row`, `identification = identified`). The operator-facing UI exposes only the **When** chip for the Peer reviewer row; the **What** cell renders as a static "Raw responses" pill.

Rationale: the scope rule (§1.1) restricts a reviewer to their own submitted responses on this instrument. Aggregating one row to itself or anonymising one's own work are both meaningless, so the schema's other form values aren't useful here. The schema columns accept any value; the editor + service simply don't surface them.

---

## 3. Window axis (when they see)

One nullable column on `instrument_view_policies` encodes the window:

| `visible_when` | Window |
|---|---|
| `while_ongoing` | `[sessions.activated_at, sessions.deadline)`. The session-lifetime window. |
| `after_release` | `[sessions.responses_release_at, sessions.responses_release_until)`. The Release-responses window authored on Session Edit Details / Create New Session (W14 + S12). Operator-explicit Release-now / Stop-release buttons (forthcoming) write the same columns. |
| `throughout` | Union of `while_ongoing` and `after_release` — viewable in either window. Useful when the operator wants results visible during the review *and* after release without authoring two grants. |
| `always` | **Reserved.** Today this value is only meaningful for the operator (who is not a row in this table). The column accepts it for forward-compatibility. |

### 3.1 Per-audience valid `visible_when` values

| Audience | UI cycle | Stored values |
|---|---|---|
| Peer reviewer | `while_ongoing` ⇄ `throughout` (2-step toggle). | `while_ongoing` is the default. `after_release` and `always` are not exposed: a reviewer reading their own work after release is well-served by `throughout`. |
| Reviewee | `while_ongoing` → `after_release` → `throughout` (3-step cycle). | All three are valid. Default: `after_release`. |
| Observer | Same as Reviewee. | All three are valid. Default: `after_release`. |

### 3.2 Anchor-null inertness

The `after_release` and `throughout` windows depend on `responses_release_at`. When the anchor is `NULL`, the §8.2.2 anchor-null rule applies — the after-release half is treated as "no scheduled fire". Per the view-time predicate:

> *Release window is open* ⇔ `responses_release_at IS NOT NULL` AND `now() ≥ responses_release_at` AND (`responses_release_until IS NULL` OR `now() < responses_release_until`).

A policy with `visible_when = "after_release"` and no anchor is **inert** — the resolver returns "not viewable" until the operator sets the anchor. Saving the policy without an anchor is allowed and harmless.

### 3.3 Archive overrides

When `sessions.status = "archived"`, the resolver returns `enabled = FALSE` for every non-operator audience regardless of `visible_when` or window state. No schema change — pure view-time gate. Mirrors how archive retires a session out of reviewer reach today.

---

## 4. Storage shape

```
instrument_view_policies
  id              PK
  instrument_id   FK -> instruments.id    (indexed, NOT NULL)
  audience        String(16)  NOT NULL    'reviewee' | 'peer_reviewer' | 'observer'
  enabled         Boolean     NOT NULL    default FALSE
  granularity     String(16)  NOT NULL    'row' | 'aggregated'
  identification  String(16)  NOT NULL    'identified' | 'deidentified'
  visible_when    String(16)    NULL      'while_ongoing' | 'after_release' |
                                          'throughout' | 'always' (reserved)
  observer_tag    String        NULL      (observer audience only — restrict the
                                           grant to observers carrying this tag;
                                           NULL = all observers on the session)
  created_at      DateTime(tz) NOT NULL
  updated_at      DateTime(tz) NOT NULL
  UNIQUE (instrument_id, audience)
```

- One row per (instrument, audience). Upserts cover both the create and update cases.
- Rows for a disabled audience are still written so the operator's last chosen form / window survive a toggle-off / toggle-on cycle.
- `observer_tag` only carries meaning when `audience = "observer"`; the service layer enforces NULL otherwise (no DB CHECK constraint).

### 4.1 Default state

Default on instrument create: no rows. Resolver treats a missing row as `enabled = FALSE` — instrument is invisible to that audience. The operator opts each audience in deliberately on the Band 3 editor.

---

## 5. Audit

Every write emits `instrument.view_policy_set` per the canonical envelope (changes + refs). One event per (instrument, audience) row touched in a single save:

- `payload = audit.changes({field: [old, new], ...})` — every field that actually changed.
- `refs = {"instrument_id": …, "policy_id": …}`.
- `session = …`.

A no-op save (operator clicked Save with no changes) emits nothing.

---

## 6. Where this is wired

| Slice | What | Status |
|---|---|---|
| S2 (PR #1678) | `instrument_view_policies` table | ✓ shipped |
| S12 (PR #1724) | `visible_when` column | ✓ shipped |
| W15 — Band 3 editor (persistence half) | `app/services/visibility_policies.py` (mode encoder / decoder + per-audience vocabulary + `upsert_policy` + `upsert_many`); `POST /operator/sessions/{id}/instruments/{instrument_id}/view-policy`; Band 3 template rewired with Save button + persisted prefill; `build_instruments_context` carries `band3_visibility_by_instrument`. | ✓ shipped |
| W7 — Resolver | Reads policies + applies the scope rules; consumed by W16 / W17 surfaces. | ✘ pending |
| W16 — Reviewee `/results` body | Renders the policy-permitted content. | ✘ pending |
| W17 — Observer `/collation` body | Renders the policy-permitted content. | ✘ pending |

---

## Cross-references

- `guide/participant_model_upgrade.md` §3.3 — design rationale + the audience-scope table.
- `guide/participant_model_prep.md` — implementation-phase audit (S2 / S12 / W7 / W15 / W16 / W17).
- `spec/participant_model.md` — cross-cutting participant-model contract; release-window columns.
- `spec/instruments.md` — the per-instrument card layout; Band 3 visibility editor sits here.
- `spec/lifecycle.md` — schedule columns (`responses_release_at` / `responses_release_until`), §8.2.2 anchor-null, §8.2.7 save-time ordering.
