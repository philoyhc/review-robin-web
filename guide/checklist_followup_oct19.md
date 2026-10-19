# Browser checklist follow-up, 2026-10-19

What the 2026-10-19 run of `guide/browser_check_files/checklist/README.md`
turned up that needs building, plus the steps set aside for later. Step
numbers are the run order's. An entry is deleted once it ships; the file
goes once it is empty.

## To fix first

### 1. Dismiss doesn't clear a Quick Setup banner on Home

**Seen at:** steps 52 and 56. Every refusal on Session Home's Quick Setup
card has the same problem, including step 54's ask about deleting
instruments.

**Cause (traced, not yet fixed):**

- A refused upload re-renders Home at the POST's address, and a script
  in `app/web/templates/operator/session_detail.html` then rewrites the
  address to Home's own path (findings O7).
- The banner's Dismiss is a link to that same path plus
  `#quick-setup-<slot>` (`cancel_url_for` in
  `app/web/views/_quick_setup.py`).
- Because only the fragment differs, the browser jumps to the anchor
  instead of reloading, so the banner stays.

**Setup pages:** their upload banners (`_upload_problems.html`) are not
rewritten this way, so they should be unaffected. Confirm while fixing.

### 2. An ask's tick belongs inside its red banner

**Seen at:** steps 47 and 54. On some cards, the tick that answers an
ask sits outside the red banner:

- **Relationships, Upload** (`session_relationships.html`): the
  `group_clear` "import" banner, with `Yes, clear them` under it.
- **Relationships, Danger Zone:** the "delete_all" banner, likewise.
- **Quick Setup on Home:** the deletion tick is inside the banner, but it
  also asks the operator to re-tick the replace box below the slots.

**Ruling (author, 2026-10-19):** a tick the banner throws up sits
inside the banner, under its message. A tick the card already had, such
as `Yes, replace the existing N relationships`, stays where it is.

Before building, inventory every ask. These are not checked yet:

- the Reviewees and Reviewers pages;
- the row editors' `group_clear` "editor" surface;
- `instruments_index.html`'s scripted ask on Save.

### 3. The chosen file stays chosen after an ask

**Problem:** after an ask, the operator has to choose the file again
before they can tick and resubmit. A browser cannot refill a file input
on a page the server renders. The operator should be able to either
tick and upload, or dismiss outright.

**Options:**

- **(a) Echo the file back (recommended).** The ask re-renders with the
  file's bytes in a hidden field (base64) and its name shown as kept.
  The route takes the uploaded file or the kept one, and checks it in
  full either way.
  - Stateless, so it works across App Service instances and without
    JavaScript.
  - The page carries the operator's own upload, which they can already
    see on the roster pages.
  - Dismiss drops the kept file.
- **(b) Submit through `fetch`.** A script posts the form and swaps the
  banner into the page, so the file input is never cleared. This needs
  JavaScript, and every card would need its own swap.
- **(c) Keep the file on the server** under a token. This needs a table,
  because the bytes would otherwise sit in one instance's memory or temp
  folder.

**Ruling (author, 2026-10-19): (c).** It holds a file across an ask,
so it needs a table and a migration, and so a plan before any build. The
plan settles:

- which surfaces it covers: the Setup pages' upload cards, Quick Setup
  on Home, the Create page;
- how long a held file lives;
- who can use the token;
- what Dismiss deletes.

## Set aside

- **Steps 10–13:** sort memory and CSV downloads, for a later pass.
- **Steps 50–51:** the Team review card's boundary split and merge,
  which need more work.
- **Step 16's `BC fresh` Quick Setup:** not yet run.
- **Reopened rows:** the parts still missing are lobby bulk archive,
  the observer CSV `abc` address, and the Closed/archived status labels.
- **Parts 9–12:** not finished. The remaining steps get reorganized after
  the fixes above.
