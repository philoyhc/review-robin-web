# Cordware v0.8 — Implementation Sequence for Stages 1–2

> **Retired 2026-10-22, at segment 21D's close.** Its four workstreams shipped as segments 21A–21D (`guide/archive/segment_21_domain_retrofit.md`). Decision history, not instructions: the live contracts are `cordware/spec/` and `spec/architecture.md`.

**Date:** 20 October 2026  
**Status:** Accepted by the author (2026-10-20) and written into v0.8 §5. Originally a sequencing proposal. It answers one question: in which order should the v0.8 work before Residential Apps (stages 1 and 2) land? Should Cordware be extracted first, or should RRW's routing move to `/reviewrobin` first?  
**Baseline:** `cordware_repository_strategy_v0.8.md` §3 and §5. Measurements are from `philoyhc/review-robin-web` `4ed8114` (2026-10-20), read only.

---

## 1. Short answer

**Extract the Cordware host first, but not its identity, and move the prefix last.** v0.8's stage 1 bundles three separable jobs, and only one of them changes a URL. Split it, and the order becomes:

1. **A. Host skeleton.** `cordware/` exists and runs RRW, still at `/`.
2. **B. URL sweep.** RRW generates every link route-aware, which does nothing at root.
3. **C. Shared identity.** Easy Auth parsing moves to `cordware/identity.py`, which also does nothing to URLs. It can run in parallel with B.
4. **D. Prefix flip.** RRW moves to `/reviewrobin`, and Cordware takes over `/`.

A, B and C each leave RRW's behavior at `/` unchanged, so each can merge on its own and be tested by the existing ~6,700 tests. D is the only step that changes what users see, and after B it is small.

This reorders v0.8 in one respect: v0.8 originally put identity extraction (stage 2) *after* the mounted URL behavior was established. This note moves it *before* the prefix flip, and v0.8 §5 now says so, so that the one live dev-slot check at D exercises both the new identity and the new prefix under real Easy Auth.

## 2. What stages 1–2 actually contain

| Workstream | Contents | Size at `4ed8114` | Changes URLs? |
|---|---|---|---|
| **A. Host skeleton** | `cordware/main.py`; the `CORDWARE_APPS` setting; Cordware alone runs `/health`; RRW mounted **at `/`** for now; the module-level `app = create_app()` removed from `app/main.py`; root-logger setup moved to the host; the import-boundary test; start commands (local, Codespaces, dev slot) moved to `cordware.main:app` | ~5 new small files; edits to `app/main.py`, `app/logging_config.py`, docs and the devcontainer | **No** |
| **B. Route-aware URL sweep** | Every literal root path becomes route-aware generation (as built, an app-relative path gains `root_path` at emission through `app/web/urls.py`; `guide/archive/segment_21B_url_sweep.md`); path comparisons become app-relative; cookie `Path`s; a test harness that mounts RRW under a test prefix; a leak-check test | 187 template `href`/`action`/`src` literals; ~370 root-path strings in Python, 4 of them `RedirectResponse`s; 7 `fetch(` calls in inline scripts; 31 uses of `request.url.path`; 3 `set_cookie`s; only 14 `url_for` uses today | **No**, at root (`root_path` is empty) |
| **C. Shared identity** | `app/auth/identity.py` (165 lines, self-contained) moves to `cordware/identity.py`, with fake identity and its guard; RRW keeps fake *roles*; `app/auth/identity.py` re-exports from Cordware, so its 78 importers needn't change at once | 1 module moved, a settings split, a re-export shim | **No** |
| **D. Prefix flip** | Mount RRW at `/reviewrobin`; the Cordware landing page at `/`; RRW's `/` redirect becomes `/reviewrobin/`; `/.auth/*` login/logout return paths (6 references); deep-link return through Easy Auth; dev slot verified live | A few files once B is done | **Yes**: the only step that does |

The 793 root-path requests in RRW's tests stay valid throughout. They call RRW's app directly at app-relative paths (v0.8 §3), which a mount doesn't change.

## 3. Dependencies

```text
A ──┬──> C ──┐
    │        ├──> D
B ──┴────────┘
```

- **B needs nothing.** Its test harness can mount RRW under `/reviewrobin` with a bare Starlette app; it doesn't need `cordware/`. But if A lands first, the harness *is* Cordware, which is simpler.
- **C needs A**, because `cordware/` must exist to receive the module.
- **D needs B** (or links leak) **and A** (or there is no host to own `/`). It is easier, but not required, after C.
- **B and C barely touch each other.** B edits templates, routes and redirects; C edits `app/auth/` and settings. They can run as parallel ladders.

## 4. The orders compared

| Order | What it means | For | Against |
|---|---|---|---|
| **Original v0.8 order (superseded 2026-10-20):** stage 1 (A+B+D) → stage 2 (C) | Mount at `/reviewrobin` with the sweep, then extract identity | Follows the document; identity moves only once the mounted URLs are proven | Stage 1 is one large ladder whose last rung changes every URL; the dev slot needs two live checks (after stage 1, then after stage 2); the sweep and the flip are coupled, so a leak found late blocks the whole stage |
| **Identity first:** C → A+B+D | Extract identity before any host exists | — | C has nowhere to go without A; in practice this collapses to A → C → B → D |
| **Routing first:** B → D → A → C | Sweep, flip the prefix with a throwaway mount, then build the host | The URL risk is retired earliest | The flip needs a host to own `/` and `/health`, so a throwaway host gets built and then replaced: wasted work |
| **Proposed:** A → B ∥ C → D | Host at root; sweep and identity in parallel; flip last | Every step but D is behavior-neutral and merges alone; the bulk work (B) proceeds while C lands; one live check at D covers identity and prefix together; D is small and easy to revert | Identity extraction no longer waits for mounted URLs, so it is proven at `/`, not at `/reviewrobin`; but identity parsing reads headers, not paths, so the mount doesn't affect it |

