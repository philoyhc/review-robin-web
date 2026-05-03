## Reviewer Experience Preview hub — functional spec

A read-only Operations Page that renders, for an operator-selected reviewer, every reviewer-facing artifact the session generates: invitation email, response form, reminder email, responses-received email, and any future reviewer-facing artifacts. The operator uses this surface to eyeball the reviewer experience before activating the session and sending real communications.

### Rationale and placement

The hub is the human analogue of Validate: where Validate checks the session's setup mechanically against rules ("every reviewer has assignments," "instruments are well-formed"), the hub lets the operator inspect what the reviewer will actually see. Both are pre-flight checks; both belong to the moment between setup-done and going-live.

For that reason, the hub is an **Operations Page**, not a Setup Page and not a sub-page of Home:

- It draws from multiple Setup Pages (Email Template, Instruments, Reviewers, Assignments) but is owned by none of them.
- Its purpose — pre-flight inspection — is operationally adjacent to Invitations and Monitoring.
- Placing it alongside the other Operations Pages keeps Home focused on lifecycle transitions and metadata.

### Page identity

| Field | Value |
|---|---|
| Page name | Reviewer Experience Preview (display label: "Preview" in the chrome) |
| Template | `session_preview.html` (new) |
| URL | `/sessions/{id}/preview` |
| Grouping | Operations |

The new URL replaces the existing `GET /operator/sessions/{id}/preview` (the form-only reviewer preview). The existing form preview is folded into this hub as one of its rendered artifacts; the standalone surface is retired.

### Chrome and navigation

The Operations row of the session chrome gains a `Preview` tab, sitting alongside Invitations, Monitoring, and (in dev-mode SMTP) Outbox. Suggested order:

```
Operations  [Preview][Invitations][Monitoring][Outbox]
```

Preview comes first because it's the artifact the operator consults *before* sending anything; Invitations and Monitoring are consulted *during and after*.

The `Run Session` card on Home, which currently links to the form-only preview, updates its link target to the new hub URL. The card's label may also want to update ("Preview reviewer experience" rather than "Preview the reviewer surface") to reflect the broader scope.

### Page layout

The page renders three regions, top to bottom:

**1. Reviewer picker (top of page).**

A picker that selects which reviewer the artifacts are previewed for. Renders:
- A dropdown or searchable selector listing all reviewers in the session, displayed as "Name (email) — N reviewees assigned."
- A passive context strip below the picker showing the selected reviewer's key attributes: name, email, count and list of assigned reviewees. This is the "previewing for" header that grounds what the operator is about to see.

**Default selection:** the first reviewer in the session's reviewer list (alphabetical or insertion-order; reuse whatever the Reviewers Setup page uses). Predictable and no-surprise.

**Empty state:** if the session has no reviewers configured, the picker renders disabled with an explanatory message: "No reviewers configured. Add reviewers via the Reviewers Setup page or the Quick Setup card on Home." The artifact previews below render their respective empty states (see "Missing-data handling" below).

**2. Artifact previews (main body).**

A list of preview cards, one per reviewer-facing artifact. Cards render top-to-bottom in the order the reviewer would encounter them:

1. **Invitation email** — the message that brings the reviewer into the session.
2. **Response form** — the page where the reviewer completes their review (the artifact previously rendered by the standalone `/preview` surface).
3. **Reminder email** — the message sent if the reviewer hasn't responded by the configured threshold.
4. **Responses-received email** — the confirmation sent after the reviewer submits.

The list is **extensible**: new reviewer-facing artifacts added to the system in future segments should appear in this list automatically (or with minimal addition). The hub's structure should not hard-code exactly four artifacts; it should iterate over a registry of reviewer-facing artifacts.

Each card contains:
- Artifact name and a one-line description ("Sent when the operator activates the session").
- The rendered artifact itself, displayed as it would be sent or shown:
  - Email artifacts: rendered with subject, from-address, to-address, and body, styled approximately as the reviewer's email client would show them. Plain-text and HTML versions both shown if the system generates both.
  - Form artifact: rendered as a static, non-interactive snapshot of the form the reviewer would see. Form fields display but do not submit; the snapshot reflects exactly what the live form would render for this reviewer with their assigned reviewees.
- A small footer or sidebar noting the artifact's source: "Rendered from Email Template (Setup) and Reviewers (Setup)." This helps the operator know where to go to fix something they don't like.

**3. Send-test affordance (per email card).**

