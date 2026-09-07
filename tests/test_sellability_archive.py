"""test_sellability_archive.py — the one observable that cannot be recovered later.

Price, reserves and trade counts at time t are irrecoverable, and the snapshot already
records them. Contract bytecode is not: it stays on chain and can be fetched in six
months. A **sell simulation** can not — it needs a live pool with liquidity in it, and
once a token is dead there is nothing left to simulate against.

So "could you have got out on day one" is answerable only by having asked on day one.
That matters more than any other addition to the archive, because every headline this
project publishes rests on an adversarial cohort of 17 tokens, and the reason it is 17
is that confirmed-bad tokens are found by looking backwards — at which point they can no
longer be tested.

This file pins the three ways that collection can silently produce nothing:

1. **The address must be an address.** The first run passed GeckoTerminal's chain-prefixed
   id (`base_0x1313…`) straight through as an address and recorded six nulls. That looks
   exactly like "brand-new tokens are not indexed yet" and would have run for four months
   before anyone questioned it.
2. **A missing answer must be recorded as missing.** `answered: false` is a fact about
   honeypot.is's coverage, not about the token — E11, the shape this project keeps
   getting wrong. Dropping those rows would turn a coverage gap into a silent selection
   bias in the eventual dataset.
3. **Raw upstream fields only, never our verdict.** DECISIONS P4: scoring rules change,
   the simulator's own answer does not, and a future rule can only be replayed over raw
   values.

Run:  python tests/test_sellability_archive.py
"""

import io
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "bench"))

import snapshot  # noqa: E402

_FAILURES = []
_PASSED = 0


def check(name, condition, detail=""):
    global _PASSED
    if condition:
        _PASSED += 1
        print("  PASS  %s" % name)
    else:
        _FAILURES.append((name, detail))
        print("  FAIL  %s  %s" % (name, detail))


ADDR = "0x13137714eb14ce5a3b7b3689f13d63ff35e997ba"


def test_the_address_sent_upstream_is_an_address():
    print("\n[archive] GeckoTerminal ids are chain-prefixed; honeypot.is wants an address")
    check("the chain prefix is stripped",
          snapshot._address_of("base_" + ADDR, "base") == ADDR,
          snapshot._address_of("base_" + ADDR, "base"))
    check("a bare address passes through unchanged",
          snapshot._address_of(ADDR, "eth") == ADDR)
    check("case is normalised",
          snapshot._address_of("ETH_" + ADDR.upper(), "eth") == ADDR)
    check("a Solana id yields nothing rather than a bad request",
          snapshot._address_of("solana_So11111111111111111111111111111111111112",
                               "solana") == "")
    check("junk yields nothing", snapshot._address_of("", "eth") == "")
    check("a truncated address is refused",
          snapshot._address_of("base_0x1313", "base") == "")


def _probe(monkey_result, rows=None, limit=3):
    """Run the probe with the network stubbed."""
    original = snapshot.fetch_json
    calls = []

    def fake(url, role, **kw):
        calls.append((url, role, kw))
        return monkey_result

    rows = rows or [
        {"kind": "new", "chain": "base", "base_token": "base_" + ADDR,
         "pool_address": "0xpool", "pool_created_at": "2026-09-07T14:18:05Z",
         "reserve_usd": "14092.30"},
    ]
    # The real archive is on disk and the probe skips tokens it has already asked about.
    # Without this the test passes or fails depending on what the scheduled job collected
    # this morning, which is the kind of test that goes green for the wrong reason.
    original_done = snapshot._probed_already
    snapshot.fetch_json = fake
    snapshot._probed_already = lambda: set()
    try:
        out = snapshot.probe_sellability(rows, "2026-09-07T14:25:53+00:00", limit)
    finally:
        snapshot.fetch_json = original
        snapshot._probed_already = original_done
    return out, calls


def test_a_missing_answer_is_recorded_as_missing():
    """An unobserved dimension is a gap, not a finding. Dropping it biases the cohort."""
    print("\n[archive] 'honeypot.is has never heard of this token' is data")
    out, _ = _probe(None)
    check("the row is still written", len(out) == 1, str(out))
    if out:
        check("and it says so", out[0]["answered"] is False, str(out[0]))
        check("without inventing a verdict", out[0]["isHoneypot"] is None,
              str(out[0]["isHoneypot"]))


