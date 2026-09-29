# Tasks

One spec per task: `T-NNN-slug.md` (template in the lead kit). Status values: draft, ready,
in_progress, in_review, changes_requested, done, dropped. `docs/BACKLOG.md` remains the list of
what to do; a spec is written when an item is started and names its W-id, if it has one.

| ID | Title | Level | Size | Depends on | Status |
|---|---|---|---|---|---|
| T-001 | Judge the scorecard's production row by the scorecard's own measured/not-measured rule | 1 | S | — | done (`0a3098d`) |
| T-002 | Make publish_numbers.py report what it could not do, instead of crashing or exiting 0 | 1 | S | — | done (`16e100e`) |
| T-003 | Make publish_numbers.py's report say what changed and what to do about what is left | 1 | S | T-002 | done (`fec26df`) |
| T-004 | Run the whole offline suite before every deploy | 3 | M | — | done (`d0eb7e8`) |
| T-005 | Make second_oracle.py ready for the Owner's W5 check on the adversarial cohort | 2 | M | — | in_progress |
