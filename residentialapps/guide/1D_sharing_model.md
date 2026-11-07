# Segment 1D: who sees whose records (the sharing model)

**Decided 2026-11-07** (author, from notes reviewed in session). Replaces
the two sharing ideas on today's screens: Share with a colleague (all of
the owner's records for a student, with no acknowledgement) and Share on
their behalf (a senior sharing another's records), and the Allocate to a
colleague scaffold proposed for a student's history, which was not
merged. Nothing here is built yet; this file is the model the screens and
the wiring will follow. Confidentiality rule 2 in
`residentialapps/spec/supportlogs_ui.md` §6 points here.

## The base rule

An encounter record belongs to the frontline staff member who logged it.
Only they can see it, plus senior identifiable access, which still names
the student only under confidentiality rule 3.

## Four ways to see someone else's records

Every step below is audited: a share and its acknowledgement or decline,
a withdrawal, and a team's formation, change or dissolution.

### 1. Share past records

- **The owner shares** one or more of their past records about a student,
  up to all of them, with one colleague.
- **The receiver acknowledges first.** Until then they see only that
  "Priya Raman has shared 3 records about a student with you", with no
  name. Acknowledging opens the records; declining ends the share.
- **The owner can withdraw** a share at any time.
- **Past records only.** Records logged later are not covered; looking
  forward is a team's job.

### 2. Share at logging

- **On Log**, an optional detail, folded away like the others, shares
  the encounter being saved with a colleague.
- The receiver acknowledges it as in 1.

### 3. A team

- **Two or more frontline staff share responsibility for one student.**
  Each member acknowledges at formation. The team forms once at least
  two have accepted; anyone who declines stays out.
- **At formation, each member chooses** whether the team sees their past
  records about the student.
- **Records made while in the team are team records**, tagged to every
  member at the time they were made.
- **Plans and follow-ups can be the team's**: the most likely use, one
  follow-up the members keep up between them.
- **Any member can withdraw.** A team down to one member dissolves.
- **After a withdrawal or dissolution**, each person sees their own
  records and the team records tagged to them; nothing else.
- **A senior can trigger a team's formation.** The rest is the same:
  each member acknowledges. A senior is not a member unless they join
  explicitly, as a frontline staff member.

### 4. A handover

- **Records are tagged to the receiving staff member**, so they become
  that person's records too, not merely visible to them.
- **Both the receiver and a senior acknowledge** before it takes effect.

## What follows for the other rules

- **Rule 3 (Overview naming):** a student with a team counts, as a
  formal plan or a safety flag does, and is named by default.
- **Safety flags** stay outside this model: flag recipients see the flags
  whatever the sharing state.
- **Other Staff view** (rule 4) is unchanged.

## Still open

- **Who starts a handover:** the owner, a senior, or either.
- **Whether a handover tags all of the owner's records** for the student,
  or chosen ones.
- **What the outgoing staff member keeps after a handover:** their own
  copy, or nothing new.
- **How a team's plan is shown on Students:** a member's All / Plans /
  Following filter, with the team named.

## Effect on today's screens

- Share with a colleague, on a student's page, becomes **Share past
  records** (1).
- Share on their behalf, on a student's history, goes.
- A student's history gains **Form a team** (3) and **Hand over** (4),
  in place of the unmerged Allocate to a colleague.
- Log gains the share-at-logging detail (2).

These land as scaffolds first, one slice each, once this model is
accepted.
