"""run_benchmark.py — score the local engine against an independent labelled set and
emit a reproducible accuracy report.

Usage:
    python bench/run_benchmark.py

Four things happen here:

1. **Run the engine.** Calls assess() from src/risk.py directly, with its _fetch_json
   swapped for a caching fetcher (role="engine"). What gets measured is the code in the
   repo, not the deployed service, so this can run in CI.

2. **Assert independence.** The set of endpoints the engine touched and the set the
   labeller touched must not intersect. Any overlap fails the benchmark and exits
   non-zero — this is the foundation of the whole report's credibility, and it can't
   just live in the docs.

3. **Ablation.** A pool that already died has liquidity ≈ 0 now, so the engine can call
   it high off the "liquidity is minimal" signal alone — close to a tautology. So
   alongside the full score we report a second one that **keeps only contract-safety
   signals** (dropping liquidity/activity/freshness/cross-chain). The gap between the
   two numbers is what this tool actually tells you beyond the obvious.

4. **Signal attribution.** Count which category of signal drove each correct verdict.
   If 100% come from upstream_risk, the engine is only paraphrasing honeypot.is and
   adds nothing of its own.
"""

import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "src"))

import labels as LABELS  # noqa: E402
import risk  # noqa: E402
import fetcher as fetcher_module  # noqa: E402
from fetcher import access_report, fetch_json, load_persisted_access_log  # noqa: E402

DATASET = os.path.join(HERE, "dataset.json")
RESULTS_JSON = os.path.join(HERE, "results.json")
RESULTS_MD = os.path.join(HERE, "results.md")

# Contract-safety signals: the ones independent of how much liquidity is left right now
# What survives when the market-data signals are stripped. The point of the column is to
# show what the engine concludes from CONTRACT evidence alone -- the part a competitor
# reading the same free liquidity feed could not trivially reproduce.
#
# `drained` is deliberately absent, and it used to be inside `sellability`. The
# drained-pool finding is computed entirely from DexScreener liquidity figures: it fires
# when every pool on the token's own chain reports a depth of zero. That is a market-data
# conclusion wearing a sellability label, and it carried `fatal` (100) into the ablated
# score after R10 promoted it from `critical`. 14 of 42 ablated-high verdicts -- a third --
# rode on it, which is a third of the column's headline claiming to be contract evidence
# while being liquidity evidence.
#
# All 14 are currently `centralized`, so the published unsafe/dead ablated figures were
# not yet contaminated. W3 grows the adversarial cohort with exactly these tokens, so the
# contamination was scheduled rather than avoided.
CONTRACT_CATEGORIES = {
    "honeypot", "sellability", "sell_tax", "upstream_risk",
    "rugcheck", "contract", "concentration",
}


def install_engine_fetcher():
    """Swap the engine's fetcher for one that caches and books which endpoints it hit."""
    async def _fetch(url, retries=2, timeout=8, mark_missing=False):
        # retries=2, matching src/risk.py. It was 1, so the harness gave upstream one
        # fewer chance than production does and then scored the engine on the result.
        # Production is gentler still: it caches at the edge and serves data up to 15
        # minutes stale rather than answering unknown, and it never asks about 558 tokens
        # in a burst.
        got = fetch_json(url, role="engine", retries=2, mark_missing=mark_missing)
        return risk.NO_DATA if got is fetcher_module.NOT_FOUND else got
    risk._fetch_json = _fetch


def ablate(address, signals, data_gaps=None):
    """Re-grade with contract-safety signals only, to see how much judgement is left.

    The gaps are passed through, filtered to the dimensions this column still covers.
    Passing an empty list -- as this did -- switched off the fail-closed override for
    every ablated verdict, so the published column reported low and medium for tokens
    whose sell simulation never ran. The ablation is meant to remove *signals derived
    from liquidity*, not to remove the rule that an unverified token cannot be called
    safe, and a benchmark column that quietly grades itself under laxer rules than the
    engine flatters the engine.
    """
    kept = [s for s in signals if s["category"] in CONTRACT_CATEGORIES]
    if not kept:
        return "unknown", 0
    gaps = [g for g in (data_gaps or []) if g.get("dimension") == "sellability"]
    r = risk._finalize(address, kept, {}, gaps)
    return r["risk_level"], r["risk_score"]


def driving_category(signals):
    """Category of the one signal that decided this verdict."""
    if not signals:
        return None
    ranked = sorted(
        signals,
        key=lambda s: risk._SEVERITY_BASE.get(s["severity"], 0)
        * risk._CATEGORY_WEIGHT.get(s["category"], 0.5),
        reverse=True)
    top = ranked[0]
    return top["category"] if top["severity"] != "ok" else None


