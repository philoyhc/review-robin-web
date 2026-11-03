# Cordware — Mobile-to-Desktop UX Guidance

> **Moved 2026-10-25 from the private deployment repository** (author), where it was `docs/cordware_mobile_to_desktop.md` (at `ad94c1c`): shared UX guidance for every Cordware application, RRW and Residential alike.

**Status:** Design guidance  
**Scope:** Cordware applications, especially Residential Apps  
**Principle:** Responsiveness is universal; mobile optimisation is workflow-specific.

---

## 1. Purpose

Cordware applications do not need every screen to be equally optimised for every device size.

Some workflows are naturally performed on a phone, especially quick actions by staff or RAs while away from a desk. Other workflows depend on wide tables, comparison, filtering, dashboards, configuration, or bulk administration and can reasonably assume a notebook or desktop.

The design goal is therefore not "make every screen mobile-first." It is:

> **Every screen must remain usable and safe on a narrow viewport, but only workflows that are realistically expected to be performed on a phone need to be optimised for phone use.**

This avoids two opposite errors:

- building desktop-only interfaces for workflows that staff will actually perform on phones; and
- degrading complex administrative or analytical workflows merely to make them resemble phone-native screens.

Residential Apps should use one responsive web application, not separate desktop and mobile applications.

---

## 2. Three UX Classes

Every significant application surface should be classified during design as one of the following.

### 2.1 Mobile-critical

A workflow is **mobile-critical** when users are reasonably expected to perform it frequently on a phone, often immediately after or during an activity.

Requirements:

- design narrow-screen layout first;
- primary workflow should normally fit a single-column form;
- minimise typing;
- use sensible defaults and preselected values where safe;
- use large, touch-friendly controls;
- avoid hover-dependent interaction;
- avoid wide tables as the primary UI;
- keep the number of required fields low;
- make the primary action obvious;
- ensure completion is practical with one hand where feasible;
- test explicitly at phone viewport sizes.

A desktop version may use additional space, but should preserve the same simple interaction model.

### 2.2 Responsive general-use

A workflow is **responsive general-use** when it is reasonably likely to be used on either phone or desktop.

Requirements:

- function fully on narrow and wide screens;
- use layouts that naturally reflow;
- tables may become cards, stacked rows, or horizontally scrollable regions where appropriate;
- secondary controls may collapse into menus or disclosure panels;
- avoid assumptions about pointer precision, hover, or fixed viewport width;
- retain essentially the same capability on phone and desktop unless there is a clear usability reason not to.

### 2.3 Desktop-oriented

A workflow is **desktop-oriented** when its natural task involves comparison, bulk manipulation, dense tabular information, multi-column analysis, or configuration.

Examples include dashboards, roster administration, audit review, and batch processing.

Requirements:

- optimise the canonical working experience for notebook/desktop width;
- the page must still render safely on a phone;
- narrow-screen users must not encounter clipped controls, inaccessible actions, or unreadable content;
- it is acceptable for complex tables to scroll horizontally or for analytical panels to stack;
- low-frequency emergency actions should remain possible where practical;
- do not distort a naturally desktop-oriented workflow merely to claim full mobile parity.

Where useful, the mobile presentation may tell the user that the task is easier on a larger screen, but it should not use device detection to block access unnecessarily.

---

## 3. Initial Residential Apps Classification

The following is the initial design classification. It may be refined as workflows are tested.

| Module / surface | UX class | Rationale |
|---|---|---|
| Support Logs — Log encounter | **Mobile-critical** | An RF/RSLM may log immediately after speaking with a student |
| Support Logs — My follow-ups / assignments | **Mobile-critical** | Useful while moving around the residential college |
| Support Logs — Student view | **Responsive general-use** | Useful both in the field and at a desk |
| Support Logs — Personal RF/RSLM dashboard | **Responsive general-use** | Follow-up schedule checked on a phone; activity views use desktop width |
| Support Logs — Master overview/dashboard | **Desktop-oriented** | Comparison, trends, workload and drill-down |
| Support Logs — Opportunity/applicant batch review | **Desktop-oriented** | Batch input, comparison and consultation workflow |
| Support Logs — Audit review | **Desktop-oriented** | Dense administrative inspection |
| Support Logs — Authorization and configuration administration | **Desktop-oriented** | Tabular grant management and settings |
| Residential shared core — Staff roster administration | **Desktop-oriented** | Tabular maintenance and role/appointment management |
| Residential shared core — RA roster administration | **Desktop-oriented** | Similar bulk/tabular administration |
| RA Leave — Apply for leave | **Mobile-critical** | Standard short-form transaction likely to be done on phone |
| RA Leave — Balance | **Mobile-critical** | Frequently checked personal information |
| RA Leave — Own history | **Responsive general-use** | Looked up on either device, less often |
| RA Leave — Approver action | **Responsive general-use** | Approval may occur on phone or desktop |
| RA Leave — Team/dashboard view | **Desktop-oriented** | Team comparison and coverage planning |
| RA Leave — Administration / roster setup | **Desktop-oriented** | Dense configuration and bulk maintenance |
| RA Events — Submit / edit proposal | **Responsive general-use** | Can be done on phone, but longer proposals benefit from desktop |
| RA Events — Approval | **Responsive general-use** | Suitable for either form factor |
| RA Events — Budget/dashboard/admin | **Desktop-oriented** | Comparison, oversight and configuration |

Classification should be recorded in the relevant functional or design spec when a new substantial surface is introduced.

---

## 4. Support Logs: Mobile-Critical Encounter Logging

The encounter workflow is the strongest mobile-critical use case in Residential Apps.

The routine path should remain approximately:

> **Student → duration → encounter type → submit**

Additional fields should appear only when needed or remain optional.

