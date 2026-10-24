# Review: T-063 - Changes required

Head: `e01ad2d30773f3494aa2428cc97bb8058c3409dc`.
Implementation and contract base: `91e71cbb496472096ff04087e3940b976d88af85`.

## Required change

**[P2] A non-finite optional quote makes previously readable pool evidence unreadable.**
At `bench/snapshot.py:71`, the added raw quote can be a Python infinity after the
standard JSON parser accepts the valid numeric lexeme `1e400`. The existing real
writer at line 777 then emits `Infinity`. The unchanged strict reader rejects that
entire row, including its previously readable old fields.

An isolated fake-HTTP test used the actual `_fetch_pool_page`, collector, `main`
writer, NDJSON bytes, reader and real reader CLI. Both parent and candidate wrote
one line and returned success. The parent produced one parsed, eligible pool row
and no malformed row; the candidate produced no parsed or eligible pool row and
one malformed row. The input's primary price was the ordinary string `7`.

This is a prospective malformed-input seam regression against AC3/AC5. No actual
Vendor occurrence or historical token verdict change was observed. Repair the
bounded quote-capture contract and tests first. Keep JSON-representable raw values
exact; use an explicit fixed capture status for an unrepresentable value without
losing prior row information or relaxing the strict reader.

## Reproduced evidence

| AC | Result | Independent evidence |
|---|---|---|
| 1 | Pass | Native and legacy spellings remain independent literal counts; null, false, zero, containers, future and unknown-time rows are counted literally. |
| 2 | Pass | Actual fake-HTTP producer, real writer, exact NDJSON and real reader CLI agree at file and kind levels; prior output projection and bytes remain exact. |
| 3 | Changes required | Finite and JSON-representable quote values are retained exactly, but the overflowing numeric quote makes the entire saved row unreadable. |
| 4 | Pass | Actual saved quote strings 3 and 5 reproduce 6 and 10 through the unchanged pure pricing seam; primary-price edge semantics remain exact. |
| 5 | Changes required | Ordinary fetch options/order/count, privacy, clocks, limits and guards pass. The optional quote can nevertheless remove an otherwise readable row. |
| 6 | Pass | Contract holds. Exact first-finding parent gives 4 failed assertions; exact pre-quote source with corrected new fixture gives 19. Named B/C/D changes match their permissions. All 85 prior definitions and the old runner remain byte/AST exact in Git blobs. |
| 7 | Pending | Independent complete45 deliberately not run after the material finding. This is a withheld gate, not a failed gate. Other reviewers and later integration/release gates remain separate. |

The actual registered focused runner passed **855/0**, native exit **0**. The
three added acceptance functions passed **49/0**. Independent tiny probes passed
**72/0**. Omitting native `tx` and discarding the quote value both made acceptance
fail; restored in-memory source passed again. No repository source was mutated.
The original new Clock fixture without the native parser independently gives two
fixture failures; the authorized parser-only repair preserves its assertions.

All **1014 tracked raw files**, **145 archive files**, the five frozen controls and
their static local import closure, and the protected primary files remain exact.
Windows CRLF bytes and canonical Git bytes are recorded separately. The old
certificate was used only as an executed-source freeze reference. CI flags were
preserved. No network request, workflow, publication or research operation ran.

Rubric: spec **1**; scope **2**; correctness **0**; tests **1**; invariants **2**;
maintainability **2** = **8/12**.

**VERDICT: CHANGES_REQUIRED.** The candidate is held for the bounded regression;
passing focused checks do not establish readiness. The Windows heavy slot was
released without starting the independent complete45 gate.
