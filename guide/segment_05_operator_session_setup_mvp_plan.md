# Segment 5 Plan — Operator Session Setup MVP

**Project:** Review Robin Web  
**Repository:** <https://github.com/philoyhc/review-robin-web>  
**Segment:** 5 of the low-intensity workplan  
**Purpose:** Let an authenticated operator create and view basic review sessions through the web UI

> **See also:** `guide/segment_05A.md` — agreed implementation plan with
> decisions made (Azure Postgres tier and networking, secret strategy,
> migration-on-deploy, two-PR split, permission model, deferrals into
> Segment 13). Read this parent plan for scope and intent; read 05A for
> the implementation contract.

---

## 1. Segment goal

Segment 5 creates the first real operator-facing workflow.

By the end of this segment, an authenticated user should be able to:

- create a review session;
- see their sessions in a list;
- open a session detail page;
- see basic session metadata;
- be blocked from viewing sessions they do not operate.

This segment does not yet include reviewer imports, reviewee imports, assignments, activation, or invitations.

---

## 2. Success criteria

Segment 5 is complete when:

1. Operator routes exist.
2. A session list page exists.
3. A create-session form exists.
4. A session detail page exists.
5. Session ownership/operator relationship is created when a session is created.
6. Basic server-side permission checks exist.
7. Session creation writes an audit event.
8. Tests cover session creation and access denial.
9. The UI is plain but usable.

---

## 3. What this segment deliberately does not do

Do not include:

- reviewer or reviewee upload;
- assignment modes;
- instruments beyond maybe a placeholder;
- activation;
- invitations;
- reviewer-facing pages;
- role management UI;
- rich dashboard cards;
- production styling.

This is only the first operator loop.

---

## 3.1 Inherited from Segment 4A

Segment 4 (per `guide/segment_04A.md`) was scoped to the data model only and
deferred all live-database work into this segment. Segment 5 must therefore
**also** cover:

- **Azure Database for PostgreSQL Flexible Server (dev) provisioning.** Use
  the institutionally appropriate region and the smallest dev tier. Public
  access with firewall allow-rules for the dev App Service and the
  developer machine is acceptable for the dev environment.
- **App Service configuration.** Set the `DATABASE_URL` (or equivalent) App
  Setting to the Postgres connection string. Do not commit the secret;
  store it as an App Setting (or a Key Vault reference if Key Vault is
  introduced earlier).
- **Local Postgres for development.** Add a `docker-compose.yml` (or
  equivalent instructions) so a contributor can run a local Postgres on a
  known port. Update `docs/database.md` accordingly.
- **Migration on deploy.** Decide how `alembic upgrade head` runs against
  Azure Postgres on each deploy (recommended: a step in
  `.github/workflows/main_app-review-robin-web-dev.yml` that runs migrations
  before the App Service swap, against the dev DB, using the same
  connection string).
- **First real-Postgres smoke test.** The Segment 4 migration was only
  exercised against SQLite. Running it against Azure Postgres for the first
  time in Segment 5 is the moment any portability gaps surface — budget
  time to fix them rather than work around them.

---

## 4. Recommended branch strategy

```bash
git checkout -b segment-5-operator-session-setup
```

Suggested PR title:

```text
Segment 5: Add operator session setup MVP
```

---

## 5. Pages to add

### 5.1 Sessions list

Route example:

```text
GET /operator/sessions
```

Shows:

- sessions where current user is operator;
- session name;
- session code;
- status;
- deadline;
- created date;
- link to detail;
- button/link to create new session.

### 5.2 Create session

Routes:

```text
GET /operator/sessions/new
POST /operator/sessions
```

Fields:

- session name;
- session code;
- description;
- deadline.

Keep validation simple:

- name required;
- code required;
- deadline optional or required depending on current model;
- duplicate code within the operator's sessions should be blocked or warned.

### 5.3 Session detail

Route:

```text
GET /operator/sessions/{session_id}
```

Shows:

- session name;
- code;
- description;
- deadline;
- status;
- basic next-step placeholders:
  - Reviewers: not yet implemented;
  - Reviewees: not yet implemented;
  - Instruments: not yet implemented;
  - Assignments: not yet implemented.

---

## 6. Files to add or modify

```text
app/
  services/
    session_service.py
    audit_service.py
    permission_service.py

  schemas/
    sessions.py

  web/
    routes_operator.py
    templates/
      base.html
      operator/
        sessions_list.html
        session_new.html
        session_detail.html

tests/
  integration/
    test_operator_sessions.py
```

If templates are not yet configured, add minimal Jinja2 template setup.

---

## 7. Service responsibilities

### 7.1 `session_service.py`

Should handle:

- create session;
- list sessions for user;
- get session by id;
- add creator as session operator.

### 7.2 `permission_service.py`

Should handle:

- checking whether current user can view/manage session;
- raising or returning clear denial when unauthorized.

Keep this simple. Do not build a general enterprise permission system yet.

### 7.3 `audit_service.py`

Should handle:

- writing `SessionCreated` audit event;
- later reusable pattern for other audit events.

---

## 8. Tests to add

Minimum tests:

1. Authenticated user can create session.
2. Creating session creates `SessionOperator` link.
3. Creating session writes audit event.
4. Operator can see their session in list.
5. Operator can open their session detail.
6. Another user cannot open the session detail.
7. Missing required session name fails validation.

---

## 9. AI-assisted prompts

### Initial implementation prompt

```text
Implement Segment 5 operator session setup MVP.

Add:
- operator session list page
- create-session form
- session detail page
- session_service.py
- permission_service.py
- basic audit event for session creation
- tests for create/list/detail/access denial

Constraints:
- Keep route handlers thin.
- Use Jinja2 templates.
- Use existing authenticated-user dependency from Segment 3.
- Do not add reviewer/reviewee imports yet.
- Do not add activation or invitation logic.
```

### Review prompt

```text
Review this Segment 5 PR.

Check:
- Are permission checks server-side?
- Is business logic kept out of route handlers?
- Does session creation link the operator correctly?
- Is audit written in one place?
- Are templates plain but understandable?
- Are tests sufficient?
```

---

## 10. Suggested GitHub issues

### Issue 1 — Add operator routes and templates

Acceptance criteria:

- session list page exists;
- create-session page exists;
- detail page exists.

### Issue 2 — Add session service and permission checks

Acceptance criteria:

- user can create session;
- user is linked as operator;
- unauthorized access is blocked.

### Issue 3 — Add session audit event

Acceptance criteria:

- session creation writes audit event;
- test verifies audit event.

---

## 11. Common mistakes to avoid

### 11.1 Trusting UI hiding

Do not rely on hiding links. Permission must be checked on the server.

### 11.2 Putting business logic in templates

Templates should display state, not decide session ownership.

### 11.3 Building a dashboard too early

Keep the detail page plain. Workflow cards can come later.

### 11.4 Overbuilding roles

For now, creator = session operator is enough.

---

## 12. Completion note template

```markdown
## Segment 5 completion note

Completed:
- operator session list
- create-session form
- session detail page
- basic permission checks
- session creation audit event
- tests

Verified:
- operator can create and view own session
- non-operator cannot view session
- tests pass

Deferred:
- reviewer/reviewee import
- instruments
- assignments
- activation
- invitations
```

---

## 13. Final checkpoint

- [ ] Session list works.
- [ ] Create-session form works.
- [ ] Detail page works.
- [ ] Permission tests pass.
- [ ] Audit event is written.
- [ ] No import/assignment/invitation logic was added prematurely.

Next segment: **Import and validation MVP**.