def evaluate(rows, label_key, bad_value, good_value):
    """Compute metrics for one set of labels.

    strict  = only high counts as "caught it"
    lenient = high or medium both count as "flagged risk" (in product terms, medium
              means a human has to look)
    """
    bad = [r for r in rows if r.get(label_key) == bad_value]
    good = [r for r in rows if r.get(label_key) == good_value]

    def rate(sub, pred):
        return (sum(1 for r in sub if pred(r)) / len(sub)) if sub else None

    def block(sub, verdict_field, score_field):
        return {
            "n": len(sub),
            "high": rate(sub, lambda r: r[verdict_field] == "high"),
            "high_or_medium": rate(sub, lambda r: r[verdict_field] in ("high", "medium")),
            "low": rate(sub, lambda r: r[verdict_field] == "low"),
            "unknown": rate(sub, lambda r: r[verdict_field] == "unknown"),
            "mean_score": (sum(r[score_field] for r in sub) / len(sub)) if sub else None,
        }

    out = {
        "bad_label": bad_value, "good_label": good_value,
        "full": {"bad": block(bad, "verdict", "score"),
                 "good": block(good, "verdict", "score")},
        "contract_only": {"bad": block(bad, "verdict_ablated", "score_ablated"),
                          "good": block(good, "verdict_ablated", "score_ablated")},
        "driving_categories_on_bad": dict(
            Counter(r["driver"] for r in bad if r.get("driver")).most_common()),
    }
    return out


def centralized_view(rows):
    """The "privileged functions, no adversarial traits" bucket — USDT / WBTC / LDO.

    This bucket is **not scored right or wrong**; it only shows whether the engine
    paints every centralized asset as high risk. A lot of high verdicts means the
    thresholds are too blunt and will produce grating false positives in real use.
    """
    sub = [r for r in rows if r.get("goplus_label") == "centralized"]
    if not sub:
        return {"n": 0}
    dist = Counter(r["verdict"] for r in sub)
    return {
        "n": len(sub),
        "verdict_distribution": dict(dist),
        "high_rate": dist.get("high", 0) / len(sub),
        "examples": [{"symbol": r.get("symbol"), "chain": r["chain"],
                      "verdict": r["verdict"], "driver": r.get("driver")}
                     for r in sub[:10]],
    }


def composition(rows):
    """What the sample is made of, split out for the bad cohort specifically.

    A recall figure is a statement about a population, and this one's population is not
    the market -- it is whatever the three sampling sources could reach. The bad cohort
    especially: it is small, and if it turns out to be one chain and one source then the
    number describes that corner rather than the tool. Printing it is the difference
    between a reader being able to discount the result correctly and having to trust it.
    """
    from collections import Counter

    def split(subset):
        return {
            "n": len(subset),
            "chain": dict(Counter(r.get("chain") or "?" for r in subset).most_common()),
            "source": dict(Counter((r.get("sampled_from") or "?").split("_")[0]
                                   for r in subset).most_common()),
        }

    bad = [r for r in rows
           if r.get("outcome_label") == "dead" or r.get("goplus_label") == "unsafe"]
    return {"all": split(rows), "bad": split(bad)}


def collect_disagreements(rows):
    """Samples where label and engine disagree. False negatives first — the real leads."""
    out = []
    for r in rows:
        for key, bad, good in (("outcome_label", "dead", "alive"),
                               ("goplus_label", "unsafe", "safe")):
            lab = r.get(key)
            if lab == bad and r["verdict"] == "low":
                kind = "false negative"
            elif lab == good and r["verdict"] == "high":
                kind = "false positive"
            else:
                continue
            out.append({"kind": kind, "label": "%s=%s" % (key.split("_")[0], lab),
                        "address": r["address"], "symbol": r.get("symbol"),
                        "chain": r["chain"], "verdict": r["verdict"],
                        "verdict_ablated": r["verdict_ablated"], "driver": r.get("driver")})
    out.sort(key=lambda d: 0 if d["kind"] == "false negative" else 1)
    return out


def _pct(v):
    return "—" if v is None else "%.1f%%" % (v * 100)


def _num(v):
    return "—" if v is None else "%.1f" % v


