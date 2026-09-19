"""Compare the fresh-clone benchmark run with the published results, under PREREG_fresh_clone_drift.md."""
import json
import os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
pub = json.load(open(os.path.join(HERE, "results.published.json"), encoding="utf-8"))
new = json.load(open(os.path.join(HERE, "fresh", "bench", "results.json"), encoding="utf-8"))


def cohort_counts(r):
    rows = r["rows"]
    alive = [x for x in rows if x["outcome_label"] == "alive"]
    dead = [x for x in rows if x["outcome_label"] == "dead"]
    unsafe = [x for x in rows if x["goplus_label"] == "unsafe"]
    return {
        "fp_alive_high": sum(1 for x in alive if x["verdict"] == "high"),
        "unknown": sum(1 for x in rows if x["verdict"] == "unknown"),
        "adversarial_high": sum(1 for x in unsafe if x["verdict"] == "high"),
        "adversarial_high_ablated": sum(1 for x in unsafe if x["verdict_ablated"] == "high"),
        "dead_high": sum(1 for x in dead if x["verdict"] == "high"),
        "dead_not_low": sum(1 for x in dead if x["verdict"] != "low"),
        "dead_not_low_ablated": sum(1 for x in dead if x["verdict_ablated"] != "low"),
        "false_blocks": r["false_block"]["blocked"],
        "false_block_n": r["false_block"]["n"],
        "centralized_high": r["centralized"]["verdict_distribution"].get("high", 0),
    }


P, N = cohort_counts(pub), cohort_counts(new)
bands = {"fp_alive_high": (2, 8), "unknown": (105, 139), "adversarial_high": (8, 12), "false_blocks": (25, 35)}
print("%-26s %9s %9s  %s" % ("figure", "published", "fresh", "pre-registered band"))
for k in P:
    band = bands.get(k)
    verdict = ""
    if band:
        verdict = "inside" if band[0] <= N[k] <= band[1] else "OUTSIDE"
        verdict = "%d..%d %s" % (band[0], band[1], verdict)
    print("%-26s %9s %9s  %s" % (k, P[k], N[k], verdict))

print("\nindependence overlap (fresh):", new["independence"]["overlap"])
print("n_evaluated:", pub["n_evaluated"], "->", new["n_evaluated"])


def our_side_unknowns(r):
    ours = 0
    for x in r["rows"]:
        if x["verdict"] != "unknown":
            continue
        reasons = x.get("gap_reasons") or []
        if reasons and all(str(g).startswith("upstream request failed") for g in reasons):
            ours += 1
    return ours


print("unknown rows whose every gap reason is 'upstream request failed': published %d, fresh %d"
      % (our_side_unknowns(pub), our_side_unknowns(new)))

# row-by-row flips
key = lambda x: (x["chain"], x["address"].lower())
pm = {key(x): x for x in pub["rows"]}
nm = {key(x): x for x in new["rows"]}
flips = Counter()
examples = []
for k, a in pm.items():
    b = nm.get(k)
    if b is None:
        flips["missing in fresh"] += 1
        continue
    if a["verdict"] != b["verdict"]:
        flips["%s -> %s" % (a["verdict"], b["verdict"])] += 1
        examples.append((a["symbol"], a["chain"], a["outcome_label"], a["goplus_label"], a["verdict"], b["verdict"],
                         b["driver"], (b.get("gap_reasons") or [])[:2]))
print("\nverdict flips, published -> fresh: %d of %d rows" % (sum(flips.values()), len(pm)))
for k, v in flips.most_common():
    print("  %3d  %s" % (v, k))
print("\nflipped rows (symbol, chain, outcome, goplus, old, new, new driver, new gap reasons):")
for e in examples:
    print("  ", e)
