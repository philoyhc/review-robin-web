# Apply Desk — accounts and permissions

Who may be what, who may reach which page, and what each kind of account
may do (the author's rulings, 2026-11-22). Review Robin is the model
(`spec/audience_and_identity_model.md` §4, `spec/permissions.md`) except
where this file says otherwise; `guide/rrw_permissions_update.md` queues
bringing Review Robin to this file's per-exercise model.

This is the **target contract**. Each section marks what is built; the rest
is to build, and its plan will name this file in its `Doc impact`.
`spec/applications.md` describes the pages as they stand ("Who reaches
what", Accounts Management, the Operators card, the Operator Lobby).

## 1. Principles

- **Identity comes from Cordware.** Easy Auth's headers become an
  `Identity` (`cordware/identity.py`); Apply Desk binds it to a person by
  tenant and object ID, as `spec/applications.md` "The people" says.
  A *pending* person, known only by address, reaches nothing until a
  sign-in binds them. *Built.*
- **Roles nest.** At workspace level, Super-admin ⊇ Admin ⊇ Operator; on an
  exercise, Owner ⊇ Operator. Every gate honors the nesting, so a higher
  role never needs the lower one granted separately.
- **Two layers.** A workspace role says what someone may be; a grant on an
  exercise says which exercises they work on, and as what.
- **Participants hold no role.** Applicants and evaluators reach `/me/…`
  because a record names them (an application, an invitation, a panel), not
  by a flag (§4).
- **Fail closed, and say nothing.** A page someone may not reach is a 404,
  so it does not admit to existing. An action refused is said in words, never
  carried out in part.
- **Every change is audited** (§8). No in-app action makes, demotes or
  removes a super-admin.

## 2. Workspace roles

| Role | Stored as | Granted by | Revoked by | Built |
|---|---|---|---|---|
| **Operator** | `person.may_operate` (the operator list) | *Admit*, by an Admin or the super-admin | *Revoke*, by an Admin or the super-admin | Yes (AD2A, AD2W) |
| **Admin** | `person.is_admin` (to add) | the super-admin | the super-admin | No: being built (the author's ruling, 2026-11-22), after Review Robin's sys-admin |
| **Super-admin** | derived from Cordware's `SUPER_ADMIN_EMAILS`, never stored | deployer config | deployer config | Yes |

- An Operator may make exercises, and becomes the Owner of each they make.
  Being on the operator list opens no exercise by itself.
- An Admin reaches the Admin pages and manages Operators; an Admin is an
  Operator, so may make exercises.
- The super-admin reaches every Admin page and manages Admins. Like an Admin,
  they work on an exercise only once they own or operate it: an exercise they
  hold no role on, they adopt (§5). They see the Operator Lobby as any operator
  does: only the exercises they own or operate (§7).

## 3. Exercise roles

Every exercise has **one or more Owners**. Every Owner is also an operator of
it: **Owner ⊇ Operator**.

| Role | Stored as | Becomes one by | Stops by |
|---|---|---|---|
| **Operator** | an `exercise_operator` row | an Owner adding them | an Owner removing them, or leaving |
| **Owner** | the same row, `is_owner` true | making the exercise; an Owner making an operator an Owner; an Owner transferring ownership to them | an Owner demoting them to operator; transferring their own ownership away; stepping down |

*Built:* the rows, adding and removing operators, and a handover. *To
build:* more than one Owner (today `uq_exercise_one_owner` allows one), Make
Owner, demote, step down and leave.

### What each may do on an exercise

| Action | Operator | Owner |
|---|---|---|
| Open every page of the exercise | ✓ | ✓ |
| Set it up: Details, Form, Process, Panels, Emails | ✓ | ✓ |
| Run it: open the form, send gates, decide outcomes, release, extract | ✓ | ✓ |
| See every dossier item, whatever its grants | ✓ | ✓ |
| In the Lobby: rename, tag | ✓ | ✓ |
| Duplicate it (the copy's Owner is whoever duplicates it) | ✓ | ✓ |
| Leave it (take themself off) | ✓ | ✓, not the last Owner |
| Add an operator | — | ✓ |
| Remove an operator | — | ✓ |
| Make an operator an Owner | — | ✓ |
| Demote an Owner to operator (another, or themself) | — | ✓, not the last Owner |
| Transfer ownership to an operator | — | ✓ |
| Purge and archive | — | ✓ |
| Delete | — | ✓ |

### The ownership moves

- **Make Owner**: an operator becomes an Owner; every Owner stays one.
- **Transfer**: an operator becomes an Owner and the Owner doing it becomes
  an operator, in one audited step. Transfer never leaves the exercise
  without an Owner, so the last Owner may transfer.
- **Demote**: an Owner turns an Owner (themself included: *Step down*) into
  an operator.
- **Remove**: an Owner takes an **operator** off the exercise. An Owner is
  never removed directly: they are demoted first, then removed (the author's
  ruling, 2026-11-22). Their row is kept, ended, so re-adding them restores
  it, as today.
- **Leave**: an operator takes themself off. An Owner steps down first.

## 4. Participants

| Kind | Recognized by | Reaches | Built |
|---|---|---|---|
| **Applicant** (*Candidate*, ruling 71) | their application | `/me`: the exercises open to them, their applications, and what is released to applicants | Placeholder pages; per-person gating in AD2D |
| **Invitee** | an *Invitation only* exercise's invitee list | as an Applicant, for that exercise | AD2B |
| **Evaluator** | membership of a panel a gate draws on | the dossiers they evaluate, `/me/…/dossiers/<id>`, showing only items granted to *Assigned evaluators* or *Evaluators* (ruling 68); they respond in Review Robin, never in Apply Desk | AD2E, AD4, AD5 |

| **Observer** | named on an exercise as observing it (pre-positioned: the model has a place for them; nothing is built until a later segment) | `/me`: what the exercise grants observers, read-only, as Review Robin's observers read `/me/sessions/<id>/collation` | Later |

An observer, as in Review Robin (`spec/participant_model.md`), is a
participant on `/me`, not an operator: they read, never change, and hold no
role on the exercise's operator pages. Their grants join ruling 68's
audiences (*Applicant*, *Assigned evaluators*, *Evaluators*) as *Observers*
when they are built.

A participant may also be an operator; the two are independent. Until AD2D,
the participant's pages stay behind the placeholders' gate
(`gate.placeholders_only`: anyone on a local run, deployed only the
super-admin).

## 5. What each kind of account may do

✓ yes; ○ on the exercises where they hold that role; — no.

| Capability | Participant | Operator | Exercise operator | Exercise Owner | Admin | Super-admin |
|---|---|---|---|---|---|---|
| Their own `/me` pages | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| The Operator Lobby, listing what they own or operate | — | ✓ | ✓ | ✓ | ✓ | ✓ |
| Make an exercise, becoming its Owner | — | ✓ | ✓ | ✓ | ✓ | ✓, once bound |
| Set up and run an exercise; read every dossier item | — | — | ○ | ○ | via adopt | via adopt |
| Add or remove operators; Make Owner; demote; transfer | — | — | — | ○ | via adopt | via adopt |
| Purge and archive; delete an exercise | — | — | — | ○ | via adopt | via adopt |
| Admin → Exercises Diagnostics: every exercise, its Owners, Outbox, Audit log | — | — | — | — | ✓ | ✓ |
| Admin → Accounts Management: Admit and Revoke Operators | — | — | — | — | ✓ | ✓ |
| Promote and demote Admins | — | — | — | — | — | ✓ |
| Admin → System Status | — | — | — | — | ✓ | ✓ |

**Adopt** (to build, with Admins): from Exercises Diagnostics an Admin or the
super-admin who holds no role on an exercise may read its diagnostics, but
must *adopt* it to open its pages or change anything: an audited step that
makes them an Owner of it, as Review Robin's *Manage* self-adds a sys-admin.
The super-admin adopts too (the author's ruling, 2026-11-22): nobody edits an
exercise without a recorded role, so every change has an Owner on record.
Adopting one they already operate makes them an Owner. Once adopted, they are
an Owner as any other, and step down or leave the same way. Today the
super-admin reaches every exercise without a grant; adopting replaces that.

## 6. Who reaches which pages

| Pages | Reached by | Built |
|---|---|---|
| `/operator/…` (the Lobby, making an exercise) | an Operator, Admin or the super-admin | Yes |
| An exercise's pages, `/operator/exercises/<id>/…` | its operators and Owners, an Admin or the super-admin among them once adopted | Operators and the one Owner, yes; today the super-admin reaches all without adopting |
| Owner-only posts (operators, ownership, purge, delete) | its Owners | Partly: today the one Owner and the super-admin |
| `/admin/…` | Admins and the super-admin | Super-admin only today |
| `/me/…` | participants, by their records (§4) | Behind the placeholders' gate |
| `/` and `/operator` | an operator lands on the Lobby; anyone else on the User Lobby | Yes |

## 7. The Operator Lobby and Exercise Home

- **The Lobby lists only the exercises the viewer owns or operates**, the
  super-admin and Admins included (the author's ruling, 2026-11-22). Every
  exercise is seen on Admin → Exercises Diagnostics instead. On a local run
  the seeded person, Local Operator, owns the sample exercises in the
  ordinary way: the seed grants them (`applydesk/seed.py`), not their being
  super-admin.
- **Your role** replaces *Created by*: an *Owner* or *Operator* chip for the
  viewer on that exercise; it sorts as the other columns do.
- **The tick panel follows the role.** *Purge and archive* and *Delete* are
  live only when the viewer owns every ticked exercise; otherwise they say
  which ticked exercises the viewer only operates. *Duplicate*, rename and
  tags are open to operators.
- **Exercise Home's Operators card becomes *Owners and operators*.** Owners
  first, each marked *Owner*, then operators; a pending person says *Not yet
  signed in*. Each row offers only the moves the viewer may make:

  | Row | An Owner sees | An operator sees |
  |---|---|---|
  | Another operator | *Make Owner*, *Transfer ownership*, *Remove* | nothing |
  | Another Owner | *Make operator* | nothing |
  | Their own row | *Step down to operator* (not the last Owner) | *Leave* |

  An Owner also has *Add operator*, the operator-list search the card has now.
  *Transfer ownership*, *Remove* and *Leave* ask first and take the
  Outline-amber or Destructive role (`spec/ui_elements.md` §6); *Make Owner*
  and *Make operator* are Secondary. For an operator the card is otherwise
  read-only and says only Owners change who.
- **Exercises Diagnostics** names every Owner of each exercise (*Owners*), not
  one.

## 8. Guards

- **At least one Owner, always.** Demoting, stepping down or leaving that
  would leave no Owner is refused; transfer always leaves one. The check runs
  under the same row lock the handover takes now, so two Owners demoting each
  other at once cannot both succeed.
- **Owners and operators come from the operator list.** Adding an operator,
  making an Owner and transferring all require the person to be on it.
- **An Owner is demoted before removal** (§3).
- **Revoking from the operator list** ends the person's access at once and
  keeps their grants, so re-admitting restores them (built). To build: it is
  refused while they are the **only** Owner of an exercise not archived;
  ownership is handed over first, as Review Robin's `sole_owner` refuses.
- **The super-admin is protected**: no Revoke, demote or delete against them,
  and nobody acts on their own row in Accounts Management (built).
- **With Admins**: Admins are promoted and demoted by the super-admin only;
  the last Admin is never demoted; with no super-admin configured, an Admin
  may promote Admins (Review Robin's fallback).
- **Deleting a person** is allowed only for one with no history: never signed
  in, no grants, never an audit actor (Review Robin's `has_history`).
- **A pending person** may be admitted and granted, and reaches nothing until
  bound; two pending matches for one sign-in fail closed (built).
- **A refusal** is said in words on the page it came from, with a status line
  key, never text from the URL (as Accounts Management's are).

## 9. Audit

Every change writes an `audit_event` with the actor.

| Event | When | Built |
|---|---|---|
| `person.created`, `person.bound`, `person.signed_in` | a person is made, bound, first signs in | Yes |
| `person.admitted`, `person.revoked` | onto and off the operator list | Yes |
| `exercise.created` | an exercise is made, its maker its Owner | Yes |
| `exercise.operator_added`, `exercise.operator_removed` | an operator added or removed | Yes |
| `exercise.ownership_handed_over` | a transfer | Yes |
| `exercise.owner_added` | Make Owner | No |
| `exercise.owner_demoted` | an Owner made an operator, or stepping down | No |
| `exercise.operator_left` | an operator leaves | No |
| `exercise.adopted` | an Admin or the super-admin adopts an exercise as Owner | No |
| `exercise.deleted`, `exercise.archived` | an Owner deletes, or purges and archives | No |
| `person.promoted`, `person.demoted` | Admin granted, taken away | No |

## 10. Open

- **Observers**: what an exercise grants them (which dossier items, which
  outcomes), and who names them (its Owners, on Home, as Review Robin's
  operators name observers). Decided when they are built.

Decided 2026-11-22 (the author): build the Admin tier now; the super-admin
adopts as an Admin does; observers are participants on `/me`, pre-positioned
here and built later.
