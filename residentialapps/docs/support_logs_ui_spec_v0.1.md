# Support Logs — UI Specification (draft)

> **Superseded 2026-10-29 by `residentialapps/spec/supportlogs_ui.md`** (segment 1D item 1, rung 6), which settles this draft's conventions and answers or carries its open questions (§9). Kept as history: its §6 accent and token figures are still cited.

> **Moved 2026-10-25 from the private deployment repository** (author), where it was `docs/support_logs_ui_spec_v0.1.md` (at `ad94c1c`). Deployment status (which grants are in place, configuration dates, what IT has delivered) was made generic on the way; it is tracked privately with the deployment. "Strategy v1.0" below is the Cordware deployment strategy, also held privately; what Residential depends on from it is in `residentialapps/guide/todo_master.md`.
>
> **Amended 2026-10-25 (author): one package, two applications.** Residential is one `residentialapps/` package mounted as two applications, Residential Operations at `/residentialops` and Support Logs at `/supportlogs`; nothing is mounted at `/residentialapps`. Passages below that say "one application" or mount it at `/residentialapps` predate this and are revised at this spec's next version.

**Version:** 0.1, 23 October 2026 — draft for discussion
**Scope:** the RF / RSLM surface of Support Logs, phone first, plus the safety-flag list every *safety-flag recipient* needs, frontline or not (screen 9). Master, opportunity-review, audit and administration surfaces come later.
**Reads with:** `residentialapps/docs/resident_support_log_functional_spec_v0.3.md` (what the surface does), `docs/cordware_mobile_to_desktop.md` (UX classes), strategy v1.0 §3 (every application meets RRW's baseline).
**Design baseline:** RRW's design system at `philoyhc/review-robin-web` `a06e7ee`: `spec/color_tokens.md`, `spec/visual_style_general.md`, `spec/ui_elements.md`, and `tools/theme_customizer.html`.
**First mockups:** six phone screens on a private design canvas, "Support Logs RF mobile" (2026-10-23). They are a layout baseline, not yet on RRW's tokens (§8).

---

## 1. Principles

1. **RRW's design system is the baseline, adopted rather than imitated.** Residential uses the same two-tier colour model (primitives, then semantic tokens that templates consume), the same non-colour scales, the same `.btn` roles, light and dark themes, and the same customizer and contrast audit. Anything Support Logs needs beyond RRW is added as an app-specific `[A]` token or a named component, never as an inline hex.
2. **Phone first for the RF surface.** Every screen here is mobile-critical or responsive general-use (functional spec §14). RRW is desktop-first and leaves narrow viewports to "a separate spec" (`visual_style_general.md`); §4 below is that spec for Residential.
3. **The routine path stays short.** Student → duration → type → save, on one screen, in about 10–20 seconds (functional spec §5.1, §16). Everything else is optional and one tap away.
4. **Safety is visually separate and never accidental.** The safety flow has its own control, colour and screen, away from the routine controls.
5. **Data minimisation shows in the UI.** Notes are short and say so; the student view says that opening it is recorded; nothing invites clinical detail.
6. **Support Logs presents as its own application** (author, 2026-10-23), set apart from Residential Operations: its own name, entry point, navigation and accent, given how different its users, data and purpose are. Underneath it stays one Residential application with Residential Operations (strategy v1.0 §4).

## 2. Surfaces in this draft

| # | Screen | UX class | Functional spec |
|---|---|---|---|
| 1 | Home (personal dashboard) | Responsive general-use; its due/overdue list is mobile-critical | §10.1 |
| 2 | Log encounter, routine path | Mobile-critical | §5.1–5.6 |
| 3 | Log encounter, optional details | Mobile-critical | §5.7–5.9, §6 |
| 4 | Safety concern | Mobile-critical | §5.10 |
| 5 | Student view | Responsive general-use | §9, §11.1 |
| 6 | My follow-ups | Mobile-critical | §6, §7, §10.1 |
| 7 | Students (finder) | Mobile-critical | §4.2–4.3 |
| 8 | Safety flag detail | Mobile-critical | §5.10, §11.3 |
| 9 | Safety flags (recipients) | Mobile-critical | §3.5, §5.10 |

Screens 7–9 are specified below but not yet mocked up.

Navigation: a bottom bar with four destinations — Home, Log, Students, Follow-ups — on screens 1, 5, 6 and 7. The logging and safety screens are full-screen tasks with Close or Back instead. The bottom bar becomes a side or top bar at desktop width; routes and permissions are the same at every width (`cordware_mobile_to_desktop.md` §7.5, §9).

## 3. Screens

**1 · Home.** In order:
- **active safety flags** the user may see, each until it is closed with an outcome: the flags they raised, and, when they hold the *safety-flag recipient* authorization, every active flag, unacknowledged above acknowledged (functional spec §5.10). v1 has no automated alerts, so this list is where a recipient first sees a new flag;
- a full-width Primary **Log encounter**;
- **Due and overdue**: formal assignments, self-set follow-ups and students not seen despite a cadence, each row with a Secondary **Log** that opens screen 2 with the student filled in;
- **Following**: every active formal assignment and informal follow-up, due or not, with cadence and last contact, the first few shown and **All N** opening screen 6 (§10.1);
- **Recent encounters**: the user's last few, each opening the student view, with **All** opening their full list (§10.1);
- **My last 14 days**: encounters, support time, students, and a breakdown by encounter type.

**2 · Log encounter, routine path.**
- Header: Close, title, and the time (defaults to now; tap to log retrospectively, §5.2).
- **Student**: the user's own students as one-tap choices above the directory search (§4.2–4.3); the chosen student shows as a card with Change.
- **Duration**: the seven presets of §5.5 as single-select choice chips.
- **Type**: the configurable list of §5.6 as single-select choice chips, two columns.
- **Add details**: a row that opens screen 3; its subtitle names what is there.
- **Mark a safety concern**, set apart at the bottom of the content (§6, open question 1).
- A fixed footer: a one-line summary of the choices and a full-width Primary **Save encounter**, disabled until the three required fields are set (§5.3).

**3 · Optional details.**
- Concern areas: multi-select choice chips, the configured list (§5.7; ten seeded).
- **Follow-up needed?** No / Yes: the encounter's own signal (§5.4, §5.11), recorded whatever happens next.
- **My follow-ups**, a separate control: Add to my follow-ups, with an optional cadence chosen from the administrator-configured options (§3.3, §6.4), which always include **No fixed cadence**, the default; a next due date only when a cadence is set, or, when already following, the current cadence to keep or change (§6.2). Needing follow-up does not require the user to take it on, for example when it goes to formal review.
- How: In person / Phone / Online / Other (§5.9), optional.
- **Who started it?** Student / Staff / Other (the values of `Encounter.initiated_by`), optional, shown only when the type does not already say (§5.4); Student- and Staff-initiated conversation imply it.
- Short note, at most **300 characters** (within §5.8's 250–500), with a live count and the guidance text of §5.8. The limit is enforced in the browser (`maxlength`) and again on the server, which rejects a longer note rather than truncating it.
- The same fixed **Save encounter**.

**After saving** (screens 2 and 3): a confirmation names what was saved and, when the student is not on the user's follow-ups, offers **Add to my follow-ups** in one tap (§6.2), so the routine path can end there without returning to the student.

**4 · Safety concern.**
- A header in the safety colour, with Back.
- Call actions first: emergency services, campus security, the counselling duty line and duty senior staff, as `tel:` links. Numbers and the on-duty name are placeholders until the crisis protocol is supplied (functional spec §17). They never wait on anything else.
- **Encounter context**, below the call actions: whichever of student, duration and type are not yet chosen, as compact controls, so the safety flow can start from an empty form. **Save and raise safety flag** is disabled until all three and the escalation step are set.
- The crisis protocol's steps, as an ordered list.
- **Escalation step taken**, required, as a radio group, with the time.
- The data-minimisation reminder of §5.10.
- **Save and raise safety flag** and Cancel (open question 2).

**5 · Student view.**
- Name and institutional email.
- A banner that the view is recorded, and that it shows what the user's authorizations cover for this student: their own records, any a colleague has shared through a peer-view grant (§11.1), and any safety flags they may see as raiser or recipient (§5.10).
- Three tiles: following-up cadence, last contact, next due.
- A Primary **Log encounter with [name]**.
- **Encounters** with that student that the user may see, the most recent first, with **Full history** opening everything the user may see for the student, paged and under the same authorization checks (§4.5): encounters, and past and current informal follow-ups and formal assignments, including ended, paused and converted ones with their conversion history (§8).
- **Safety flags** for this student that the user may see, active first and then closed with their outcomes, each opening screen 8. This is where a raiser finds a flag again after it is closed.
- **Shared with**: each peer-view grant the user has made for this student, with its colleague and a **Revoke** action, then **Share with a colleague** (§11.1). Records a colleague has shared with the user are labelled with that colleague's name.
- **Flag for formal assignment**, and one follow-up control that matches the current state: **Start following up** (cadence optional, **No fixed cadence** by default, §6.3–6.4) when the student is not on the user's follow-ups, **Stop following up** when they are.

**6 · My follow-ups.**
- A three-way filter: All / Overdue / This week.
- Formal assignments first, with source and cadence; managed safety support carries its marker and the operational instruction (§5.10).
- Then informal follow-ups; a student with an active flag the user may see shows the flag status.
- **Add a student to follow up.**

**7 · Students (finder).** The bottom bar's Students destination:
- the same search as screen 2's student field, as the signed-in staff member (§4.2), with the email fallback when directory read is unavailable;
- the user's own students first, the whole local working set of §4.3: formal assignments, follow-ups and every student they have an encounter with, recent ones on top;
- choosing a student opens screen 5.

**8 · Safety flag detail.** Opened from a flag on Home, screen 5 or screen 6:
- the student, when and by whom it was raised, the escalation step recorded, and its state (unacknowledged, acknowledged by whom, closed with what outcome);
- for a *safety-flag recipient*: **Acknowledge** (taking it on) while unacknowledged, and **Close with outcome**, which requires an outcome (for example referred to counselling, assessed by counselling, no further action) and removes the flag from active lists;
- for the staff member who raised it and holds no recipient authorization: the state and outcome only;
- acknowledgement and closure are audited, as is every view of the flag (§11.3).

**9 · Safety flags (recipients).** Gated by the *safety-flag recipient* authorization alone, so a Master or delegate who holds it without frontline access still has a surface (§3.5):
- it is the landing page for a recipient without frontline access, and a destination from Home for one with it;
- active flags, unacknowledged above acknowledged, each opening screen 8;
- closed flags with their outcomes, below: the most recent first, with the full history searchable by student and date, so a recipient can always retrieve an outcome;
- a count of unacknowledged flags in the app's navigation wherever the user is, since v1 has no automated alerts.

**Configured lists.** Every option set on these screens renders the effective configured list, never a hard-coded one: durations (§5.5), encounter types (§5.6), concern areas (§5.7), modes (§5.9), cadences (§3.3, §6.4), and the safety escalation steps and closure outcomes (§5.10, `SafetyEscalation`). The values named above are the seeded defaults.

**Optional choices can be cleared.** An optional single-select set (how, who started it, follow-up needed) starts unset and has a **Clear** action that returns it to unset, so an accidental tap never records a value the user did not mean.

## 4. Mobile layer (what RRW does not specify)

- **Touch targets:** every control at least 44 × 44 CSS px; the main actions (Log encounter, Save) 52–56 px tall and full width.
- **Fixed footer actions:** a form's Save sits in a footer fixed to the bottom of the viewport, so it stays within thumb reach; content scrolls above it.
- **Single column** below 600 px. Choice chips wrap; tiles use `repeat(N, minmax(0, 1fr))` grids.
- **No hover dependence**; hover tints from RRW still apply on pointer devices.
- **Base text 16 px** (`--fs-body`), so phone browsers do not zoom into inputs on focus; zoom is never disabled.
- **Breakpoints by content, not device** (`cordware_mobile_to_desktop.md` §7.2).
- **Viewport testing:** every screen here is checked at a narrow and a desktop width; mobile-critical ones get a completed-workflow check at the narrow width (`cordware_mobile_to_desktop.md` §10).

## 5. Components

| Component | Treatment | RRW basis |
|---|---|---|
| Primary action | `.btn` Primary, full width, mobile height (§4) | `ui_elements.md` §6 |
| Row action (Log, Share, Flag for formal assignment) | `.btn.secondary` | §6 |
| Choice chip, single- or multi-select | pill shape; off = `--surface-card` + `--border-default`; on = `--chip-selected-bg` + `--text-body` + `--selected-bg` border, plus a leading checkmark and semibold label, so the selection shows without colour (§7). **Single-select** sets (duration, type, how, yes/no) are native radio groups styled as chips, so one choice per set is announced; **multi-select** (concern areas) are checkboxes, or `aria-pressed` buttons | chips and pills, `ui_elements.md`; **new component**, open question 3 |
| Status label (Overdue, Due today, Due Fri, Not seen recently) | `.pill-*` rules (open question 4) | `ui_elements.md` pills |
| Card | `--surface-card`, `--border-default` boundary, `--radius-card`; cards never touch | `visual_style_general.md` P8 |
| Bottom navigation | four items, icon plus label; the current item takes `aria-current="page"`, the accent, a semibold label and an indicator bar above it, so it shows without colour | **new**, Residential chrome |
| Safety banner and safety controls | §6 | **new** |

## 6. Colour roles

Every colour is a semantic token. Proposed mappings, light theme (dark follows each token's dark mapping):

| Role | Token | Light value |
|---|---|---|
| Body text / muted text | `--text-body` / `--text-subtle` | `#111827` / `#616874` |
| Page / card / muted surface | `--surface-page` / `--surface-card` / `--surface-muted` | `#ffffff` / `#ffffff` / `#f5f5f7` |
| Boundaries of cards, inputs, chips | `--border-default` | `#6f7b8e` (3:1) |
| Primary actions, selection, focus, links, current navigation | the accent tokens (below) | teal `#0f766e`, white label |
| Overdue, not seen recently | `--status-warning-bg` / `-fg` | `#fef3c7` / `#92400e` |
| Due today | `--status-info-bg` / `-fg` | `#dbeafe` / `#1e40af` |
| Due later | `--surface-muted` / `--text-body` | — |
| Safety banner, flag status | `--status-error-soft-bg` / `-border` / `-fg` | `#fdecea` / `#f2b8b5` / `#8a1c14` |
| Safety header, raise-flag action | `--status-error-solid-bg` / `-fg` | `#dc2626` / white |
| Safety-plan support marker | new `[A]` `--marker-safety-plan-bg` / `-fg`, mapped to the violet primitives | `#ede9fe` / `#5b21b6` |

**The safety-plan marker takes its own token**, even though its values equal `--status-super-*` today: that token means platform super-admin, and a marker that borrows it would move whenever super-admin's look does (`spec/color_tokens.md`, "Border colours do not paint fills", applied to meaning). Any new `[A]` token joins the customizer's targets and the contrast audit, as RRW's do.

**One accent per application** (author, 2026-10-23). Each application's main users get their own visual identity, and the accent is the only thing that varies:

| Application | Main users | Accent, light | Hover, light | Accent, dark | Hover, dark | Selected tint, light / dark |
|---|---|---|---|---|---|---|
| RRW | a wide range of operators and participants | blue `#2563eb` (unchanged) | `#3b82f6` | `#4b8bf5` | `#60a5fa` | `#dbeafe` / `#16324f` |
| **Support Logs** | residential staff | **teal `#0f766e`** | `#115e59` | `#2dd4bf` | `#5eead4` | `#ccfbf1` / `#134e4a` |
| Residential Operations | residential assistants (students) | **fuchsia `#a21caf`** | `#86198f` | `#e879f9` | `#f0abfc` | `#fae8ff` / `#4a044e` |
| Cordware Utilities (author, 2026-10-30) | the platform super-admin | **amber `#b45309`** (favicon tile; `utilityapps/README.md`) | not ruled | not ruled | not ruled | not ruled |

- **What the accent covers:** `--btn-primary-*`, `--selected-*`, `--chip-selected-bg`, `--focus-ring` and `--focus-ring-halo`, `--text-link` and `--text-link-strong`, and the current navigation item. Each application maps these to its own primitives through the customizer.
- **What stays shared:** text, surfaces, borders and every status token. A warning, an error, a success or an info state means the same thing in every application, so the accent never takes a status hue (amber, red, green). Info stays blue in all three. **The one exception is Cordware Utilities' amber** (author, 2026-10-30). Its alerts stay on the status token `--warn`, never on the accent.
- **Contrast, as measured:** labels on the accent clear AA in both themes — teal 5.47 light and 9.53 dark (dark label `--ink`), fuchsia 6.32 and 7.21 — and each fill clears 3:1 against its page. Residential's hover **darkens** in light, unlike RRW's lightening blue, so the hover label stays above 4.5 (teal 7.58, fuchsia 8.24) rather than dipping to RRW's accepted 3.68.
- **One closeness to watch:** teal sits near RRW's success green (about 1.3:1 between `#0f766e` and `#166534`), so success pills always carry their words.
- **The accent follows the application, not the user** (author, 2026-10-23). Everyone in an application sees its accent whatever their role: in Residential Operations the RA applying and the RF approving both see fuchsia; in Support Logs every staff member sees teal. Who someone is and what they may do shows in the screens and actions they get, never in colour, so there is one mapping and one contrast audit per application.
- **Shared screens are neutral.** Residential screens that belong to neither pillar — the sign-in landing and the page that switches between Support Logs and Residential Operations — take the shared neutrals and no accent.
- The accent candidates and their figures are on the design canvas, row C.

**Typography and scales:** RRW's system font stack (no web fonts), `--fs-*` type scale, `--space-*` spacing and `--radius-*` radii, unchanged.

## 7. Accessibility

RRW's floor applies unchanged: text at WCAG AA 4.5:1 against every surface, control boundaries at 3:1, both themes, checked by the contrast audit. Added for this surface:
- real `<button>`, `<a href>`, `<input>` and `<label>`; selection state in `aria-pressed` or native radio and checkbox state;
- colour is never the only signal: status labels carry words ("Overdue 3 days"), and the safety screen a heading;
- the safety call actions are links with visible numbers, reachable without scrolling on a 390 × 844 viewport.

## 8. How close the first mockups are to RRW

Close in **semantics and status colours**, apart in **structure**:

| Area | Mockups | RRW | Change |
|---|---|---|---|
| Status hues | overdue `#9A3412` on `#FFF1E6`, due-today `#1E40AF` on `#EEF3FF`, safety `#B42318`, safety-plan `#5B21B6` on `#F3EEFF` | `--status-warning-fg` `#92400e`, `--status-info-fg` `#1e40af`, `--status-error-*`, violet `#5b21b6` on `#ede9fe` | map to the tokens of §6: near-identical values |
| Text | `#17212B`, `#55606B` | `#111827`, `#616874` | map to `--text-body`, `--text-subtle` |
| Accent | teal `#0B6466` | blue `#2563eb` | Support Logs teal `#0f766e` (§6) |
| Font | Public Sans web font | system stack, no web fonts | system stack |
| Surfaces | white cards on a grey page | white page, white cards | RRW surfaces |
| Boundaries | 1px `#E2E6EA` cards, `#C9D0D6` chips, about 1.3–1.6:1 | `--border-default` at 3:1 | **fails WCAG 1.4.11; must change** |
| Radii | 10–12 px | 6 px buttons, 8 px cards, pill | RRW radii |
| Status labels | sentence case, 6 px corners | uppercase pills | open question 4 |
| Spacing | 2–22 px, ad hoc | 4 / 8 / 12 / 16 / 24 / 32 | RRW scale |
| Themes | light only | light and dark | both |
| Button heights | 44–56 px | `--space-2` padding, about 36 px | Residential mobile layer (§4) |
| Filled red action | Save and raise safety flag | no filled red role | open question 2 |

The next mockup round applies this table; the layouts of §3 carry over unchanged.

## 9. Open questions

1. **Mark a safety concern** — RRW's Destructive role (outline red) is for irreversible deletes; this act is neither. A new **Safety** role, outline in `--status-error-*`, or Destructive reused?
2. **Save and raise safety flag** — RRW has no filled red button (filled amber was retired). Allow one filled role for this single act, on `--status-error-solid-*`, or keep it Primary on a red-framed screen?
3. **Choice chips** — RRW's Toggle role is one flag per row, and its chips are table-column chips. Adopt a new **choice chip** component for duration, type and concern areas, or build them as styled radio and checkbox inputs?
4. **Status labels** — use RRW's uppercase pills as they are, or a sentence-case variant for phone reading ("Overdue 3 days")?
5. *(Settled 2026-10-23: shared Residential screens are neutral; §6.)*
6. **Residential customizer** — Residential's base template gets its own generated customizer page and contrast audit, on RRW's pattern (strategy v1.0 §3, "the template")?

## 10. History

- **0.1** (2026-10-23): first draft from the six RF mockups, against RRW's design system at `a06e7ee`. One accent per application settled the same day: blue RRW, teal Support Logs, fuchsia RA Operations, renamed Residential Operations 2026-10-26 (§6).
