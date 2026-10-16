# Cordware / Review Robin Integration Specification

**Version:** 0.2 draft  
**Purpose:** Define the required behavior for integrating Review Robin Web (RRW) into the adopted Cordware single-App-Service architecture.  
**Public host:** `https://cordware.nus.edu.sg`  
**RRW path:** `/reviewrobin`  
**Status:** Implementation specification for the RRW project.

---

## 1. Architectural decision

RRW will not run as an independent production App Service behind Cordware.

Instead, RRW will be integrated as a distinct module inside one Cordware web application deployed to one App Service.

The public structure is:

```text
https://cordware.nus.edu.sg/
    -> Cordware landing

https://cordware.nus.edu.sg/reviewrobin
    -> RRW module

https://cordware.nus.edu.sg/residentialapps
    -> Residential Apps module
```

RRW remains an independent development project and canonical source repository, but production assembly/deployment occurs from the Cordware integration repository.

---

## 2. Security model

Authentication and authorization are separate.

### Authentication

Cordware has one NUS Entra / Easy Auth boundary.

Cordware core is responsible for exposing a trustworthy authenticated-user identity to RRW.

### Authorization

RRW remains fully responsible for determining what that authenticated identity may do.

RRW must retain its existing authorization semantics, including operator/admin/super-admin behavior.

A user authenticated to Cordware is **not** automatically authorized for RRW.

---

## 3. Direct RRW behavior

A user navigating directly to:

`https://cordware.nus.edu.sg/reviewrobin`

must be able to authenticate and continue directly into RRW.

The user must not be required to visit the Cordware landing page first.

If authentication is required, it occurs at the shared Cordware Easy Auth boundary and returns to the originally requested path.

Deep links such as:

`https://cordware.nus.edu.sg/reviewrobin/sessions/123`

must survive authentication and return to the requested RRW location.

---

## 4. Cordware landing page is discovery only

The Cordware landing page may show an RRW tile/link only to users who are eligible to discover RRW.

That is not an authorization boundary.

A user who knows `/reviewrobin` may navigate there directly.

RRW must still enforce its own access rules.

---

## 5. RRW route namespace

All RRW web routes in the assembled Cordware application must live beneath:

`/reviewrobin`

The retrofit must eliminate assumptions that RRW owns the application root.

Examples:

- `/sessions` becomes `/reviewrobin/sessions`;
- `/about` becomes `/reviewrobin/about`;
- RRW-specific auth/user pages must be mounted consistently beneath the module path unless intentionally shared by Cordware core.

The exact internal router structure may differ, but the public namespace must be stable.

---

## 6. Shared authentication identity interface

RRW should no longer depend directly on being the sole Easy Auth application boundary.

Instead, Cordware core should provide a narrow authenticated-user interface consumed by RRW.

The interface should expose only identity facts RRW needs, for example:

- stable Entra/user identifier where available;
- institutional email / UPN as appropriate;
- display name;
- provider/tenant metadata if needed.

RRW authorization must consume this trusted identity but remain otherwise independent.

The design should avoid importing Cordware shell/navigation internals into RRW business logic.

---

## 7. Code assumptions that must change

The previous standalone-host assumptions are no longer valid.

The RRW project must audit and, where necessary, change assumptions about:

- owning `/`;
- direct Easy Auth handling as the outer app boundary;
- absolute redirects;
- hard-coded route paths;
- template links;
- form actions;
- static asset locations;
- JavaScript/API fetch paths;
- route-name generation;
- health endpoint placement;
- middleware ordering;
- application startup composition;
- error handlers;
- tests that instantiate RRW as the complete web application;
- config names that assume a standalone RRW deployment.

---

## 8. Code assumptions that should remain

The Cordware integration should preserve, as far as practical:

- RRW domain logic;
- RRW service layer;
- RRW authorization model;
- RRW persistence semantics;
- RRW Alembic/migration history;
- RRW-specific tests;
- local developer ability to work primarily in the RRW repo;
- fake/local authentication for local RRW development where useful.

The objective is to change the **hosting/composition boundary**, not rewrite RRW's business domain.

---

## 9. Application factory / router composition

RRW should become mountable/composable by Cordware.

The preferred code direction is that RRW exposes a clear construction boundary such as:

- router(s);
- module/app factory;
- module initialization hook;
- explicit dependencies required from Cordware core.

Cordware should not need to reach deeply into RRW internals to assemble it.

A clean target is conceptually:

```python
cordware_app.include_router(
    reviewrobin_router,
    prefix="/reviewrobin",
)
```

or an equivalent modular composition model.

This is illustrative, not prescriptive.

---

## 10. Static resources and templates

