# Residential Apps — Email Aliases and Institutional Identity Matching

**Status:** Design note for incorporation into the Residential Apps shared-core identity specification  
**Date:** 30 October 2026  
**Suggested repository location:** `residentialapps/docs/residentialapps_email_identity_matching.md` in the public RRW repository  
**Related documents:** `residentialapps_identity.md` (identity specification), `residentialapps/docs/residentialapps_roles.md` (authoritative roles), and Cordware's private `docs/cordware_azure_progress_runner_2026-10-29.md`.

## 1. Problem

Cordware applications have historically used institutional email addresses as the convenient human-facing means of identifying users. In Microsoft 365, however, **several email addresses may deliver to the same mailbox and represent the same institutional account**:

- an institutional user principal name (UPN), often resembling an account number;
- a primary email address, often more readable; and
- one or more secondary SMTP addresses or *friendly aliases*.

A roster imported from a CSV might contain a friendly alias that differs from the UPN or primary email returned at sign-in. **Matching solely by the text of one email address may fail to recognize the correct roster entry.** Before accounts are linked, different aliases for the same person can also lead to duplicate provisional Person records.

This must not lead the application to infer that different addresses necessarily represent different people, or to grant access on the basis of an unverified address claim.

## 2. Adopted identifiers and authority

| Identifier | Role | Rule |
|---|---|---|
| `person_id` | Permanent Residential Apps internal person reference | Application-generated **UUIDv4** when the Person record is first created; immutable and never recycled |
| `entra_tenant_id` + `entra_object_id` | Definitive institutional account binding | Obtained from **trusted** Easy Auth/Entra identity; unique as a pair for an active binding |
| `roster_email` | Provisional lookup key and administrative contact/reference | Imported or maintained by the Residential administrator; not a permanent identity key |
| Entra `userPrincipalName` (UPN) | Trusted first-login matching candidate | Can differ from the primary email and may change |
| Entra `mail` | Trusted first-login matching candidate | May differ from UPN, may be absent, and may change |
| Entra `displayName` | Display | Recorded on sign-in; not used for automatic identity matching |
| Enterprise-system name | Official roster reference | Optional import field; retained separately from Entra display name |
| Student ID | Enterprise reference | Optional **nine-character string**, not numeric; not used for Entra linking |

**Identity, roster membership, appointment, and authorization are distinct.** Only authorised administrators maintain Staff/RA rosters and appointments. A successful identity match does not invent an appointment or confer Support Logs authorization. The authoritative role rules remain those in `residentialapps_roles.md`.

### Scope across Cordware

The general principle—**authenticate by stable Entra account identity, not mutable email**—is applicable to Cordware applications. This document specifies the **Residential Apps implementation**, where the internal `person_id` belongs to the shared `residentialops` core. It does **not** require RRW and Residential Apps to share a Person table or internal UUID namespace.

## 3. Illustrative alias case

One Microsoft 365 account might have:

| Property | Illustrative value |
|---|---|
| Entra object ID | `a1b2…7890` |
| UPN | `e0123456@institution.edu` |
| Primary email (`mail`) | `jane.tan@institution.edu` |
| Secondary SMTP alias | `jane@institution.edu` |

All three could route to one mailbox. A roster entry using either the **UPN** or **primary email** may be resolved on first login using trusted identity data. A roster entry using the **secondary alias** may not match those fields even though the alias is valid and mail is deliverable.

An address's ability to receive mail does **not** prove that it will be present in the authenticated sign-in claims or in the basic Graph fields available to the application.

## 4. First successful sign-in: required matching sequence

1. **Authenticate** through Cordware's Azure Easy Auth. Take tenant ID and Entra object ID only from the trusted authenticated identity. Reject missing, invalid, or inconsistent authoritative identity claims; never accept client-supplied equivalents.
2. **Find an existing binding** by `(entra_tenant_id, entra_object_id)`. If found, use its existing `person_id` without requiring any email match. Apply the current, separately maintained appointment and authorization checks.
3. If the Entra account is **not yet bound**, collect the trustworthy account-address candidates available from sign-in, including UPN and any verified account email. Where Graph access is operational, obtain `mail` and `userPrincipalName` from the account's basic profile, using the authenticated object ID to address the correct user; treat missing values as absent, not as errors proving non-membership.
4. **Find an unlinked roster entry** whose `roster_email` uniquely matches one of these verified candidates. Compare email strings case-insensitively after trimming whitespace. Do not use fuzzy name matching or addresses typed by the user.
5. **If exactly one eligible, unlinked Person is found**, atomically bind the trusted Entra tenant/object IDs to that `person_id`, subject to uniqueness and conflict checks. Capture Entra display name and account email/UPN as separate, refreshable profile attributes. Continue to appointment-derived access checks.
6. **If no unique safe match exists**, do not create an account, bind an arbitrary record, or grant roster-derived access. Show the standard not-registered message. Keep the normal sign-in mechanism intact so the user can retry after an administrator corrects the roster.
7. **On subsequent sign-ins**, resolve by tenant/object ID first, regardless of changes to primary email, UPN, aliases, or display name.

If Graph is temporarily unavailable, step 3 uses only verified account addresses supplied by the trusted authentication layer. It must not treat a Graph outage as permission to broaden matching to unverified data. Existing Entra-linked users do not need Graph for routine identity resolution.

### Standard unmatched-user message

> **You are not registered in Residential Apps.**  
> If you believe this is incorrect, please contact your Residential administrator.

