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

import risk  # noqa: E402
from fetcher import access_report, fetch_json, load_persisted_access_log  # noqa: E402

DATASET = os.path.join(HERE, "dataset.json")
RESULTS_JSON = os.path.join(HERE, "results.json")
RESULTS_MD = os.path.join(HERE, "results.md")

# Contract-safety signals: the ones independent of how much liquidity is left right now
CONTRACT_CATEGORIES = {
    "honeypot", "sellability", "sell_tax", "upstream_risk",
    "rugcheck", "contract", "concentration",
}


def install_engine_fetcher():
    """Swap the engine's fetcher for one that caches and books which endpoints it hit."""
    async def _fetch(url, retries=2, timeout=8):
        return fetch_json(url, role="engine", retries=1)
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
            res = asyncio.run(risk.assess(t["address"], t["chain"]))
        except Exception as e:  # noqa: BLE001
            print("  %s failed to evaluate: %s" % (t.get("symbol"), e))
            continue
        sigs = res.get("signals") or []
        ab_level, ab_score = ablate(t["address"], sigs,
                                    (res.get("evidence") or {}).get("data_gaps"))
        rows.append({
            "address": t["address"], "symbol": t.get("symbol"), "chain": t["chain"],
            "outcome_label": t.get("outcome_label"), "goplus_label": t.get("goplus_label"),
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
        "rows": rows,
    }
    with open(RESULTS_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)

    write_markdown(report)
    print("\nWrote %s and %s" % (RESULTS_JSON, RESULTS_MD))

    o = report["outcome"]["full"]["bad"]
    print("\nAt a glance:")
    print("  dead tokens rated high           : %s (n=%d)" % (_pct(o["high"]), o["n"]))
    print("  still high on contract signals   : %s"
          % _pct(report["outcome"]["contract_only"]["bad"]["high"]))
    print("  live tokens wrongly rated high   : %s (n=%d)"
          % (_pct(report["outcome"]["full"]["good"]["high"]),
             report["outcome"]["full"]["good"]["n"]))
    print("  unknown rate                     : %s" % _pct(report["overall"]["unknown_rate"]))
    return 0


def write_markdown(rep):
    L = []
    A = L.append
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
    A("- **dead**: traded for real at some point (peak 7d volume ≥ $50k), then price "
      "fell ≥ 90% off its peak **and** 7d volume collapsed below 5% of peak. A price "
      "drop alone isn't death, and neither is volume drying up alone.\n")
    A("- **alive**: ≥ 90 days of history, drawdown ≤ 70%, 7d volume ≥ 10% of peak "
      "and ≥ $50k.\n")
    A("- **unsafe**: GoPlus flags honeypot / pausable / blacklist / mutable tax / "
      "reclaimable ownership / owner can rewrite balances / mintable with ownership "
      "not renounced / buy or sell tax >10%.\n")
    A("- **safe**: none of the above, plus open source and ≥ 100 holders.\n")
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
