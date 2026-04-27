# Segment 2 Plan — Azure Hello-World Deployment

**Project:** Review Robin Web  
**Repository:** <https://github.com/philoyhc/review-robin-web>  
**Segment:** 2 of the low-intensity workplan  
**Purpose:** Prove that the minimal FastAPI app can deploy from GitHub to Azure App Service and run successfully online

---

## 1. Segment goal

Segment 2 proves the deployment path before the application becomes complicated.

By the end of this segment, the existing Segment 1 FastAPI skeleton should be deployed to Azure App Service and reachable in a browser. The `/health` endpoint should work in Azure, not just locally.

This segment should remain deliberately small. The objective is to learn the Azure App Service and GitHub Actions deployment loop while the app is still simple.

---

## 2. Success criteria

Segment 2 is complete when:

1. An Azure App Service for Linux exists for the project.
2. The App Service is configured for Python 3.12 or the closest supported Python 3 runtime.
3. The FastAPI app deploys from GitHub Actions.
4. The deployed `/health` endpoint returns `{ "status": "ok" }`.
5. Runtime logs are accessible.
6. Deployment logs are accessible.
7. A trivial change can be pushed and redeployed successfully.
8. The repository contains basic deployment notes.

---

## 3. What this segment deliberately does not do

Do not include:

- Microsoft authentication;
- database provisioning;
- Blob Storage;
- email sending;
- Azure Functions;
- deployment slots;
- custom domain;
- production hardening;
- reviewer or operator functionality.

This is a hello-world deployment only.

---

## 4. Recommended branch strategy

Create a branch:

```bash
git checkout -b segment-2-azure-hello-world
```

Suggested PR title:

```text
Segment 2: Deploy FastAPI skeleton to Azure App Service
```

Suggested PR description:

```text
Adds Azure deployment support for the initial FastAPI skeleton.

Includes:
- GitHub Actions deployment workflow
- startup command notes
- deployment documentation
- deployed /health verification

No database, authentication, or domain functionality is added.
```

---

## 5. Azure resources to create

For a first development deployment:

- Resource group: `rg-review-robin-web-dev`
- App Service Plan: `asp-review-robin-web-dev`
- Web App: `app-review-robin-web-dev`
- Runtime: Python 3.12 if available
- OS: Linux
- Region: use the institutionally appropriate Azure region, or a convenient personal/dev region for proof of concept

Naming can be adjusted later. Segment 2 does not need production naming perfection.

---

## 6. App startup command

FastAPI requires an ASGI server. For Azure App Service, use `gunicorn` with `uvicorn` workers.

Add `gunicorn` to dependencies if not already present:

```toml
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "gunicorn>=22",
    "jinja2>=3.1",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
]
```

Suggested startup command:

```bash
gunicorn -w 2 -k uvicorn.workers.UvicornWorker app.main:app
```

For a very small dev app, one worker is also acceptable:

```bash
gunicorn -w 1 -k uvicorn.workers.UvicornWorker app.main:app
```

Record the chosen startup command in deployment notes.

---

## 7. GitHub Actions deployment workflow

Add a workflow such as:

```text
.github/workflows/deploy-dev.yml
```

Recommended simple approach for Segment 2:

- trigger manually with `workflow_dispatch`, or automatically on push to `main`;
- set up Python;
- install dependencies;
- deploy to Azure App Service.

The exact authentication method can be one of:

1. App Service publish profile stored as a GitHub secret; or
2. Azure login with federated credentials / service principal.

For a low-intensity first deployment, publish profile is simpler. For a more institutionally correct setup, federated credentials are better.

---

## 8. Repository documentation to add

Add a short deployment note, either in `README.md` or a new file:

```text
docs/deployment_dev.md
```

Recommended content:

- Azure resource names;
- runtime stack;
- startup command;
- GitHub Actions workflow name;
- where deployment credentials are stored;
- how to view logs;
- how to test `/health`;
- known deployment issues.

---

## 9. Step-by-step execution checklist

### Step 1 — Confirm local app still works

```bash
pytest
uvicorn app.main:app --reload
```

Visit:

```text
http://127.0.0.1:8000/health
```

### Step 2 — Create Azure App Service

Use the Azure Portal for the first pass.

