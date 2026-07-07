# Review Robin Web — Design Rationale

## 1. Introduction

Review Robin Web (RRW) is a web application for running structured institutional review cycles — appointment and reappointment review, admissions, peer and panel review, awards and scholarship decisions, student-leadership selection, course-wide small-group peer reviews, and similar processes.

This document explains the reasoning behind its design: the class of problem it targets, the two projects that shaped it (a predecessor and an inspiration), the constraints that made it look the way it does, and the trade-offs it knowingly accepts. It presents the rationale for the design, not a feature list. Where a decision could plausibly have gone another way, the point is to record why it went the way it did.

The document is drafted with the help of Claude Opus 4.8, with access to the GitHub repositories of both Review Robin (VBA) and Review Robin Web.

---

## 2. The problem, generalised

### 2.1 The shape of the problem

Strip away the domain specifics and the same structure recurs across all these review cycles. There is a set of **reviewers** and a set of **reviewees**. The mapping between them is usually **many-to-many and possibly asymmetric** — not one-to-one, not always everyone-reviews-everyone, and frequently *not* a case of a group evaluating itself. A reviewer may also assess the same person in more than one context, under more than one set of criteria.

The institution ultimately needs a **structured, analysable dataset** out the other end. The substance being collected is **human evaluative judgment** — commentary, ratings, contextual interpretation — not the retrieval of facts a system already holds. And the resulting judgments may later need to be **interpreted, explained, and defended** in institutional settings.

A practical fact sits underneath all of this: reviewer-facing work in these cycles is often **tabular**. A reviewer may have to work through dozens or well over a hundred rows, each representing a reviewee. The one-form-per-person interaction pattern that generic tools assume is a poor fit for that reality.

### 2.2 Why it is structurally hard

These cycles are not hard because institutions lack forms, email, or spreadsheets. They are hard because several kinds of complexity arrive at once:

- **Assignment complexity** — deciding who should review whom, by rule rather than by hand, and re-deciding it every time a roster changes.
- **Template complexity** — ensuring the right questions appear in the right format for the right reviewer.
- **Scale** — letting a reviewer move through many rows efficiently.
- **Data-quality requirements** — ensuring what comes back can actually be collated and analysed, rather than arriving as a pile of inconsistent files.
- **Defensibility requirements** — being able to reconstruct, after the fact, what was asked, who was asked to review whom, what was returned, and how the dataset was formed.
- **Operational practicality** — staying usable by ordinary administrative staff, not only by developers.

Without a structured system, the institution ends up doing the hardest work manually at *both* ends: translating review logic into reviewer-specific instruments up front, and normalising, de-duplicating, and re-aligning the returns at the back. The middle — reviewers submitting many separate forms, skipping rows, receiving files that don't clearly match their assignment — is where usability quietly erodes data quality.

### 2.3 Why the obvious tools don't fit

Two tools are what people often reach for, and each fails on the same axis.

**Passing spreadsheets around** gives a genuinely good tabular surface — dense, familiar, sortable, customisable. But the *routing* is entirely manual: who gets which sheet, chasing them back, reconciling versions, and living with the fact that a shared workbook gives everyone more access than they should have. The surface is right; the distribution and control are wrong.

**Generic feedback forms** (Microsoft Forms, Qualtrics, and the like) are easy to send and collect, but they are routing-blind — they cannot assign specific reviewers to specific reviewees — and they are not easily set up to be tabular. The distribution is right; the routing and surface are wrong.

The hard part that neither addresses is the *routing itself*: matching a pool of reviewers to a pool of reviewees by rule. That is the unsolved centre of the problem, and — as far as could be found — no commercial off-the-shelf product does it.

---

## 3. Two lineages: a predecessor and an inspiration

RRW did not appear from nothing. Two projects shaped it, and holding both in view explains most of its design.

### 3.1 Review Robin (VBA) — the predecessor

