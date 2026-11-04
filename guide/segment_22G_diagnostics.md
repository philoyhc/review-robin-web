# Segment 22G — Diagnostics

**Opened:** 2026-11-04, parked at the author's request · **Theme:** a
small set of status reports that say whether the deployed host is doing
what it should, without reading logs · **Related:**
`guide/archive/segment_14E_clock.md` (the clock Item 1 reports on)

Parked: no rung is built until the author un-parks it. The segment
collects the reports first; where they appear is decided once there are
enough of them to place (Open questions).

## Item 1 — Azure status reports about the session

### Opportunity

On Azure, what the app is doing in the background is visible only in
the logs. The clock (14E) is the first case: it runs in-process every
`SCHEDULER_INTERVAL_SECONDS` (`0` turns it off), skips a pass when another process holds
its advisory lock, and logs a failure, but nothing on a page says
whether it is running or when it last passed. An operator who sees a
scheduled Start not fire cannot tell a stopped clock from a refused
activation without the author opening the logs.

### Decision

Not yet made. The intent (author, 2026-11-04): **a small set of status
reports about the session on Azure**, the clock's state first (running,
last pass, last failure). Which other reports join it, and where they
sit, waits on the list.

### Open questions

- **The list.** What else reports beside the clock: candidates to
  collect, not commitments. Author.
- **Placement.** A card on Session Home, a host-level page, or both;
  depends on how many reports there are. Author, once the list exists.
- **Scope of "session".** Per review session (what the clock will do
  next for this session) or per running instance (the clock's own
  health), or both. Author.
- **Audience.** Operators, the platform super-admin, or both.

### Out of scope

- Host request logging: the Cordware stub in `guide/todo_master.md`
  ("Cordware host logging, events 4 and 5").

### Doc impact

- `guide/todo_master.md` — delete the segment's entry at the item's close.
