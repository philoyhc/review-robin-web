# Review Robin Web — Low-Intensity AI-Assisted Workplan

**Status:** Draft workplan  
**Source:** Based on `Technology Stack And Repo Structure`  
**Purpose:** Provide a low-intensity, staged path for building Review Robin Web with heavy AI assistance  
**Audience:** A capable citizen developer or small team that is not yet fully familiar with every technology in the stack

---

## 1. Framing

This workplan assumes a deliberately low-intensity build style.

The aim is not to rush toward a production application. The aim is to build knowledge, reduce uncertainty, and produce working slices in an order that makes sense. Each segment should end with something visible, testable, and understandable.

The plan assumes heavy AI assistance through GitHub/Codex-style workflows. AI should be used for:

- generating initial code skeletons;
- explaining unfamiliar framework concepts;
- drafting tests;
- reviewing code for consistency;
- translating functional requirements into issues;
- producing migration scripts;
- writing documentation;
- debugging deployment errors;
- keeping implementation aligned with the functional specification.

The human role remains essential:

- decide what the system should do;
- keep scope disciplined;
- verify that generated code matches intent;
- test real workflows;
- decide when a segment is good enough;
- avoid building attractive but unnecessary features.

---

## 2. Guiding principles

### 2.1 Build in visible slices

Each segment should produce a working slice of the application, not just infrastructure.

A good segment outcome is something like:

> “I can create a session and see it listed.”

or:

> “A reviewer can open a test link, enter responses in a table, save, and return later.”

Avoid long stretches where only invisible setup is happening.

### 2.2 Keep each segment conceptually narrow

Do not learn Azure, FastAPI, SQLAlchemy, HTMX, AG Grid, authentication, background jobs, and export generation all at once.

Each segment should foreground only one or two unfamiliar technologies.

### 2.3 Prefer boring patterns

Use conventional project layout, conventional route names, conventional tests, and conventional database models.

This makes AI assistance more reliable and makes future troubleshooting easier.

### 2.4 Treat tests as learning aids

Tests are not just quality controls. In this project, tests are also a way of making the domain concrete.

A test called `test_full_matrix_assignments_exclude_self_review` is a piece of executable documentation.

### 2.5 Do not overbuild early

The first useful version does not need:

- full multi-instrument support;
- full RuleBased parity;
- complex reminder targeting;
- rich dashboards;
- production-grade access reviews;
- perfect styling;
- full browser end-to-end tests.

Those can be added later after the core loop is real.

---

## 3. Overall build shape

The project is built in fifteen low-intensity segments.

The first ten segments produce a real end-to-end system:

1. Orientation and repository setup
2. Azure hello-world deployment
3. Authentication proof-of-concept
4. Core data model and migrations
5. Operator session setup MVP
6. Import and validation MVP
7. Assignment generation MVP
8. Reviewer review-surface MVP
9. Invitation, monitoring, and reminder MVP
10. Instrument builder MVP

The remaining five segments move it toward fuller Review Robin parity and operational maturity:

11. Cleaning up unfinished business (segment-1–10 follow-ups)
12. Export, audit, and retention MVP
13. RuleBased assignment builder
14. Production hardening
15. Operator polish and documentation

(Multi-instrument sessions were originally planned as their own
segment but shipped early as part of Segments 10A → 10D; the
unfinished items live in `guide/unfinished_business.md` #27 / #28 /
#29 and the original plan is archived as
`guide/archive/segment_13_multi_instrument_sessions_superseded.md`.)

---

## 4. Segment 1 — Orientation and repository setup

### Goal

Create a clean GitHub repository that AI tools can work with reliably.

### Main learning focus

- Repository organization
- Python project layout
- GitHub branch / pull request rhythm
- How to instruct AI coding agents through repository documents

### Build outcome

A repository exists with:

- basic folder structure;
- `README.md`;
- `AGENTS.md` / `CLAUDE.md` (byte-identical twins);
- `spec/functional_spec.md`;
- Python project configuration;
- empty app skeleton;
- initial test skeleton.