def test_only_raw_upstream_fields_are_stored():
    print("\n[archive] the simulator's answer, not ours")
    out, calls = _probe({
        "simulationSuccess": True,
        "simulationError": None,
        "honeypotResult": {"isHoneypot": True, "honeypotReason": "cannot sell"},
        "simulationResult": {"buyTax": 0.0, "sellTax": 99.0, "transferTax": 0.0},
        "flags": ["high_sell_tax"],
    })
    check("one row", len(out) == 1, str(out))
    if not out:
        return
    row = out[0]
    check("the upstream verdict is carried verbatim", row["isHoneypot"] is True)
    check("its taxes are carried verbatim", row["sellTax"] == 99.0, str(row["sellTax"]))
    check("its flags are carried verbatim", row["flags"] == ["high_sell_tax"])

    # DECISIONS P4: raw observables, never today's score. A `risk_level` here would make
    # the archive un-replayable the first time a scoring rule changes.
    ours = {"risk_level", "risk_score", "verdict", "confidence", "signals",
            "recommendation"}
    check("no scored field of ours is stored", not (ours & set(row)),
          str(sorted(ours & set(row))))

    check("the request went to honeypot.is with a chain id",
          calls and "api.honeypot.is" in calls[0][0] and "chainID=8453" in calls[0][0],
          str(calls[:1]))
    check("recorded as an engine upstream, not a labelling oracle",
          calls and calls[0][1] == "engine", str(calls[:1]))
    check("and never from cache -- a cached body is one moment under two timestamps",
          calls and calls[0][2].get("use_cache") is False, str(calls[:1]))


def test_chains_the_simulator_does_not_cover_are_not_asked():
    print("\n[archive] don't spend a request on a chain that always answers 400")
    rows = [{"kind": "new", "chain": "solana", "base_token": "solana_So1111",
             "pool_address": "p", "pool_created_at": "2026-09-07T14:00:00Z"},
            {"kind": "new", "chain": "arbitrum", "base_token": "arbitrum_" + ADDR,
             "pool_address": "p", "pool_created_at": "2026-09-07T14:00:00Z"}]
    out, calls = _probe({"simulationSuccess": True}, rows=rows)
    check("nothing asked", not calls, str(calls))
    check("nothing recorded", not out, str(out))


def test_the_workflow_actually_runs_it():
    """A probe the scheduled job never calls collects nothing, forever.

    This project has already shipped a counting rule that `main()` never invoked and a
    honeypot check that never fired. A daily collector is the worst place to repeat it:
    the failure is invisible and the loss is permanent.
    """
    print("\n[archive] the scheduled job has to call it")
    wf = io.open(os.path.join(ROOT, ".github", "workflows", "snapshot.yml"),
                 encoding="utf-8").read()
    check("snapshot.yml passes --sellability", "--sellability" in wf,
          "the four daily passes would record pool rows and no simulations")
    run = [ln for ln in wf.splitlines()
           if "snapshot.py" in ln and "run:" in ln]
    check("on the line that actually runs it", run, "no `run: ... snapshot.py` line")
    check("with a positive count",
          any("--sellability" in ln
              and ln.split("--sellability")[1].strip().split()[0].isdigit()
              and int(ln.split("--sellability")[1].strip().split()[0]) > 0
              for ln in run),
          str(run))


def test_the_archive_on_disk_is_wellformed():
    """If a file exists, every line has to be readable a year from now."""
    print("\n[archive] what is already collected must still parse")
    d = os.path.join(ROOT, "bench", "snapshots")
    files = [f for f in (os.listdir(d) if os.path.isdir(d) else [])
             if f.startswith("sellability-")]
    if not files:
        print("  (no sellability files yet -- nothing to check)")
        return
    required = {"seen_at", "chain", "token", "answered"}
    bad = []
    for fn in files:
        for i, line in enumerate(io.open(os.path.join(d, fn), encoding="utf-8"), 1):
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except ValueError:
                bad.append("%s:%d unparseable" % (fn, i))
                continue
            if not required <= set(o):
                bad.append("%s:%d missing %s" % (fn, i, sorted(required - set(o))))
            t = str(o.get("token") or "")
            if t and not (t.startswith("0x") and len(t) == 42):
                bad.append("%s:%d token is not an address: %r" % (fn, i, t))
    check("every recorded row is well formed", not bad, "; ".join(bad[:4]))


def main():
    print("=" * 68)
    print("Sellability archive: asking on the day, because later is too late")
    print("=" * 68)
    for _, fn in sorted((k, v) for k, v in globals().items()
                        if k.startswith("test_")):
        fn()
    print("\n" + "=" * 68)
    print("%d passed, %d failed" % (_PASSED, len(_FAILURES)))
    if _FAILURES:
        print("\nFailures:")
        for name, detail in _FAILURES:
            print("  - %s  %s" % (name, detail))
        return 1
    print("All passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