RRW is the successor to **Review Robin**, an Excel/VBA tool that attacked the same problem from inside the Microsoft 365 stack: Excel and VBA to generate reviewer-specific tabular instruments, Outlook and M365 identity for distribution, Microsoft Forms and SharePoint-backed storage for collection, and Power Query for downstream collation. By its stabilised endpoint (v1.40) it was roughly 10,900 lines of VBA across 21 modules — no longer a macro workbook but a small operational application embedded in Excel.

The reasoning behind that architecture is worth stating, because RRW inherits its *philosophy* even as it changes the *platform*:

- The hardest problem was identified early as **generation of reviewer-specific tabular instruments that can later be collated reliably** — not workflow routing. Everything else was arranged around that.
- Excel was central because the reviewer task is tabular: dense row entry, familiar interaction, sorting and filtering, durable file artifacts.
- The workbook was intentionally kept as a **visible control surface** — inspectable, rerunnable, and handoverable — because the project was about operational tractability, not only technical possibility.
- The operator was kept **in the loop by design**: the system's job was to make the loop more reliable, not to remove the human from it.

Two things about Review Robin matter most for understanding RRW. First, its technology choice was rational precisely because it *never tried to replace the platform* — it orchestrated Excel and Outlook rather than rebuilding them, which is why 10,900 lines sufficed where a standalone rebuild would have needed several times that. Second, v1.40 was treated as a deliberate **stopping point**: the richer ambitions (dashboards, reminders, response tracking, multi-session support, aggregation, a shared cross-operator record, stronger access control, tighter identity integration) were recognised as *good ideas that collectively cross the citizen-development boundary*. They were parked, explicitly, as either aspirational notes or as requirements for a future enterprise rebuild.

**RRW is that future rebuild.** Almost every capability parked at the Review Robin boundary — multi-session organisation, tracking and reminders, aggregation and per-audience visibility, real access control, identity integration — is now in scope precisely because the platform underneath changed.

### 3.2 TEAMMATES — the inspiration

The closest existing tool to what RRW set out to do is **TEAMMATES**, the free, open-source peer-feedback platform built at NUS by School of Computing faculty and students since 2010. It is the single biggest influence on RRW, and the acknowledgement is genuine. TEAMMATES already does the thing that no known commercial off-the-shelf product does: **rule-based assignment** — matching who reviews whom by rule rather than by hand. It scales to large cohorts, emails each participant a personal link, and offers per-question visibility controls. RRW borrows all of that framing.

RRW differs on three axes, each a consequence of a different target setting:

- **Asymmetric populations.** TEAMMATES is organised around peer review within courses, where the reviewing and reviewed populations are one and the same (students in a course evaluating themselves, their teammates, or other teams). RRW keeps the reviewer and reviewee pools **separate**, so any pool can review any other — a panel evaluating candidates, for instance, with no assumption that reviewers are themselves reviewed.
- **Roster ergonomics at scale.** TEAMMATES is typically populated by pasting rows in batches; RRW imports rosters by CSV, which matters when a pool runs to 1,500+.
- **Inside the institution.** TEAMMATES runs as a Google-hosted service; RRW uses Microsoft 365 sign-in and stays inside the institution's own tenant.

The differences are real, but the kinship runs deeper than they do. What unites RRW and TEAMMATES is the thing both do that nothing off-the-shelf does: **rule-based assignment at cohort scale.** Asymmetric pools are RRW's *extension* of that idea, not a rejection of the symmetric case — symmetric peer review is simply the special case where the two pools are the same population, self-review switched off, and small groups expressed through group-scoped rules. So RRW is best read as a **superset**: it can run the large symmetric course peer review that TEAMMATES was built for *and* the asymmetric panel review that TEAMMATES was not — and, even in the symmetric case, slightly more smoothly, because rosters arrive by CSV rather than pasted a hundred rows at a time.