For phone use:

- student search should work efficiently from the first field;
- recently encountered / assigned / followed-up students should be surfaced before wider directory search;
- duration should use tap-friendly preset values;
- encounter type should use a compact selection control;
- optional concern areas and follow-up controls should not obstruct the routine path;
- the submit action should remain easy to reach;
- validation errors should appear next to the relevant controls;
- the form should not depend on horizontal scrolling.

The mobile requirement reinforces the wider functional principle that routine encounter logging should take approximately 10–20 seconds.

---

## 5. Desktop-Oriented Administration Is Deliberate

Desktop-oriented surfaces should not be treated as failed responsive design.

For example, a staff-roster screen may reasonably show:

- staff identity;
- appointment type;
- start/end dates;
- active/retired state;
- application eligibility;
- related administration actions.

A wide table can be the best desktop representation of those data.

On narrow screens, the application may:

- stack row details;
- expose row actions through a menu;
- allow controlled horizontal scrolling;
- show a simplified summary before drill-down.

The requirement is **safe usability**, not identical visual layout or identical interaction density.

The same principle applies to Master dashboards, audit surfaces, and applicant-review batches.

---

## 6. One Application, Not Separate Mobile and Desktop Front Ends

Cordware should not create a separate mobile web application or native mobile app for these workflows unless a later requirement clearly justifies it.

Residential Apps should use:

- the same FastAPI routes;
- the same Jinja template system;
- the same authorization rules;
- the same underlying services;
- the same data model;
- responsive HTML/CSS to adapt presentation.

This reduces duplicated logic, security divergence, testing burden, and inconsistent behaviour.

A later native app would require a separate architectural decision.

---

## 7. Responsive Implementation Rules

### 7.1 Layout

Prefer:

- normal document flow;
- CSS Grid and Flexbox;
- fluid widths;
- `min()`, `max()`, and `clamp()` where appropriate;
- content-driven breakpoints;
- container queries for components whose layout should depend on available component width.

Avoid:

- fixed page widths;
- absolute-positioned primary layout;
- device-model-specific CSS;
- assumptions that desktop width is always available.

### 7.2 Breakpoints

Breakpoints should be chosen where the content ceases to work comfortably, not because a particular phone or tablet has a known pixel width.

Do not build rules around named devices such as "iPhone", "Galaxy", or a particular notebook model.

### 7.3 Forms

For mobile-critical and general-use forms:

- use semantic HTML form controls;
- provide explicit labels;
- choose appropriate input types;
- keep tap targets comfortably sized;
- preserve browser autofill where useful;
- avoid unnecessarily small radio buttons, links, or icon-only actions;
- keep destructive actions visually separated from routine actions.

### 7.4 Tables

Do not automatically replace every table with cards.

Choose based on task:

- small lists may stack into cards;
- comparison tables may remain tables with controlled horizontal scrolling;
- dense administrative tables may be desktop-oriented;
- key row actions must remain reachable at narrow widths.

### 7.5 Navigation

Navigation should remain coherent across device sizes.

A smaller viewport may collapse secondary navigation, but:

- route structure should not differ by device;
- permissions should never depend on viewport size;
- important destinations must remain reachable;
- hidden navigation must remain keyboard- and screen-reader-accessible.

---

## 8. Accessibility

Responsive design and accessibility are related but not interchangeable.

At minimum:

- semantic HTML should be preferred over custom controls;
- all interactive controls must be keyboard accessible;
- focus indication must remain visible;
- touch targets should be comfortably sized;
- text should remain legible without requiring horizontal page scrolling;
- zoom must not be disabled;
- information must not depend solely on colour;
- layouts must tolerate larger text and browser zoom.

No desktop-oriented classification removes these requirements.

---

## 9. Authorization and Device Size

Device size must never change authorization.

For example:

- a Master opening a Support Logs dashboard on a phone has the same authorization as on desktop;
- a phone viewport must not expose fewer security checks because it uses a simplified presentation;
- hiding a control through CSS is not an authorization mechanism;
- sensitive actions must always be protected server-side.

Responsive behaviour changes presentation, not trust boundaries.

---

## 10. Testing Expectations

Testing should reflect the UX classification.

### Mobile-critical

Must receive explicit automated and/or browser verification at representative narrow viewport sizes as well as desktop width.

Verify:

- primary workflow completion;
- no horizontal page overflow;
- controls remain tappable;
- validation remains visible;
- navigation remains available;
- modal/dialog behaviour, if any, works on narrow screens.

### Responsive general-use

Verify both narrow and desktop layouts for representative primary workflows.

### Desktop-oriented

Primary functional testing may use desktop width, but at least one narrow-screen check should verify:

- page remains navigable;
- content does not become inaccessible;
- primary actions are still reachable;
- no security-sensitive action disappears in a way that creates an inconsistent state.

Viewport tests should target representative widths or layout boundaries rather than named hardware devices.

---

## 11. Design Review Rule

When adding a new substantial route or workflow, the design/segment plan should answer:

1. What is the UX class: mobile-critical, responsive general-use, or desktop-oriented?
2. What does the user need to accomplish on a phone?
3. What, if anything, is intentionally easier only on desktop?
4. What layout change occurs when the content becomes too narrow?
5. What viewport coverage belongs in acceptance/browser tests?

This classification should be made before implementation rather than inferred from whatever layout emerges.

---

## 12. Core Rule

The project-wide rule is:

> **Responsiveness is universal; mobile optimisation is workflow-specific.**

Every Cordware application should be robust across viewport sizes. Mobile-critical workflows should be genuinely efficient on phones. Desktop-oriented analytical and administrative workflows may take advantage of larger screens without being artificially reduced to a phone-first interaction model.
