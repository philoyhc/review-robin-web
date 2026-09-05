# Email Template editor

**Current as of 2026-09-05 (`36e7b1e7`).** The per-session editor
for the three outbound reviewer emails — **Invitation**, **Reminder**
and **Responses received** — at `/operator/sessions/{id}/setup-invite`.
This file is the page's contract: what it renders, what each control
does, how overrides are stored and resolved, which merge tags exist,
who consumes the rendered result, and what is *not* yet wired behind
it.

Where the rest of the contract lives: `spec/settings_inventory.md` §3
inventories the stored keys; `spec/rrw_functional_spec.md` §11 states
the invitation-and-email subsystem in user terms; `spec/preview_hub.md`
owns the read-only previews that render these templates;
`spec/email_infra_options.md` and `guide/segment_14B_email_infrastructure.md`
own the dispatch leg. The design record is
`guide/archive/segment_11E_email_template_editor.md` (shipped
2026-05-05 → 05-07, PRs #461 → #465, #468, #532).

---

## 1. Placement and identity

- **Setup-row tab**, last in the row after Instruments:
  `[Reviewers][Reviewees][Relationships][Observers][Instruments][Email Template]`.
  Tab label and breadcrumb leaf are both **Email Template**; the page
  `<title>` is `Email Template — {session name}`.
- The URL slug `setup-invite` predates the Setup / Operations split
  and is kept for link stability; the settled page name is Email
  Template (`spec/operator_ui_concept.md`).
- Also reached from the Previews hub: each email preview card's footer
  reads "Rendered from **Email Template (Setup)** and Reviewers
  (Setup)", linking to `…/setup-invite?template=<kind>` for the kind
  being previewed.

---

## 2. Page contract

Chrome → status-pill strip → template selector → two-card body.

**Template selector.** A `tab-strip tab-strip-page` row of three
page-internal tabs reusing the chrome's `.nav-tab` styling
(`spec/ui_elements.md` §6 "Nav (page-internal)"): **Invitation** /
**Reminder** / **Responses received**. The active tab is a `<span
class="nav-tab active" aria-current="page">`; the others are anchors
carrying `?template=`. The query param makes each tab bookmarkable;
it defaults to `invitation`; any value outside the three kinds is a
**404** (`Unknown template`).

**Left card — composer** (`.card.email-composer`, `<h2>` "*Kind*
email"). One `<form id="setupinvite-form" method="post">` to
`…/setup-invite`, carrying a hidden `template` and four fields in
fixed order:

| Field | Control | Notes |
|---|---|---|
| `subject` | text input, `maxlength="255"` | client-side cap only |
| `body` | textarea | no length limit |
| `cc` | text input | raw comma-separated addresses, stored verbatim |
| `bcc` | text input | as `cc` |

Each field renders pre-filled with the **effective** value — the
operator's override if one is set, otherwise the in-code default — so
the operator always edits the text that would actually go out. When
(and only when) a field has an override, a **Reset *field* to default**
control renders beside it: a `.btn-reset` link-styled button that
submits a *separate* one-field form (`…/setup-invite/reset`, hidden
`template` + `field`) via the HTML5 `form=` attribute, so the reset
forms sit outside the composer form's HTML scope. Saving a field
**blank or whitespace-only** is the same as resetting it.

On the **Responses received** tab only, one extra control sits above
the fields: a checkbox **"Send this confirmation when a reviewer
submits?"** (`name="enabled"`), checked by default. There is no
separate reset for it — re-checking the box *is* the reset.

**Right card — Merge tags** (`.card.merge-tags`, `<h2>` "Merge
tags"): "Use these placeholders in the subject or body; they're
substituted at send time", then a `<code>$tag</code> — description`
list for the active kind (§6). It changes with the tab.

**Action row** (below the composer, left-aligned): **Cancel** — a
`.btn.secondary` anchor back to Session Home — and **Save** — a
`.btn.secondary` submit button bound to the composer via `form=`,
rendered **disabled** until any composer input or change event fires
(a five-line inline script). A successful save 303s back to the same
tab; the reload puts the form back in a clean state and Save returns
to disabled. There is no flash banner: the disabled → enabled →
disabled cycle is the whole "saved" signal.

---

## 3. Routes

All three routes gate on **`require_session_operator`** and nothing
else (§5).

| Route | Behaviour |
|---|---|
| `GET …/setup-invite?template=<kind>` | Render §2 for the kind. 404 on an unknown kind. |
| `POST …/setup-invite` (`template`, `subject`, `body`, `cc`, `bcc`, `enabled`) | For each of the kind's four fields present in the form body: non-blank → upsert the override; blank / whitespace → **remove** the override (fall through to default). On the `responses_received` kind only, `enabled` **absent** in the payload means *off* (browsers omit unchecked boxes); on any other kind the key is ignored. Emits `email_template.updated` iff something changed. 303 → same tab. |
| `POST …/setup-invite/reset` (`template`, `field`) | Remove that one override. 404 on an unknown kind *or* field. Emits `email_template.reset` iff the field had an override. 303 → same tab. |

---

## 4. Storage and resolution

One JSON column, `sessions.email_template_overrides`, `NULL` by
default. The recognised keys are pinned in
`app.services.email_templates`:

- **Twelve string keys**, `OVERRIDE_KEYS` — `{invitation, reminder,
  responses_received}` × `{subject, body, cc, bcc}`. `set_overrides`
  ignores anything else.
- **One Boolean**, `responses_received_enabled`
  (`RESPONSES_RECEIVED_ENABLED_KEY`), handled by its own getter /
  setter and deliberately *not* in `OVERRIDE_KEYS`.

**Resolution (`_resolve`).** `NULL` column, missing key, non-string
value and blank string are all the same thing: *use the default*. Only
a non-blank string is an override. `get_override` is the editor-side
variant that distinguishes "no override" (`None`) from "override set",
which is what decides whether a Reset control renders.

**Writes (`set_overrides`).** Key-by-key upsert / remove; returns a
`{key: [old, new]}` diff for the audit envelope. When the dict empties
the column is written back as `NULL`, so a session with no overrides
is indistinguishable from one that never had any.

**The toggle.** `responses_received_enabled(session)` reads `True`
when the key is absent *or* stored as a non-Boolean; only an explicit
`False` turns it off. `set_responses_received_enabled` stores `False`
explicitly and **removes the key** when set back to `True`, keeping
the JSON minimal; it returns `[old, new]` only when the effective
value changed, so a no-op save writes no audit row.

`TEMPLATE_FIELDS` is the single table mapping each (kind, field) pair
to its override key and default; the GET and POST handlers iterate it
rather than hard-coding field lists.

---

## 5. Lifecycle behaviour

**The editor is editable in every lifecycle state.** Neither route
carries `_require_editable` or `_require_not_archived`, and the
template renders no lock card. An operator can change the reminder
copy while a session is `ready`, `expired` or `archived`, and the
change takes effect on the next render. This is consistent with the
reminder being *sent* mid-session — the copy has to be adjustable
after activation — but it is unlike every other Setup-row page, all of
which lock at `ready` (`spec/lifecycle.md` §5). Whether `archived`
should also lock this page is an open question rather than a decided
contract; today it does not.

---

## 6. Rendering and merge tags

Rendering is `string.Template.safe_substitute` over the resolved
subject and body (`app/services/email_templates.py`). `$name` syntax,
not `{{ }}`: substitution is the whole job and the stdlib does it. An
**unrecognised tag is left in the text verbatim** — never blanked,
never an error — so a typo in an override cannot fail a send.

| Tag | Invitation | Reminder | Responses received | Resolves to |
|---|---|---|---|---|
| `$reviewer_name` | ✓ | ✓ | ✓ | roster name; `""` in previews with no reviewer |
| `$session_name` | ✓ | ✓ | ✓ | `session.name` |
| `$deadline` | ✓ | ✓ | ✓ | `format_datetime(session.deadline)` — `YYYY-MM-DD HH:MM` plus the zone token when shown; `""` when unset |
| `$help_contact` | ✓ | ✓ | ✓ | `session.help_contact` or `""` |
| `$invite_url` | ✓ | ✓ | — | the reviewer's `/me/invite/{token}` URL; a fixed placeholder in previews |
| `$submitted_at` | — | — | ✓ | latest `Response.submitted_at` for the reviewer in this session, `YYYY-MM-DD HH:MM TZ`; `"(not yet submitted)"` when none (previews only, in practice) |

**Defaults** (verbatim parameterisations of the pre-11E hard-coded
strings, so a `NULL` column renders byte-identically to the old
behaviour):

- Invitation — subject `Invitation to review: $session_name`; body
  `You've been invited to review for: $session_name.` / `Open this
  link (sign in with your work email): $invite_url`.
- Reminder — subject `Reminder: review for $session_name`; body
  `Reminder — your review for $session_name isn't complete yet.` /
  `Open this link (sign in with your work email): $invite_url`.
- Responses received — subject `Responses received: $session_name`;
  body `Hi $reviewer_name,` / `Thanks. Your responses for
  $session_name are recorded as of $submitted_at.` / `Questions?
  Contact $help_contact.` — and **when `help_contact` is unset and the
  body is not overridden, the "Questions?" line is dropped** rather
  than rendering `Contact .`. An overridden body that references
  `$help_contact` substitutes the empty string verbatim; operator
  intent wins.

**Cc / Bcc.** `cc_bcc_for(session, kind)` returns the raw operator
strings (or `None` when blank); the send path copies them onto the
outbox row's `cc_emails` / `bcc_emails` unparsed.

---

## 7. Who consumes the templates

| Consumer | Uses | State |
|---|---|---|
| `invitations.send_invitation` / `send_reminder` | `render_invitation` / `render_reminder` + `cc_bcc_for` → an `EmailOutbox` row (`kind`, to / cc / bcc, merged `subject` + `body`) | **Wired, but nothing is transmitted.** The row is written `queued` and flipped to `sent` in the same transaction with no transport call — the dev-mode preview state described in `spec/rrw_functional_spec.md` §11.6. Lighting the `EmailTransport` is Segment 14B. |
| Previews hub (`app/web/views/_previews.py`) | all three renderers, with a placeholder invite URL and the picked reviewer | Wired. |
| Reviewer submit (the responses-received confirmation) | `responses_received_enabled` + `render_responses_received` | **No consumer exists.** The toggle is stored, round-tripped, audited and previewed, but no submit-time code path reads it — the docstrings' "consumed by Segment 11C Part 2 PR H" describes intent, not a caller. Until 14B wires it, the checkbox is inert. |
| Settings CSV export / import, clone | the JSON wholesale (§8) | Wired. |

---

## 8. Round-trip and clone

**Settings CSV** (`spec/csv_contracts.md`; coverage row
`spec/roundtrip_coverage.md` §3 — "✅ All"). Field paths use a
**three-segment dotted grammar that differs from the JSON keys**:

```
email_overrides.<kind>.<slot>              string   — 12 rows, one per override key
email_overrides.responses_received.enabled boolean  — the toggle
```

e.g. `email_overrides.invitation.subject`, `email_overrides.reminder.bcc`.
Export writes every one of the twelve string rows, blank cell when no
override is set, and the `enabled` row as `TRUE` unless stored `False`.
Import (`session_config_io/_apply_email.py`) parses each row against
`^email_overrides\.(\w+)\.(\w+)$`; a path that does not match, or a
`<kind>_<slot>` that is not in `OVERRIDE_KEYS`, is a **parse error**
(phase 1, no writes). A blank cell means *key absent* — the same
fall-through the resolver applies — and the apply phase **replaces the
JSON column wholesale** from the parsed dict.

**Clone** copies the JSON verbatim onto the new session
(`session_clone`).

---

## 9. Validation

One rule touches this page, at **info** severity:
`email_template.no_help_contact` — "No help contact set —
reviewer-facing emails will fall back to a generic placeholder". It
sits in the Validate page's *setup* group; being info-level it never
blocks activation and does not trigger the warnings acknowledgement
(`spec/validate_page.md`). The Validate page's setup-coverage grid
shows the page's state as "Custom overrides" or "Default (no
overrides)".

---

## 10. Audit

| Event | When | Envelope |
|---|---|---|
| `email_template.updated` | a Save that changed at least one key (including the toggle) | `changes` = `{key: [old, new]}`, `context.template` = kind |
| `email_template.reset` | a Reset that removed an override | `changes`, `context.template`, `context.field` |

A Save or Reset that changes nothing writes **no** event. Both types
are registered in `EVENT_SCHEMAS` (`spec/architecture.md`).

---

## 11. Tests

- `tests/integration/test_email_template_editor.py` (17) — tab
  rendering and defaults, 404s on unknown kind / field, save persists
  + audits, no-change saves do not audit, blank clears an override,
  reset removes + audits, Reset control renders only for overridden
  fields, the third tab and its checkbox (absent on other tabs,
  explicit-`False` on uncheck, key removed on re-check).
- `tests/unit/test_email_templates.py` (23) — resolver fall-through
  (`NULL` / blank / subject-only), all five tags substitute, unknown
  tag passes through, unset help-contact and deadline render `""`,
  the responses-received default variants and `$invite_url` drop, and
  every branch of the `enabled` getter / setter.

---

## 12. Drift noted at writing (2026-09-05)

Corrected in the same change as this file:

- `spec/lifecycle.md` §5 listed Email Template among the Setup pages
  that lock at `ready`. It does not lock (§5 here).
- `spec/rrw_functional_spec.md` §11.2 said the reminder carries no
  `$invite_url` (it does — the default body is the link), that
  unmatched tags "render as empty" (they pass through verbatim), and
  that a 2000-character body limit applies (nothing enforces one;
  the subject has a 255-character client-side cap). §11.6 repeated the
  limit.
- `spec/csv_contracts.md`'s Settings-CSV example used
  `email_template_overrides.invitation_subject`, a path the importer
  rejects; the grammar is `email_overrides.invitation.subject` (§8).
- `spec/settings_inventory.md` §3 described "a side-by-side composer +
  preview region"; the right card is the merge-tag reference and
  previews live on the Previews hub.

Left for a code change (not spec):

- The right-card description of `$deadline` reads "(YYYY-MM-DD)";
  the renderer has produced `YYYY-MM-DD HH:MM` with a zone token since
  Segment 18B.
- `ReviewSession.email_template_overrides`'s column comment and the
  `responses_received_enabled` docstring cite a submit-time consumer
  that does not exist (§7).

---

## 13. Cross-references

- `spec/settings_inventory.md` §3 — the key inventory; §10 the
  `?template=` UI-state param.
- `spec/rrw_functional_spec.md` §11 — the subsystem in user terms,
  including what is and is not wired.
- `spec/preview_hub.md` — the read-only renders of all three emails.
- `spec/operator_ui_concept.md` "Email Template" — the page in the
  Setup-row taxonomy; `spec/operator_button_audit.md` §10 — its
  buttons (#63–#67).
- `spec/csv_contracts.md`, `spec/roundtrip_coverage.md` §3 — the
  Settings-CSV carrier.
- `spec/email_infra_options.md`, `guide/segment_14B_email_infrastructure.md`
  — the dispatch leg this editor feeds.
- `guide/archive/segment_11E_email_template_editor.md` — design
  record and PR ladder.