There is also a timing dimension. RRW began as a private, local team-tool idea. Its developer has been a long-time, active TEAMMATES user — running peer review across 1,200 students in small groups of five or six — while Review Robin was built to plug a different gap: asymmetric reviews for smaller populations (say, 30 reviewers across 90 reviewees), scalable in principle. If TEAMMATES really winds down, its users — the developer's own large course among them — will need a replacement, and the space it occupied opens. That is part of why a tool that started as a proof of concept may become a plausible candidate for wider adoption. And that possibility raises the bar for the very things RRW invests in: identity, accountability, and staying in-tenant.

---

## 4. Why RRW exists now: two walls that came down

The most important design fact about RRW is not a feature. It is *why it was buildable at all*, when its immediate predecessor (Review Robin) deliberately stayed in Excel.

Review Robin went the VBA route because two walls made a web/Azure application look infeasible:

1. **A technical wall.** Building and maintaining a real web application — data model, migrations, auth, deployment, the whole substrate that Excel and Outlook otherwise supply for free — was more than a single citizen developer could realistically carry.
2. **An institutional wall.** Even a well-built application needs somewhere sanctioned to run, with an identity story and a data policy the institution will accept. That approval path looked hard.

Both walls came down.

The technical wall came down because **AI-assisted development changed the cost structure of building.** The predecessor already showed the pattern: a 10,900-line tool reached a documented, tested, operator-ready state for a few hundred dollars of tooling spend plus concentrated owner time, by collapsing product owner, analyst, tester, and implementer into one fast loop. RRW extends the same bet to a genuinely harder substrate — a FastAPI/SQLAlchemy web application with migrations, an audit subsystem, and a real permission model — as a proof of concept that AI-assisted coding can clear the first wall.

The institutional wall is coming down because **there are enough allies for it to.** There is now in-principle approval to host citizen-developed projects on the institution's own Azure, properly sandboxed, under a workable data policy. That is what makes an in-tenant web application a real option rather than a thought experiment — and it is why RRW leans so hard on Microsoft identity and on staying inside institutional infrastructure. The architecture is, in part, an argument addressed to the second wall: *this can live safely inside the institution.*

So RRW should be read as a deliberate step across the citizen-development boundary that Review Robin respected — made responsible by the fact that the platform (institutional Azure, sandboxing, data policy) now supplies the governance layer that a lone Excel tool could not.

---

## 5. Principles carried across both versions

Several principles run through both Review Robin and RRW. They are the connective tissue of the design, and most individual decisions are applications of them.

- **Design around the hardest problem.** The hard problem is structured generation and reliable collation of reviewer-specific instruments, and the routing that feeds it — not workflow orchestration. Effort goes there first; orchestration is an adjunct, never the centre.
- **Automation as a removable accelerator over a manual floor.** Automation should make the operator's loop faster and more reliable, never remove the operator from it. Anything the system does automatically should also be inspectable, reversible, and — where it matters — confirmable before it acts.
- **Keep the control surface visible.** The system should stay inspectable and understandable to operators rather than disappearing into opaque automation.
- **Preserve traceability across the cycle.** It should always be possible to reconstruct what configuration was used, who was asked to review whom, what they received, what they returned, and how the returns became a dataset.
- **Ask humans only for judgment that can't be automated.** The justification for reviewer-facing work is elicitation of genuine evaluative judgment, not re-entry of facts a system already holds.
- **Don't overbuild orchestration before the core is solved**, and **be honest about boundaries** — say plainly what the tool does and does not do.

RRW's own house style reinforces these: keep route handlers thin and business logic in services, land changes as small reviewable slices, write the rules down rather than leaving them implicit, and register every change in the audit log. The discipline that Review Robin kept inside a workbook, RRW keeps inside a layered codebase.

---

## 6. The core design decisions

Each decision below is stated as *what was decided, why, and what it trades off.*

### 6.1 Asymmetric pools and rule-based assignment

**Decision.** Model reviewers and reviewees as two independent pools, and derive every assignment from a rule engine rather than allowing hand-authored pairings. Rules combine predicates, combinators, quotas, and deterministic ordering, and can read pair-level context (relationships between a specific reviewer and reviewee).

