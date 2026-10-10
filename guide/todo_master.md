# Master todo sequence

**Open work only.** What is queued, what is filed but small, and the
order constraints between them. Nothing here is history: when a
segment closes it deletes its own entries from this file (its queue
line, any stub it shipped or absorbed, any sequencing note that named
it — the `segment-plan` skill, "Closing a segment"), and the record of
what shipped is the archived plan (`guide/archive/README.md`), its PRs
and the git log. The `## Done` section this file carried until
2026-10-05 is verbatim in `guide/archive/todo_master_done.md`.

When a segment plan exists, that plan is the day-to-day source of truth
for its own slices; this file points at it without duplicating its PR
ladder.

Two sibling registers hold the open work that is not queued here:

- `guide/post_azure_todo_checklist.md` — work **blocked on the
  institutional Azure deployment** itself, not merely unscheduled.
- `guide/deferred_consolidated.md` — work scoped but not scheduled,
  ordered by disposition.

---

## Upcoming

### In progress

- **UX refinements** — `guide/ux_refinements.md`. Items 1–3 built;
  Item 3 (↰ only joins a branch) reversed 2026-10-10, restored in one
  PR. Each item's close is owed. (`guide/operator_pages_enhancements.md`
  Items 1–3 closed 2026-10-09; new items are added there.)

### Queued segments

Both are **gated on the institutional Azure deployment concluding**
(decision 2026-09-05) and independent of each other.

1. **14B — Email infrastructure (send activation + backends).** All
   email *wiring*. Parts A → E are sequential: SMTP send activation →
   `correlation_id` strategy → bulk-send queue + worker →
   per-deployment from-identity defaults → generalised Outbox
   diagnostic surface. Parts F → H are independent backend swaps
   (Microsoft Graph, Azure Communication Services, a third-party
   transactional service), shipped as a deployment needs them. Not
   started until the host exists with a sending identity; meanwhile
   invitations are covered by the operator's own email (access is
   roster + sign-in), and the real gap is targeted reminders.
   **Plan:** `guide/segment_14B_email_infrastructure.md`.
   **Functional spec:** `spec/email_infra_options.md`.

2. **20 — Operator polish + documentation.** Documentation *of a real
   deployment*, so it waits for one: the **administrator guide** for
   the institutional host, the institutional half of
   **troubleshooting**, a **currency pass** over the in-app Guide and
   `docs/known_limitations.md`, and setting the technical-support
   address the stub below introduces.
   **Plan:** `guide/segment_20_operator_polish_and_documentation.md`.

### Stubs

Small items with no plan doc; each fits one PR and its reasoning fits
the PR body unless it says otherwise.

- **Technical-support contact (global)** *(filed 2026-05-03)*. A
  deployment-wide "something looks broken" address, distinct from the
  per-session help contact on `ReviewSession`
  (`app/schemas/sessions.py`), for a reviewer hitting an auth failure,
  a 500 or an invalid link. A new env var read through `app/config.py`,
  shown on the chrome footer, the error pages and the invalid-link
  landing; **unset renders nothing**, so the mechanism does not wait
  for the deployment — only the address does, and setting it is
  Segment 20's.

- **`regenerate_token` leaves `last_reminder_at` standing** *(filed
  2026-09-18; the author answered **yes, clear it**, placement open)*.
  `regenerate_token` (`app/services/invitations.py`) clears
  `token_hash`, `status`, `sent_at` and `opened_at`, but not
  `last_reminder_at` or the outbox rows, so a reissued invitation still
  reports a reminder sent against the dead token. Clearing it moves the
  Invitations **Reminder** column and the reminder scheduler. Reasoning
  at `guide/archive/segment_19P_expander_revamp.md` Item 6 OQ4.

- **The three Operations pages gate their left toolbar pane on having
  rows** *(filed 2026-09-17)*, where the four roster pages let the
  partials guard themselves. The filter in the right pane stays
  reachable on a search that matches nothing, so nothing is lost
  today; it is a divergence of pattern between the two families.

- **`close_check`'s manifest check is one-directional** *(filed
  2026-09-13)*. C3 asks whether every path a plan **declared** was
  edited in the window, never whether every path **edited** was
  declared — 19N.1 edited three specs with no `Doc impact` bullet and
  passed. The advisory `touched; not in manifest` notes compute most
  of it; the open question is promoting them to a check without
  drowning in the long-window noise 19C and 19J recorded. Likely one
  slice in `tools/close_check/`.

- **Should a rehydrate audit observer, relationship and assignment
  counts?** *(filed 2026-09-13)*. `session.rehydrated` carries four
  count keys (`reviewers`, `reviewees`, `responses`,
  `responses_dropped`) and `spec/rehydrate.md` §7 names those four. A
  design question the author ruled future work: deciding it needs a
  reason someone would read the other three.

- **Theme customizer — a full pass over every element** *(author
  intent, 2026-09-06)*. 19C Item 8 found three defects only by looking
  (an inherited 2px border, a stale pick-list facet, an edit box with
  no visible edge). The intent is to work through every element the
  same way rather than as defects surface. Unscoped on purpose; each
  finding is likely its own slice. Open a plan doc when the pass starts.

- **Does *Invitations* still name the page?** *(filed 2026-09-18)*.
  Since 19P.6 it is reviewer-keyed and its rows render with no
  invitation at all, so the tab name describes the artefact rather than
  the job. Naming only. **Author's call**, and cheap to leave alone.

### Sequencing notes

- **11C Part 2 → 14B Part A** is the email pipeline: the
  `email_outbox` schema landed inert in 11C Part 2 (migration
  `c4f6a8b0d2e5`), and 14B Part A is its first writer.
- **Within 14B**, Parts B–E build on Part A in order; Parts F–H are
  independent of each other. Scheduled reminders (18G Part 3) already
  fire into the dev outbox and go out once Part A lights the transport.
- **20** is independent of the email pipeline but gated on the
  deployment, so it does not interleave with other work.
