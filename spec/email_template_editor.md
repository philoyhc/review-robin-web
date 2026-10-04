# Email Template editor

The per-session editor
for the three outbound reviewer emails — **Invitation**, **Reminder**
and **Responses received** — at `/operator/sessions/{id}/setup-invite`.
This file is the page's contract: what it renders, what each control
does, how overrides are stored and resolved, which merge tags exist,
who consumes the rendered result, and what is *not* yet wired behind
it.

Where the rest of the contract lives: `spec/settings_inventory.md` §3
inventories the stored keys; `spec/rrw_functional_spec.md` §11 states
the invitation-and-email subsystem in user terms; `spec/operations_pages.md`
owns the Invitations drill-in previews that render these templates;
`spec/email_infra_options.md` and `guide/segment_14B_email_infrastructure.md`
own the dispatch leg. The design record is
`guide/archive/segment_11E_email_template_editor.md`.

---

## 1. Placement and identity

- **Setup-row tab**, last in the row after Instruments:
  `[Reviewers][Reviewees][Relationships][Observers][Instruments][Email Template]`,
  where Relationships and Observers render only when
  `relationships_enabled` / `observers_enabled` is on.
  Tab label and breadcrumb leaf are both **Email Template**; the page
  `<title>` is `Email Template — {session name}`.
- **The URL slug is `setup-invite`, not the page name.** It does not
  match the settled page name (Email Template,
  `spec/operator_ui_concept.md`) and is kept that way for link
  stability — renaming it breaks every bookmark and every
  `?template=` link in circulation.
- Also reached from the Invitations per-reviewer drill-in: each email preview card's footer
  reads "Rendered from **Email Template (Setup)** and Reviewers
  (Setup)", linking to `…/setup-invite?template=<kind>` for the kind
  being previewed.

---

## 2. Page contract

Chrome → status-pill strip → template selector → `.card-columns`:
composer in the left column, **page guidance** then merge tags in the
right.

**Columns, not a three-slot `.page-grid`.** A grid aligns the right
column to the left column's rows, so a merge-tag card under the
guidance card starts at row 2 — level with the composer's midpoint —
leaving a gap beneath the guidance and bottom-aligning the merge tags
against the composer. Column stacks have no rows to align to.

**Page guidance.** The shared half-width
`<details class="card page-guidance">` card specced in
`spec/setup_pages.md` "Shared body shape", stacked directly above the
merge-tag reference it introduces — the guidance reads as one of the
page's cards rather than a band over them.
Its body states three things this page's controls do not: that a
session has three emails and each tab edits one of them for this
session only; that a blank field falls back to the default shown as
the placeholder; and — the one an operator most needs — that
**sending is not switched on yet** (Segment 14B), so a saved
template is stored rather than delivered and no part of reviewer
access depends on it. It links to the Guide's "Give reviewers
access" section (`/guide#guide-give_access`) rather than repeating
what that section says.

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
`…/setup-invite`, carrying a hidden `template`, two read-only muted
rows — **From:** "(your configured SMTP From email — see Settings)",
linking to `/operator/settings?return_to=…`, and **To:** "(sent
individually to each reviewer)" — and four fields in fixed order:

| Field | Control | Notes |
|---|---|---|
| `subject` | text input, `maxlength="255"` | client-side cap only |
| `body` | textarea | no length limit |
| `cc` | text input | raw comma-separated addresses, stored verbatim |
| `bcc` | text input | as `cc` |

Each field renders **empty unless overridden**, with the in-code
default as its `placeholder` (shown in grey); a field with an override
renders the override as its value, and its label (`Subject` / `Body` /
`Cc` / `Bcc`) adds a muted "— overridden". When
(and only when) a field has an override, a **Reset *field* to default**
control renders beside it: a `.btn-reset` link-styled button that
submits a *separate* one-field form (`…/setup-invite/reset`, hidden
`template` + `field`) via the HTML5 `form=` attribute, so the reset
forms sit outside the composer form's HTML scope. Saving a field
**blank or whitespace-only** is the same as resetting it.

On the **Responses received** tab only, one extra control sits above
the fields: a checkbox **"Send this confirmation when a reviewer
submits."** (`name="enabled"`), checked by default. There is no
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
| `$deadline` | ✓ | ✓ | ✓ | `session.deadline` in the session's resolved zone (`sessions.resolve_session_timezone`, as `spec/timezone_display.md` requires): `YYYY-MM-DD HH:MM`, plus the zone token when `SHOW_ZONE_TOKEN` is on; `""` when unset |
| `$help_contact` | ✓ | ✓ | ✓ | `session.help_contact` trimmed; `""` when unset or blank |
| `$invite_url` | ✓ | ✓ | — | the reviewer's `/me/invite/{token}` URL; a fixed placeholder in previews |
| `$submitted_at` | — | — | ✓ | latest `Response.submitted_at` for the reviewer in this session, `YYYY-MM-DD HH:MM` in the session's resolved zone (plus the zone token when `SHOW_ZONE_TOKEN` is on); `"(not yet submitted)"` when none (previews only, in practice) |

**Defaults** (what a `NULL` column renders):

- Invitation — subject `Invitation to review: $session_name`; body
  `You've been invited to review for: $session_name.` / `Open this
  link (sign in with your work email): $invite_url`.
- Reminder — subject `Reminder: review for $session_name`; body
  `Reminder — your review for $session_name isn't complete yet.` /
  `Open this link (sign in with your work email): $invite_url`.