**Why.** This is the unsolved centre of the problem and the thing that most sharply separates the target cycles from peer-review-only solutions. Deriving assignments means the mapping survives roster churn: change a roster, re-run the rule, and the pairings reconcile rather than needing to be rebuilt by hand. Keeping the pools asymmetric means the tool fits panels-evaluating-candidates, not only groups-evaluating-themselves.

Symmetric peer review is not excluded by this — it is the *special case* where the reviewer and reviewee pools are the same population, self-review is switched off, and small groups are expressed through group-scoped rules and relationships. Rule-based assignment at cohort scale is exactly what RRW and TEAMMATES share; independent pools are what RRW adds on top. So the same engine that runs an asymmetric panel review also runs a 1,200-student, small-group course peer review.

**Trade-off.** Rules are more up-front work than dragging names around, and they demand that the operator can express review logic declaratively. The bet is that this cost is paid once and amortised across scale and re-runs — and that manual pairing simply does not survive 1,500 reviewers.

### 6.2 A tabular review surface built for scale

**Decision.** Give reviewers a paginated, tabular response surface — one page per instrument, each a grid of (reviewee × response field) cells — with typed fields, bounds, native and server-side validation, drafts, and autosave.

**Why.** The reviewer task is intrinsically tabular and can be long. A dense grid that a reviewer can move through quickly is a better fit than a sequence of single-record forms, and it is the affordance that spreadsheets got right. Typed fields with validation shift data-quality enforcement to *authoring time* rather than leaving it to post-hoc cleanup.

The surface has to hold two quite different load shapes, and a dense grid serves both: many reviewers each doing only a few rows (large-cohort peer review — 1,200 reviewers rating five or six teammates), and few reviewers each working through a long list (a panel across dozens or a hundred candidates).

**Trade-off.** A custom tabular surface is more to build and maintain than adopting a generic form tool, and it deliberately forgoes a heavyweight data-grid framework in favour of something server-rendered and inspectable (see 6.8). The payoff is a surface tuned to the actual task and to large row counts.

### 6.3 Granular, per-audience visibility

**Decision.** Make visibility an explicit, per-instrument, per-audience, and per-window policy: each instrument can be shown to reviewees or observers as raw, anonymised, or summarised, and gated on whether responses have been released. Anonymised downloads use per-session opaque tokens, with a separate operator-only key for de-anonymisation.

**Why.** "Who may see what" is a first-class requirement in real review, not an afterthought. Different audiences legitimately deserve different views of the same responses, and getting this wrong is both an ethical and an institutional risk. Making it a declared policy rather than an emergent behaviour keeps it auditable and defensible.

**Trade-off.** A full visibility matrix is more machinery than a single "anonymous: yes/no" switch. It earns its keep in exactly the settings RRW targets, where feedback flows to multiple audiences under different rules.

### 6.4 The session as the unit of organisation

**Decision.** Organise everything around the **session** — one configured review cycle with its own rosters, instruments, rules, and lifecycle — rather than around a persistent course. Reuse a population across cycles by duplicating a session and tagging sessions that belong to the same context.

**Why.** RRW's cycles are not tied to a standing course roster; they are discrete events, sometimes with overlapping but rarely identical populations. Making the session the primary object keeps each cycle self-contained, independently configurable, and independently defensible. A course-wide peer review is then simply a session (or one session per cohort), reused across terms by duplicate-and-tag rather than by inheriting a mutable standing roster. (This is the axis on which RRW most quietly diverges from a course-centric peer-review tool.)

**Trade-off.** Reusing a population means an explicit duplicate-and-tag step rather than inheriting a course roster automatically. In exchange, cycles never entangle, and each carries its own clean record.

### 6.5 Collection, not analysis

**Decision.** Solve the data-*collection* problem well and stop there. RRW routes, collects, and exports clean, structured data (per-entity CSVs and a zip bundle), and deliberately does **not** provide analysis, modelling, or dashboards.

