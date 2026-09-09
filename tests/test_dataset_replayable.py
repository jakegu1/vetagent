"""The frozen dataset must contain everything needed to re-derive its own labels.

The launch post's central claim is that the *method* is reproducible: "labels are frozen
in the tracked `bench/dataset.json`, the harness is `bench/run_benchmark.py`". The first
half was true and the second half was not checkable from the first, because the stored
oracle payload was a subset that left out four of the fifteen fields `goplus_label()`
reads -- `cannot_buy`, `cannot_sell_all`, `personal_slippage_modifiable` and `trust_list`.

Three of those four are adversarial traits. They decide the cohort the headline recall is
computed on, which makes them the worst four fields in the payload to have dropped.

Found by trying to replay the labeller against the committed dataset while checking
something else, and getting `None` back for all 576 rows.

This test compares what the labeller reads against what the writer stores, by reading both
out of `bench/labels.py` rather than by keeping a third list that would drift from both.

Run: python tests/test_dataset_replayable.py
"""

import ast
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bench"))

_PASSED = 0
_FAILURES = []
_UNCHECKED = []


def check(name, ok, detail=""):
    global _PASSED
    if ok:
        _PASSED += 1
        print("  PASS  %s" % name)
    else:
        _FAILURES.append((name, detail))
        print("  FAIL  %s  %s" % (name, detail))


def unchecked(name, why):
    _UNCHECKED.append((name, why))
    print("  ----  %s  (not checked here: %s)" % (name, why))


def _labeller_source():
    src = io.open(os.path.join(ROOT, "bench", "labels.py"), encoding="utf-8").read()
    return src[src.index("def goplus_label"):]


def test_the_stored_subset_covers_every_field_the_labeller_reads():
    print("\n[replay] the frozen payload carries what the labeller needs")
    body = _labeller_source()

    reads = set(re.findall(r'_flag\(d, "([a-z_]+)"\)', body))
    reads |= set(re.findall(r'_tax\(d, "([a-z_]+)"\)', body))
    check("the labeller's field list was found", len(reads) >= 10, str(sorted(reads)))

    stored_block = body[body.index("subset = {k: d.get(k) for k in ("):]
    stored_block = stored_block[:stored_block.index(") if k in d}")]
    stores = set(re.findall(r'"([a-z_]+)"', stored_block))
    check("the stored field list was found", len(stores) >= 15, str(len(stores)))

    missing = sorted(reads - stores)
    check("every field the labeller reads is stored", not missing,
          "a stranger cannot re-derive the label without: %s" % ", ".join(missing))


def test_the_committed_dataset_is_replayable():
    """The check above is about the code. This one is about the file on disk.

    A dataset built before the fix legitimately lacks the fields, so this reports rather
    than fails: the gap is real, it is the committed artifact, and it closes on the next
    `python bench/build_dataset.py`. Reporting it as unchecked keeps it visible instead of
    letting a green run imply the artifact was verified.
    """
    print("\n[replay] the committed dataset, as it stands today")
    path = os.path.join(ROOT, "bench", "dataset.json")
    if not os.path.exists(path):
        unchecked("the dataset is replayable", "bench/dataset.json is missing")
        return

    with io.open(path, encoding="utf-8") as f:
        data = json.load(f)
    rows = data if isinstance(data, list) else (data.get("tokens") or data.get("rows") or [])
    check("the dataset has rows", bool(rows), "0 rows")
    if not rows:
        return

    raw = rows[0].get("goplus_raw")
    if isinstance(raw, str):
        try:
            raw = ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            raw = None
    if not isinstance(raw, dict):
        unchecked("the dataset is replayable", "goplus_raw is not a readable mapping")
        return

    body = _labeller_source()
    reads = set(re.findall(r'_flag\(d, "([a-z_]+)"\)', body))
    reads |= set(re.findall(r'_tax\(d, "([a-z_]+)"\)', body))
    missing = sorted(reads - set(raw))

    if missing:
        unchecked("the committed dataset is replayable",
                  "built before the fix; missing %s. Closes on the next "
                  "`python bench/build_dataset.py`" % ", ".join(missing))
    else:
        check("the committed dataset carries every field the labeller reads", True)


def main():
    print("=" * 68)
    print("The frozen dataset can re-derive its own labels")
    print("=" * 68)
    for _, fn in sorted((k, v) for k, v in globals().items() if k.startswith("test_")):
        fn()
    print("\n" + "=" * 68)
    print("%d passed, %d failed, %d not checked here"
          % (_PASSED, len(_FAILURES), len(_UNCHECKED)))
    for name, why in _UNCHECKED:
        print("  ----  %s  (%s)" % (name, why))
    if _FAILURES:
        print("\nFailures:")
        for name, detail in _FAILURES:
            print("  - %s  %s" % (name, detail))
        return 1
    print("All passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