No self-registration, self-claim process, automated alias guessing, or pending-user reconciliation queue is required for the initial release. The same generic user-facing outcome is appropriate for missing, ambiguous, and conflicting matches; diagnostic detail is reserved for authorised administrators and safe operational logs.

## 5. Administrator correction

The Residential Operations Administrator (or platform super-admin acting within their administrative rights) handles exceptions through ordinary roster editing:

1. The user contacts the administrator outside the application.
2. The administrator checks the appropriate enterprise/roster evidence and corrects the **provisional** `roster_email` to an institutional address matching the user's trusted UPN or primary email.
3. The user signs in again. The normal exact-match flow establishes the Entra binding.
4. Thereafter, the Entra object ID takes precedence; later changes to the contact email do not cause a new person to be created or the binding to be reassigned.

The administrator should normally correct an **unlinked** roster record. Any proposed change or re-link involving a record already bound to another Entra account requires an explicit, separate, audited administrator-controlled procedure, not an automatic overwrite.

## 6. Duplicate and conflict protections

- Enforce **one active binding per `(entra_tenant_id, entra_object_id)`** at the database level.
- Never overwrite a roster person's existing different Entra binding during first sign-in.
- Never link one authenticated account to multiple `person_id` records automatically.
- If two provisional entries match one account's trusted addresses, **fail closed** and require administrator correction; do not choose one using the name or appointment type.
- CSV imports should detect exact duplicate roster addresses and preserve the existing `person_id` on known, reliably matched reimports. They must not silently merge entries based on similar names.
- When two different aliases were previously imported as two provisional people, administrator review may be necessary to resolve the duplication. The initial release need not provide a bulk merging tool, but must prevent a second automatic Entra binding.
- Historical appointments and support-record references must continue to point to the correct immutable `person_id`.
- Identity-linking and administrator correction events must be audited without exposing sensitive tokens or Graph access tokens.

## 7. Graph permissions and deployment status (29 October 2026)

According to Cordware's 29 October Azure progress report:

- The delegated Graph permissions **`User.ReadBasic.All`** and **`Mail.Send`** are declared and tenant-consented.
- Easy Auth's token store and configured login scopes are in place.
- The user-assigned managed identity and federated identity credential for Easy Auth are created and assigned.
- **Final Web App-side managed-identity/FIC assertion wiring and live token acquisition/refresh and Graph-call testing remain to be completed.** Do not describe Graph lookups as already production-validated.
- A separate NUS firewall issue remains for GitHub Actions artifact/blob egress; it is not an email-alias identity rule.

`User.ReadBasic.All` covers basic properties including `id`, `displayName`, `mail`, and `userPrincipalName`. It does **not** expose the full `proxyAddresses` alias collection. Accordingly, **do not presume that arbitrary secondary SMTP aliases can be resolved with the currently consented permission**.

The initial design does not require additional Graph permissions, direct Teams membership import, Forms integration, directory-wide synchronization, or broader alias lookup. The basic Graph lookup may improve matching once the final Easy Auth configuration is verified.

## 8. Data placement and authorization

- Person, institutional identity links, Staff/RA rosters, and residential appointments reside in the shared **`residentialops`** core database.
- Support Logs may read the shared core for staff eligibility, but its **explicit Support Logs authorizations remain in `supportlogs`**. An RF or RSLM appointment alone does not grant access to student support content.
- No Residential Unit is permanently attached to the Person record; unit scope belongs to appointments and relevant operational records.
- `person_id` is generated when a previously unknown Person is actually created, including at CSV import, **not** only at first sign-in.

## 9. Acceptance scenarios

| Scenario | Expected behaviour |
|---|---|
| CSV has UPN; first login uses that UPN | Unique unlinked record is linked to Entra ID |
| CSV has primary email; sign-in presents a different UPN but Graph returns matching `mail` | Unique unlinked record is linked, if Graph is working and the values are verified |
| CSV has only a friendly SMTP alias absent from trusted UPN and `mail` | No automatic match; user is told to contact administrator |
| Administrator corrects provisional email; user retries | Normal first-login matching succeeds and populates Entra ID |
| Same person signs in later with changed UPN or email | Existing Entra binding resolves the same `person_id` |
| Two provisional entries correspond to two aliases for one account | Second automatic binding is blocked; administrator resolves duplicates |
| Roster entry already bound to another Entra account | No overwrite; access denied pending administrative correction |
| Graph unavailable but user already linked | The user is recognized by trusted Entra ID without a Graph call |
| Sign-in finds an RA appointment | RA eligibility follows the active appointment, not merely successful identity linking |
| Sign-in finds an RF/RSLM appointment but no Support Logs grant | No Support Logs content access |

## 10. Implementation decision

**Adopt the smallest reliable rule:** before first login, an institutional email address is a *provisional matching hint*; after first successful linking, the **Entra tenant/object ID** is the institutional account key, while **UUIDv4 `person_id`** remains the permanent Residential Apps internal person key. Try exact trusted UPN and primary-email matching only. When these fail, have the administrator correct the roster and the user sign in again.

## References

- Cordware private progress report: `docs/cordware_azure_progress_runner_2026-10-29.md`
- RRW roles: `residentialapps/docs/residentialapps_roles.md`
- [Microsoft Entra ID token claims](https://learn.microsoft.com/en-us/entra/identity-platform/id-token-claims-reference)
- [Microsoft Graph permissions — User.ReadBasic.All](https://learn.microsoft.com/en-us/graph/permissions-reference)
- [Microsoft Graph user resource — mail, UPN, proxyAddresses](https://learn.microsoft.com/en-us/graph/api/resources/user?view=graph-rest-1.0)