**Why.** This is the same boundary the predecessor drew — Review Robin handed off to Power Query — and it is a principled one. The valuable, hard, tool-specific work is getting *clean, portable, analysis-ready data* out of a potentially messy human process. Analysis is better served by whatever engine the user already prefers (Excel, Power BI, Python/R). Keeping RRW analysis-agnostic avoids reimplementing a weaker version of tools that already exist, and keeps the scope honest.

**Trade-off, stated plainly.** A class of would-be users — those less comfortable on the analysis side, or expecting a built-in reporting layer — will perceive the absence of dashboards as *incomplete*. TEAMMATES offers some basic in-tool presentation; RRW does not. This is an accepted cost of the scope discipline, not an oversight: the tool optimises for portable data over presentation.

### 6.6 Inside the institution

**Decision.** Authenticate through Microsoft Entra ID via Azure Easy Auth, deploy on the institution's Azure, and keep data within the institutional tenant. Do not build a separate login system; trust the platform's identity headers.

**Why.** For institutional review, staying in-tenant is the difference between a tool that can be sanctioned and one that cannot. It aligns with the second wall coming down (Section 4): in-principle approval to host sandboxed citizen projects on institutional Azure under a workable data policy. Reusing institutional identity also means no separate credentials to manage and a permission story the institution already understands.

One honesty caveat belongs here. At the pilot stage, the safety of "inside the institution" rests on the **platform sandbox and the institutional data policy**, not yet on the application's own hardening: database access is currently guarded by a firewall allow-list rather than private networking, secrets are held as plain application settings, and there is no monitoring layer. Private networking, managed secret storage, and telemetry are on the roadmap. The in-tenant posture is what makes the tool *sanctionable now*; the deeper hardening follows. Saying so is part of the same honesty the design otherwise insists on.

**Trade-off.** RRW is bound to Easy Auth and has no standalone login fallback; it must run behind the platform's identity layer. That coupling is accepted deliberately — it is a feature, not a limitation, for the intended setting.

### 6.7 Accountability by construction

**Decision.** Make the cycle defensible by construction: every mutating operation writes a typed, schema-validated audit event; the session moves through an explicit lifecycle (draft → validated → ready/"Activated", with an archived off-ramp) with edit-locks once live; permissions scope operators to sessions they own; and regenerating assignments **reconciles** rather than wipes — inserting newly eligible pairs, dropping orphaned ones, and leaving matched pairs and their saved responses untouched.

**Why.** Defensibility was named as a core requirement of the problem, not a nice-to-have. An append-only audit log answers "what happened and who did it," lifecycle locks stop live cycles from being edited out from under their data, scoped permissions keep operators in their lane, and reconciling regeneration removes a whole class of accidental data-loss. Together they let the institution stand behind decisions like hiring and admissions.

**Trade-off.** This is the machinery that, in any maturing system, grows to rival the core business logic in size. It is a deliberate investment in the floor of trust the tool needs to be usable for real decisions.

### 6.8 A boring, inspectable technical shape

**Decision.** Build a server-rendered FastAPI + Jinja + SQLAlchemy monolith with a strict three-layer split (thin routes, business logic in services, models in between), no frontend framework and no JS build step, Postgres in production and SQLite in tests, and migrations round-tripped on both dialects in CI.

**Why.** The same instinct that kept Review Robin inspectable inside a workbook keeps RRW inspectable inside a small, conventional codebase. A server-rendered monolith with plain forms is easy to reason about, easy to hand over, and cheap to maintain by one person with AI assistance. Avoiding a JS framework is a scope-discipline decision: the reviewer surface uses targeted progressive enhancement, not a single-page application. Keeping complexity *located* where it can be read — thin routes, explicit services, a validated audit envelope — is the codebase-level expression of "keep the control surface visible."

**Trade-off.** A richer client framework could deliver a slicker reviewer experience; a heavier architecture could add scale headroom. Both were declined in favour of legibility and maintainability at the current scale, consistent with the tool's citizen-development origins.

---

## 7. What RRW deliberately is not

