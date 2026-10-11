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
| T-005 | Make second_oracle.py ready for the Owner's W5 check on the adversarial cohort | 2 | M | — | done (`0fa831a`) |
| T-006 | Refuse regenerate-derived.sh's bots' mode outside GitHub Actions | 3 | S | — | done (`053fe0a`) |
| T-007 | Make the gate guard require a written conclusion, as its docstrings say it does | 3 | S | — | done (`3fb1d3d`) |
| T-008 | Refuse snapshot-commit.sh outside GitHub Actions, and pin its push path | 3 | S | — | done (`f1a767d`) |
| T-009 | Show answered gates as answered, and put a gate that is coming due in Needs you | 1 | S | T-007 | done (`235b20c`) |
| T-010 | Keep a half-answered gate in Needs you, and read gates from section 8 only | 1 | S | T-009 | done (`47db199`) |
| T-011 | Make benchmark replay deterministic and keep live fills explicitly limited | 2 | M | none | done (deployed fefe6d1) |
| T-012 | Preserve the liquidity gap for traded pools without claiming no market trace | 3 | M | T-011, T-019, T-013 | changes_requested (named container-regression fix b) |
| T-013 | Use validated full pool identifiers for upstream lookups | 3 | M | T-011, T-019 | done (deployed 7f796e4) |
| T-016 | Distinguish Solana liquidity pools from holder concentration | 2 | S | none | done (deployed c18de92) |
| T-019 | Fill the benchmark's recorded miss list and publish an attributable replay baseline | 3 | S | T-011 | done (deployed a19c3dc) |
| T-020 | Recover snapshot failures and report incomplete collection after preserving data | 3 | M | — | in_review |
| T-021 | Reject invalid market scalars and preserve unavailable depth | 3 | M | T-011, T-019, T-013, T-012 | draft (exact-base conflict and replay gates pending) |
| T-022 | Pace scheduled snapshot requests using the verified slower interval | 3 | S | T-020 source | in_review |
| T-023 | Compare observed coverage before a cold upstream-baseline write | 3 | S | T-016 | draft (after current correctness repairs; exact-base refresh pending) |