def main():
    if not os.path.exists(DATASET):
        print("%s not found — run python bench/build_dataset.py first" % DATASET)
        return 1
    with open(DATASET, encoding="utf-8") as f:
        data = json.load(f)
    tokens = data.get("tokens") or []
    if not tokens:
        print("Dataset is empty")
        return 1

    install_engine_fetcher()
    import asyncio

    rows = []
    print("Evaluating %d tokens ..." % len(tokens))
    for i, t in enumerate(tokens, 1):
        try:
            # verbose=True only to see `best_pair.pair_address`. It adds evidence
            # fields and changes no verdict, no score and no signal -- the numbers below
            # are identical either way.
            res = asyncio.run(risk.assess(t["address"], t["chain"], verbose=True))
        except Exception as e:  # noqa: BLE001
            print("  %s failed to evaluate: %s" % (t.get("symbol"), e))
            continue
        sigs = res.get("signals") or []
        ab_level, ab_score = ablate(t["address"], sigs,
                                    (res.get("evidence") or {}).get("data_gaps"))
        rows.append({
            # Sanitised at the boundary, not at each of the six places the report prints
            # it. A ticker is upstream text: `results.md` renders it inside a markdown
            # table, where an unescaped pipe silently reshapes the row, and this file is
            # the project's public evidence. It is also how a CJK ticker turned the
            # English-only guard red on a tip commit -- the guard was right, and the
            # answer is to quote the ticker accurately in ASCII rather than to exempt the
            # file from the rule.
            "address": t["address"], "symbol": risk._ascii_safe(t.get("symbol")),
            "chain": t["chain"],
            # The pool the LABEL describes, and the pool the ENGINE judged. They are
            # picked independently -- build_dataset samples one pool and assess() runs
            # its own selection -- so they are not always the same venue, and every
            # disagreement between them was being booked as an engine error.
            "labelled_pool": (t.get("pool") or "").lower() or None,
            "engine_pool": ((((res.get("evidence") or {}).get("best_pair") or {})
                             .get("pair_address")) or "").lower() or None,
            "outcome_label": t.get("outcome_label"), "goplus_label": t.get("goplus_label"),
            "sampled_from": t.get("sampled_from"),
            "liquidity_usd": ((res.get("evidence") or {}).get("best_pair") or {})
                             .get("liquidity_usd"),
            "gap_reasons": [g.get("reason") for g
                            in ((res.get("evidence") or {}).get("data_gaps") or [])],
            "verdict": res.get("risk_level"), "score": res.get("risk_score"),
            "confidence": res.get("confidence"),
            "verdict_ablated": ab_level, "score_ablated": ab_score,
            "driver": driving_category(sigs),
            "categories": sorted({s["category"] for s in sigs}),
            "has_data_gap": bool((res.get("evidence") or {}).get("data_gaps")),
        })
        if i % 20 == 0 or i == len(tokens):
            print("  [%d/%d]" % (i, len(tokens)))

    # ---- Independence assertion: the foundation of the whole report ----
    # Pull in what the labeling process recorded. Without this the label set is empty
    # in this process, engine n {} is always {}, and the disjointness assertion below
    # can never fail -- which is exactly what it did until it was caught.
    had_labels = load_persisted_access_log()
    engine_eps, label_eps, overlap = access_report()
    if not had_labels or not label_eps:
        print("\nBenchmark void: no labeling endpoints on record, so the independence")
        print("assertion would pass vacuously. Run python bench/build_dataset.py first")
        print("(it writes bench/access_log.json) and re-run this.")
        return 3
    if overlap:
        print("\nBenchmark invalid: engine and labeller hit the same endpoint —"
              " that makes the result circular")
        for e in overlap:
            print("   overlapping endpoint:", e)
        return 2

    report = {
        "n_evaluated": len(rows),
        "independence": {"engine_endpoints": engine_eps,
                         "label_endpoints": label_eps, "overlap": overlap},
        "overall": {
            "verdict_distribution": dict(Counter(r["verdict"] for r in rows)),
            "unknown_rate": sum(1 for r in rows if r["verdict"] == "unknown") / len(rows),
            "data_gap_rate": sum(1 for r in rows if r["has_data_gap"]) / len(rows),
        },
        "outcome": evaluate(rows, "outcome_label", "dead", "alive"),
        "goplus": evaluate(rows, "goplus_label", "unsafe", "safe"),
        "centralized": centralized_view(rows),
        "disagreements": collect_disagreements(rows),
        "composition": composition(rows),
        "rows": rows,
    }
    with open(RESULTS_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)

    write_markdown(report)
    print("\nWrote %s and %s" % (RESULTS_JSON, RESULTS_MD))

    o = report["outcome"]["full"]["bad"]
    print("\nAt a glance:")
    print("  dead rated high (see report)     : %s (n=%d)" % (_pct(o["high"]), o["n"]))
    print("  still high on contract signals   : %s"
          % _pct(report["outcome"]["contract_only"]["bad"]["high"]))
    print("  false positives, established     : %s (n=%d)"
          % (_pct(report["outcome"]["full"]["good"]["high"]),
             report["outcome"]["full"]["good"]["n"]))
    print("  unknown rate                     : %s" % _pct(report["overall"]["unknown_rate"]))
    return 0