### Work items

1. Create GitHub repository.
2. Add the recommended folder structure from `Technology Stack And Repo Structure`.
3. Add `README.md` explaining the project in plain terms.
4. Add `AGENTS.md` with instructions for AI coding agents.
5. Add `pyproject.toml` with core dependencies.
6. Add a minimal `app/main.py`.
7. Add `tests/` with one smoke test.
8. Create first pull request and merge.

### AI assistance prompts

Useful prompts for this segment:

> Create a minimal FastAPI project skeleton using Python 3.12, pytest, and the folder structure described in `AGENTS.md` / `CLAUDE.md` (Stack summary).

> Review this repository layout for consistency with AGENTS.md. Do not add functionality. Identify missing files or confusing names.

> Generate a minimal smoke test for the FastAPI app.

### Done when

- The repository installs locally.
- A minimal test passes.
- The repository has enough structure for future AI-assisted tasks.
- The first PR has been created and merged.

### Keep deliberately out of scope

- Azure deployment
- database setup
- authentication
- frontend styling
- actual Review Robin logic

---

## 5. Segment 2 — Azure hello-world deployment

### Goal

Prove that the app can deploy from GitHub to Azure App Service.

### Main learning focus

- Azure App Service basics
- GitHub Actions deployment
- App settings
- Logs and startup errors

### Build outcome

A hello-world FastAPI app is deployed to Azure App Service and reachable in a browser.

### Work items

1. Create Azure App Service for Linux.
2. Configure Python runtime.
3. Add or refine startup command.
4. Create GitHub Actions deployment workflow.
5. Store deployment credentials or configure publish profile / federated credential according to chosen method.
6. Deploy minimal app.
7. Confirm health endpoint works.
8. Confirm logs can be viewed.

### AI assistance prompts

> Generate a GitHub Actions workflow to deploy this Python FastAPI app to Azure App Service for Linux. Use the simplest code-deployment path.

> Diagnose this Azure App Service startup error. Here is the log output. Explain the likely cause and the smallest fix.

> Add a `/health` route suitable for Azure App Service health checks.

### Done when

- The app is deployed from GitHub Actions.
- `/health` returns a successful response.
- You know where to view deployment and runtime logs.
- You can make a trivial change, push it, and see it deployed.

### Keep deliberately out of scope

- database
- authentication
- production slots
- custom domain
- storage
- email

---

## 6. Segment 3 — Authentication proof-of-concept

### Goal

Prove that Microsoft sign-in can identify a user and pass identity information into the app.

### Main learning focus

- App Service Easy Auth
- Microsoft Entra sign-in flow
- Reading authenticated user headers
- Separating authentication from authorization

### Build outcome

A signed-in user can visit a test page and see their authenticated identity as received by the application.

### Work items

1. Enable App Service Authentication / Easy Auth.
2. Configure Microsoft identity provider.
3. Add a simple `/me` route.
4. Read identity headers supplied by App Service.
5. Display user email/name for debugging.
6. Add a fallback behavior for local development without Easy Auth.
7. Add tests for identity parsing logic.

### AI assistance prompts

> Write a small FastAPI dependency that reads App Service Easy Auth headers and returns an AuthenticatedUser object. Include a local-development fallback.

> Review this identity-parsing code. What assumptions does it make about Easy Auth headers?

> Add tests for parsing authenticated-user headers.

### Done when

- Visiting the deployed app requires Microsoft sign-in.
- The app can read the signed-in user's email or principal name.
- Local development still works using a controlled fake identity.
- The code clearly distinguishes authentication from authorization.

### Keep deliberately out of scope

- role management
- session operator permissions
- reviewer link access
- invitation links
- full user database

---

## 7. Segment 4 — Core data model and migrations

### Goal

Create the database foundation for sessions, users, reviewers, reviewees, instruments, assignments, responses, and audit events.

### Main learning focus

