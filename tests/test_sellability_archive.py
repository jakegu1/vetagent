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


def _probe(monkey_result, rows=None, limit=3, done=None):
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
    snapshot._probed_already = lambda: dict(done or {})
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


def test_an_unanswered_token_is_not_blacklisted_forever():
    """A miss is not an answer, and the first version treated it as one.

    `_probed_already` returned every token ever ASKED about. One unanswered attempt
    excluded a token permanently -- and the misses are not random: honeypot.is cannot
    simulate Uniswap V4 pools at all, the probe sorts youngest-first, and V4 is where new
    launches concentrate. So the rule was strongest exactly against the newest venue,
    which is the population the archive most needs.
    """
    print("\n[archive] an unanswered token comes back round")
    key = ("base", ADDR)

    out, _ = _probe({"simulationSuccess": True}, done={key: 1})
    check("asked once, no answer -> ask again", len(out) == 1, str(len(out)))

    out, _ = _probe({"simulationSuccess": True}, done={key: snapshot._MAX_ATTEMPTS})
    check("answered, or asked to the cap -> never again", not out, str(out))

    check("the cap exists and is small",
          1 < snapshot._MAX_ATTEMPTS <= 5, str(snapshot._MAX_ATTEMPTS))

    # An answered token must be recorded at the cap, so it is never re-asked.
    import json as _json
    import os as _os
    d = _os.path.join(ROOT, "bench", "snapshots")
    files = [f for f in (_os.listdir(d) if _os.path.isdir(d) else [])
             if f.startswith("sellability-")]
    if files:
        real = snapshot._probed_already()
        answered = set()
        for fn in files:
            for line in io.open(_os.path.join(d, fn), encoding="utf-8"):
                line = line.strip()
                if line:
                    o = _json.loads(line)
                    if o.get("answered"):
                        answered.add((o.get("chain"), str(o.get("token") or "").lower()))
        check("every answered token in the real archive is at the cap",
              all(real.get(k, 0) >= snapshot._MAX_ATTEMPTS for k in answered),
              str(sorted(k for k in answered
                         if real.get(k, 0) < snapshot._MAX_ATTEMPTS)[:3]))


def test_a_venue_the_simulator_cannot_read_goes_last():
    """Deprioritised, not skipped -- 21% of them do answer."""
    print("\n[archive] spend the budget where an answer is possible")
    v4 = "0x" + "a" * 64                      # a V4 pool id is 32 bytes, not a pair
    v2 = "0x" + "b" * 40
    check("a 32-byte pool id is flagged unsimulatable",
          snapshot._unsimulatable({"pool_address": v4}) == 1)
    check("a pair address is not",
          snapshot._unsimulatable({"pool_address": v2}) == 0)

    rows = [
        {"kind": "new", "chain": "base", "base_token": "base_0x" + "1" * 40,
         "pool_address": v4, "pool_created_at": "2026-09-07T14:30:00Z"},   # youngest
        {"kind": "new", "chain": "base", "base_token": "base_0x" + "2" * 40,
         "pool_address": v2, "pool_created_at": "2026-09-07T09:00:00Z"},   # older
    ]
    out, _ = _probe({"simulationSuccess": True}, rows=rows, limit=1)
    check("the older pair beats the younger V4 pool",
          out and out[0]["token"].endswith("2" * 40),
          str([o["token"][-6:] for o in out]))

    out, _ = _probe({"simulationSuccess": True}, rows=rows, limit=2)
    check("but the V4 pool is still asked when budget remains",
          len(out) == 2, str(len(out)))


def test_the_whole_response_is_kept():
    """Thirteen branches came back; the first version stored five.

    This is the one upstream in the archive whose answer expires, so a field dropped
    here is dropped for good -- on a call already made, already parsed, already paid for.
    """
    print("\n[archive] keep what the response already contained")
    out, _ = _probe({
        "simulationSuccess": True,
        "honeypotResult": {"isHoneypot": False},
        "simulationResult": {"buyTax": 0.0, "sellTax": 0.0, "buyGas": "144224",
                             "sellGas": "103488"},
        "holderAnalysis": {"holders": "812", "successful": "770", "failed": "42",
                           "siphoned": "3"},
        "contractCode": {"openSource": True, "rootOpenSource": True},
        "token": {"totalHolders": 812},
        "pair": {"liquidity": 41233.1, "reserves0": "12", "reserves1": "9"},
    })
    check("one row", len(out) == 1, str(out))
    if not out:
        return
    row = out[0]
    # holderAnalysis is the densest of them: `failed` and `siphoned` count real holders
    # who tried to sell and could not -- close to the label the archive exists to build,
    # observed directly instead of inferred from a price chart four months later.
    check("holderAnalysis is kept whole",
          (row.get("holderAnalysis") or {}).get("failed") == "42",
          str(row.get("holderAnalysis")))
    check("and its siphoned count",
          (row.get("holderAnalysis") or {}).get("siphoned") == "3")
    check("contract source flags are kept",
          (row.get("contractCode") or {}).get("openSource") is True)
    check("holder count is kept", row.get("totalHolders") == 812)
    check("gas is kept", row.get("buyGas") == "144224" and row.get("sellGas") == "103488")
    check("pair reserves are kept",
          (row.get("pair") or {}).get("liquidity") == 41233.1)
    check("the row says which schema wrote it", row.get("schema") == 2)