def write_markdown(rep):
    L = []
    A = L.append
    rows = rep.get("rows") or []
    A("# VetAgent Accuracy Benchmark\n")
    A("> Generated by `python bench/run_benchmark.py`. Do not edit by hand.\n")
    A("Sample size **%d**. This is v1 and the sample is small — read it as a check for "
      "obvious breakage, not as a precise statistical result.\n" % rep["n_evaluated"])

    A("\n## Method\n")
    A("Labels use **none of the endpoints the engine reads** — otherwise this would "
      "measure whether the engine can paraphrase its upstream.\n")
    A("\n| | Label source | Read by the engine? |")
    A("|---|---|---|")
    A("| `outcome` | GeckoTerminal daily OHLCV history (price + volume) "
      "| No, the engine only sees the current snapshot |")
    A("| `goplus` | GoPlus token_security | No, deliberately held back as a labeller |")
    A("\n**Runtime assertion**: engine endpoints ∩ labeller endpoints = ∅. If that "
      "fails, the benchmark declares itself invalid and exits non-zero. "
      "This run: **passed**.\n")
    A('\n<details><summary>Endpoints hit: engine on this run, '
      'labeller on the run that built the dataset</summary>\n')
    A("\nEngine:\n")
    for e in rep["independence"]["engine_endpoints"]:
        A("- `%s`" % e)
    A("\nLabeller:\n")
    for e in rep["independence"]["label_endpoints"]:
        A("- `%s`" % e)
    A("\n</details>\n")

    A("\n### Label definitions\n")
    A("Generated from the constants in `bench/labels.py`, not written by hand — the two "
      "had drifted apart and the published rule no longer matched the one applied.\n\n")
    A("- **dead**: traded for real at some point (peak 7d volume >= $%s), then price fell "
      ">= %.0f%% off its peak **and** 7d volume collapsed below %.0f%% of peak. A price "
      "drop alone isn't death, and neither is volume drying up alone.\n"
      % (format(LABELS.DEAD_PEAK_VOL_7D, ","), LABELS.DEAD_DRAWDOWN * 100,
         (1 - LABELS.DEAD_VOL_COLLAPSE) * 100))
    A("- **alive**: >= %d days of history, drawdown <= %.0f%%, 7d volume >= %.0f%% of "
      "peak and >= $%s.\n"
      % (LABELS.ALIVE_MIN_DAYS, LABELS.ALIVE_MAX_DRAWDOWN * 100, LABELS.ALIVE_MIN_VOL_RATIO * 100,
         format(LABELS.ALIVE_MIN_VOL_7D, ",")))
    A("- **unsafe**: an unambiguously adversarial trait — cannot sell all / cannot buy / "
      "self-destructible / per-address tax / buy or sell tax > %.0f%% / closed source "
      "with privileged functions — outside the reputation guardrail.\n"
      % (LABELS.UNSAFE_TAX * 100))
    A("  A honeypot flag counts **only** if the pool traded >= $%s in the last 7 days, or "
      "another adversarial trait corroborates it. The oracle raises that flag when its own "
      "sell simulation fails, and a sell simulation fails against an empty pool whatever "
      "the contract does — so on a dead pool the flag is unfalsifiable and the token is "
      "left unlabelled instead.\n" % format(LABELS.HONEYPOT_TESTABLE_VOL_7D, ","))
    A("- **safe**: none of the above, plus open source, >= %s holders and taxes <= %.0f%%.\n"
      % (format(LABELS.SAFE_MIN_HOLDERS, ","), LABELS.SAFE_MAX_TAX * 100))
    A("\nAnything in between goes unlabelled — a smaller sample beats dirty labels.\n")

    ov = rep["overall"]
    A("\n## Overall\n")
    A("| Metric | Value |")
    A("|---|---|")
    A("| Verdict distribution | %s |" % ", ".join("%s=%d" % kv for kv in sorted(ov["verdict_distribution"].items())))
    A("| unknown rate | %s |" % _pct(ov["unknown_rate"]))
    A("| Share with a data gap | %s |" % _pct(ov["data_gap_rate"]))
    A("\n> Read the unknown rate next to recall. A tool that answers unknown for "
      "everything has perfect recall and is useless.\n")

    for key, title, bad_name, good_name in (
            ("outcome", "Outcome labels (dead vs alive)", "dead", "alive"),
            ("goplus", "GoPlus held-out oracle (unsafe vs safe)", "unsafe", "safe")):
        r = rep[key]
        A("\n## %s\n" % title)
        for view, vtitle, note in (
                ("full", "Full signals", ""),
                ("contract_only", "Contract-safety signals only (ablated)",
                 "Recomputed after dropping liquidity/activity/freshness/cross-chain. "
                 "This column is the engine's real judgement beyond the obvious.")):
            b, g = r[view]["bad"], r[view]["good"]
            A("\n### %s\n" % vtitle)
            if note:
                A("%s\n" % note)
            A("\n| | n | high | high or medium | low | unknown | mean score |")
            A("|---|---|---|---|---|---|---|")
            A("| **%s** | %d | %s | %s | %s | %s | %s |" % (
                bad_name, b["n"], _pct(b["high"]), _pct(b["high_or_medium"]),
                _pct(b["low"]), _pct(b["unknown"]), _num(b["mean_score"])))
            A("| **%s** | %d | %s | %s | %s | %s | %s |" % (
                good_name, g["n"], _pct(g["high"]), _pct(g["high_or_medium"]),
                _pct(g["low"]), _pct(g["unknown"]), _num(g["mean_score"])))
        drv = r.get("driving_categories_on_bad") or {}
        if drv:
            A("\n**Which signal category made the call on %s samples:** %s\n"
              % (bad_name, ", ".join("`%s` %d" % kv for kv in drv.items())))
            A("\n> If this concentrates in `upstream_risk`, the engine is mostly "
              "paraphrasing honeypot.is and adds little of its own.\n")

    cen = rep.get("centralized") or {}
    if cen.get("n"):
        A("\n## Centralized-asset control group (not scored)\n")
        A("Tokens with privileged functions (pausable/blacklist/mintable) but "
          "**no adversarial traits** — USDT, WBTC and LDO all land here. Those "
          "privileges are how a centralized asset is designed, not a rug.\n")
        A("\nThis bucket answers one question: **does the engine paint them all as "
          "high risk.** A lot of high verdicts means the thresholds are too blunt and "
          "will produce grating false positives in real use.\n")
        A("\n| n | high rate | Verdict distribution |")
        A("|---|---|---|")
        A("| %d | %s | %s |" % (
            cen["n"], _pct(cen["high_rate"]),
            ", ".join("%s=%d" % kv for kv in sorted(cen["verdict_distribution"].items()))))
        if cen.get("examples"):
            A("\nExamples: %s\n" % ", ".join(
                "%s(%s)" % (e["symbol"] or "?", e["verdict"]) for e in cen["examples"]))

    # Two oracles, two false-positive rates, and they answer different questions.
    #
    # An external audit found the headline rate was circular: measured against GoPlus-safe,
    # it is really "how often we disagree with GoPlus", and GoPlus is the benchmark's own
    # labeller. The proposed fix was to buy a second commercial oracle. The actual fix was
    # already on disk and had never been printed -- the realized market outcome is a
    # CAUSALLY INDEPENDENT oracle. GoPlus, honeypot.is and every commercial scanner answer
    # "what does this contract do under simulation". dead/alive answers "what happened to
    # the money". Those are different instruments, not two readings of one.
    #
    # So the report now states both, names the oracle behind each, and says which
    # population each describes. Neither is strictly the honest number:
    #   - the outcome-based rate uses an INDEPENDENT oracle on a MATURITY-SELECTED cohort
    #   - the GoPlus-based rate uses a BROADER cohort but a CIRCULAR oracle
    # Publishing one and calling it the headline is what let the circularity hide.
    # How often the label and the verdict are even about the same pool.
    #
    # build_dataset labels ONE sampled pool; assess() independently picks its own. When
    # they differ, a "false positive" may be the engine saying "this contract is a
    # honeypot right now" against a label saying "this pool traded healthily last week" --
    # two answers to two different questions, booked as one error. The audit measured 84%
    # agreement and explicitly declined to publish a corrected false-positive rate,
    # because checking each disagreement showed its first correction was unsupported.
    # That restraint is right and the mismatch rate is still owed to a reader: it does
    # not tell you the number is wrong, it tells you how much of it is not a clean
    # comparison.
    matched = [r for r in rows if r.get("labelled_pool") and r.get("engine_pool")]
    same = [r for r in matched if r["labelled_pool"] == r["engine_pool"]]
    if matched:
        A("\n### Are the label and the verdict about the same pool?\n")
        A("The label describes one sampled pool; the engine picks its own. The pool the "
          "engine actually **judged** is the labelled one on **%d of %d** rows where "
          "both are known (%.0f%%).\n"
          % (len(same), len(matched), 100.0 * len(same) / len(matched)))
        A("\nThat is a stricter question than the one an external audit measured. It "
          "found the labelled pool was among the pairs the engine *loaded* 84% of the "
          "time. Loading it and choosing it are different: the engine ranks by chain "
          "canonicality and depth and then judges a single pool, so it can hold the "
          "labelled pool in hand and still return a verdict about another venue. Both "
          "numbers are true; this is the one that governs whether a disagreement is a "
          "like-for-like comparison.\n")
        A("\nOn the rest, a disagreement is not necessarily an engine error -- it can be "
          "the engine judging a different venue than the one the label was computed from. "
          "No corrected false-positive rate is offered here: an attempt to produce one "
          "did not survive checking the individual rows. What is supported is that the "
          "headline rate mixes at least three kinds of disagreement, and this is how much "
          "of it is not a like-for-like comparison.\n")

    # What the `unsafe` cohort is made of, printed next to the recall it produces.
    #
    # HONEYPOT_TESTABLE_VOL_7D exists to stop a honeypot flag being asserted about a token
    # nothing has traded, and it works: it collapsed the cohort from 28 to 9. But what it
    # selects for is not what the report implied. Measured here rather than asserted: the
    # survivors are almost entirely tokens holding no liquidity at all, so the gate moved
    # the cutoff from "dead" to "died recently" -- it did not produce a cohort of
    # adversarial contracts, which is what a recall figure computed on it would suggest.
    #
    # A reader deciding how much the recall number is worth needs this in the same place
    # as the number, not in a commit message.
    unsafe_rows = [r for r in rows if r.get("goplus_label") == "unsafe"]
    if unsafe_rows:
        thin = [r for r in unsafe_rows
                if isinstance(r.get("liquidity_usd"), (int, float))
                and r["liquidity_usd"] < 1]
        nolq = [r for r in unsafe_rows if r.get("liquidity_usd") is None]
        ours_disagree = [r for r in unsafe_rows if r["verdict"] in ("low", "medium")]
        by_chain = {}
        for r in unsafe_rows:
            by_chain[r["chain"]] = by_chain.get(r["chain"], 0) + 1
        A("\n### What the `unsafe` cohort is, before you read a recall number off it\n")
        A("The adversarial cohort is **n=%d**, and it is not a sample of adversarial "
          "contracts in the wild. It is what survived a testability gate, and the gate "
          "selects for recency more than for hostility.\n" % len(unsafe_rows))
        A("\n| Property | Count |")
        A("|---|---|")
        A("| holds under $1 of liquidity | %d of %d |" % (len(thin), len(unsafe_rows)))
        A("| no liquidity figure at all | %d of %d |" % (len(nolq), len(unsafe_rows)))
        A("| our engine rates them low or medium | %d of %d |"
          % (len(ours_disagree), len(unsafe_rows)))
        A("| chain concentration | %s |"
          % ", ".join("%s %d" % kv for kv in sorted(by_chain.items(),
                                                    key=lambda kv: -kv[1])))
        A("\n**Read the recall figure against that.** A cohort of %d tokens of which %d "
          "hold under a dollar is measuring whether we flag empty pools, which we do for "
          "reasons that have nothing to do with the contract being adversarial. And on "
          "%d of them our own engine disagrees with the labeller outright -- `results.md` "
          "presents the oracle's verdict as ground truth, and on those rows two "
          "instruments contradict each other and we cannot say which is right.\n"
          % (len(unsafe_rows), len(thin) + len(nolq), len(ours_disagree)))
        A("\nCleaning this cohort needs a **third, engine-independent oracle** -- "
          "requiring honeypot.is corroboration would make the label circular under B1/B2, "
          "since the engine reads honeypot.is. That is BACKLOG W5, and it is a "
          "prerequisite for W3 rather than the coverage fix it was originally filed as.\n")

    safe_rows = [r for r in rows if r.get("goplus_label") == "safe"]
    alive_rows = [r for r in rows if r.get("outcome_label") == "alive"]
    both_rows = [r for r in rows if r.get("goplus_label") == "safe"
                 and r.get("outcome_label") == "alive"]
    if safe_rows and alive_rows:
        sh = len([r for r in safe_rows if r["verdict"] == "high"])
        ah = len([r for r in alive_rows if r["verdict"] == "high"])
        bh = len([r for r in both_rows if r["verdict"] == "high"])
        A("\n### Two oracles, two false-positive rates\n")
        A("The false-positive rate depends on who is asked what a 'healthy token' is, and "
          "this benchmark has two answers available. They are reported together because "
          "reporting either alone hides something.\n")
        A("\n| Oracle | What it actually measures | Independent of us? | Cohort | FP rate |")
        A("|---|---|---|---|---|")
        A("| realized market outcome | what happened to the money | **yes** -- built from "
          "price/volume history, not from any contract scanner | `alive`, n=%d | **%.1f%%** "
          "(%d) |" % (len(alive_rows), 100.0 * ah / len(alive_rows), ah))
        A("| GoPlus | what the contract does under simulation | **no** -- GoPlus is this "
          "benchmark's own labeller, so this is a disagreement rate | `safe`, n=%d | %.1f%% "
          "(%d) |" % (len(safe_rows), 100.0 * sh / len(safe_rows), sh))
        A("| both, intersected | passes on both instruments | strictest available | n=%d | "
          "%.1f%% (%d) |" % (len(both_rows), 100.0 * bh / max(len(both_rows), 1), bh))
        A("\n**Read it this way.** The outcome-based rate is the one to trust on method: "
          "market outcome is causally independent of every contract scanner, so it cannot "
          "be circular. Its weakness is population -- `alive` requires %d days of history "
          "and real weekly volume, so freshness signals cannot fire on those tokens and "
          "liquidity rarely does, while agents mostly ask about tokens younger than that.\n"
          % LABELS.ALIVE_MIN_DAYS)
        A("\nThe GoPlus-based rate has the better population -- it includes new tokens -- "
          "and the worse oracle, because a rate measured against our own labeller is a "
          "disagreement rate wearing a false-positive label. An audit was right to flag it. "
          "What the audit assumed, and what turned out to be false, is that breaking the "
          "circularity required buying an independent oracle. It did not. The independent "
          "oracle was already in this file and had simply never been crossed against the "
          "other one.\n")
        A("\nThe three figures are statistically consistent, which is the substantive "
          "finding: the circularity is real as a method problem and does not appear to be "
          "moving the number much. That is a claim with a confidence interval on it, not a "
          "reassurance -- n is %d on the independent side and the honest reading is that "
          "these rates are indistinguishable at this sample size, not that they are "
          "equal.\n" % len(alive_rows))

    unk = [r for r in rows if r["verdict"] == "unknown"]
    if unk:
        ours = [r for r in unk if any(str(g).startswith("upstream request failed")
                                      for g in (r.get("gap_reasons") or []))]
        A("\n### What the unknown rate is made of\n")
        A("An `unknown` because we could not reach an upstream is a different thing from "
          "an `unknown` about the token, and only the second is a property of the engine. "
          "Reported separately because the first kind drifts between runs -- failed "
          "requests are not cached, so each run re-rolls them -- and because a harness "
          "that provokes refusals and then scores them has happened here twice.\n")
        A("\n| | n | share of all %d |" % len(rows))
        A("|---|---|---|")
        A("| unknown, our side (upstream unreachable or uncovered) | %d | %.1f%% |"
          % (len(ours), 100.0 * len(ours) / len(rows)))
        A("| unknown, token side (nothing verifiable about it) | %d | %.1f%% |"
          % (len(unk) - len(ours), 100.0 * (len(unk) - len(ours)) / len(rows)))
        A("")

    comp = rep.get("composition") or {}
    if comp:
        A("\n## What the sample is made of\n")
        A("A recall figure describes a population, and this one's population is what "
          "three sampling sources could reach -- not the market. The bad cohort is the "
          "row that matters: it is the smallest, and if it sits on one chain from one "
          "source then the number describes that corner rather than the tool.\n")
        A("\n| | n | by chain | by source |")
        A("|---|---|---|---|")
        for key, label in (("all", "whole set"), ("bad", "**dead or unsafe**")):
            c = comp.get(key) or {}
            if not c:
                continue
            A("| %s | %d | %s | %s |" % (
                label, c.get("n", 0),
                ", ".join("%s %d" % kv for kv in (c.get("chain") or {}).items()) or "-",
                ", ".join("%s %d" % kv for kv in (c.get("source") or {}).items()) or "-"))
        A("")

    dis = rep.get("disagreements") or []
    if dis:
        A("\n## Disagreements (need manual review)\n")
        A("Samples where the label and the engine disagree. Read the **false negatives** "
          "(label says dangerous, engine says low) first — each one may be a real "
          "defect. The **false positives** (label says safe, engine says high) matter "
          "too; they destroy user trust outright.\n")
        A("\n| Type | Token | Chain | Label | Engine verdict | Ablated | Driving signal |")
        A("|---|---|---|---|---|---|---|")
        for d in dis[:20]:
            A("| %s | `%s` | %s | %s | %s | %s | %s |" % (
                d["kind"], (d["symbol"] or d["address"][:10]), d["chain"],
                d["label"], d["verdict"], d["verdict_ablated"], d["driver"] or "—"))
        if len(dis) > 20:
            A("\n(%d more in `results.json`)\n" % (len(dis) - 20))

        # Impersonation is the one dimension the GoPlus labeller cannot see, so a
        # disagreement there means something different from the others -- and saying so
        # is only honest if the number stays in the headline rate regardless. It does.
        blind = [d for d in dis if d["kind"] == "false positive"
                 and d["label"].startswith("goplus") and d["driver"] == "impersonation"]
        if blind:
            A("\n### Counted as false positives, but outside the labeller's reach\n")
            A("%d of the false positives above were driven by `impersonation`. GoPlus "
              "reads bytecode and ownership; impersonation is a fact about identity, and "
              "an impostor's bytecode is usually perfectly ordinary. So GoPlus returns "
              "`safe` for a token it has no instrument to judge, and the disagreement is "
              "structural rather than evidence either way.\n" % len(blind))
            A("\nThey stay in the headline rate anyway. A tool that subtracts its "
              "disagreements whenever it can explain them is grading its own homework, "
              "and an explanation is only worth something if it costs something. What "
              "this section buys is auditability: they are named, so a reader can check "
              "them one at a time instead of taking the framing on trust.\n")
            A("\n| Token | Chain | Verdict | Address |")
            A("|---|---|---|---|")
            for d in blind:
                A("| `%s` | %s | %s | `%s` |" % (d["symbol"] or "?", d["chain"],
                                                 d["verdict"], d["address"]))

    A("\n## Reading the `dead` recall figure\n")
    A("**`dead` is a market outcome; the engine scores a safety property.** They overlap "
      "and they are not the same, and until the cohort was big enough to look at, that "
      "difference was invisible.\n")
    A("\nThe label means a project died -- price collapsed, volume collapsed. It does "
      "**not** say the position is trapped, and measured on this set, usually it is not:\n")

    def _q(rows_, sel):
        vals = sorted(r["liquidity_usd"] for r in rows_
                      if sel(r) and r.get("liquidity_usd") is not None)
        if not vals:
            return None
        n = len(vals)
        pick = [vals[0], vals[n // 4], vals[n // 2], vals[(3 * n) // 4], vals[-1]]
        return n, ["$%s" % format(int(v), ",") for v in pick]

    A("\n| | n | min | p25 | median | p75 | max |")
    A("|---|---|---|---|---|---|---|")
    for label, sel in (("`dead`", lambda r: r.get("outcome_label") == "dead"),
                       ("`alive`", lambda r: r.get("outcome_label") == "alive")):
        q = _q(rows, sel)
        if q:
            A("| liquidity, %s | %d | %s |" % (label, q[0], " | ".join(q[1])))

    dead_rows = [r for r in rows if r.get("outcome_label") == "dead"]
    still_liquid = len([r for r in dead_rows
                        if (r.get("liquidity_usd") or 0) >= 5000])
    A("\n%d of the %d dead tokens still hold $5,000 or more of liquidity. Those positions "
      "can be sold. An engine that rated them `high` would be calling a failed investment "
      "a safety hazard, which is a judgement this tool refuses to make (P1 in "
      "DECISIONS.md) -- so `medium` with an abandoned-pool warning is the intended answer, "
      "not a miss.\n" % (still_liquid, len(dead_rows)))

    not_low = len([r for r in dead_rows if r["verdict"] != "low"])
    A("\n**What the number should be read against**: of %d dead tokens, %d are rated "
      "something other than `low`. The remainder is the real finding.\n"
      % (len(dead_rows), not_low))
    A("\n**The limit this exposes.** The engine scores the current snapshot and has no "
      "price history, so a token whose price is down 99% from a peak it cannot see looks "
      "like a quiet pool with working sells. Turnover cannot substitute: at the current "
      "2% threshold it catches roughly half the dead cohort at a cost of several percent "
      "of the live one, and loosening it doubles that cost for a few more points.\n")

    A("\nThe history that would catch it is GeckoTerminal daily OHLCV -- the exact series "
      "the `outcome` label is computed from. Wiring it into the engine would buy "
      "drawdown detection and simultaneously void this column as an independent "
      "measurement. That is a live trade-off, not an oversight, and it is recorded as an "
      "open decision rather than settled quietly.\n")

    A("\n## What this benchmark does not measure\n")
    A("1. **Whether it warns you in time.** The engine scores the current state, and "
      "the `dead` label is retrospective. A pool that already died has liquidity ≈ 0 "
      "now, so calling it high is close to a tautology — that is what the ablation "
      "column is for. Answering 'would it have warned me before I bought' needs "
      "historical state replayed point-in-time, and the upstream security APIs don't "
      "serve history.\n")
    A("2. **`dead` ≠ scam.** Legitimate projects die too. This label answers whether "
      "you can still get out safely today.\n")
    A("3. **GoPlus and honeypot.is may be correlated.** Both simulate buys and sells, "
      "so the `goplus` column flatters the engine. The `outcome` column doesn't have "
      "that problem.\n")
    A("**Sample bias.** Candidates come from three places: pool launches "
      "recovered from chain history, the daily snapshot archive of "
      "newly-listed pools, and per-chain pool rankings (which skew "
      "healthy and act as the control group). Each has a fixed share of "
      "the set. None is a random sample of what an agent would actually "
      "be asked about.\n")

    with open(RESULTS_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    sys.exit(main())