- SQLAlchemy 2.x models
- Alembic migrations
- PostgreSQL connection
- test database patterns

### Build outcome

The app has a working relational schema with migrations and basic database tests.

### Work items

1. Add SQLAlchemy database setup.
2. Add Alembic.
3. Define initial models:
   - User
   - Session
   - SessionOperator
   - Reviewer
   - Reviewee
   - Instrument
   - InstrumentDisplayField
   - InstrumentResponseField
   - Assignment
   - Response
   - Invitation
   - AuditEvent
4. Generate initial migration.
5. Apply migration locally.
6. Connect deployed app to development PostgreSQL.
7. Add test fixtures.
8. Add basic model tests.

### AI assistance prompts

> Draft SQLAlchemy 2.x models for the core Review Robin Web entities. Use `Mapped[]` and `mapped_column`. Keep relationships explicit.

> Generate an Alembic migration for these models and check for missing indexes on common lookup paths.

> Review this schema for the ability to export long-format and wide-format review data.

### Done when

- Models exist.
- Migration applies cleanly.
- Tests can create a session with reviewers, reviewees, an instrument, assignments, and responses.
- The schema can support the core functional spec.

### Keep deliberately out of scope

- polished UI
- imports
- assignment generation logic
- autosave
- email
- export generation

---

## 8. Segment 5 — Operator session setup MVP

### Goal

Allow an operator to create and view a basic review session through the web UI.

### Main learning focus

- FastAPI routes
- Jinja2 templates
- form handling
- basic authorization checks

### Build outcome

An authenticated operator can create a session, view a sessions list, and open a session detail page.

### Work items

1. Add operator routes.
2. Add session list page.
3. Add create-session form.
4. Add session detail page.
5. Add basic operator ownership.
6. Add simple permission checks.
7. Add audit event for session creation.
8. Add tests for session creation and access control.

### AI assistance prompts

> Implement a simple operator session list and create-session form using FastAPI and Jinja2. Keep route handlers thin and put business logic in `session_service.py`.

> Add server-side permission checks so only the session owner can view the session detail page.

> Generate tests for creating a session and denying access to a non-operator.

### Done when

- Operator can create a session.
- Operator sees their sessions.
- Unauthorized users cannot access another operator's session.
- Session creation writes an audit event.

### Keep deliberately out of scope

- reviewer/reviewee upload
- instruments beyond a placeholder
- activation
- invitation sending
- reviewer surface

---

## 9. Segment 6 — Import and validation MVP

### Goal

Allow the operator to populate reviewers and reviewees and validate basic setup.

### Main learning focus

- file upload handling
- CSV parsing
- import preview
- validation results
- error/warning/info pattern

### Build outcome

An operator can upload reviewer and reviewee CSV files, preview import results, save valid rows, and see validation issues.

### Work items

1. Define simple reviewer CSV format.
2. Define simple reviewee CSV format.
3. Add upload routes.
4. Parse CSV files.
5. Show import preview.
6. Validate required columns.
7. Validate duplicate identifiers.
8. Validate email format where applicable.
9. Save valid rows.
10. Add setup validation page.
11. Add tests for import and validation.

### AI assistance prompts

> Build a CSV import service for reviewers with preview, row-level validation, and duplicate email detection.

> Create a validation result object with severity levels: Error, Warning, Info. Use it for reviewer and reviewee imports.

> Generate tests for malformed reviewer CSV uploads.

### Done when

- Reviewers can be imported.
- Reviewees can be imported.
- Invalid rows are clearly reported.
- Duplicate identifiers are caught.
- Setup validation shows useful errors and warnings.

### Keep deliberately out of scope

- Excel upload
- complex import mapping UI
- RuleBased status fields beyond simple optional columns
- assignment generation
- reviewer response UI

---

## 10. Segment 7 — Assignment generation MVP

### Goal

Create assignments for FullMatrix and ManualAssignment modes.

### Main learning focus

- domain services
- deterministic generation logic
- assignment validation
- preview counts