Create:

- resource group;
- Linux App Service Plan;
- Web App;
- Python runtime.

### Step 3 — Set startup command

In the App Service configuration, set startup command:

```bash
gunicorn -w 1 -k uvicorn.workers.UvicornWorker app.main:app
```

### Step 4 — Add deployment workflow

Create `.github/workflows/deploy-dev.yml`.

### Step 5 — Add GitHub secret

If using publish profile:

- download publish profile from Azure App Service;
- add it to GitHub repository secrets as `AZURE_WEBAPP_PUBLISH_PROFILE`;
- never commit it to the repo.

### Step 6 — Run deployment

Trigger the workflow.

### Step 7 — Test deployed app

Open:

```text
https://<app-name>.azurewebsites.net/health
```

Expected:

```json
{"status":"ok"}
```

### Step 8 — Confirm logs

Find where to view:

- deployment logs;
- application logs;
- live log stream.

### Step 9 — Make a trivial change

Change the health endpoint to return an additional field temporarily, deploy, confirm, then decide whether to keep or revert.

---

## 10. AI-assisted prompts

### Initial deployment workflow prompt

```text
Create a GitHub Actions workflow to deploy this FastAPI app to Azure App Service for Linux.

Constraints:
- Python 3.12
- App name: app-review-robin-web-dev
- Use publish profile from GitHub secret AZURE_WEBAPP_PUBLISH_PROFILE
- Install with pip install -e .
- Deploy from main or manual workflow_dispatch
- Keep the workflow minimal
```

### Startup error prompt

```text
The Azure App Service deployment succeeded but the app does not start.

Here are the App Service logs:

[paste logs]

Diagnose the likely cause and propose the smallest fix. Do not add database or authentication.
```

### Workflow failure prompt

```text
The GitHub Actions deployment failed.

Here is the workflow log:

[paste log]

Explain the cause and propose the smallest correction.
```

---

## 11. Suggested GitHub issues

### Issue 1 — Add Azure deployment dependency and startup notes

Scope:

- add `gunicorn` dependency;
- document startup command.

Acceptance criteria:

- app runs locally with gunicorn;
- startup command is documented.

### Issue 2 — Add dev deployment workflow

Scope:

- `.github/workflows/deploy-dev.yml`;
- GitHub secret setup notes.

Acceptance criteria:

- workflow can deploy to Azure;
- no secrets are committed.

### Issue 3 — Document dev Azure deployment

Scope:

- deployment notes file;
- log viewing instructions;
- health check URL.

Acceptance criteria:

- another person can understand how the dev app is deployed.

---

## 12. Common mistakes to avoid

### 12.1 Wrong startup command

A FastAPI app cannot be run like a WSGI Flask app. Use gunicorn with uvicorn workers.

### 12.2 Missing dependency

If the startup command uses `gunicorn`, make sure `gunicorn` is in dependencies.

### 12.3 Committing publish profile

Publish profiles are credentials. Store them only as GitHub secrets.

### 12.4 Adding database too early

Do not add PostgreSQL in this segment. Keep deployment failure modes simple.

### 12.5 Confusing CI and deployment

Keep `ci.yml` and `deploy-dev.yml` separate. CI proves tests. Deployment publishes the app.

---

## 13. Segment 2 completion note template

```markdown
## Segment 2 completion note

Completed:
- Azure App Service dev app created
- FastAPI skeleton deployed
- /health verified online
- GitHub Actions deployment workflow added
- startup command documented
- logs located and checked

Verified:
- pytest passes locally
- CI passes on GitHub
- deploy-dev workflow succeeds
- deployed /health endpoint works

Deferred:
- Easy Auth
- database
- production deployment slots
- custom domain
- application functionality

Notes:
- [resource names]
- [startup command]
- [deployment issues encountered]
```

---

## 14. Final checkpoint

Before moving to Segment 3, confirm:

- [ ] App Service exists.
- [ ] Startup command is set.
- [ ] `gunicorn` dependency is present.
- [ ] GitHub Actions deployment works.
- [ ] Deployed `/health` works.
- [ ] Logs are accessible.
- [ ] No secrets are committed.
- [ ] Deployment notes are written.

Next segment: **Authentication proof-of-concept**.