RRW static assets must continue to resolve correctly when RRW is served beneath `/reviewrobin`.

The implementation should prefer route-aware URL generation over string concatenation.

The audit must cover:

- CSS;
- JavaScript;
- images;
- downloads;
- template includes;
- any generated absolute URLs.

---

## 11. Redirects and deep links

RRW redirects must stay inside its module namespace.

Incorrect:

`Location: /sessions`

Correct:

`Location: /reviewrobin/sessions`

or route-aware equivalent.

Authentication return behavior must preserve the full originally requested Cordware path.

---

## 12. Health behavior

The single deployed Cordware application needs an outer health endpoint suitable for Application Gateway.

RRW may retain an internal/module health check if useful, for example:

`/reviewrobin/health`

but the production gateway does not necessarily need to probe RRW separately.

Recommended distinction:

- `/health` -> overall Cordware process/application health;
- `/reviewrobin/health` -> optional RRW module health;
- `/residentialapps/health` -> optional Residential Apps module health.

Health routes used for Azure probes must not require interactive authentication.

---

## 13. Persistence boundary

RRW should retain its own explicit database boundary even though it shares one App Service process with other modules.

The existing `reviewrobin` database may remain RRW's persistence target.

Cordware integration must not require RRW tables to be merged into Residential Apps tables.

RRW database configuration should remain namespaced and independently identifiable.

---

## 14. Configuration boundary

RRW configuration should be explicitly namespaced where ambiguity could arise in the shared process.

Examples may include:

- RRW DB URL;
- RRW admin/operator settings;
- RRW feature flags;
- RRW mail/settings.

Whether existing setting names are retained or prefixed should be decided during implementation, but collisions with other modules must be prevented.

Shared settings such as environment, common logging, or shared identity may remain Cordware-level.

---

## 15. Local development

RRW should remain convenient to develop in `review-robin-web`.

The source repo should support a standalone local harness so contributors do not need the full Cordware repo for every RRW change.

That harness may mount RRW at `/` or `/reviewrobin`, but CI must explicitly test the production module-path behavior.

The canonical production behavior is `/reviewrobin`.

---

## 16. CI expectations in the RRW repo

RRW's own CI should continue to validate RRW independently.

It should add tests for:

- module/router composition;
- `/reviewrobin` path behavior;
- redirects;
- generated links;
- static assets;
- authorization with a supplied trusted identity;
- health behavior;
- configuration isolation.

A green RRW build means the revision is suitable for synchronization into Cordware.

It does not replace Cordware integration CI.

---

## 17. Synchronization contract

`review-robin-web` remains the authoritative RRW source repo.

Cordware receives an automated synchronized copy.

RRW source should be exportable into the expected Cordware module location without manual patching.

The Cordware copy must not become a second place for RRW feature development.

If Cordware integration reveals an RRW bug:

1. fix it in `review-robin-web`;
2. merge there;
3. sync the new revision into Cordware.

---

## 18. Acceptance criteria

The RRW retrofit is complete when:

1. RRW remains developable/testable in its canonical repo.
2. RRW can be assembled into Cordware as a module.
3. RRW public routes live under `/reviewrobin`.
4. Direct entry to `/reviewrobin` works.
5. Deep links survive shared Cordware authentication.
6. RRW authorization remains unchanged in meaning.
7. An authenticated but unauthorized user is denied by RRW.
8. RRW links/redirects/assets do not leak to the Cordware root incorrectly.
9. RRW retains a clear persistence boundary.
10. RRW code does not depend on Residential Apps internals.
11. Cordware can consume RRW through a documented module interface.
12. RRW's synchronized Cordware copy can be regenerated from a recorded upstream commit.
13. RRW tests cover the module-path and shared-identity assumptions.
14. Normal browser navigation does not expose the backend Azure App Service hostname.

---

## 19. Explicit non-goals

This retrofit does not require:

- merging RRW's canonical Git history into Cordware;
- moving normal RRW feature development into the Cordware repo;
- replacing RRW authorization with Cordware authorization;
- merging RRW and Residential Apps databases;
- sharing RRW business services with unrelated modules;
- forcing RRW contributors to run the entire Cordware stack for normal development.

---

## 20. Recommended RRW implementation sequence

1. audit route/root/auth assumptions;
2. define the RRW module construction interface;
3. separate shared-auth identity consumption from RRW authorization;
4. make routing compatible with `/reviewrobin`;
5. fix redirects/links/assets/forms/API paths;
6. preserve RRW persistence/config boundaries;
7. add module-mode tests;
8. define a deterministic Cordware export/sync shape;
9. prove RRW integration in the Cordware repo;
10. only then make Cordware the production deployment target.