### Build outcome

An operator can generate FullMatrix assignments or upload ManualAssignment rows, preview results, and save assignments.

### Work items

1. Add assignment mode to session.
2. Implement FullMatrix generation.
3. Add self-review exclusion option.
4. Add assignment preview page.
5. Add save-generated-assignments action.
6. Define manual assignment CSV format.
7. Add manual assignment import.
8. Validate reviewer/reviewee references.
9. Validate duplicate assignment rows.
10. Add tests for FullMatrix and ManualAssignment.

### AI assistance prompts

> Implement FullMatrix assignment generation for a session, with an option to exclude self-review when reviewer and reviewee emails match.

> Add assignment preview counts: total assignments, reviewers covered, reviewees covered, orphan reviewers, orphan reviewees.

> Generate tests for manual assignment import with missing reviewer references.

### Done when

- FullMatrix mode can generate assignments.
- ManualAssignment mode can import assignments.
- Operator can preview assignment counts before activation.
- Assignment data is stored in the database.

### Keep deliberately out of scope

- RuleBased assignment builder
- multi-instrument assignments unless required early
- random allocation policies
- invitation sending

---

## 11. Segment 8 — Reviewer review-surface MVP

### Goal

Allow a reviewer to access assigned work, enter responses in a tabular surface, save, and submit.

### Main learning focus

- reviewer routing
- grid component integration
- response saving
- validation
- submission state

### Build outcome

A reviewer can open a test review link, complete a tabular review form, save responses, submit, and return later to see saved data.

### Work items

1. Add reviewer dashboard route.
2. Add reviewer assignment lookup.
3. Add a simple single-instrument review surface.
4. Render assignment rows.
5. Render response fields.
6. Add response save endpoint.
7. Add save-state feedback.
8. Add submit action.
9. Validate required fields on submit.
10. Add reviewer access tests.
11. Add response save/submit tests.

### AI assistance prompts

> Build a reviewer dashboard that shows assignments for the authenticated reviewer only.

> Create a JSON endpoint for saving one response cell. It should verify that the current user is the assigned reviewer.

> Implement a simple tabular review page first with ordinary HTML inputs before introducing AG Grid.

> Now replace the simple table with AG Grid while keeping the same save endpoint.

### Done when

- Reviewer sees only their own assignments.
- Reviewer can enter response values.
- Responses are saved centrally.
- Reviewer can submit completed work.
- Operator can see completion status change.

### Keep deliberately out of scope

- polished spreadsheet UX
- multi-tab multi-instrument review
- complex autosave conflict handling
- reminder emails
- export generation

### Low-intensity advice

Start with a plain HTML table before introducing AG Grid. This makes the business logic real before the frontend grid adds complexity.

---

## 12. Segment 9 — Invitation, monitoring, and reminder MVP

### Goal

Allow operators to activate a session, send invitations, monitor progress, and send simple reminders.

### Main learning focus

- activation workflow
- email templates
- background job queue
- monitoring aggregates
- reminder targeting

### Build outcome

An operator can activate a session, send invitation emails, monitor reviewer progress, and send reminders to incomplete reviewers.

### Work items

1. Add activation action.
2. Freeze or mark active configuration.
3. Generate invitation records.
4. Generate individualized links.
5. Add invitation email template.
6. Implement email send service.
7. Add queue-based batch sending.
8. Track invitation status.
9. Add monitoring dashboard.
10. Add simple reminder action for incomplete reviewers.
11. Add tests for activation and invitation creation.

### AI assistance prompts

> Implement a session activation service that validates readiness, creates invitation records, and writes an audit event.

> Build an email template renderer with merge fields for reviewer name, session name, deadline, help contact, and review link.

> Add a monitoring query that returns invited, opened, started, submitted, and incomplete counts.

### Done when

- Operator can activate session.
- Invitations can be sent.
- Invitation status is tracked.
- Monitoring dashboard shows meaningful progress.
- Operator can send reminders to incomplete reviewers.

