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
| T-012 | Preserve the liquidity gap for traded pools without claiming no market trace | 3 | M | T-011, T-019, T-013 | done (deployed e657c32) |
| T-013 | Use validated full pool identifiers for upstream lookups | 3 | M | T-011, T-019 | done (deployed 7f796e4) |
| T-015 | Describe the demo's failed simulation with the Owner-confirmed wording | 3 | S | T-024 | done (published 19ea3af; deployed and read back) |
| T-016 | Distinguish Solana liquidity pools from holder concentration | 2 | S | none | done (deployed c18de92) |
| T-019 | Fill the benchmark's recorded miss list and publish an attributable replay baseline | 3 | S | T-011 | done (deployed a19c3dc) |
| T-020 | Recover snapshot failures and report incomplete collection after preserving data | 3 | M | — | done (real schedule 38165984869) |
| T-021 | Reject invalid market scalars and preserve unavailable depth | 3 | M | T-011, T-019, T-013, T-012 | done (deployed 7da5bdf) |
| T-022 | Pace scheduled snapshot requests using the verified slower interval | 3 | S | T-020 source | done (real schedule 38165984869) |
| T-023 | Compare observed coverage before a cold upstream-baseline write | 3 | S | T-016, T-021 | done (published 2a8204f; required master CI 38175829622 passes) |
| T-024 | Apply the Owner's Experiment D postponement to 2026-10-20 | 3 | S | none | done (published 19ea3af; actual CI passes) |
| T-025 | Refuse incomplete coverage recordings after engine error handling | 3 | S | T-024 | done (published 19ea3af; actual CI passes) |
| T-026 | Attribute selected fallback-pool depth before a runtime proposal | 3 | S | T-015, T-024, T-025 | done; evidence only, numerical cap not implemented |
| T-027 | Separate recorded power regression from live RPC monitoring | 3 | M | T-015, T-024, T-025, T-031 | done; deployed d354179; actual upload, observer and following bot CI pass |
| T-028 | Preserve discovery completeness across malformed listings and interfaces | 3 | M | T-025 | done; deployed d44d79a, actual partial handoff observed |
| T-029 | Detect stale/incomplete snapshots after observation preservation | 3 | M | T-020, T-022 | done; deployed d44d79a, actual monitor 39055381257 |
| T-030 | Disclose selected liquidity with unchecked reserve amounts | 3 | M | T-026, T-028 | done; deployed d44d79a, both live markers observed |
| T-031 | Route discovery through existing configured on-chain providers | 3 | S | T-028, T-030 | done; deployed d354179; actual upload, observer and following bot CI pass |
| T-032 | Preserve complete and terminating inclusive backfill ranges | 3 | S | T-027 | done; deployed d354179; actual upload, observer and following bot CI pass |
| T-033 | Lock host Python build dependencies and verify credential-free Linux builds | 3 | M | T-032 | done; deployed d354179; actual upload, observer and following bot CI pass |
| T-034 | Keep rendered templates and pasted instructions from answering a gate | 3 | S | none | done; deployed d354179; actual upload, observer and following bot CI pass |
| T-035 | Lock existing Node and Pyodide package resolutions before deployment | 3 | M | T-033 | done; deployed d354179; actual upload, observer and following bot CI pass |
| T-036 | Pin supported Node 24 actions and the verified Ubuntu runner generation | 3 | M | T-033, T-035 | done; deployed d354179; actual upload, observer and following bot CI pass |
| T-037 | Make release guards and reproduction instructions report unavailable evidence | 3 | M | T-032, T-034 | done; deployed d354179; actual upload, observer and following bot CI pass |
| T-038 | Separate unavailable backfill observations from decoder contradictions | 3 | M | T-032, T-036 | done; deployed d354179; actual upload, observer and following bot CI pass |
| T-039 | Describe a withheld provisional score without a false unsupported-chain claim | 3 | S | T-038 | done; deployed d354179; actual upload, observer and following bot CI pass |
| T-040 | Keep failed requests and invalid ages out of coverage-probe observations | 3 | M | T-039 | done; published d82b98d, actual Linux and complete master CI pass |
| T-041 | Measure discovery status and deployment windows with aggregate-only evidence | 3 | M | T-028, T-039 | done; published d82b98d, actual optional readout succeeds, observation sufficiency separate |
| T-042 | Honor adopted simulator controls and preserve independent experiment runs | 3 | M | T-039 | done; published 66ffa4e, actual Linux/master CI and bounded screen complete; simulator decision remains open |
| T-043 | Preserve the pre-registered RugCheck study across bounded CI jobs | 3 | M | T-040 | source published; both fixed studies closed and exported; later report/integrity/owned stop verified, scientific readout inconclusive/censored |
| T-044 | Measure the existing held-out oracle quota without hidden retries or data publication | 3 | M | none | published 31cae13 after actual Linux/master gates; sole finite pilot complete, availability false, no quota/reset inference |
| T-045 | Preserve prospective enrollment and independently replayable paired evidence | 3 | M | none | published 31cae13 after actual Linux/master gates; immutable core remains offline, no thirty-day clock |
| T-046 | Acquire one due paired packet through a bounded native engine adapter | 3 | M | T-044, T-045 | source published 1de0259 after complete/Linux/master44; original control failed before requests, distinct direct-base control exposes datetime seam; T-052 repairs source, new bound control separate |
| T-048 | Select W57 checkpoints by verified chronology rather than opaque Artifact ID | 3 | M | T-043 | source published 1de0259 after complete/Linux/master44; actual original source_changed terminal and full export verified |
| T-051 | Record an honest undecided D checkpoint without changing its rule | 3 | S | T-024 | done; independent12/12/red-team none, complete44 and exact9dc8686 master39392487756/two locked builds pass; empirical D remains unavailable/undecided |
| T-052 | Preserve the engine datetime contract in native acquisition | 3 | S | T-046, T-051 | done source; independent12/12/red-team none, actual feature39399891382/45/two locked builds and post-merge9034ccf complete45 pass; live/runtime and scientific proof separate |
| T-053 | Select snapshot coverage by observed UTC chronology rather than append order | 1 | S | T-029 | done source; fresh ordinary12/12, executor/independent45, actual source Linux39440532687/two locked builds and post-merge859bed8 complete45 pass; real archive read-only CLI passes |
| T-054 | Preserve finite research slots inside bounded running CI sessions | 3 | M | T-043, T-048, T-053 | in progress; isolated tests-first implementation, no scientific enrollment |
| T-055 | Distinguish a disappeared Linux process from inaccessible identity | 2 | S | T-046, T-052 | source approved12/12; complete45 and actual Linux39917097945/two locked builds pass; integration/publication pending |
| T-056 | Compare an elapsed float budget at its representable precision | 1 | S | T-052 | source approved12/12; named test-only correction, complete45/Linux/two locked builds pass; integration/publication pending |
| T-057 | Start a refusal cancellation test after durable child headers | 1 | S | T-046, T-052, T-055, T-056 | in progress; isolated test-only synchronization, original failed gate retained |
