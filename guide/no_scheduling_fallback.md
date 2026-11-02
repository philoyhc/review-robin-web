# If scheduling stays infeasible: the manual fallback

**Opened 2026-11-02, at the author's request.** An action plan for the
case where Review Robin never gets a clock that fires on its own, or never
gets a way to send mail with nobody signed in. In that case every timed
step is the operator's to take: activate, send invitations and reminders,
close. Whether that case arises is decided by two requests to IT (offline
sending as the operator, else a dedicated mailbox; kept privately with the
deployment) and by the clock in `guide/post_azure_todo_checklist.md`
item 7; `guide/email_and_scheduling.md` holds the choices. This note
becomes a segment plan if it is taken up, and leaves when either path
ships.

## Which times mislead, and which do not

Not every date field needs a clock. Some are **checked when someone
arrives**, so they hold whatever runs in the background; others must
**push** something at a time, and only happen when an operator next opens
a page (`spec/lifecycle.md` §8).

| Field | Kind | Without a clock |
|---|---|---|
| **End** (`deadline`) | Checked on arrival | **True.** A reviewer's save or submit after it is refused and the instruments close (`observe_deadline`, §4). Keep. |
| **Release-from / release-until** (`responses_release_at` / `_until`) | Checked on arrival | **True.** The reviewee and observer pages test the window when they load. Keep. |
| **Start** (`scheduled_activate_at`) | Pushes a state change | **Late.** The session opens on the first operator page view after it; a reviewer arriving earlier finds it not yet open. |
| **Auto-send invites** (`invite_offsets`) | Pushes mail | **Late, or never.** Fires on an owner's page view, and sends only once a transport exists. |
| **Auto-send reminders** (`reminder_offsets`) | Pushes mail | **Late, or never**, as invites. |
| Auto-archive, auto-delete after archive | Push | Not built (`guide/deferred_consolidated.md`); nothing to change. |

So the fallback touches **three** fields, not every time box.

## Recommendation

1. **Make Start dependable without a clock.** Activation sends no mail, so
   it needs no token: fire the scheduled activation on *any* request that
   reaches the session, a reviewer's invite link or `/me` included, not
   only an operator's page view. Then Start is "checked on arrival" like
   End, and stays a live field. Small and in RRW's hands; worth doing
   whatever IT answers.
2. **Turn the two auto-send fields off, visibly, behind one deployment
   setting** rather than deleting them. `RRW_SCHEDULED_SEND=off` (proposed
   name; default off until a transport and a clock exist):
   - the invite and reminder offset fields render disabled, with one line:
     "Scheduled sending isn't available on this deployment; send from
     Invitations when it's time";
   - Quick Setup and the Settings CSV import keep reading the columns but
     say the values are inert, so a file from another deployment
     round-trips without loss;
   - the Workflow card's auto-send caption drops its "System will dispatch
     automatically" promise (it is also wrong today: checklist item 7).

   Greying out beats removing: the values survive, nothing migrates, and
   switching the setting on later restores them. It beats leaving them
   live: an operator who sets a reminder for Friday 09:00 believes it
   goes out.
3. **Replace the promise with a prompt.** Where the schedule would have
   acted, the operator pages say what is due:
   - **Session Home / Workflow card:** "Reminders due: 12 reviewers have
     not submitted, 2 days before End" with the Send reminders button;
     "Start has passed" with Activate, on a session that has not opened
     (should step 1 not ship).
   - **The lobby:** a small "action due" marker on sessions with a due
     step, so a busy operator sees them without opening each.
   These read the same offsets the scheduler would have used, so an
   operator's plan still drives the nudges.
4. **Close stays manual, and that is fine.** End already refuses late
   saves on arrival; Close session is the operator's tidy-up, as now.
5. **Say so in the Guide and the reviewer-facing copy.** One Guide
   section, "Running a session by hand": activate, send, remind, close,
   release, with the order and the buttons. Reviewer invitations keep the
   End date, which stays true.

## Order, if taken up

1. Start fires on any arrival (code + tests; `spec/lifecycle.md` §8.3).
2. The setting and the disabled auto-send fields, scaffold-first: the
   copy and the greyed fields, then the import and caption behavior.
3. The due-action prompts on Session Home and the lobby.
4. The Guide section and the spec sweep (`spec/lifecycle.md` §8,
   `spec/settings_inventory.md`, `spec/workflow_card.md`).

## Open questions

- **Default of the setting before IT answers.** Off is honest today (no
  transport); the question is whether to flip it on when request 6 lands
  but before the clock exists. Author.
- **Do due-action prompts also go by email to the owner?** Not without a
  transport; revisit with segment 14B.
- **Per-deployment or per-session?** Proposed per-deployment: the
  limitation is the host's, not the session's.