- Responses received — subject `Responses received: $session_name`;
  body `Hi $reviewer_name,` / `Thanks. Your responses for
  $session_name are recorded as of $submitted_at.` / `Questions?
  Contact $help_contact.` — and **when `help_contact` is unset or
  blank and the body is not overridden, the "Questions?" line is
  dropped** rather than rendering `Contact .`. An overridden body that
  references `$help_contact` keeps its line and substitutes the
  contact trimmed, so an unset or blank one renders empty; operator
  intent wins.

**Cc / Bcc.** `cc_bcc_for(session, kind)` returns the raw operator
strings (or `None` when blank); the send path copies them onto the
outbox row's `cc_emails` / `bcc_emails` unparsed.

---

## 7. Who consumes the templates

| Consumer | Uses | State |
|---|---|---|
| `invitations.send_invitation` / `send_reminder` | `render_invitation` / `render_reminder` + `cc_bcc_for` → an `EmailOutbox` row (`kind`, to / cc / bcc, merged `subject` + `body`) | **Wired, but nothing is transmitted.** The row is written `queued` and flipped to `sent` in the same transaction with no transport call — the dev-mode preview state described in `spec/rrw_functional_spec.md` §11.6. No `EmailTransport` is wired. |
| Invitations per-reviewer drill-in (`app/web/views/_previews.py`) | all three renderers, with a placeholder invite URL and the named reviewer | Wired. |
| Reviewer submit (the responses-received confirmation) | `responses_received_enabled` + `render_responses_received` + `cc_bcc_for` → `invitations.queue_responses_received` | **Queued, and work in progress awaiting Azure.** A successful submit (`/me/sessions/{id}/submit`) writes one `responses_received` `EmailOutbox` row when the toggle is on, and nothing when it is off, the submit is blocked or it recorded no response. A reviewer has one queued confirmation: a second submit refreshes it (a read then a write, not a constraint). Queueing runs after the submit commits and never fails it. A recall, a reviewer's clear-all or an operator's Delete Data leaves a queued confirmation in place. The row stays `queued` — unlike invitations and reminders it is not flipped to `sent` — until a transport exists; what to send of it then is decided with the transport (`guide/post_azure_todo_checklist.md` item 9). |
| Settings CSV export / import, clone | the JSON wholesale (§8) | Wired. |

---

## 8. Round-trip and clone

**Settings CSV** (`spec/csv_contracts.md`; coverage row
`spec/roundtrip_coverage.md` §"Coverage matrix — configuration" — "✅ All"). Field paths use a
**three-segment dotted grammar that differs from the JSON keys**:

```
email_overrides.<kind>.<slot>              string   — 12 rows, one per override key
email_overrides.responses_received.enabled boolean  — the toggle
```

e.g. `email_overrides.invitation.subject`, `email_overrides.reminder.bcc`.
Export writes every one of the twelve string rows, blank cell when no
override is set, and the `enabled` row as lowercase `true` unless stored
`False` (then `false`).
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
`email_template.no_help_contact` — "No help contact set — the
responses-received email omits its 'Questions? Contact …' line". It
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
| `responses_received.queued` | a successful submit queued, or refreshed, the confirmation (§7) | `refs` = `reviewer_id`, `outbox_id`; `context.refreshed`; actor = the reviewer |

A Save or Reset that changes nothing writes **no** event. All three
types are registered in `EVENT_SCHEMAS` (`spec/architecture.md`).

---

## 11. Tests

- `tests/integration/test_email_template_editor.py` — tab
  rendering and defaults, 404s on unknown kind / field, save persists
  + audits, no-change saves do not audit, blank clears an override,
  reset removes + audits, Reset control renders only for overridden
  fields, the third tab and its checkbox (absent on other tabs,
  explicit-`False` on uncheck, key removed on re-check).
- `tests/unit/test_email_templates.py` — resolver fall-through
  (`NULL` / blank / subject-only), all five tags substitute, unknown
  tag passes through, unset help-contact and deadline render `""`,
  dates in the session's zone (own zone, creator fallback, UTC), the
  responses-received default variants and `$invite_url` drop, and
  every branch of the `enabled` getter / setter.
- `tests/integration/test_responses_received_queued.py` — the
  submit-time queue (§7): queued on submit, nothing when the toggle is
  off or the submit is blocked, one row refreshed on a second submit,
  the subject kept within its column, and a queue failure that does
  not fail the submit.
- `tests/integration/test_email_dates_session_zone.py` — the same
  zone rule on mapped rows, through the session's creator.

---

## 12. Cross-references

- `spec/settings_inventory.md` §3 — the key inventory; §7 "URL state" the
  `?template=` UI-state param.
- `spec/rrw_functional_spec.md` §11 — the subsystem in user terms,
  including what is and is not wired.
- `spec/preview_hub.md` — the read-only renders of all three emails.
- `spec/operator_ui_concept.md` "Email Template" — the page in the
  Setup-row taxonomy; `spec/operator_button_audit.md` §10 — its
  buttons (#63–#67).
- `spec/csv_contracts.md`, `spec/roundtrip_coverage.md` §"Coverage matrix — configuration" — the
  Settings-CSV carrier.
- `spec/email_infra_options.md`, `guide/segment_14B_email_infrastructure.md`
  — the dispatch leg this editor feeds.
- `guide/archive/segment_11E_email_template_editor.md` — design
  record and PR ladder.