def test_the_pools_archive_on_disk_is_wellformed():
    """The irreplaceable half had no well-formedness test at all.

    Until now the only archive test covered the 2.6 KB sellability file, while the
    megabytes of pool rows -- the part that cannot be re-collected at any price -- went
    unchecked. And the consumer is built to swallow the failure: build_dataset.py wraps
    each line in try/except json.JSONDecodeError and `continue`s, in two places. So a
    truncated final line from a killed process, or any future format change, degrades the
    archive silently, and an unparseable day reads downstream exactly like a day when no
    pools launched.
    """
    print("\n[archive] the pool rows are the part that cannot be re-collected")
    d = os.path.join(ROOT, "bench", "snapshots")
    files = sorted(f for f in (os.listdir(d) if os.path.isdir(d) else [])
                   if f.startswith("pools-") and f.endswith(".ndjson"))
    check("the pools archive exists", bool(files), "no pools-*.ndjson")
    if not files:
        return
    required = {"seen_at", "chain", "pool_id", "base_token"}
    bad, rows = [], 0
    for fn in files:
        for i, line in enumerate(io.open(os.path.join(d, fn), encoding="utf-8"), 1):
            line = line.strip()
            if not line:
                continue
            rows += 1
            try:
                o = json.loads(line)
            except ValueError:
                bad.append("%s:%d unparseable" % (fn, i))
                continue
            missing = required - set(o)
            if missing:
                bad.append("%s:%d missing %s" % (fn, i, sorted(missing)))
    check("every one of %d rows parses and carries its keys" % rows, not bad,
          "; ".join(bad[:4]))


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

    def _count(line, flag):
        if flag not in line:
            return None
        tail = line.split(flag, 1)[1].strip().split()
        return int(tail[0]) if tail and tail[0].isdigit() else None

    probes = [c for ln in run
              for c in (_count(ln, "--sellability-only"), _count(ln, "--sellability"))
              if c]
    check("something probes a positive number of tokens", probes, str(run))

    # THE ORDER IS THE SAFETY PROPERTY, so it is pinned rather than trusted.
    #
    # The probe's worst case is roughly 25 x (25 s timeout x 3 retries), which exceeds
    # this job's 25-minute limit. It used to run between the pool file being written and
    # the commit, so a honeypot.is outage would kill the runner with that pass's pool
    # rows -- the irreplaceable half -- still only on the runner's disk. The optional
    # thing could destroy the primary thing, precisely when the upstream was degraded.
    body = wf.split("steps:", 1)[-1]
    i_pools_commit = body.find('snapshot-commit.sh "pools"')
    i_probe = body.find("--sellability-only")
    check("the pool rows are committed before the probe runs",
          i_pools_commit != -1 and i_probe != -1 and i_pools_commit < i_probe,
          "pools-commit at %d, probe at %d" % (i_pools_commit, i_probe))
    check("and a failing probe cannot fail the job",
          "continue-on-error: true" in body,
          "the optional step must not take the pass down with it")

    # A bare `git push` after a job-start checkout loses the pass to any commit that
    # lands in the 142-265 s window, and the loss is invisible downstream.
    sh = os.path.join(ROOT, ".github", "scripts", "snapshot-commit.sh")
    check("the commit script exists", os.path.exists(sh), sh)
    if os.path.exists(sh):
        body = io.open(sh, encoding="utf-8").read()
        check("the push rebases and retries rather than dying",
              "pull --rebase" in body and "for attempt" in body)
        check("and says so loudly if it finally fails",
              "::error::" in body and "LOST" in body)


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