Scope discipline is a design feature, so it is worth stating the exclusions directly. RRW does not analyse or present data (Section 6.5). It is not a case-management or HR platform, and does not replace substantive human judgment or the operator's oversight. It does not guarantee fairness or good decision-making; it makes the *collection* of judgment reliable and defensible. And, as a pilot-stage build, several things remain deliberately unfinished — live email sending is queued but not yet wired, there is a single environment rather than separate staging and production, retention is operator-driven, app-level security hardening (private networking, managed secret storage, monitoring) is still on the roadmap, and accessibility has had a basic pass rather than a full audit. These are honest boundaries, most of them chosen rather than missed.

---

## 8. Where RRW sits now

Read against its predecessor, RRW is the far side of a boundary Review Robin respected on purpose. Review Robin was a disciplined citizen-development tool that solved the tabular generation problem inside Excel, with Outlook integration, and stopped, because going further meant becoming a platform. RRW *is* the platform step — multi-session, per-audience, access-controlled, identity-integrated, audit-backed — attempted now because AI-assisted development lowered the cost of building the substrate and institutional approval lowered the cost of running it.

It carries forward the predecessor's philosophy intact: design around the hardest problem, keep the human in the loop over a manual floor, keep the surface inspectable, preserve traceability, and stay honest about scope. It borrows TEAMMATES's central insight — rule-based assignment at cohort scale — and re-aims it at review that can be asymmetric, session-scoped, and in-tenant, while still covering the large symmetric peer review TEAMMATES was built for. And it draws its scope line in the same place both predecessors drew theirs: collect clean, structured, defensible data, and hand it off for analysis elsewhere.

---

## 9. The thesis in one paragraph

RRW exists to solve one structurally hard, widely recurring problem — **routing a pool of reviewers to a pool of reviewees, collecting their structured judgment at scale, and producing a clean, defensible dataset** — that neither spreadsheets, generic forms, nor (for its asymmetric, institution-hosted setting) any known off-the-shelf tool solves. Its design is the disciplined application of a few principles inherited from an Excel predecessor and an insight borrowed from TEAMMATES: automate the routing and collection, keep the human in the loop over a manual floor, make the whole cycle traceable and defensible, stay inside the institution's identity and infrastructure, and stop firmly at clean data rather than drifting into analysis. It is a proof — of both AI-assisted buildability and institutional hostability — that a tool once confined to a workbook can now live, responsibly, as a sanctioned web application.

---

## Appendix — Generalised problem mapped to design response

| Generalised problem | RRW design response |
|---|---|
| Arbitrary, many-to-many reviewer→reviewee mapping (asymmetric *or* symmetric) | Independent reviewer/reviewee pools; rule-based assignment engine — symmetric peer review as the shared-pool special case |
| Large symmetric course peer review (the TEAMMATES use case) | Shared pool with self-review excluded; small groups via group-scoped rules; CSV roster import instead of block paste |
| Reviewer work is tabular and long | Paginated tabular response surface with typed fields, drafts, autosave — serving both many-reviewers-few-rows and few-reviewers-many-rows load shapes |
| Returns must be collatable and analysable | Typed fields + validation at authoring time; structured CSV/zip export |
| Different audiences may see different views | Per-instrument, per-audience, per-window visibility policy (raw/anonymised/summarised) with tokenised downloads |
| Cycles are discrete, not tied to a standing roster | Session as the unit of organisation; duplicate-and-tag to reuse a population |
| Judgments must be defended later | Typed audit envelope on every mutation; lifecycle locks; scoped permissions; reconciling (non-destructive) regeneration |
| Must be sanctioned to run in the institution | Microsoft 365 / Entra identity; in-tenant Azure hosting under a workable data policy (pilot safety rests on sandbox + policy; app-level hardening on the roadmap) |
| Must stay maintainable by a citizen developer | Server-rendered monolith, thin routes / explicit services, no JS framework, migrations tested on both dialects |
| Analysis is better served elsewhere | Deliberate scope stop at clean, portable data — hand off to Excel / Power BI / Python / R |