### Keep deliberately out of scope

- sophisticated reminder filters
- bounce tracking unless readily available
- rich email editor
- production-grade bulk email tuning

---

## 13. Segment 10 — Instrument builder MVP

### Goal

Let operators rename, edit, add, reorder, and delete response fields on the session's single Default Instrument before activation.

### Main learning focus

- per-field schema-vs-data trade-offs
- form-builder UX in plain HTML
- cascade safety when a field is deleted with saved responses
- audit trail for instrument structure changes

### Build outcome

An operator can shape the questions reviewers see — beyond the seed `rating` integer + `comments` long-text pair — without leaving the operator UI.

### Work items

1. Operator page listing the session's Instrument's response fields.
2. Add / edit / delete / reorder field actions, with confirm + cascade warnings on destructive paths.
3. Field types: integer (with min/max), short-text, long-text, yes/no.
4. Server-side validation of required + per-type validation JSON on submit.
5. Audit events: `instrument.field_added`, `instrument.field_updated`, `instrument.field_deleted`, `instrument.fields_reordered`.
6. Tests for the new routes, cascade behaviour, and reviewer-surface auto-adapt.

### Out of scope

- multi-instrument (planned for Segment 13 originally; ended up
  shipping early as part of Segments 10A → 10D — see archived
  `guide/archive/segment_13_multi_instrument_sessions_superseded.md`)
- conditional / branching field logic
- file-upload field type
- editing the instrument after activation locks it (revisit later if needed)

---

## 14. Segment 11 — Cleaning up unfinished business

### Goal

Pick up the segment-1–10 follow-ups before opening export /
RuleBased / production-hardening work.

### Build outcome

The audit at
`guide/archive/segment_1-10_unfinished.md` (2026-05-03) catalogued
items planned for Segments 1–10 that didn't ship. Segment 11 is the
focused pass that lands them — or formally defers them — before the
rest of the post-MVP roadmap opens.

### Work items

The detailed punch list lives in
`guide/archive/segment_11A_cleaning_up_unfinished_business.md` (Tier 1
tiny cleanups → Tier 2 decisions → Tier 3 small features → Tier 4
medium features). Each item lands as its own PR. The Session Home
rebuild + Quick Setup card portion of the Tier 4 bundle is split
out into `guide/archive/segment_11B_session_home.md`.

### Done when

- All items in
  `guide/archive/segment_11A_cleaning_up_unfinished_business.md` Tier 1 +
  Tier 2 + Tier 3 are landed or have a written decision.
- Tier 4 items are either landed or moved to
  `guide/unfinished_business.md` with an explicit deferral.
- Segment 11B (Session Home rebuild + Quick Setup card) lands.

---

## 15. Segment 12 — Export, audit, and retention MVP

### Goal

Produce the final dataset and support basic retention/deletion.

### Main learning focus

- CSV generation
- Excel generation
- long vs wide export shapes
- audit trail
- retention actions

### Build outcome

An operator can export session responses as CSV/Excel and apply a basic retention action.

### Work items

1. Define long-format export.
2. Define wide-format export.
3. Add export options page.
4. Generate CSV export.
5. Generate Excel export.
6. Store generated export in Blob Storage or return as download.
7. Add export audit event.
8. Add export readiness summary.
9. Add delete-response-data action.
10. Add retention audit event.
11. Add tests for export shapes and deletion behavior.

### AI assistance prompts

> Generate a long-format export service for Review Robin responses. Include reviewer, reviewee, instrument, assignment context, response field, response value, and submission status.

> Generate a wide-format export service with one row per reviewer-reviewee-instrument assignment.

> Add tests proving that incomplete assignments are included with completion status in the export.

### Done when

- Operator can export a usable CSV.
- Operator can export a usable Excel file.
- Export includes enough metadata for downstream analysis.
- Export action is audited.
- Basic deletion/retention action exists and is audited.

### Keep deliberately out of scope

- advanced analytics
- dashboards of results
- Power BI integration
- anonymized exports unless specifically required