Each email-artifact card has a "Send test to..." affordance: an input for an email address (defaulting to the operator's own, if known) and a Send button. Clicking sends the previewed email — rendered for the selected reviewer, with their data — to the test address.

Important constraints:
- The test email's `To:` address is the operator-supplied test address, **never** the reviewer's actual address. The card surfaces this clearly: "This will send to *[test@example.com](mailto:test@example.com)*, not to *[reviewer@example.com](mailto:reviewer@example.com)*."
- The test email's body and subject are rendered identically to what would be sent to the reviewer in production — same template, same data, same rendering path.
- Test sends are recorded somewhere auditable but do not affect the session's invitation/reminder state. Sending a test invitation does *not* mark the reviewer as invited.

The send-test affordance does not appear on the form-artifact card (no analogous action).

### Rendering: production parity

All artifact previews must render through the **same code paths** that produce the artifacts in production. The invitation email preview calls the same template-rendering function the live invitation flow calls; the form preview uses the same form-rendering logic the live reviewer surface uses. No bespoke "preview mode" rendering.

The only difference between preview and live: the preview renders into the operator's page rather than being sent or displayed to the reviewer. The output bytes should be identical to what the reviewer would receive.

This is non-negotiable. A preview that drifts from production silently misleads operators and defeats the hub's purpose.

### Missing-data handling

The hub is useful as a setup-completeness diagnostic in addition to a preview tool. When data needed to render an artifact is missing, the corresponding card renders a clear, scoped error rather than a blank or broken preview:

- **Email template not configured.** Card renders: "Invitation email template not set up. Configure on the Email Template Setup page." with a link.
- **Reviewer has no assigned reviewees.** Form card renders: "This reviewer has no reviewees assigned. Configure assignments on the Assignments Setup page."
- **Instruments not configured.** Form card renders: "No instruments configured. Configure on the Instruments Setup page."
- **Other dependencies absent.** Same pattern — name what's missing, name where to fix it, link there.

Errors are scoped per-card. A missing email template doesn't block the form preview from rendering; a reviewer with no assignments doesn't block the email previews from rendering (the emails may still be sendable in their own right).

### Lifecycle behavior

The hub renders in all session lifecycle states (`draft`, `validated`, `ready`, `closed`):

- **`draft` / `validated`:** Full functionality. All previews render (or surface missing-data messages). Send-test is enabled.
- **`ready`:** Full functionality. Previews still render against current setup data; this is when the operator most wants the hub. Send-test is enabled.
- **`closed`:** Previews still render (read-only inspection of what was sent). Send-test renders disabled with the standard yellow lock card explanation, since the session is no longer active.

The hub never renders fully locked behind a yellow lock card — even on closed sessions, inspecting what the reviewer experience looked like is useful. Only the send-test affordance gates on lifecycle.

### Out of scope for this segment

- **Editing artifacts.** The hub is strictly read-only; edits happen on the Setup pages.
- **A/B comparing previews** across multiple reviewers side-by-side.
- **Generating exportable previews** (PDF, screenshot, downloadable bundle).
- **Showing the reviewer's submission state** (that's Monitoring's job).
- **History of past sends** (that's Monitoring / Outbox).

### Forward-looking: Reviewee Experience Preview

The current app is asymmetric: reviewees do not enter the system, do not see artifacts, and may not know they are under review. The hub is therefore reviewer-facing only.

Some envisioned future scenarios — non-confidential peer review, 360-degree feedback, results-sharing flows — would introduce reviewee-facing artifacts (review-completed notifications, results emails, etc.). At that point, a parallel **Reviewee Experience Preview** hub would be added as a separate Operations Page, with the same structure as this hub but scoped to a reviewee picker and reviewee-facing artifact list.

Two hubs (one per audience) is preferred over a single hub with an audience toggle: the audiences will diverge in artifact composition enough that a unified hub becomes contorted. The current hub should not bake in reviewer-only assumptions that prevent the parallel hub from being built later — for example, the artifact registry that drives the preview list should be neutral about audience, with reviewer-facing and reviewee-facing being two different registry filters.

This is forward-looking and not a deliverable for this segment. Recorded here so the implementation doesn't accidentally close off the path.

### Doc impact

UI concept doc:

- The Operations Pages section in the page taxonomy gains a new entry: Preview (`session_preview.html`, `/sessions/{id}/preview`).
- The Preview Pages grouping in the page taxonomy is **retired**. Its sole member (the form-only reviewer preview) is absorbed into the Operations hub. The grouping name and slot are removed; the page count drops from "five active groupings plus two forward-looking" to "four active groupings plus two forward-looking" (Overview, Control Panel, Setup Pages, Operations Pages, plus Preview Pages and Sysadmin as forward-looking — the latter is still on the list).
- The chrome description for Operations adds Preview to the tab list.
- The `Run Session` card on Home updates its link target.

`spec/operator_map.md`:

- New page entry for `session_preview.html` with its layout contract.
- Removal or rewriting of the existing `/preview` form-only preview entry.
- Updates to the Home page's Run Session card to reflect the new link target.

### Implementation pointers

- The artifact registry that drives the preview list should be a small, extensible structure — a list of (artifact-name, render-function, source-Setup-pages, audience) tuples, iterated over by the page template. Adding a future reviewer-facing artifact is then a matter of registering it; adding the future Reviewee hub is a matter of filtering the registry by audience.
- Reuse the existing email-rendering and form-rendering code paths verbatim. If the production rendering needs refactoring to be callable in preview context, do that refactoring rather than duplicating logic.
- The send-test affordance should reuse whatever email-sending infrastructure the live invitation/reminder flows use, with the `To:` address swapped. Do not introduce a parallel test-send path.
- The picker's reviewer list should reuse the same query the Reviewers Setup page uses, sorted the same way.
- Lifecycle locking on the send-test affordance should reuse the existing yellow lock card component.

The intent throughout: the hub is a thin presentation surface over existing primitives. It owns layout, picker state, and the artifact registry; it owns no rendering, no sending, no validation logic of its own.