## 5. Proposed ladder

Rough rungs, each one reviewable PR. RRW's segment plan, when the author opens it, sets the real cut points.

**A. Host skeleton**
1. `cordware/` package: `main.py` with `CORDWARE_APPS` (empty runs Cordware alone), host `/health`, RRW mounted at `/`. Tests: Cordware alone, Cordware + RRW.
2. Construct once: remove the module-level `app = create_app()`; move start commands to `cordware.main:app` (docs, devcontainer, deploy workflows). The dev slot's startup command is an Azure setting the author changes by hand.
   The module-level `app` has consumers that must move in the same rung, or RRW breaks at runtime:
   - `app/web/return_to.py` imports `app.main.app` while handling a request, to check which GET routes exist. It must use the RRW application the request is running in (`request.app`, which inside a mount is RRW's sub-app, not the host) rather than a module global.
   - 15 test and tool files import `app.main.app`. They move to one test fixture built from `create_app()`, so the suite builds RRW once per session as before.
   - `tests/browser/conftest.py` starts `uvicorn app.main:app`; it starts the Cordware entry point instead.
   A test that imports `app.main` and asserts it builds no application keeps the rule from creeping back.
3. Host-owned logging, and the import-boundary test.

**B. URL sweep** (runs while C lands)
1. A URL helper for strings built outside a request (emails, scripts), a test harness mounting RRW under `/reviewrobin`, and a leak-check test with an allowlist of known literals.
2. Sweep area by area (templates, redirects, inline scripts, path comparisons, cookies), shrinking the allowlist each PR.
3. Remove the allowlist: the leak check becomes a hard gate.

**C. Shared identity**
1. `cordware/identity.py`, with fake identity moved from RRW's settings; `app/auth/identity.py` re-exports it. Cordware also exposes the fake-auth state at host level, readable outside a request (whether fake auth is on, and the fake account's email), for RRW's checks that take an email or a stored user rather than the request identity; `app/auth/roles.py`'s `effective_super_admin_emails()` switches to it in the same rung, so no rung leaves it reading settings that have moved. `APP_ENV` moves to Cordware as a platform setting, and Cordware adds the guard that refuses to start with `ALLOW_FAKE_AUTH` on outside `APP_ENV=local` (v0.8 §3); the personal dev slot's `APP_ENV` is set to a non-`local` value first. Every fake-auth switch keeps its name and default, and a test sets each one per run to prove it.
2. RRW's fake *application* roles stay in RRW, but they read the fake-auth state from Cordware's identity instead of RRW's settings. Today `app/web/deps.py` grants the fake operator and admin roles on `allow_fake_auth` plus the user's `is_fake` flag. After the move, those key off the fake marker on the identity Cordware supplies, which Cordware's guard never sets outside local development, and RRW keeps only its role flags: `fake_auth_operator`, `fake_auth_sys_admin`, and `fake_auth_super_admin` until C3 replaces it. Through C2 the fake super-admin is still derived in RRW: `effective_super_admin_emails()` keeps folding in the fake email from Cordware's host-level fake-auth state (from C1), so the email-based checks (`app/services/users.py`'s admin-management and protected-super-admin guards, `app/services/account_listing.py`'s markers and counts) keep resolving the fake user, and it never loses a role between rungs.
3. Super-admin becomes Cordware's platform role (v0.8 §3): Cordware reads `SUPER_ADMIN_EMAILS` and exposes `is_super_admin` on the identity, marking the fake user too while fake auth and `FAKE_AUTH_SUPER_ADMIN` are both on (the switch moves to Cordware with its name and default-on unchanged, so the false case still works), plus `is_super_admin_email`, the same test on any email, for accounts other than the signed-in user (`app/services/users.py`'s protected-super-admin guard and `app/services/account_listing.py`'s markers and counts), and `super_admin_configured`, both readable outside a request. `super_admin_configured` is whether the *effective* list is empty, the fake account included while both switches are on, as `effective_super_admin_emails()` computes it today, so local fake auth with an empty `SUPER_ADMIN_EMAILS` keeps the fallback off. Cordware takes over the startup warning for an empty list, and RRW's warning in `app/main.py` retires in the same rung. `app/auth/roles.py` and its callers read those instead of the setting, keeping RRW's empty-list fallback keyed off `super_admin_configured`, and RRW's copy of `fake_auth_super_admin` retires in the same rung that adds its replacement, with `tests/unit/test_roles_super_admin.py`'s on and off cases moved onto the Cordware switch. Tests: the trusted-identity interface on its own, the platform super-admin flag, the predicate on a target account, the fallback on and off with an empty and a non-empty list, and the fake user keeping all its roles.
4. Optional: repoint the 78 importers and drop the re-export.

**D. Prefix flip**
1. Mount RRW at `/reviewrobin`; Cordware landing page at `/`; `/.auth/*` return paths; deep-link return through Easy Auth.
2. Dev slot redeployed on the Cordware entry point; the author verifies v0.8 §3's four behavior requirements under real Easy Auth.

After D, stage 3 (Residential Apps) can start.

## 6. Points for the author

1. **The one change to v0.8:** identity extraction (C) moves from after the mounted URLs to before the prefix flip. Accepted: v0.8 §5 now reads stage 1 = A + B and stage 2 = C, then D.
2. **Segment 21's rework maps onto B and D.** Its audit (2026-10-16) is the starting inventory for B. A and C are new plans, or rungs within the same segment.
3. **The dev slot changes twice:** its start command at A, then its served path at D. Both are behavior-visible only to the author, since nothing consequential is in the wild.
4. **Re-take the counts** in §2 when B opens. RRW's ongoing work changes them.
