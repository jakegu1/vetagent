# Red-team review: T-063 R2

Head: `25bfb4324467f739b41e131f9d0078ae726812c1`.

This focused adversarial review covers the R1 regression class, A4/A5 and
regressions across the accepted producer/writer/strict-reader seam.

## What held up

- The valid JSON numeric lexemes 1e400 and -1e400 and nested nonfinite values
  cannot poison the newly retained quote: the old row is readable with a null
  quote and fixed capture status. The exact E parent reproduces 36 failures.
- Escaped lone high/low surrogates in scalar, nested value and object-key
  positions cannot break the actual ensure_ascii=False UTF-8 writer. Valid
  Unicode, an astral pair, finite extremes, containers and literal NaN/Infinity
  strings remain exact without failure status.
- Inputs are immutable; the full pre-existing raw-field projection is exact.
  Primary price, schema, response clock, HTTP order/options and three false
  replay/independence/full-engine flags are unchanged.
- The actual reader CLI exposes fixed aggregates and hashes; identity, raw
  quote values, capture-status details, URLs, paths and exception text are absent.
- Omitted-native, discarded-quote and missing-containment mutants fail the
  acceptance; restored source passes. Registered source/size/symlink/clock guards
  and the complete 45-command gate also pass.

Coverage is 24 bounded independent JSON/Unicode quote cases, alongside the
registered acceptance and guard tests. Existing source-size limits remain in
force; no universal raw-field-width claim is made.

## Material findings

None. R1's reproduced regression is closed on this exact source.

## Minor notes

None requiring a task follow-up. Private harness premise failures were retained
and corrected before being used as source evidence; they are not source findings.

**RED-TEAM: none.**