---

## 16. Segment 13 — RuleBased assignment builder

### Goal

Add the rule-based assignment logic that gives Review Robin much of its power.

### Main learning focus

- translating existing RuleBased concepts into web app form;
- rule preview;
- deterministic assignment generation;
- operator explainability.

### Build outcome

An operator can define simple rules, preview generated assignments, and apply the results.

### Work items

1. Define rule schema.
2. Add rule editor.
3. Support reviewer-side criteria.
4. Support reviewee-side criteria.
5. Support include/exclude semantics.
6. Support allow/exclude self-review.
7. Support allocate-all policy.
8. Add deterministic RandomN-per-reviewer later, if required.
9. Add rule preview.
10. Add tests for rule outputs.

### Done when

- RuleBased mode can generate assignments equivalent to the core existing concept.
- Operator can preview counts before committing.
- Rule outputs are test-covered and auditable.

---

## 17. Segment 14 — Production hardening

### Goal

Make the system safer, more observable, and more supportable for real use.

### Main learning focus

- performance;
- logging;
- error handling;
- backups;
- deployment slots;
- operational documentation.

### Build outcome

The app is credible for a real internal pilot.

### Work items

1. Add deployment slot workflow.
2. Add production app settings discipline.
3. Add structured logging.
4. Add Application Insights dashboards.
5. Add database indexes for hot paths.
6. Add rate limiting where appropriate.
7. Add backup/restore notes.
8. Add error pages.
9. Review permission checks.
10. Add basic accessibility review of reviewer grid.
11. Add operator runbook.
12. Add incident/recovery notes.

### Done when

- A real pilot could run with known risks.
- Logs are useful.
- Deployment has rollback path.
- Operator has a runbook.
- Permission model has been reviewed.

---

## 18. Segment 15 — Operator polish and documentation

### Goal

Make the app understandable to someone who did not build it.

### Main learning focus

- onboarding;
- explanatory UI;
- documentation;
- handover materials.

### Build outcome

A new operator can understand the system, set up a test session, and run through the workflow.

### Work items

1. Add Start Here page.
2. Add inline guidance to setup screens.
3. Add validation explanations.
4. Add sample CSV templates.
5. Add sample session fixture.
6. Add operator guide.
7. Add administrator guide.
8. Add developer setup guide.
9. Add troubleshooting guide.
10. Add known limitations page.

### Done when

- A new operator can run a test session using documentation.
- A future developer can set up the app locally.
- Known limitations are documented honestly.

---

## 19. Suggested low-intensity cadence

A sustainable rhythm might be:

- one small GitHub issue at a time;
- one branch per issue;
- one pull request per issue;
- merge only when tests pass;
- stop after each segment and write a short reflection;
- update docs as part of the segment, not at the end of the whole project.

For evening-and-weekend work, a realistic pattern is:

```text
Week 1–2     Segment 1: Repository setup
Week 3       Segment 2: Azure hello-world deployment
Week 4       Segment 3: Authentication proof-of-concept
Week 5–7     Segment 4: Core data model
Week 8–10    Segment 5: Operator session setup
Week 11–13   Segment 6: Import and validation
Week 14–15   Segment 7: Assignment generation
Week 16–20   Segment 8: Reviewer surface
Week 21–23   Segment 9: Invitations and monitoring
Week 24       Segment 10: Instrument builder
Week 25       Segment 11: Cleaning up unfinished business
Week 26–28   Segment 12: Export, audit, and retention
```

This is not a deadline. It is a low-pressure sequencing guide.

Some segments will go faster because AI assistance handles the boilerplate. Some will go slower because Azure, authentication, or frontend grid work will produce unfamiliar errors.

---

## 20. How to break segments down later

Each segment can later be decomposed into smaller issues using this pattern:

```text
Issue title:
  Add reviewer CSV import preview

Purpose:
  Allow operator to upload reviewer CSV and see parsed rows before saving.

Scope:
  - route
  - template
  - import service
  - validation result object
  - tests

Out of scope:
  - Excel upload
  - saving rows to database
  - complex column mapping

Acceptance criteria:
  - valid CSV shows preview rows
  - missing required column shows blocking error
  - duplicate email shows row-level error
  - tests pass
```

This pattern keeps AI-assisted tasks bounded.

Avoid prompts like:

> Build the whole import system.

Prefer prompts like:

> Implement only reviewer CSV preview. Do not save to the database yet. Add tests for missing required columns and duplicate emails.

---

## 21. Recommended AI workflow

### 20.1 Before asking AI to code

Write or update:

- the issue description;
- the acceptance criteria;
- the out-of-scope list;
- any relevant data model notes.

### 20.2 Ask AI for a plan first

Useful prompt:

> Read AGENTS.md (or its twin CLAUDE.md) and the issue below. Propose a minimal implementation plan. Do not write code yet.

### 20.3 Ask for implementation in small patches

Useful prompt:

> Implement step 1 only: add the service function and tests. Do not add UI yet.

### 20.4 Ask for review

Useful prompt:

> Review this PR for consistency with the architecture. Look for business logic in routes, missing permission checks, missing tests, and SQLAlchemy 2.x style violations.

### 20.5 Ask for documentation update

Useful prompt:

> Update the developer notes to explain how this feature works and how to test it locally.

---

## 22. Risk points to expect

### 21.1 Azure deployment errors

Likely early friction:

- wrong startup command;
- package installation issues;
- environment variables not set;
- wrong Python version;
- GitHub Actions authentication problems.

Mitigation:

- keep hello-world deployment very small;
- do not add database or auth before deployment is proven;
- copy logs into AI prompts for diagnosis.

### 21.2 Authentication confusion

Likely friction:

- difference between authentication and authorization;
- Easy Auth headers available only in Azure, not local dev;
- email vs UPN matching;
- test users not matching imported reviewer emails.

Mitigation:

- build `/me` route early;
- create a local fake-auth mode;
- write identity parsing tests;
- defer complex roles until the identity proof-of-concept works.

### 21.3 SQLAlchemy complexity

Likely friction:

- older 1.x patterns suggested by AI;
- relationship configuration errors;
- migration drift;
- test database setup.

Mitigation:

- state SQLAlchemy 2.x style clearly in `AGENTS.md`;
- ask AI to review for 2.x consistency;
- keep first schema small;
- use migrations from the beginning.

### 21.4 Reviewer grid complexity

Likely friction:

- frontend grid integration;
- autosave edge cases;
- keyboard navigation;
- validation display;
- multi-tab behavior.

Mitigation:

- start with plain HTML table;
- get save/submit logic working first;
- introduce grid component later;
- keep grid-specific code isolated.

### 21.5 Scope expansion

Likely friction:

- adding analytics;
- adding elaborate dashboards;
- adding multi-instrument too early;
- adding full RuleBased parity before the simple loop works.

Mitigation:

- keep the core acceptance path visible;
- defer attractive features;
- treat the first end-to-end loop as the milestone.

---

## 23. First end-to-end milestone

The first major milestone is not production readiness. It is this:

> A test operator can create a session, upload reviewers and reviewees, generate assignments, activate the session, invite a test reviewer, receive responses through an online table, and export the resulting dataset.

This proves the web architecture.

After this milestone, the remaining work is improvement and parity:

- better UI;
- RuleBased;
- multi-instrument;
- reminders;
- audit polish;
- retention discipline;
- deployment hardening;
- documentation.

Before this milestone, avoid deep polish.

---

## 24. Final note

This workplan intentionally does not assume mastery of all technologies at the start.

It uses the project itself as the learning path:

1. deploy a tiny app;
2. authenticate a user;
3. store a session;
4. import rows;
5. generate assignments;
6. collect responses;
7. export data.

Each step is understandable on its own. Each step gives AI assistance a bounded target. Each step produces something useful enough to test before moving on.

