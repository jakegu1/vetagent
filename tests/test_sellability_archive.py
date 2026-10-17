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


def test_a_missing_answer_says_which_kind_of_missing():
    """E11, in the archive's own storage layer, written by me the day before.

    `answered: false` merged four different facts: honeypot.is has no record of this
    token, honeypot.is refused us, our request timed out, and the venue is one it
    structurally cannot read. The first is a fact about the TOKEN; the rest are facts
    about US. A cohort assembled in 2027 from `answered: false` rows cannot tell them
    apart, and only one of them is correlated with anything.

    Four independent reviewers raised this from four different angles, which is why it is
    pinned rather than merely fixed.
    """
    print("\n[archive] an absence has to say what kind of absence it is")
    out, _ = _probe({"simulationSuccess": True, "honeypotResult": {"isHoneypot": False},
                     "simulationResult": {}})
    check("a real answer is ok", out and out[0]["outcome"] == "ok",
          str(out and out[0].get("outcome")))

    out, _ = _probe(snapshot.NOT_FOUND)
    check("upstream has no record -> no_record",
          out and out[0]["outcome"] == "no_record", str(out and out[0].get("outcome")))
    check("and that still counts as unanswered",
          out and out[0]["answered"] is False)

    out, _ = _probe(None)
    check("we could not ask -> unreachable",
          out and out[0]["outcome"] == "unreachable", str(out and out[0].get("outcome")))

    # A request that never reached honeypot.is is not evidence about the token, so it
    # must not spend that token's budget.
    key = ("base", ADDR)
    check("an unreachable attempt does not count toward the cap",
          _probe({"simulationSuccess": True}, done={key: 0})[0],
          "a token whose only attempts failed must be asked again")


def test_the_manifest_separates_a_failed_page_from_an_empty_one():
    """A failed fetch and an exhausted listing took the same `break`.

    So "base recorded 40 pools this pass" could mean Base was quiet or that page 3 timed
    out and collection stopped. Downstream those are identical and no later analysis can
    separate them, because the information was never written down. Every other finding in
    this review loses a column; this one made the surviving columns un-interpretable.
    """
    print("\n[archive] a rate-limit is not a fact about the market")
    src = io.open(os.path.join(ROOT, "bench", "snapshot.py"), encoding="utf-8").read()
    body = src.split("def collect(")[1].split("\ndef ")[0]
    check("collect() records a per-page outcome", '"outcome": "fetch_failed"' in body)
    check("and distinguishes the end of a listing", '"outcome": "end_of_listing"' in body)
    check("and a successful page with its row count",
          '"outcome": "ok"' in body and '"rows": page_rows' in body)
    check("a failed page raises a CI warning rather than passing quietly",
          "::warning::" in src and "page fetches failed" in src)
    # A failed page used to end the whole chain/kind. The first CI pass with a manifest
    # reported nine failures across all eight chains, five of them on page 1 -- so those
    # combinations collected nothing at all, and it read downstream as a quiet market.
    check("a failed page does not abandon the rest of the chain",
          "misses += 1" in body and "continue" in body.split("misses += 1")[1][:400],
          "one bad page must not discard pages 2-5")
    check("but it does give up after a second miss",
          "if misses >= 2:" in body, "otherwise a rate limit is hammered")

    d = os.path.join(ROOT, "bench", "snapshots")
    runs = sorted(f for f in (os.listdir(d) if os.path.isdir(d) else [])
                  if f.startswith("runs-"))
    if not runs:
        print("  (no manifest written yet -- nothing on disk to check)")
        return
    need = {"seen_at", "chain", "kind", "page", "outcome", "rows"}
    bad = []
    for fn in runs:
        for i, line in enumerate(io.open(os.path.join(d, fn), encoding="utf-8"), 1):
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except ValueError:
                bad.append("%s:%d unparseable" % (fn, i))
                continue
            if not need <= set(o):
                bad.append("%s:%d missing %s" % (fn, i, sorted(need - set(o))))
    check("every manifest row is well formed", not bad, "; ".join(bad[:3]))


def test_no_single_chain_can_take_the_whole_budget():
    """BSC launches fastest, and honeypot.is answers for it 0% of the time.

    Measured over the first 53 probes: base 3/3 answered, eth 2/2 answered, bsc 0 of 48.
    Youngest-first sorting handed BSC the entire quota -- one CI pass spent all 25
    requests there and answered none. The two chains that answer every time got nothing.
    """
    print("\n[archive] one prolific chain must not starve the others")
    rows = []
    for i in range(30):                       # bsc floods the candidate list
        rows.append({"kind": "new", "chain": "bsc", "base_token": "bsc_0x%040d" % i,
                     "pool_address": "0x" + "b" * 40,
                     "pool_created_at": "2026-09-07T15:%02d:00Z" % (i % 60)})
    for i in range(3):
        rows.append({"kind": "new", "chain": "base", "base_token": "base_0x%040d" % (900 + i),
                     "pool_address": "0x" + "c" * 40,
                     "pool_created_at": "2026-09-07T09:0%d:00Z" % i})
    out, _ = _probe({"simulationSuccess": True}, rows=rows, limit=6)
    chains = set(r["chain"] for r in out)
    check("base is reached even though bsc floods the list", "base" in chains, str(chains))
    check("and bsc does not take all six",
          sum(1 for r in out if r["chain"] == "bsc") < 6,
          str([r["chain"] for r in out]))


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


# T-020 acceptance contract. All upstreams, clocks and output directories are isolated.
def _snapshot_pool(pid):
    return {"id": pid, "attributes": {"address": "fixture-pool", "reserve_in_usd": "7"}}


def _snapshot_replay(reply, chains=None, pages=5, recovery_cost=0.1):
    from contextlib import redirect_stdout
    from datetime import datetime, timedelta, timezone
    from urllib.parse import parse_qs, urlparse
    old = (snapshot.fetch_json, snapshot.time.sleep, snapshot.time.monotonic,
           snapshot.datetime)
    calls, visits, clock = [], {}, [0.0]

    class Clock:
        @staticmethod
        def now(zone):
            return datetime(2026, 10, 9, tzinfo=timezone.utc) + timedelta(seconds=clock[0])

    def fake(url, role, **kw):
        parsed = urlparse(url)
        parts = parsed.path.split("/")
        chain, kind = parts[-2], "new" if parts[-1] == "new_pools" else "trending"
        page = int(parse_qs(parsed.query)["page"][0])
        key = (chain, kind, page)
        visits[key] = visits.get(key, 0) + 1
        recovery = kw.get("retries") == 0
        calls.append({"chain": chain, "kind": kind, "page": page,
                      "visit": visits[key], "role": role, "kw": kw.copy(),
                      "start": clock[0]})
        result = reply(chain, kind, page, visits[key])
        if isinstance(kw.get("diagnostics"), dict):
            kw["diagnostics"].update(status=429 if result is None else 200,
                                     error="http" if result is None else None,
                                     attempts=1 if recovery else 2)
        clock[0] += min(recovery_cost, kw.get("timeout", 10)) if recovery else 0.1
        return result

    snapshot.fetch_json = fake
    snapshot.time.sleep = lambda seconds: None
    snapshot.time.monotonic = lambda: clock[0]
    snapshot.datetime = Clock
    stream = io.StringIO()
    try:
        with redirect_stdout(stream):
            result = snapshot.collect(chains or ["base"], pages=pages)
    finally:
        (snapshot.fetch_json, snapshot.time.sleep, snapshot.time.monotonic,
         snapshot.datetime) = old
    return result, calls, stream.getvalue()


def test_snapshot_recovers_real_rows_without_duplicate_or_cache():
    print("\n[snapshot] recovery preserves the initial gap and the actual observation time")

    def reply(chain, kind, page, visit):
        if kind == "trending" or page == 3:
            return {"data": []}
        if page == 1 and visit == 1:
            return None
        ids = ["shared", "recovered"] if page == 1 else ["shared"]
        return {"data": [_snapshot_pool(pid) for pid in ids]}

    (rows, seen_at, manifest), calls, _ = _snapshot_replay(reply, pages=5)
    check("recovery adds fetched rows and deduplicates an overlapping page",
          sorted(r["pool_id"] for r in rows) == ["recovered", "shared"], str(rows))
    recovered = [r for r in rows if r["pool_id"] == "recovered"]
    check("recovered rows remain grouped under the original pass timestamp",
          recovered and recovered[0]["seen_at"] == seen_at)
    check("recovered rows expose a later actual fetch timestamp",
          recovered and recovered[0].get("fetched_at", "") > seen_at)
    page1 = next(m for m in manifest if m["kind"] == "new" and m["page"] == 1)
    check("manifest retains failure and recovery outcome",
          page1.get("initial_outcome") == "fetch_failed"
          and page1.get("recovery_outcome") == "ok" and page1["outcome"] == "ok",
          str(page1))
    check("initial diagnostics identify the bounded HTTP failure",
          page1.get("diagnostics", {}).get("status") == 429
          and page1.get("diagnostics", {}).get("attempts") == 2, str(page1))
    initial = [c for c in calls if c["kw"].get("retries") != 0]
    recovery = [c for c in calls if c["kw"].get("retries") == 0]
    check("every initial fetch has one retry and a ten-second timeout",
          initial and all(c["kw"].get("retries") == 1 and c["kw"].get("timeout") == 10
                          for c in initial))
    check("recovery is a single zero-retry attempt", len(recovery) == 1, str(recovery))
    check("snapshot fetches never read or write benchmark cache",
          all(c["kw"].get("use_cache") is False
              and c["kw"].get("write_cache") is False for c in calls))
    check("confirmed initial listing ends are never recovered or paged past",
          not any(c["kind"] == "new" and c["page"] > 3 for c in calls))


def test_snapshot_records_skipped_pages_and_preserves_recovered_ends():
    print("\n[snapshot] a two-miss stop leaves explicit gaps, not empty pages")

    def reply(chain, kind, page, visit):
        if kind == "trending" or page >= 3:
            return {"data": []}
        if page == 1 or visit == 1:
            return None
        return {"data": [_snapshot_pool("page-two")]}

    (rows, _, manifest), calls, _ = _snapshot_replay(reply, pages=5)
    by_page = {m["page"]: m for m in manifest if m["kind"] == "new"}
    check("all planned new-pool pages remain represented after a two-miss stop",
          set(by_page) == set(range(1, 6)), str(by_page))
    check("initial skipped pages are explicitly different from empty listings",
          all(by_page.get(p, {}).get("initial_outcome") == "skipped" for p in (3, 4, 5)))
    check("one unresolved failed page remains a failed page",
          by_page[1]["outcome"] == "fetch_failed")
    check("a skipped page can be recovered as a confirmed end",
          by_page.get(3, {}).get("recovery_outcome") == "end_of_listing")
    check("later gaps are marked past a confirmed end without inventing empty fetches",
          all(by_page.get(p, {}).get("outcome") == "past_end_of_listing" for p in (4, 5))
          and not any(c["page"] > 3 for c in calls))
    check("successfully fetched data survives remaining gaps",
          [r["pool_id"] for r in rows] == ["page-two"])


def test_snapshot_recovery_has_fixed_count_and_deadline():
    print("\n[snapshot] recovery prioritizes early new-pool pages under both budgets")
    fail = lambda chain, kind, page, visit: None
    (_, _, manifest), calls, _ = _snapshot_replay(fail, chains=["a", "b", "c", "d"], pages=5)
    recovery = [c for c in calls if c["kw"].get("retries") == 0]
    check("at most twelve extra fetches, never an unbounded recovery loop",
          len(recovery) == 12, str([(c["chain"], c["kind"], c["page"]) for c in recovery]))
    check("early new-pool pages take precedence over later pages and trending",
          [(c["kind"], c["page"]) for c in recovery[:4]] == [("new", 1)] * 4)
    check("the count limit leaves explicit missing pages",
          any(m.get("recovery_outcome") == "fetch_limit" for m in manifest)
          and all(m["outcome"] in ("fetch_failed", "skipped") for m in manifest))
    (_, _, manifest), calls, _ = _snapshot_replay(fail, chains=["a", "b", "c", "d"],
                                                pages=5, recovery_cost=9.6)
    recovery = [c for c in calls if c["kw"].get("retries") == 0]
    check("the ninety-second deadline stops further recovery requests",
          len(recovery) == 10 and any(m.get("recovery_outcome") == "budget_exhausted"
                                     for m in manifest), str(len(recovery)))
    check("each timeout is bounded by remaining budget and capped at ten seconds",
          recovery and all(0 < c["kw"]["timeout"] <= min(10, 90 -
                           (c["start"] - recovery[0]["start"])) + 0.000001 for c in recovery)
          and recovery[-1]["kw"]["timeout"] < 4)


def test_snapshot_invalid_payloads_are_failures_and_never_listing_ends():
    print("\n[snapshot] malformed upstream payloads are unobserved gaps")
    payloads = [{"error": "not a listing"}, {"data": {}}, {"data": [None]},
                {"data": [{"attributes": {}}]}]
    for i, payload in enumerate(payloads):
        try:
            (rows, _, manifest), _, _ = _snapshot_replay(
                lambda chain, kind, page, visit: payload, pages=2)
            correct = (not rows and manifest and
                       all(m["outcome"] in ("fetch_failed", "skipped") for m in manifest)
                       and any(m.get("diagnostics", {}).get("error") == "invalid_payload"
                               for m in manifest))
        except (TypeError, AttributeError, ValueError):
            correct = False
        check("invalid payload %d neither crashes nor becomes an empty market" % i, correct)


def test_fetch_diagnostics_are_bounded_and_preserve_return_and_cache_contract():
    print("\n[fetch] diagnostics never contain URL, body, credential or exception text")
    import fetcher
    import tempfile
    import urllib.error
    from contextlib import redirect_stdout
    from unittest.mock import patch
    secret = "fixture-secret-must-not-escape"
    url = "https://fixture.invalid/private?token=" + secret

    class Response:
        status = 200
        def __init__(self, body):
            self.body = body
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return self.body

    cases = [(urllib.error.HTTPError(url, 429, secret, {}, None), None, "http", 429, 2),
             (urllib.error.HTTPError(url, 404, secret, {}, None), fetcher.NOT_FOUND,
              "http", 404, 1),
             (TimeoutError(secret), None, "timeout", None, 2),
             (urllib.error.URLError(secret), None, "network", None, 2),
             (RuntimeError(secret), None, "request", None, 2),
             (Response(b"invalid body"), None, "invalid_json", 200, 2),
             (Response(b'{"data": [7]}'), {"data": [7]}, None, 200, 1)]
    with tempfile.TemporaryDirectory() as tmp:
        for i, (effect, expected, error, status, attempts) in enumerate(cases):
            diagnostics, stream = {}, io.StringIO()
            try:
                with patch.object(fetcher, "CACHE_DIR", tmp), \
                     patch.object(fetcher, "_throttle", lambda *a, **kw: None), \
                     patch.object(fetcher.time, "sleep", lambda seconds: None), \
                     patch.object(fetcher.urllib.request, "urlopen",
                                  side_effect=effect if isinstance(effect, Exception) else None,
                                  return_value=effect), redirect_stdout(stream):
                    result = fetcher.fetch_json(url, "label", retries=1, use_cache=False,
                                                write_cache=False, mark_missing=True,
                                                diagnostics=diagnostics)
                correct = (result is expected if expected is fetcher.NOT_FOUND
                           else result == expected)
                correct = (correct and diagnostics == {"status": status, "error": error,
                                                        "attempts": attempts})
            except TypeError:
                correct = False
            check("diagnostics case %d preserves result and bounded categories" % i, correct,
                  str(diagnostics))
            check("diagnostics case %d redacts all identifying material" % i,
                  secret not in json.dumps(diagnostics) + stream.getvalue()
                  and "private" not in json.dumps(diagnostics) + stream.getvalue())
        check("live snapshot-style fetches never create response cache entries",
              not os.listdir(tmp), str(os.listdir(tmp)))
        with patch.object(fetcher, "CACHE_DIR", tmp), \
             patch.object(fetcher, "_throttle", lambda *a, **kw: None), \
             patch.object(fetcher.urllib.request, "urlopen", return_value=Response(b'{"data": [7]}')):
            first = fetcher.fetch_json(url, "label")
        with patch.object(fetcher, "CACHE_DIR", tmp), \
             patch.object(fetcher.urllib.request, "urlopen", side_effect=AssertionError("cache miss")):
            second = fetcher.fetch_json(url, "label")
        check("existing callers keep success caching and cache reads", first == second == {"data": [7]})
        check("endpoint provenance still records the role", fetcher.endpoint_of(url) in
              fetcher.access_report()[1])


def _snapshot_cli(directory, args, result=None, probe=None):
    from contextlib import redirect_stdout, redirect_stderr
    from unittest.mock import patch
    stream = io.StringIO()
    with patch.object(snapshot, "OUT_DIR", directory), \
         patch.object(snapshot.sys, "argv", ["snapshot.py"] + args), \
         patch.object(snapshot, "collect", return_value=result), \
         patch.object(snapshot, "probe_sellability", side_effect=probe or (lambda *a: [])), \
         redirect_stdout(stream), redirect_stderr(stream):
        try:
            code = snapshot.main()
        except SystemExit as exc:
            code = exc.code
    return code, stream.getvalue()


def _snapshot_manifest(timestamp, outcome="ok", rows=1):
    return [{"seen_at": timestamp, "chain": "base", "kind": kind, "page": 1,
             "pages": 1, "initial_outcome": outcome, "outcome": outcome,
             "rows": rows if kind == "new" else 0}
            for kind in ("new", "trending")]


def test_snapshot_zero_and_partial_passes_persist_before_failure_or_optional_work():
    print("\n[snapshot] save the pass manifest even when every pool fetch fails")
    import tempfile
    timestamp = "2026-10-09T14:00:00+00:00"
    with tempfile.TemporaryDirectory() as tmp:
        result = ([], timestamp, _snapshot_manifest(timestamp, "fetch_failed", rows=0))
        code, output = _snapshot_cli(tmp, ["--sellability", "0"], result)
        manifest_path = os.path.join(tmp, "runs-2026-10-09.ndjson")
        check("zero rows exit nonzero and write their failure manifest",
              code != 0 and os.path.isfile(manifest_path), output)
        check("zero rows do not manufacture an empty pool file",
              not os.path.exists(os.path.join(tmp, "pools-2026-10-09.ndjson")))
    for partial in (False, True):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "pools-2026-10-09.ndjson")
            old = b'{"seen_at":"old","pool_id":"historical"}\n'
            with open(path, "wb") as fh:
                fh.write(old)
            rows = [snapshot._row("base", "new", _snapshot_pool("new"), timestamp)]
            manifest = _snapshot_manifest(timestamp)
            if partial:
                manifest[1].update(outcome="fetch_failed", initial_outcome="fetch_failed")

            def probe(*args):
                with open(path, "rb") as fh:
                    saved = fh.read()
                check("pool rows are appended before optional work", saved.startswith(old)
                      and b'"pool_id": "new"' in saved)
                check("manifest is saved before optional work", os.path.isfile(
                      os.path.join(tmp, "runs-2026-10-09.ndjson")))
                return []

            code, output = _snapshot_cli(tmp, ["--sellability", "1"],
                                         (rows, timestamp, manifest), probe)
            check("collection status reports %s coverage after preservation" %
                  ("partial" if partial else "complete"), code == (1 if partial else 0), output)
            with open(path, "rb") as fh:
                check("existing archive rows stay byte-for-byte unchanged", fh.read().startswith(old))


def test_snapshot_health_cli_checks_last_pass_and_rejects_absence_corruption_and_zero():
    print("\n[snapshot] coverage is about the last recorded pass, not an older success")
    import tempfile
    timestamp = "2026-10-09T14:00:00+00:00"
    good = _snapshot_manifest(timestamp)
    partial = _snapshot_manifest("2026-10-09T20:00:00+00:00", "fetch_failed", rows=0)
    cases = [("missing", None, 1), ("complete", good, 0),
             ("older success then failure", good + partial, 1),
             ("zero", _snapshot_manifest(timestamp, "end_of_listing", rows=0), 1),
             ("malformed JSON", "{invalid}", 1), ("malformed shape", [{}], 1),
             ("missing page", [dict(good[0], pages=2)], 1)]
    for name, data, expected in cases:
        with tempfile.TemporaryDirectory() as tmp:
            if data is not None:
                with open(os.path.join(tmp, "runs-2026-10-09.ndjson"), "w", encoding="utf-8") as fh:
                    fh.write(data if isinstance(data, str) else
                             "".join(json.dumps(m) + "\n" for m in data))
            code, output = _snapshot_cli(tmp, ["--check-coverage"])
            check("coverage CLI %s returns %d" % (name, expected), code == expected, output)
            check("coverage CLI %s prints counts and a bounded cause" % name,
                  "coverage:" in output and "rows" in output and "causes:" in output, output)
    with tempfile.TemporaryDirectory() as tmp:
        result, _, _ = _snapshot_replay(lambda chain, kind, page, visit:
            None if kind == "new" and visit == 1 else
            {"data": [_snapshot_pool("real")]} if kind == "new" else {"data": []}, pages=1)
        _snapshot_cli(tmp, ["--sellability", "0"], result)
        code, output = _snapshot_cli(tmp, ["--check-coverage"])
        check("a recovered pass can be complete", code == 0, output)


def test_snapshot_workflow_preserves_failures_then_reports_current_coverage():
    print("\n[snapshot] collection failure never skips the commit or becomes an old healthy pass")
    import re
    wf = io.open(os.path.join(ROOT, ".github", "workflows", "snapshot.yml"), encoding="utf-8").read()
    steps = {part.splitlines()[0].strip(): part for part in re.split(r"- name: ", wf)[1:]}
    collect = steps.get("Collect pools", "")
    commit = steps.get("Commit pools", "")
    probe = steps.get("Collect day-one sellability", "")
    health = steps.get("Check pool coverage", "")
    check("collection has an outcome id and continues to the preservation step",
          "id: collect_pools" in collect and "continue-on-error: true" in collect)
    check("pool preservation runs even after a collector failure", "always()" in commit)
    check("sellability is skipped unless this collection succeeded",
          "steps.collect_pools.outcome == 'success'" in probe)
    check("coverage is the final step and runs even after an earlier failure",
          health and list(steps)[-1] == "Check pool coverage" and "always()" in health)
    check("final step runs the real coverage CLI after pool preservation",
          "--check-coverage" in health and wf.find('snapshot-commit.sh "pools"') <
          wf.find("--check-coverage"))
    check("an old healthy pass cannot override this collection's failed outcome",
          "POOL_COLLECTION_OUTCOME: ${{ steps.collect_pools.outcome }}" in health
          and '"$POOL_COLLECTION_OUTCOME" != "success"' in health and "exit 1" in health)
    check("the original four daily schedule slots and job timeout remain",
          'cron: "23 2,8,14,20 * * *"' in wf and "timeout-minutes: 25" in wf)


# T-020 named change (a): additive real-fetcher absolute-attempt tests.
def _absolute_http_replay(phase="fast", deadline=None, delay=9, retries=0,
                          scheme="http", throttle=False, blocked_dns=False):
    import inspect
    import socket
    import ssl
    import threading
    import urllib.request
    import fetcher
    from contextlib import ExitStack
    from unittest.mock import patch
    clock, sockets, threads, waits = [0.0], [], [], []
    body = b'{"data": []}'
    headers = ("HTTP/1.1 200 OK\r\nContent-Length: %d\r\nConnection: close\r\n\r\n" % len(body)).encode()

    class Event:
        def __init__(self):
            self.flag = False
        def set(self):
            self.flag = True
        def is_set(self):
            return self.flag
        def wait(self, timeout=None):
            if not self.flag and timeout is not None:
                clock[0] += timeout
            return self.flag

    class Thread:
        def __init__(self, target, **kwargs):
            self.target = target
            threads.append(self)
        def start(self):
            if not blocked_dns:
                self.target()

    class Socket:
        def __init__(self, timeout=10):
            self.timeout, self.requests, self.files, self.closed = timeout, [], [], False
        def settimeout(self, timeout):
            self.timeout = timeout
        def setsockopt(self, *args):
            pass
        def connect(self, address):
            pass
        def bind(self, address):
            pass
        def sendall(self, data):
            self.requests.append(data)
        def makefile(self, mode):
            raw = Drip(self)
            self.files.append(raw)
            return io.BufferedReader(raw, buffer_size=8)
        def close(self):
            self.closed = True

    class Drip(io.RawIOBase):
        def __init__(self, connection):
            self.connection, self.wire, self.offset = connection, headers + body, 0
        def readable(self):
            return True
        def readinto(self, target):
            if self.offset == len(self.wire):
                return 0
            slow = ((phase == "headers" and self.offset < len(headers))
                    or (phase == "body" and self.offset >= len(headers)))
            if slow:
                if delay >= self.connection.timeout:
                    clock[0] += self.connection.timeout
                    raise TimeoutError("fixture progressive socket timeout")
                clock[0] += delay
            target[0] = self.wire[self.offset]
            self.offset += 1
            return 1

    def connect(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, *args, **kwargs):
        connection = Socket(timeout)
        sockets.append(connection)
        return connection

    def socket_factory(*args, **kwargs):
        return connect(None)

    def sleep(seconds):
        waits.append(seconds)
        clock[0] += seconds

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    diagnostics, result, before_late = {}, None, None
    options = dict(role="label", retries=retries, timeout=10, deadline=deadline,
                   use_cache=False, write_cache=False, diagnostics=diagnostics)
    # Round 1 has no snapshot-only mode; run the same real HTTP failure there so red
    # evidence shows progressing IO, rather than just an unexpected keyword error.
    if "absolute_timeout" in inspect.signature(fetcher.fetch_json).parameters:
        options["absolute_timeout"] = True
    with ExitStack() as stack:
        stack.enter_context(patch.object(socket, "create_connection", connect))
        stack.enter_context(patch.object(socket, "socket", socket_factory))
        stack.enter_context(patch.object(socket, "getaddrinfo", return_value=[
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))]))
        stack.enter_context(patch.object(ssl.SSLContext, "wrap_socket",
                                        lambda self, sock, **kw: sock))
        stack.enter_context(patch.object(urllib.request, "getproxies", return_value={}))
        stack.enter_context(patch.object(fetcher.urllib.request, "urlopen", side_effect=opener.open))
        stack.enter_context(patch.object(threading, "Event", Event))
        stack.enter_context(patch.object(threading, "Thread", Thread))
        stack.enter_context(patch.object(fetcher.time, "monotonic", lambda: clock[0]))
        stack.enter_context(patch.object(fetcher.time, "time", lambda: 100 + clock[0]))
        stack.enter_context(patch.object(fetcher.time, "sleep", sleep))
        stack.enter_context(patch.object(fetcher, "_RATE", {"fixture.invalid": 2.1}))
        stack.enter_context(patch.object(fetcher, "_last_hit", {"fixture.invalid": 100 if throttle else 90}))
        if hasattr(fetcher, "_SnapshotResolver"):
            stack.enter_context(patch.object(fetcher, "_SNAPSHOT_RESOLVER", fetcher._SnapshotResolver()))
        result = fetcher.fetch_json(scheme + "://fixture.invalid/absolute-fixture", **options)
        before_late = sum(len(s.requests) for s in sockets)
        if blocked_dns:
            # A second pass may wait on the same unresolved lookup, but must not spawn
            # a second DNS worker or dispatch HTTP when the first lookup finishes late.
            fetcher.fetch_json(scheme + "://fixture.invalid/absolute-fixture", **options)
            for thread in threads:
                thread.target()
    return {"result": result, "elapsed": clock[0], "diagnostics": diagnostics,
            "requests": before_late, "requests_after_late": sum(len(s.requests) for s in sockets),
            "threads": len(threads), "waits": waits,
            "socket_timeouts": [s.timeout for s in sockets],
            "raw_files_closed": all(raw.closed for s in sockets for raw in s.files)}


def test_absolute_fetcher_deadline_covers_expiry_throttle_and_remaining_io():
    print("\n[absolute] the real fetcher accounts for throttle before HTTP IO")
    for name, deadline, expected_wait in (("expired", -1, 0), ("throttle exceeds budget", 1, 0)):
        replay = _absolute_http_replay(deadline=deadline, throttle=True)
        check(name + " performs no HTTP or over-budget wait", replay["requests"] == 0
              and replay["waits"] == [] and replay["elapsed"] == 0)
        check(name + " records bounded budget diagnostics", replay["diagnostics"] ==
              {"status": None, "error": "budget_exhausted", "attempts": 0})
    replay = _absolute_http_replay(deadline=3, throttle=True)
    check("fast HTTP survives a throttle within the deadline", replay["result"] == {"data": []}
          and abs(sum(replay["waits"]) - 2.1) < 0.000001)
    check("the real connection receives only the remaining timeout after throttle",
          replay["socket_timeouts"] and all(0 < value <= 0.900001
                                            for value in replay["socket_timeouts"]))


def test_absolute_http_headers_and_body_cannot_extend_initial_or_recovery_attempts():
    print("\n[absolute] progressive stdlib HTTP IO shares one ten-second attempt limit")
    for scheme in ("http", "https"):
        for phase in ("headers", "body"):
            for deadline in (None, 90, 3):
                replay = _absolute_http_replay(phase, deadline=deadline, scheme=scheme)
                cap = 10 if deadline is None else min(10, deadline)
                check("%s %s drip with deadline %s stops inside the whole-attempt budget" %
                      (scheme, phase, deadline), replay["result"] is None
                      and 0 < replay["elapsed"] <= cap + 0.000001, str(replay))
                check("%s %s cutoff closes raw IO and reports an unavailable attempt" %
                      (scheme, phase), replay["raw_files_closed"]
                      and replay["diagnostics"].get("error") in ("timeout", "budget_exhausted")
                      and replay["diagnostics"].get("attempts") == 1)
    replay = _absolute_http_replay("body", retries=1)
    check("both initial retry attempts have independent ten-second IO limits",
          replay["result"] is None and replay["requests"] == 2
          and replay["diagnostics"].get("attempts") == 2 and replay["elapsed"] <= 20.800001,
          str(replay))


def test_absolute_dns_lookup_is_bounded_without_late_http_or_worker_fanout():
    print("\n[absolute] an unresolved DNS lookup cannot hold preservation or queue late requests")
    replay = _absolute_http_replay(deadline=3, blocked_dns=True)
    check("DNS expiry returns unavailable within the original deadline",
          replay["result"] is None and replay["elapsed"] <= 3.000001)
    check("only one pending DNS-only worker exists across repeated requests",
          replay["threads"] == 1, str(replay))
    check("a late DNS completion cannot send HTTP or trigger retries",
          replay["requests"] == replay["requests_after_late"] == 0)


def test_absolute_snapshot_fetch_mode_retains_cutoff_gaps():
    print("\n[absolute] snapshot requests explicitly opt into whole-attempt IO bounds")
    result, calls, _ = _snapshot_replay(lambda *args: None, pages=2)
    check("every initial and recovery snapshot call selects absolute HTTP limits",
          calls and all(c["kw"].get("absolute_timeout") is True for c in calls))
    check("cutoff pages remain gaps under the original manifest grouping",
          not result[0] and all(m["outcome"] in ("fetch_failed", "skipped") for m in result[2]))


# T-022 additive acceptance. Keep the original archive contract above unchanged.
class _PacingRates(dict):
    def __init__(self, values):
        super().__init__(values)
        self.changes = []

    def __setitem__(self, key, value):
        self.changes.append((key, value))
        super().__setitem__(key, value)

    def pop(self, key, *default):
        self.changes.append((key, None))
        return super().pop(key, *default)

    def __delitem__(self, key):
        self.changes.append((key, None))
        super().__delitem__(key)


def _pacing_cli_replay(args, mode="complete", previous=2.1, ordinary=False):
    """Real CLI, collection, fetcher, throttle and stdlib HTTP; fake sockets/clock only."""
    import fetcher
    import socket
    import ssl
    import tempfile
    import threading
    import urllib.request
    from contextlib import ExitStack, redirect_stdout, redirect_stderr
    from datetime import datetime, timedelta, timezone
    from unittest.mock import patch
    from urllib.parse import parse_qs, urlparse
    host = "api.geckoterminal.com"
    initial = dict(fetcher._RATE)
    if previous is None:
        initial.pop(host, None)
    else:
        initial[host] = previous
    rates = _PacingRates(initial)
    clock, calls, http, visits, writes, probes, waits = [0.0], [], [], {}, [], [], []
    stream, code, error, result = io.StringIO(), None, None, None
    real_fetch, real_collect, real_open = fetcher.fetch_json, snapshot.collect, io.open

    class Clock:
        fromisoformat = staticmethod(datetime.fromisoformat)

        @staticmethod
        def now(zone):
            return datetime(2026, 10, 9, tzinfo=timezone.utc) + timedelta(seconds=clock[0])

    class Event:
        def __init__(self):
            self.flag = False
        def set(self):
            self.flag = True
        def is_set(self):
            return self.flag
        def wait(self, timeout=None):
            return self.flag

    class Thread:
        def __init__(self, target, **kwargs):
            self.target = target
        def start(self):
            self.target()

    class SlowWire(io.RawIOBase):
        def __init__(self, connection):
            self.connection, self.offset = connection, 0
        def readable(self):
            return True
        def readinto(self, target):
            if self.offset == len(self.connection.wire):
                return 0
            delay = min(9.0, self.connection.timeout)
            clock[0] += delay
            if delay == self.connection.timeout:
                raise TimeoutError("fixture progressive HTTP timeout")
            target[0] = self.connection.wire[self.offset]
            self.offset += 1
            return 1

    class Socket:
        def __init__(self, timeout=10):
            self.timeout, self.wire = timeout, b""
        def settimeout(self, timeout):
            self.timeout = timeout
        def setsockopt(self, *args):
            pass
        def connect(self, address):
            pass
        def bind(self, address):
            pass
        def sendall(self, data):
            lines = data.decode("ascii").splitlines()
            target = lines[0].split()[1]
            request_host = next(line.split(": ", 1)[1] for line in lines
                                if line.lower().startswith("host: "))
            parsed = urlparse(target)
            page = int(parse_qs(parsed.query).get("page", [1])[0])
            key = (request_host, parsed.path, page)
            visits[key] = visits.get(key, 0) + 1
            failed = request_host == host and (mode == "partial" or
                     (mode == "recover" and parsed.path.endswith("new_pools")
                      and page == 1 and visits[key] <= 2))
            status = 429 if failed else 200
            payload = {"data": []} if parsed.path.endswith("trending_pools") else {
                "data": [_snapshot_pool("fixture_%s_%d" % (parsed.path.split("/")[-2], page))]}
            body = json.dumps(payload).encode("utf-8")
            self.wire = (("HTTP/1.1 %d fixture\r\nContent-Length: %d\r\n"
                          "Connection: close\r\n\r\n" % (status, len(body))).encode("ascii")
                         + body)
            http.append({"host": request_host, "path": target, "start": clock[0],
                         "status": status, "rate": rates.get(request_host, 0.3),
                         "timeout": self.timeout})
        def makefile(self, mode_name):
            return (io.BufferedReader(SlowWire(self)) if mode == "timeout"
                    else io.BytesIO(self.wire))
        def close(self):
            pass

    def connect(address, timeout=10, *args, **kwargs):
        return Socket(timeout)

    def observe_fetch(url, role, **options):
        call = {"url": url, "role": role, "options": options.copy(),
                "start": clock[0], "rates": dict(rates)}
        calls.append(call)
        value = real_fetch(url, role, **options)
        call.update(end=clock[0], diagnostics=dict(options.get("diagnostics", {})))
        return value

    def observe_collect(*positional, **options):
        nonlocal result
        result = real_collect(*positional, **options)
        if mode == "exception":
            raise RuntimeError("fixture collection exception")
        return result

    def observe_open(path, mode_name="r", *positional, **options):
        if "a" in mode_name or "w" in mode_name:
            writes.append({"path": os.path.basename(path), "rates": dict(rates)})
        return real_open(path, mode_name, *positional, **options)

    def observe_probe(*positional):
        probes.append(dict(rates))
        return []

    def sleep(seconds):
        waits.append(seconds)
        clock[0] += seconds

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
        stack.enter_context(patch.object(snapshot, "OUT_DIR", os.path.join(tmp, "output")))
        stack.enter_context(patch.object(fetcher, "CACHE_DIR", os.path.join(tmp, "cache")))
        stack.enter_context(patch.object(fetcher, "_RATE", rates))
        stack.enter_context(patch.object(fetcher, "_last_hit", {}))
        stack.enter_context(patch.object(fetcher, "_ACCESS_LOG", {"label": set(), "engine": set()}))
        stack.enter_context(patch.object(fetcher, "_SNAPSHOT_RESOLVER", fetcher._SnapshotResolver()))
        stack.enter_context(patch.object(socket, "create_connection", connect))
        stack.enter_context(patch.object(socket, "socket", lambda *a, **kw: Socket()))
        stack.enter_context(patch.object(socket, "getaddrinfo", return_value=[
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]))
        stack.enter_context(patch.object(ssl.SSLContext, "wrap_socket", lambda self, sock, **kw: sock))
        stack.enter_context(patch.object(urllib.request, "getproxies", return_value={}))
        stack.enter_context(patch.object(urllib.request, "urlopen", side_effect=opener.open))
        stack.enter_context(patch.object(threading, "Event", Event))
        stack.enter_context(patch.object(threading, "Thread", Thread))
        stack.enter_context(patch.object(fetcher.time, "time", lambda: 1000 + clock[0]))
        stack.enter_context(patch.object(fetcher.time, "monotonic", lambda: clock[0]))
        stack.enter_context(patch.object(fetcher.time, "sleep", sleep))
        stack.enter_context(patch.object(snapshot, "datetime", Clock))
        stack.enter_context(patch.object(snapshot, "fetch_json", side_effect=observe_fetch))
        stack.enter_context(patch.object(snapshot, "collect", side_effect=observe_collect))
        stack.enter_context(patch.object(snapshot.io, "open", side_effect=observe_open))
        stack.enter_context(patch.object(snapshot, "probe_sellability", side_effect=observe_probe))
        stack.enter_context(patch.object(snapshot.sys, "argv", ["snapshot.py"] + args))
        with redirect_stdout(stream), redirect_stderr(stream):
            try:
                code = snapshot.main()
            except SystemExit as exc:
                code = exc.code
            except RuntimeError as exc:
                error = str(exc)
        collection_end, restored = clock[0], dict(rates)
        if ordinary:
            for request_host in (host, host, "api.dexscreener.com", "api.dexscreener.com"):
                real_fetch("https://%s/api/v2/networks/base/new_pools?page=1" % request_host,
                           "label", retries=0, use_cache=False, write_cache=False)
        cache_exists = os.path.exists(fetcher.CACHE_DIR)
        files = sorted(os.listdir(snapshot.OUT_DIR)) if os.path.isdir(snapshot.OUT_DIR) else []
    return {"code": code, "error": error, "output": stream.getvalue(), "result": result,
            "calls": calls, "http": http, "writes": writes, "probes": probes,
            "initial": initial, "restored": restored, "changes": rates.changes,
            "collection_end": collection_end, "cache_exists": cache_exists, "files": files,
            "waits": waits}


def test_request_gap_rejects_invalid_values_before_any_work():
    print("\n[pacing] invalid CLI values do not fetch, read, create or change shared rates")
    import fetcher
    import tempfile
    from contextlib import ExitStack, redirect_stdout, redirect_stderr
    from unittest.mock import patch
    invalid = ["garbage", "-1", "0", "2.0", "2.099999", "nan", "NaN", "inf", "-inf", "1e309", None]
    for value in invalid:
        for extra in ([], ["--check-coverage"], ["--sellability-only", "1"]):
            rates, work, stream = _PacingRates(dict(fetcher._RATE)), [], io.StringIO()
            original = dict(rates)
            with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
                stack.enter_context(patch.object(snapshot, "OUT_DIR", os.path.join(tmp, "missing")))
                stack.enter_context(patch.object(fetcher, "_RATE", rates))
                args = extra + (["--request-gap"] if value is None else ["--request-gap=" + value])
                stack.enter_context(patch.object(snapshot.sys, "argv", ["snapshot.py"] + args))
                for owner, name in ((snapshot, "collect"), (snapshot, "fetch_json"),
                                    (snapshot, "_last_pass"), (snapshot, "_check_coverage"),
                                    (snapshot.os, "makedirs"), (snapshot.os, "listdir"),
                                    (snapshot.io, "open")):
                    def forbidden(*a, action=name, **kw):
                        work.append(action)
                        raise AssertionError("work before validation: " + action)
                    stack.enter_context(patch.object(owner, name, side_effect=forbidden))
                with redirect_stdout(stream), redirect_stderr(stream):
                    try:
                        code = snapshot.main()
                    except SystemExit as exc:
                        code = exc.code
            check("invalid gap %r in %s exits before every work or rate mutation" %
                  (value, extra or "collection"), code != 0 and not work
                  and not rates.changes and dict(rates) == original, stream.getvalue())


def test_request_gap_reaches_real_initial_recovery_and_ordinary_http():
    print("\n[pacing] the CLI interval reaches real throttle and fake stdlib HTTP starts")
    common = ["--chains", "base", "--pages", "2", "--sellability", "0"]
    for value in ("2.1", "12.1", "1e2"):
        replay = _pacing_cli_replay(common + ["--request-gap", value])
        starts = [h["start"] for h in replay["http"]]
        check("finite gap %s performs at least two successful real HTTP requests" % value,
              replay["code"] == 0 and len(starts) >= 2
              and all(h["status"] == 200 for h in replay["http"]), replay["output"])
        check("finite gap %s is the minimum between real HTTP starts" % value,
              len(starts) >= 2 and all(b - a >= float(value) - 0.000001
                                      for a, b in zip(starts, starts[1:])), str(starts))
        check("finite gap %s never reads or writes the shared response cache" % value,
              replay["calls"] and all(c["options"].get("use_cache") is False
              and c["options"].get("write_cache") is False for c in replay["calls"])
              and not replay["cache_exists"])
    replay = _pacing_cli_replay(common + ["--request-gap", "12.1"], mode="recover", ordinary=True)
    calls = replay["calls"]
    recovery = [c for c in calls if "deadline" in c["options"]]
    collection_http = replay["http"][:-4]
    check("a failed initial page is retried and really recovered under the same host rate",
          replay["code"] == 0 and recovery and len(collection_http) >= 5
          and all(c["rates"]["api.geckoterminal.com"] == 12.1 for c in calls)
          and any(m.get("initial_outcome") == "fetch_failed" and m["outcome"] == "ok"
                  for m in (replay["result"] or ([], "", []))[2]), replay["output"])
    check("initial retry, other pages and recovery share the real 12.1-second throttle",
          len(collection_http) >= 2 and all(b["start"] - a["start"] >= 12.1 - 0.000001
              for a, b in zip(collection_http, collection_http[1:])), str(collection_http))
    ordinary = replay["http"][-4:]
    check("ordinary GeckoTerminal calls retain the original 2.1-second default",
          len(ordinary) == 4 and all(h["rate"] == 2.1 for h in ordinary[:2])
          and abs(ordinary[1]["start"] - ordinary[0]["start"] - 2.1) < 0.000001,
          str(ordinary))
    check("another host keeps its own ordinary fetch interval",
          len(ordinary) == 4 and all(h["rate"] == 0.25 for h in ordinary[2:])
          and abs(ordinary[3]["start"] - ordinary[2]["start"] - 0.25) < 0.000001)


def test_request_gap_restores_existing_and_absent_rates_before_writes_and_probe():
    print("\n[pacing] rate state is restored before preservation and optional work on every exit")
    args = ["--chains", "base", "--pages", "2", "--sellability", "1", "--request-gap", "12.1"]
    for previous in (5.5, None):
        for mode, expected in (("complete", 0), ("partial", 1), ("exception", None)):
            replay = _pacing_cli_replay(args, mode=mode, previous=previous)
            check("%s with prior rate %r restores the exact original mapping" % (mode, previous),
                  replay["code"] == expected and replay["restored"] == replay["initial"]
                  and (replay["error"] == "fixture collection exception" if mode == "exception"
                       else replay["error"] is None), replay["output"])
            check("%s with prior rate %r changes only the collection host" % (mode, previous),
                  bool(replay["changes"]) and all(key == "api.geckoterminal.com"
                                                 for key, _ in replay["changes"]))
            if mode == "exception":
                check("the collection exception is propagated before any write or probe",
                      not replay["writes"] and not replay["probes"])
            else:
                check("%s with prior rate %r has restored pacing at every archive write" %
                      (mode, previous), replay["writes"]
                      and all(w["rates"] == replay["initial"] for w in replay["writes"]))
                check("%s with prior rate %r respects the optional-probe coverage guard" %
                      (mode, previous), replay["probes"] == ([replay["initial"]]
                                                            if mode == "complete" else []))


def test_request_gap_unset_import_and_noncollection_modes_do_not_change_rates():
    print("\n[pacing] only an explicitly paced collection changes the shared rate mapping")
    import fetcher
    import importlib.util
    import tempfile
    from contextlib import ExitStack, redirect_stdout, redirect_stderr
    from unittest.mock import patch
    for previous in (5.5, None):
        replay = _pacing_cli_replay(["--chains", "base", "--pages", "2", "--sellability", "0"],
                                    previous=previous)
        expected = previous if previous is not None else 0.3
        check("unset retains caller-specific prior rate %r without any mutation" % previous,
              replay["code"] == 0 and not replay["changes"]
              and all(h["rate"] == expected for h in replay["http"])
              and replay["restored"] == replay["initial"])
    rates = _PacingRates(dict(fetcher._RATE))
    with patch.object(fetcher, "_RATE", rates), patch.object(sys, "path", list(sys.path)):
        spec = importlib.util.spec_from_file_location("snapshot_import_fixture", snapshot.__file__)
        spec.loader.exec_module(importlib.util.module_from_spec(spec))
    check("importing snapshot has no shared-rate mutation", not rates.changes)
    for args, expected in ((["--check-coverage"], "health"), (["--sellability-only", "1"], "probe")):
        rates, calls, stream = _PacingRates(dict(fetcher._RATE)), [], io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            stack.enter_context(patch.object(fetcher, "_RATE", rates))
            stack.enter_context(patch.object(snapshot, "OUT_DIR", tmp))
            stack.enter_context(patch.object(snapshot.sys, "argv",
                                            ["snapshot.py"] + args + ["--request-gap", "12.1"]))
            stack.enter_context(patch.object(snapshot, "collect", side_effect=AssertionError("collection")))
            stack.enter_context(patch.object(snapshot, "fetch_json", side_effect=AssertionError("network")))
            stack.enter_context(patch.object(snapshot, "_check_coverage",
                                            side_effect=lambda: calls.append("health") or 0))
            stack.enter_context(patch.object(snapshot, "_last_pass", return_value=([{}], "fixture")))
            stack.enter_context(patch.object(snapshot, "probe_sellability",
                                            side_effect=lambda *a: calls.append("probe") or []))
            stack.enter_context(patch.object(snapshot, "_write_sellability", return_value=0))
            with redirect_stdout(stream), redirect_stderr(stream):
                try:
                    code = snapshot.main()
                except SystemExit as exc:
                    code = exc.code
        check("%s ignores a valid collection gap without changing rate state" % expected,
              code == 0 and calls == [expected] and not rates.changes, stream.getvalue())
    stream = io.StringIO()
    with patch.object(snapshot.sys, "argv", ["snapshot.py", "--help"]), redirect_stdout(stream):
        try:
            snapshot.main()
        except SystemExit:
            pass
    help_text = " ".join(stream.getvalue().lower().split())
    check("help describes the option as applying only to pool collection",
          "--request-gap" in help_text and "pool collection only" in help_text, help_text)


def test_request_gap_slow_recovery_keeps_deadline_cap_attempt_limits_and_gaps():
    print("\n[pacing] a slower real throttle consumes, rather than expands, the recovery budget")
    args = ["--chains", "a,b,c,d", "--pages", "5", "--sellability", "0", "--request-gap", "12.1"]
    for mode in ("partial", "timeout"):
        replay = _pacing_cli_replay(args, mode=mode)
        calls = replay["calls"]
        recovery = [c for c in calls if "deadline" in c["options"]]
        manifest = (replay["result"] or ([], "", []))[2]
        check("%s real recovery performs at most twelve calls within the original ninety seconds" % mode,
              recovery and 0 < len(recovery) <= 12
              and abs(recovery[0]["options"]["deadline"] - recovery[0]["start"] - 90) < 0.000001
              and replay["collection_end"] - recovery[0]["start"] <= 90 + 0.000001,
              str([(c["start"], c["end"]) for c in recovery]))
        check("%s keeps initial retries, recovery retries and whole-attempt limits" % mode,
              calls and all(c["options"].get("absolute_timeout") is True
                            and c["options"].get("retries") == (0 if "deadline" in c["options"] else 1)
                            and 0 < c["options"]["timeout"] <= 10 for c in calls)
              and all(c["options"]["timeout"] <= c["options"]["deadline"] - c["start"] + 0.000001
                      for c in recovery))
        check("%s leaves unobserved pages as persisted gaps and exits incomplete" % mode,
              replay["code"] == 1 and manifest
              and all(m["outcome"] in ("fetch_failed", "skipped") for m in manifest)
              and any(m.get("recovery_outcome") == "budget_exhausted" for m in manifest)
              and any(fn.startswith("runs-") for fn in replay["files"])
              and not any(fn.startswith("pools-") for fn in replay["files"]), replay["output"])
        starts = [h["start"] for h in replay["http"]]
        check("%s real HTTP requests remain at least 12.1 seconds apart" % mode,
              len(starts) >= 2 and all(b - a >= 12.1 - 0.000001
                                      for a, b in zip(starts, starts[1:])), str(starts))


def test_request_gap_workflow_paces_the_actual_collection_command_only():
    print("\n[pacing] the executable scheduled command selects 12.1 seconds")
    import re
    import shlex
    wf = io.open(os.path.join(ROOT, ".github", "workflows", "snapshot.yml"), encoding="utf-8").read()
    steps = {part.splitlines()[0].strip(): part for part in re.split(r"- name: ", wf)[1:]}
    commands = {name: shlex.split(match.group(1)) for name, body in steps.items()
                for match in [re.search(r"^\s*run:\s*(python\s+bench/snapshot\.py[^\n]*)$", body, re.M)]
                if match}
    collect = commands.get("Collect pools", [])
    check("Collect pools executes the real CLI with --request-gap 12.1 exactly once",
          collect[:2] == ["python", "bench/snapshot.py"] and collect.count("--request-gap") == 1
          and collect[collect.index("--request-gap") + 1:collect.index("--request-gap") + 2] == ["12.1"]
          and "--pages" in collect and collect[collect.index("--pages") + 1] == "5"
          and "--sellability" in collect and collect[collect.index("--sellability") + 1] == "0",
          str(collect))
    check("all other snapshot invocations retain their own collection defaults",
          commands.get("Collect day-one sellability") == ["python", "bench/snapshot.py", "--sellability-only", "25"]
          and all("--request-gap" not in body for name, body in steps.items() if name != "Collect pools"))
    replay = _pacing_cli_replay(collect[2:])
    starts = [h["start"] for h in replay["http"]]
    check("the actual workflow args reach real throttle and stdlib HTTP without network or real sleep",
          replay["code"] == 0 and len(starts) >= 2
          and all(h["rate"] == 12.1 for h in replay["http"])
          and all(b - a >= 12.1 - 0.000001 for a, b in zip(starts, starts[1:])), replay["output"])


# T-022 named change (a): wire starts after variable connection setup.
def _completion_cli_replay(setups=(), mode="ok", prior=2.1, anchor=13.0,
                           chains="base", pages=2, ordinary=False, operation="collect"):
    import fetcher
    import hashlib
    import socket
    import ssl
    import tempfile
    import threading
    import urllib.request
    from contextlib import ExitStack, redirect_stdout, redirect_stderr
    from datetime import datetime, timedelta, timezone
    from unittest.mock import patch
    from urllib.parse import parse_qs, urlparse
    host = "api.geckoterminal.com"
    initial_rates = dict(fetcher._RATE)
    if prior is None:
        initial_rates.pop(host, None)
    else:
        initial_rates[host] = prior
    rates = _PacingRates(initial_rates)
    initial_anchors = {"fixture.other.invalid": 17.0}
    if anchor is not None:
        initial_anchors[host] = anchor
    anchors = _PacingRates(initial_anchors)
    clock, http, calls, visits, phases, writes, probes, waits = [0.0], [], [], {}, [], [], [], []
    result, raised, code = None, None, None
    real_fetch, real_collect, real_open = fetcher.fetch_json, snapshot.collect, io.open
    stream = io.StringIO()

    class Clock:
        fromisoformat = staticmethod(datetime.fromisoformat)
        @staticmethod
        def now(zone):
            return datetime(2026, 10, 11, tzinfo=timezone.utc) + timedelta(seconds=clock[0])

    class Event:
        def __init__(self):
            self.flag = False
        def set(self):
            self.flag = True
        def is_set(self):
            return self.flag
        def wait(self, timeout=None):
            return self.flag

    class Thread:
        def __init__(self, target, **kwargs):
            self.target = target
        def start(self):
            self.target()

    setup_index = [0]
    active_setup = [(0, 0, 0)]

    def dns(*args):
        index = setup_index[0]
        setup_index[0] += 1
        active_setup[0] = setups[index] if index < len(setups) else (0, 0, 0)
        clock[0] += active_setup[0][0]
        phases.append(("dns", active_setup[0][0], clock[0]))
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]

    def tls(context, sock, **kwargs):
        delay = active_setup[0][2]
        elapsed = min(delay, sock.timeout)
        clock[0] += elapsed
        phases.append(("tls", elapsed, clock[0]))
        if delay >= sock.timeout and delay:
            raise TimeoutError("fixture TLS cutoff")
        return sock

    class SlowWire(io.RawIOBase):
        def __init__(self, connection):
            self.connection, self.offset = connection, 0
        def readable(self):
            return True
        def readinto(self, target):
            if self.offset == len(self.connection.wire):
                return 0
            delay = min(9.0, self.connection.timeout)
            clock[0] += delay
            if delay >= self.connection.timeout:
                raise TimeoutError("fixture HTTP cutoff after setup")
            target[0] = self.connection.wire[self.offset]
            self.offset += 1
            return 1

    class Socket:
        def __init__(self, timeout=10):
            self.timeout, self.wire = timeout, b""
        def settimeout(self, timeout):
            self.timeout = timeout
        def setsockopt(self, *args):
            pass
        def connect(self, address):
            delay = active_setup[0][1]
            elapsed = min(delay, self.timeout)
            clock[0] += elapsed
            phases.append(("connect", elapsed, clock[0]))
            if delay >= self.timeout and delay:
                raise TimeoutError("fixture connect cutoff")
        def bind(self, address):
            pass
        def sendall(self, data):
            if mode == "interrupt":
                raise KeyboardInterrupt("fixture wire interrupt")
            lines = data.decode("ascii").splitlines()
            target = lines[0].split()[1]
            request_host = next(line.split(": ", 1)[1] for line in lines
                                if line.lower().startswith("host: "))
            parsed = urlparse(target)
            page = int(parse_qs(parsed.query).get("page", [1])[0])
            key = (parsed.path, page)
            visits[key] = visits.get(key, 0) + 1
            failed = mode == "partial" or (mode == "recover" and
                     parsed.path.endswith("new_pools") and page == 1 and visits[key] <= 2)
            status = 429 if failed else 200
            body = json.dumps({"data": [] if parsed.path.endswith("trending_pools") else
                               [_snapshot_pool("fixture_%s_%d" % (parsed.path.split("/")[-2], page))]}).encode("utf-8")
            self.wire = (("HTTP/1.1 %d fixture\r\nContent-Length: %d\r\nConnection: close\r\n\r\n" %
                          (status, len(body))).encode("ascii") + body)
            http.append({"start": clock[0], "host": request_host, "status": status,
                         "io_remaining": self.timeout, "anchors": dict(anchors)})
        def makefile(self, mode_name):
            return io.BufferedReader(SlowWire(self)) if mode == "cutoff" else io.BytesIO(self.wire)
        def close(self):
            pass

    def observe_fetch(url, role, **options):
        call = {"start": clock[0], "options": options.copy(), "anchors": dict(anchors)}
        calls.append(call)
        value = real_fetch(url, role, **options)
        call.update(end=clock[0], diagnostics=dict(options.get("diagnostics", {})))
        return value

    def observe_collect(*args, **options):
        nonlocal result
        result = real_collect(*args, **options)
        return result

    def observe_open(path, mode_name="r", *args, **options):
        if "a" in mode_name or "w" in mode_name:
            writes.append((dict(rates), dict(anchors)))
        return real_open(path, mode_name, *args, **options)

    def observe_probe(*args):
        probes.append((dict(rates), dict(anchors)))
        return []

    def sleep(seconds):
        waits.append(seconds)
        clock[0] += seconds

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
        stack.enter_context(patch.object(snapshot, "OUT_DIR", os.path.join(tmp, "archive")))
        stack.enter_context(patch.object(fetcher, "CACHE_DIR", os.path.join(tmp, "cache")))
        stack.enter_context(patch.object(fetcher, "_RATE", rates))
        # create=True makes the pre-fix red behavioral, without an unknown API failure.
        stack.enter_context(patch.object(fetcher, "_SNAPSHOT_COMPLETION", anchors, create=True))
        stack.enter_context(patch.object(fetcher, "_last_hit", {}))
        stack.enter_context(patch.object(fetcher, "_ACCESS_LOG", {"engine": set(), "label": set()}))
        stack.enter_context(patch.object(fetcher, "_SNAPSHOT_RESOLVER", fetcher._SnapshotResolver()))
        stack.enter_context(patch.object(socket, "socket", lambda *a, **kw: Socket()))
        stack.enter_context(patch.object(socket, "create_connection", lambda *a, timeout=25, **kw: Socket(timeout)))
        stack.enter_context(patch.object(socket, "getaddrinfo", side_effect=dns))
        stack.enter_context(patch.object(ssl.SSLContext, "wrap_socket", tls))
        stack.enter_context(patch.object(ssl, "_create_default_https_context",
                                        return_value=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)))
        stack.enter_context(patch.object(urllib.request, "getproxies", return_value={}))
        stack.enter_context(patch.object(urllib.request, "urlopen", side_effect=opener.open))
        stack.enter_context(patch.object(threading, "Event", Event))
        stack.enter_context(patch.object(threading, "Thread", Thread))
        stack.enter_context(patch.object(fetcher.time, "time", lambda: 1000 + clock[0]))
        stack.enter_context(patch.object(fetcher.time, "monotonic", lambda: clock[0]))
        stack.enter_context(patch.object(fetcher.time, "sleep", sleep))
        stack.enter_context(patch.object(snapshot, "datetime", Clock))
        stack.enter_context(patch.object(snapshot, "fetch_json", side_effect=observe_fetch))
        stack.enter_context(patch.object(snapshot, "collect", side_effect=observe_collect))
        stack.enter_context(patch.object(snapshot.io, "open", side_effect=observe_open))
        stack.enter_context(patch.object(snapshot, "probe_sellability", side_effect=observe_probe))
        args = ["--chains", chains, "--pages", str(pages), "--sellability", "1"]
        if operation != "unset":
            args += ["--request-gap", "12.1"]
        stack.enter_context(patch.object(snapshot.sys, "argv", ["snapshot.py"] + args))
        url = "https://%s/api/v2/networks/base/new_pools?page=1" % host
        with redirect_stdout(stream), redirect_stderr(stream):
            if operation in ("ordinary", "other-host", "cached"):
                if operation == "cached":
                    os.makedirs(fetcher.CACHE_DIR)
                    path = os.path.join(fetcher.CACHE_DIR, hashlib.sha256(url.encode()).hexdigest()[:40] + ".json")
                    with real_open(path, "w", encoding="utf-8") as fh:
                        json.dump({"url": url, "data": {"fixture_cached": True}}, fh)
                    code = real_fetch(url, "label", use_cache=True, write_cache=False)
                else:
                    if operation == "other-host":
                        url = url.replace(host, "api.dexscreener.com")
                    for _ in range(2):
                        code = real_fetch(url, "label", retries=0, use_cache=False, write_cache=False,
                                          absolute_timeout=operation == "other-host")
            else:
                try:
                    code = snapshot.main()
                except BaseException as exc:
                    raised = type(exc).__name__
                    code = exc.code if isinstance(exc, SystemExit) else None
        collection_end, restored_anchors, restored_rates = clock[0], dict(anchors), dict(rates)
        collection_http = list(http)
        if ordinary:
            for _ in range(2):
                real_fetch(url, "label", retries=0, use_cache=False, write_cache=False)
        files = sorted(os.listdir(snapshot.OUT_DIR)) if os.path.isdir(snapshot.OUT_DIR) else []
    return {"code": code, "raised": raised, "output": stream.getvalue(), "http": http,
            "collection_http": collection_http, "calls": calls, "result": result,
            "initial_rates": initial_rates, "rates": restored_rates,
            "initial_anchors": initial_anchors, "anchors": restored_anchors,
            "anchor_changes": anchors.changes, "writes": writes, "probes": probes,
            "end": collection_end, "phases": phases, "waits": waits, "files": files}


def test_request_gap_completion_keeps_wire_starts_apart_after_variable_setup():
    print("\n[completion] DNS, TCP and TLS costs cannot shorten actual HTTP-send gaps")
    cases = [("DNS", [(8, 0, 0)]), ("TLS", [(0, 0, 8)]), ("mixed", [(4, 0, 4)]),
             ("variable", [(2, 2, 3), (1, 0, 2), (0, 1, 0)])]
    for label, setups in cases:
        replay = _completion_cli_replay(setups)
        starts = [h["start"] for h in replay["collection_http"]]
        check(label + " uses the actual main/fetcher/stdlib HTTP sends with successful coverage",
              replay["code"] == 0 and len(starts) == 3, replay["output"])
        check(label + " setup leaves every real wire-start gap at least 12.1 seconds",
              len(starts) == 3 and all(b - a >= 12.1 - 0.000001 for a, b in zip(starts, starts[1:])), str(starts))
        check(label + " applies gap waiting before, rather than inside, each ten-second IO attempt",
              len(replay["collection_http"]) == 3 and all(0 < h["io_remaining"] <= 10.000001
              for h in replay["collection_http"]) and replay["collection_http"][-1]["io_remaining"] >= 8.999999)


def test_request_gap_completion_covers_retry_recovery_and_restored_ordinary_calls():
    print("\n[completion] failed attempts, retries and recovery retain the same wire gap")
    replay = _completion_cli_replay([(4, 0, 4)], mode="recover", ordinary=True)
    starts = [h["start"] for h in replay["collection_http"]]
    recovery = [c for c in replay["calls"] if "deadline" in c["options"]]
    check("failed initial attempts really retry and recover the page with original retry choices",
          replay["code"] == 0 and len(starts) == 5 and recovery
          and [h["status"] for h in replay["collection_http"]] == [429, 429, 200, 200, 200]
          and all(c["options"]["retries"] == (0 if "deadline" in c["options"] else 1) for c in replay["calls"]))
    check("both failed and successful attempt completions protect every wire-start gap",
          len(starts) == 5 and all(b - a >= 12.1 - 0.000001 for a, b in zip(starts, starts[1:])), str(starts))
    check("the old rate and completion anchor are already restored before preservation and probing",
          replay["rates"] == replay["initial_rates"] and replay["anchors"] == replay["initial_anchors"]
          and replay["writes"] and replay["probes"] and all(pair ==
          (replay["initial_rates"], replay["initial_anchors"]) for pair in replay["writes"] + replay["probes"]))
    ordinary = replay["http"][-2:]
    check("ordinary requests after the collection preserve their original 2.1-second interval",
          len(ordinary) == 2 and abs(ordinary[1]["start"] - ordinary[0]["start"] - 2.1) < 0.000001)


def test_request_gap_completion_retains_cutoffs_deadline_refusal_and_gap_manifest():
    print("\n[completion] setup and progressive IO keep original recovery and attempt budgets")
    for mode, chains, pages in (("partial", "a,b", 5), ("cutoff", "base", 5)):
        replay = _completion_cli_replay([(8, 0, 0)], mode=mode, chains=chains, pages=pages)
        recovery = [c for c in replay["calls"] if "deadline" in c["options"]]
        manifest = (replay["result"] or ([], "", []))[2]
        check(mode + " recovery obeys the unchanged ninety-second deadline and twelve-call cap",
              recovery and len(recovery) <= 12 and abs(recovery[0]["options"]["deadline"] -
              recovery[0]["start"] - 90) < 0.000001 and replay["end"] - recovery[0]["start"] <= 90.000001)
        check(mode + " keeps ten-second whole-attempt IO and recovery timeouts",
              recovery and all(c["options"]["absolute_timeout"] is True and
              c["options"]["timeout"] <= 10 and c["options"]["retries"] == 0 for c in recovery)
              and all(0 < h["io_remaining"] <= 10.000001 for h in replay["collection_http"]))
        check(mode + " refuses the next over-budget pacing wait without sending another request",
              replay["code"] == 1 and recovery and recovery[-1]["diagnostics"].get("error") == "budget_exhausted"
              and recovery[-1]["diagnostics"].get("attempts") == 0)
        check(mode + " records unavailable pages and restores both state maps before writes",
              manifest and all(m["outcome"] in ("fetch_failed", "skipped") for m in manifest)
              and any(m.get("recovery_outcome") == "budget_exhausted" for m in manifest)
              and replay["writes"] and all(pair == (replay["initial_rates"], replay["initial_anchors"])
              for pair in replay["writes"]) and any(fn.startswith("runs-") for fn in replay["files"]))
        starts = [h["start"] for h in replay["collection_http"]]
        check(mode + " unavailable attempts also keep actual send gaps at least 12.1 seconds",
              len(starts) >= 2 and all(b - a >= 12.1 - 0.000001 for a, b in zip(starts, starts[1:])), str(starts))


def test_request_gap_completion_restores_absent_state_and_interrupted_exit():
    print("\n[completion] absent entries and a BaseException restore the full temporary state")
    for mode in ("ok", "partial", "interrupt"):
        replay = _completion_cli_replay([(4, 0, 4)], mode=mode, prior=None, anchor=None, pages=1)
        check(mode + " restores absent rate and completion entries, including a wire interrupt",
              replay["rates"] == replay["initial_rates"] and replay["anchors"] == replay["initial_anchors"]
              and (replay["raised"] == "KeyboardInterrupt" if mode == "interrupt" else
                   replay["code"] == (0 if mode == "ok" else 1)))
        check(mode + " opts in transiently and never changes another host's completion state",
              replay["anchor_changes"] and all(host == "api.geckoterminal.com" for host, _ in replay["anchor_changes"]))
        if mode == "interrupt":
            check("the interrupted wire exits before any archive write or optional probe",
                  not replay["writes"] and not replay["probes"])


def test_request_gap_completion_is_noop_for_unset_cached_ordinary_and_other_hosts():
    print("\n[completion] cached/default callers and other hosts retain their previous behavior")
    for operation in ("unset", "ordinary", "other-host", "cached"):
        replay = _completion_cli_replay(anchor=None if operation == "unset" else 1000.0, operation=operation)
        check(operation + " never changes a completion anchor or its opt-in configuration",
              not replay["anchor_changes"] and replay["anchors"] == replay["initial_anchors"])
        if operation == "cached":
            check("a cached result is read without any HTTP or real pacing wait",
                  replay["code"] == {"fixture_cached": True} and not replay["http"] and not replay["waits"])
        else:
            starts = [h["start"] for h in replay["http"]]
            gap = 0.25 if operation == "other-host" else 2.1
            check(operation + " keeps its ordinary host's original start-based gap",
                  len(starts) >= 2 and abs(starts[1] - starts[0] - gap) < 0.000001)


# T-022 named change (b): preservation before the scheduled job's timeout.
def _collection_budget_cli_replay(setup="dns", mode="retry", prior_deadline=4500.0,
                                  absent=False, operation="scheduled", optional=False,
                                  start=0.0):
    import fetcher
    import hashlib
    import re
    import shlex
    import socket
    import ssl
    import tempfile
    import threading
    import urllib.request
    from contextlib import ExitStack, redirect_stdout, redirect_stderr
    from datetime import datetime, timedelta, timezone
    from unittest.mock import patch
    from urllib.parse import urlparse
    host = "api.geckoterminal.com"
    initial_rates = dict(fetcher._RATE)
    initial_anchors = {"fixture.other.invalid": 17.0}
    initial_deadlines = {"fixture.other.invalid": -1.0}
    if absent:
        initial_rates.pop(host, None)
    elif operation != "unset":
        initial_anchors[host] = 13.0
    if prior_deadline is not None:
        initial_deadlines[host] = prior_deadline
    rates, anchors, deadlines = (_PacingRates(value) for value in
                                 (initial_rates, initial_anchors, initial_deadlines))
    clock, http, calls, visits, writes, probes, waits = [start], [], [], {}, [], [], []
    result, raised, code = None, None, None
    real_fetch, real_collect, real_open = fetcher.fetch_json, snapshot.collect, io.open
    stream = io.StringIO()
    wf = io.open(os.path.join(ROOT, ".github", "workflows", "snapshot.yml"), encoding="utf-8").read()
    steps = {part.splitlines()[0].strip(): part for part in re.split(r"- name: ", wf)[1:]}
    command = shlex.split(re.search(r"^\s*run:\s*(python\s+bench/snapshot\.py[^\n]*)$",
                                   steps["Collect pools"], re.M).group(1))
    args = command[2:]
    if optional:
        args[args.index("--sellability") + 1] = "1"
    if operation == "unset":
        flag = args.index("--request-gap")
        del args[flag:flag + 2]
    elif operation in ("coverage", "sellability"):
        args = (["--check-coverage"] if operation == "coverage" else ["--sellability-only", "1"])
        args += ["--request-gap", "12.1"]

    class Clock:
        fromisoformat = staticmethod(datetime.fromisoformat)
        @staticmethod
        def now(zone):
            return datetime(2026, 10, 11, tzinfo=timezone.utc) + timedelta(seconds=clock[0])

    class Event:
        def __init__(self):
            self.flag = False
        def set(self):
            self.flag = True
        def is_set(self):
            return self.flag
        def wait(self, timeout=None):
            return self.flag

    class Thread:
        def __init__(self, target, **kwargs):
            self.target = target
        def start(self):
            self.target()

    def dns(*args):
        if setup == "dns":
            clock[0] += 9.0
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]

    def tls(context, sock, **kwargs):
        if setup == "tls":
            elapsed = min(9.0, sock.timeout)
            clock[0] += elapsed
            if elapsed >= sock.timeout:
                raise TimeoutError("fixture collection TLS deadline")
        return sock

    class SlowWire(io.RawIOBase):
        def __init__(self, connection):
            self.connection = connection
        def readable(self):
            return True
        def readinto(self, target):
            clock[0] += self.connection.timeout
            raise TimeoutError("fixture collection body deadline")

    class Socket:
        def __init__(self, timeout=10):
            self.timeout, self.wire = timeout, b""
        def settimeout(self, timeout):
            self.timeout = timeout
        def setsockopt(self, *args):
            pass
        def connect(self, address):
            pass
        def bind(self, address):
            pass
        def sendall(self, data):
            lines = data.decode("ascii").splitlines()
            target = lines[0].split()[1]
            request_host = next(line.split(": ", 1)[1] for line in lines
                                if line.lower().startswith("host: "))
            visits[target] = visits.get(target, 0) + 1
            failed = mode == "all-fail" or (mode == "retry" and visits[target] == 1)
            if mode == "recover":
                failed = "/eth/new_pools?page=1" in target and visits[target] <= 2
            status = 429 if failed else 200
            body = json.dumps({"data": [] if "trending_pools" in target else
                               [_snapshot_pool("fixture_" + target)]}).encode("utf-8")
            self.wire = (("HTTP/1.1 %d fixture\r\nContent-Length: %d\r\nConnection: close\r\n\r\n" %
                          (status, len(body))).encode("ascii") + body)
            http.append({"start": clock[0], "target": target, "host": request_host,
                         "status": status, "io_remaining": self.timeout,
                         "deadlines": dict(deadlines), "anchors": dict(anchors)})
            if mode == "interrupt":
                raise KeyboardInterrupt("fixture collection wire interrupt")
        def makefile(self, mode_name):
            return io.BufferedReader(SlowWire(self)) if mode == "body-cutoff" else io.BytesIO(self.wire)
        def close(self):
            pass

    def observe_fetch(url, role, **options):
        call = {"start": clock[0], "options": options.copy(), "deadlines": dict(deadlines)}
        calls.append(call)
        value = real_fetch(url, role, **options)
        call.update(end=clock[0], diagnostics=dict(options.get("diagnostics", {})))
        return value

    def observe_collect(*args, **options):
        nonlocal result
        result = real_collect(*args, **options)
        return result

    def state():
        return (dict(rates), dict(anchors), dict(deadlines))

    def observe_open(path, mode_name="r", *args, **options):
        if "a" in mode_name or "w" in mode_name:
            writes.append({"at": clock[0], "path": os.path.basename(path), "state": state()})
        return real_open(path, mode_name, *args, **options)

    def observe_probe(*args):
        probes.append(state())
        return []

    def sleep(seconds):
        waits.append({"at": clock[0], "seconds": seconds})
        clock[0] += seconds

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
        stack.enter_context(patch.object(snapshot, "OUT_DIR", os.path.join(tmp, "archive")))
        stack.enter_context(patch.object(fetcher, "CACHE_DIR", os.path.join(tmp, "cache")))
        stack.enter_context(patch.object(fetcher, "_RATE", rates))
        stack.enter_context(patch.object(fetcher, "_SNAPSHOT_COMPLETION", anchors))
        stack.enter_context(patch.object(fetcher, "_SNAPSHOT_DEADLINE", deadlines, create=True))
        stack.enter_context(patch.object(fetcher, "_last_hit", {}))
        stack.enter_context(patch.object(fetcher, "_ACCESS_LOG", {"engine": set(), "label": set()}))
        stack.enter_context(patch.object(fetcher, "_SNAPSHOT_RESOLVER", fetcher._SnapshotResolver()))
        stack.enter_context(patch.object(socket, "socket", lambda *a, **kw: Socket()))
        stack.enter_context(patch.object(socket, "create_connection", lambda *a, timeout=25, **kw: Socket(timeout)))
        stack.enter_context(patch.object(socket, "getaddrinfo", side_effect=dns))
        stack.enter_context(patch.object(ssl.SSLContext, "wrap_socket", tls))
        stack.enter_context(patch.object(ssl, "_create_default_https_context",
                                        return_value=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)))
        stack.enter_context(patch.object(urllib.request, "getproxies", return_value={}))
        stack.enter_context(patch.object(urllib.request, "urlopen", side_effect=opener.open))
        stack.enter_context(patch.object(threading, "Event", Event))
        stack.enter_context(patch.object(threading, "Thread", Thread))
        stack.enter_context(patch.object(fetcher.time, "time", lambda: 1000 + clock[0]))
        stack.enter_context(patch.object(fetcher.time, "monotonic", lambda: clock[0]))
        stack.enter_context(patch.object(fetcher.time, "sleep", sleep))
        stack.enter_context(patch.object(snapshot, "datetime", Clock))
        stack.enter_context(patch.object(snapshot, "fetch_json", side_effect=observe_fetch))
        stack.enter_context(patch.object(snapshot, "collect", side_effect=observe_collect))
        stack.enter_context(patch.object(snapshot.io, "open", side_effect=observe_open))
        stack.enter_context(patch.object(snapshot, "probe_sellability", side_effect=observe_probe))
        stack.enter_context(patch.object(snapshot.sys, "argv", ["snapshot.py"] + args))
        url = "https://%s/api/v2/networks/eth/new_pools?page=1" % host
        with redirect_stdout(stream), redirect_stderr(stream):
            if operation == "cached":
                os.makedirs(fetcher.CACHE_DIR)
                path = os.path.join(fetcher.CACHE_DIR, hashlib.sha256(url.encode()).hexdigest()[:40] + ".json")
                with real_open(path, "w", encoding="utf-8") as fh:
                    json.dump({"url": url, "data": {"fixture_cached": True}}, fh)
                code = real_fetch(url, "label", use_cache=True, write_cache=False, absolute_timeout=True)
            elif operation in ("ordinary", "other-host", "fetch"):
                if operation == "other-host":
                    url = url.replace(host, "api.dexscreener.com")
                diagnostics = {}
                code = real_fetch(url, "label", retries=1 if operation == "fetch" else 0,
                                  timeout=10, use_cache=False, write_cache=False,
                                  absolute_timeout=operation != "ordinary", diagnostics=diagnostics)
                calls.append({"diagnostics": diagnostics})
            elif operation == "import":
                import runpy
                runpy.run_path(snapshot.__file__, run_name="collection_budget_import")
            else:
                try:
                    code = snapshot.main()
                except BaseException as exc:
                    raised = type(exc).__name__
                    code = exc.code if isinstance(exc, SystemExit) else None
        persisted = {}
        files = sorted(os.listdir(snapshot.OUT_DIR)) if os.path.isdir(snapshot.OUT_DIR) else []
        for name in files:
            with real_open(os.path.join(snapshot.OUT_DIR, name), encoding="utf-8") as fh:
                persisted[name.split("-", 1)[0]] = [json.loads(line) for line in fh if line.strip()]
    return {"code": code, "raised": raised, "output": stream.getvalue(), "http": http,
            "calls": calls, "result": result, "end": clock[0], "writes": writes, "probes": probes,
            "waits": waits, "persisted": persisted, "args": args,
            "initial_state": (initial_rates, initial_anchors, initial_deadlines), "state": state(),
            "deadline_changes": deadlines.changes, "anchor_changes": anchors.changes}


def test_request_gap_collection_budget_preserves_the_full_scheduled_prefix_before_job_cutoff():
    print("\n[collection budget] the full scheduled command preserves slow-retry observations on time")
    for setup in ("dns", "tls"):
        replay = _collection_budget_cli_replay(setup)
        rows, _, manifest = replay["result"]
        http, writes = replay["http"], replay["writes"]
        check(setup + " exercises the actual eight-chain, forty-eight-page scheduled arguments",
              replay["args"] == ["--pages", "5", "--sellability", "0", "--request-gap", "12.1"]
              and len(manifest) == 48 and len({m["chain"] for m in manifest}) == 8)
        check(setup + " preserves a successful prefix and incomplete manifest before the 1500-second cutoff",
              replay["code"] == 1 and 0 < len(rows) < 40 and writes
              and min(w["at"] for w in writes) < 1500 and replay["end"] <= 1200.000001,
              "end=%s writes=%s rows=%s" % (replay["end"], [w["at"] for w in writes], len(rows)))
        check(setup + " stops real HTTP sends at the opt-in monotonic collection deadline",
              2 < len(http) < 96 and all(h["start"] < 1200 and
              h["deadlines"].get("api.geckoterminal.com") == 1200 for h in http))
        check(setup + " initial failures really retry before successful pages without extending IO",
              [h["status"] for h in http[:4]] == [429, 200, 429, 200]
              and all(0 < h["io_remaining"] <= 1.000001 for h in http)
              and all(c["options"]["timeout"] <= 10 and c["options"]["absolute_timeout"]
              and c["options"]["retries"] == (0 if "deadline" in c["options"] else 1)
              for c in replay["calls"]))
        check(setup + " retains the earlier completion-anchored minimum gap on actual stdlib sends",
              all(b["start"] - a["start"] >= 12.1 - 0.000001 for a, b in zip(http, http[1:])))
        check(setup + " stores exactly its observed rows and a valid honest gap manifest",
              replay["persisted"].get("pools") == rows and replay["persisted"].get("runs") == manifest
              and snapshot._coverage(manifest)[2] > 0
              and not snapshot._coverage(manifest)[3].get("manifest_invalid")
              and any(m.get("recovery_outcome") == "budget_exhausted" for m in manifest)
              and all(m["outcome"] != "end_of_listing" for m in manifest
                      if m["initial_outcome"] in ("fetch_failed", "skipped")))
        check(setup + " restores all scoped state before writing and skips optional work",
              replay["state"] == replay["initial_state"] and not replay["probes"]
              and all(w["state"] == replay["initial_state"] for w in writes))


def test_request_gap_collection_budget_bounds_retry_waits_and_remaining_real_io():
    print("\n[collection budget] the real fetcher bounds setup, body and retry waits by remaining time")
    for label, setup, mode, deadline in (("TLS", "tls", "ok", 5.0),
                                        ("body", "none", "body-cutoff", 5.0),
                                        ("retry", "none", "retry", 2.0)):
        replay = _collection_budget_cli_replay(setup, mode, prior_deadline=deadline,
                                               absent=True, operation="fetch")
        diagnostic = replay["calls"][-1]["diagnostics"]
        check(label + " fails at the scoped deadline without a late HTTP attempt or unbounded retry wait",
              replay["code"] is None and replay["end"] <= deadline + 0.000001
              and diagnostic.get("error") == "budget_exhausted"
              and all(h["start"] < deadline for h in replay["http"]), str(diagnostic))
        check(label + " retains at most one original IO attempt and leaves external configuration unchanged",
              diagnostic.get("attempts") == 1 and len(replay["http"]) <= 1
              and replay["state"] == replay["initial_state"] and not replay["deadline_changes"])
    replay = _collection_budget_cli_replay("dns", "all-fail")
    recovery = [c for c in replay["calls"] if "deadline" in c["options"]]
    check("the independent recovery stage still has its ninety-second and twelve-call limits",
          recovery and len(recovery) <= 12 and abs(recovery[0]["options"]["deadline"] -
          recovery[0]["start"] - 90) < 0.000001
          and replay["end"] - recovery[0]["start"] <= 90.000001
          and all(c["options"]["retries"] == 0 and c["options"]["timeout"] <= 10 for c in recovery))


def test_request_gap_collection_budget_restores_existing_absent_and_interrupted_state():
    print("\n[collection budget] deadlines restore with rates and anchors on every exit path")
    for mode, setup, absent in (("ok", "none", False), ("retry", "dns", True),
                                ("interrupt", "dns", False), ("interrupt", "tls", True)):
        replay = _collection_budget_cli_replay(setup, mode, prior_deadline=None if absent else 4500.0,
                                               absent=absent, optional=True, start=37.0)
        check(mode + " restores exact prior deadline presence/value with existing pacing state",
              replay["state"] == replay["initial_state"] and replay["deadline_changes"]
              and replay["deadline_changes"][0] == ("api.geckoterminal.com", 1237.0)
              and all(host == "api.geckoterminal.com" for host, _ in replay["deadline_changes"]))
        if mode == "interrupt":
            check("an interrupted HTTP send restores state before propagating without preservation or probing",
                  replay["raised"] == "KeyboardInterrupt" and not replay["writes"] and not replay["probes"])
        else:
            check(mode + " writes only after restoring all temporary maps and observes the optional-work rule",
                  replay["writes"] and all(w["state"] == replay["initial_state"] for w in replay["writes"])
                  and (replay["code"] == 0 and replay["probes"] == [replay["initial_state"]]
                       if mode == "ok" else replay["code"] == 1 and not replay["probes"]))


def test_request_gap_collection_budget_is_noop_for_unset_cached_and_noncollection_calls():
    print("\n[collection budget] ordinary, cached and noncollection callers retain their contract")
    for operation in ("unset", "cached", "ordinary", "other-host", "import", "coverage", "sellability"):
        replay = _collection_budget_cli_replay("none", "ok", operation=operation,
                                               prior_deadline=None if operation == "unset" else -1.0)
        check(operation + " never changes a collection deadline or any caller's previous scope",
              replay["state"] == replay["initial_state"] and not replay["deadline_changes"])
        if operation in ("ordinary", "other-host"):
            check(operation + " can fetch despite an unrelated expired collection deadline",
                  isinstance(replay["code"], dict) and len(replay["http"]) == 1)
        elif operation == "unset":
            check("an unset collection still completes its full plan with no temporary deadline",
                  replay["code"] == 0 and len(replay["http"]) == 48)
        else:
            check(operation + " performs no HTTP request or pacing wait",
                  not replay["http"] and not replay["waits"])


# T-029: freshness observes manifests only, after the observer preserves its evidence.
def _freshness_module():
    import importlib.util
    path = os.path.join(ROOT, "bench", "snapshot_health.py")
    exists = os.path.isfile(path)
    check("the offline snapshot freshness monitor exists", exists)
    if not exists:
        return None
    spec = importlib.util.spec_from_file_location("snapshot_health_acceptance", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _freshness_now():
    from datetime import datetime, timezone
    return datetime(2026, 10, 18, 12, tzinfo=timezone.utc)


def _freshness_write(directory, rows, name="runs-2026-10-18.ndjson"):
    with io.open(os.path.join(directory, name), "w", encoding="utf-8") as fh:
        fh.write(rows if isinstance(rows, str) else
                 "".join(json.dumps(row) + "\n" for row in rows))


def _freshness_guard(directory):
    """Block all network, archive writes and pool reads while the monitor runs."""
    import builtins
    import socket
    import urllib.request
    from contextlib import ExitStack
    from unittest.mock import patch
    stack, reads = ExitStack(), []
    real_io_open, real_open, real_os_open = io.open, builtins.open, os.open
    archive = os.path.abspath(directory)

    def observe(file, mode):
        if any(flag in mode for flag in "wax+"):
            raise AssertionError("monitor attempted a write")
        if isinstance(file, (str, bytes, os.PathLike)):
            path = os.path.abspath(os.fsdecode(file))
            if os.path.dirname(path) == archive:
                name = os.path.basename(path)
                if not name.startswith("runs-"):
                    raise AssertionError("monitor inspected a pool file")
                reads.append(name)

    def guarded_io(file, mode="r", *args, **kwargs):
        observe(file, mode)
        return real_io_open(file, mode, *args, **kwargs)

    def guarded_open(file, mode="r", *args, **kwargs):
        observe(file, mode)
        return real_open(file, mode, *args, **kwargs)

    def guarded_os_open(file, flags, *args, **kwargs):
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            raise AssertionError("monitor attempted an OS write")
        observe(file, "r")
        return real_os_open(file, flags, *args, **kwargs)

    def blocked(*args, **kwargs):
        raise AssertionError("freshness must not use the network")

    for owner, name in ((socket, "socket"), (socket, "create_connection"),
                        (urllib.request, "urlopen"), (snapshot, "fetch_json")):
        stack.enter_context(patch.object(owner, name, side_effect=blocked))
    stack.enter_context(patch.object(io, "open", side_effect=guarded_io))
    stack.enter_context(patch.object(builtins, "open", side_effect=guarded_open))
    stack.enter_context(patch.object(os, "open", side_effect=guarded_os_open))
    return stack, reads


def _freshness_cli(module, directory, extra=()):
    from contextlib import redirect_stdout, redirect_stderr
    from datetime import datetime
    from unittest.mock import patch
    out, err = io.StringIO(), io.StringIO()

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return _freshness_now().astimezone(tz)

    stack, _ = _freshness_guard(directory)
    with stack, patch.object(module, "datetime", Clock), redirect_stdout(out), redirect_stderr(err):
        try:
            code = module.main(["--archive-dir", directory] + list(extra))
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def test_snapshot_freshness_exact_boundary_clock_and_current_coverage():
    print("\n[freshness] the twelve-hour policy includes its exact boundary")
    import tempfile
    from datetime import timedelta, timezone
    module = _freshness_module()
    if module is None:
        return
    now = _freshness_now()
    for age, status in ((12, "healthy"), (12 + 1 / 3600, "stale"), (11, "healthy")):
        with tempfile.TemporaryDirectory() as tmp:
            stamp = (now - timedelta(hours=age)).isoformat()
            _freshness_write(tmp, _snapshot_manifest(stamp))
            stack, _ = _freshness_guard(tmp)
            with stack:
                result = module.report(tmp, now=now)
            check("age %r has the expected boundary status" % age, result["status"] == status)
            check("age %r reports measured coverage and age" % age,
                  abs(result["latest_age_hours"] - age) < 1e-8
                  and result["latest_seen_at"] == stamp
                  and result["coverage"] == {"complete": True, "rows": 1, "pages": 2, "gaps": 0}
                  and result["causes"] == {})
            check("clock output is UTC with the required machine-readable fields",
                  result["checked_at"] == now.isoformat()
                  and set(result) == {"checked_at", "status", "latest_seen_at", "latest_age_hours",
                                      "observed_passes_24h", "complete_passes_24h", "coverage", "causes"})
    with tempfile.TemporaryDirectory() as tmp:
        _freshness_write(tmp, _snapshot_manifest(now.isoformat()))
        stack, _ = _freshness_guard(tmp)
        with stack:
            result = module.report(tmp, now=now.astimezone(timezone(timedelta(hours=2))))
        check("an offset-aware input clock normalizes to UTC", result["checked_at"] == now.isoformat())


def test_snapshot_freshness_latest_incomplete_overrides_an_older_complete_pass():
    print("\n[freshness] the actual newest pass wins even when collection failed")
    import tempfile
    module = _freshness_module()
    if module is None:
        return
    old = _snapshot_manifest("2026-10-18T08:00:00+00:00")
    failed = _snapshot_manifest("2026-10-18T11:00:00+00:00")
    failed[1].update(outcome="fetch_failed", diagnostics={"error": "http", "status": 429})
    with tempfile.TemporaryDirectory() as tmp:
        _freshness_write(tmp, failed + old)
        stack, _ = _freshness_guard(tmp)
        with stack:
            result = module.report(tmp, now=_freshness_now())
        check("newer failure cannot become old healthy evidence",
              result["status"] == "incomplete" and result["latest_seen_at"] == failed[0]["seen_at"]
              and result["latest_age_hours"] == 1)
        check("real failure causes and pass counts survive",
              result["causes"] == {"http_429": 1}
              and result["coverage"] == {"complete": False, "rows": 1, "pages": 2, "gaps": 1}
              and (result["observed_passes_24h"], result["complete_passes_24h"]) == (2, 1))


def test_snapshot_freshness_groups_equivalent_instants_and_ignores_filename_dates():
    print("\n[freshness] offsets and file order cannot fabricate extra passes")
    import tempfile
    module = _freshness_module()
    if module is None:
        return
    newest = _snapshot_manifest("2026-10-18T12:00:00+00:00")
    newest[1]["seen_at"] = "2026-10-18T14:00:00+02:00"
    with tempfile.TemporaryDirectory() as tmp:
        _freshness_write(tmp, _snapshot_manifest("2026-10-18T11:00:00+00:00"),
                         "runs-9999-12-31.ndjson")
        _freshness_write(tmp, newest[:1], "runs-0001-01-01.ndjson")
        _freshness_write(tmp, newest[1:], "runs-other-date.ndjson")
        stack, _ = _freshness_guard(tmp)
        with stack:
            result = module.report(tmp, now=_freshness_now())
        check("actual instants choose the latest observation across all manifest files",
              result["status"] == "healthy" and result["latest_seen_at"] == newest[0]["seen_at"]
              and result["latest_age_hours"] == 0)
        check("equivalent offsets make one complete pass",
              (result["observed_passes_24h"], result["complete_passes_24h"]) == (2, 2)
              and result["coverage"]["pages"] == 2)


def test_snapshot_freshness_counts_an_inclusive_window_and_preserves_observed_zero():
    print("\n[freshness] zero observed passes differs from an unavailable measurement")
    import tempfile
    from datetime import timedelta
    module = _freshness_module()
    if module is None:
        return
    now = _freshness_now()
    rows = []
    for hours in (24 + 1 / 3600, 24, 12, 6, 0):
        part = _snapshot_manifest((now - timedelta(hours=hours)).isoformat())
        if hours == 6:
            part[1].update(outcome="skipped", recovery_outcome="budget_exhausted")
        rows.extend(part)
    with tempfile.TemporaryDirectory() as tmp:
        _freshness_write(tmp, rows)
        stack, _ = _freshness_guard(tmp)
        with stack:
            result = module.report(tmp, now=now)
        check("the inclusive 24-hour window counts distinct actual observed and complete passes",
              (result["observed_passes_24h"], result["complete_passes_24h"]) == (4, 3))
        _freshness_write(tmp, rows[:2])
        stack, _ = _freshness_guard(tmp)
        with stack:
            old = module.report(tmp, now=now)
        check("a valid observed empty window is stale with real zero counts",
              old["status"] == "stale"
              and (old["observed_passes_24h"], old["complete_passes_24h"]) == (0, 0)
              and old["coverage"]["complete"] is True)


def test_snapshot_freshness_corrupt_missing_unreadable_and_future_evidence_are_unobserved():
    print("\n[freshness] unavailable evidence never falls back to an older success")
    import tempfile
    from unittest.mock import patch
    module = _freshness_module()
    if module is None:
        return
    good = _snapshot_manifest("2026-10-18T10:00:00+00:00")
    prefix = "".join(json.dumps(row) + "\n" for row in good)
    invalid = [("truncated current", prefix + '{"seen_at":"2026-10-18T11'),
               ("invalid JSON", prefix + "private-source-value\n"),
               ("malformed shape", prefix + "[]\n"),
               ("missing fields", good + [{"seen_at": "2026-10-18T11:00:00+00:00"}]),
               ("naive timestamp", _snapshot_manifest("2026-10-18T11:00:00")),
               ("date-only timestamp", _snapshot_manifest("2026-10-18")),
               ("future timestamp", _snapshot_manifest("2026-10-18T12:00:01+00:00")),
               ("empty file", "\n"), ("absent manifests", None)]
    for label, rows in invalid:
        with tempfile.TemporaryDirectory() as tmp:
            if rows is not None:
                _freshness_write(tmp, rows)
            stack, _ = _freshness_guard(tmp)
            with stack:
                result = module.report(tmp, now=_freshness_now())
            check(label + " is unobserved with unavailable measurements",
                  result["status"] == "unobserved" and result["coverage"] is None
                  and result["observed_passes_24h"] is None
                  and result["complete_passes_24h"] is None
                  and result["latest_age_hours"] is None and bool(result["causes"]))
            check(label + " never discloses source content", "private-source-value" not in json.dumps(result))
    with tempfile.TemporaryDirectory() as tmp:
        _freshness_write(tmp, good)
        stack, _ = _freshness_guard(tmp)
        with stack, patch.object(module.io, "open", side_effect=PermissionError("private-source-value")):
            unreadable = module.report(tmp, now=_freshness_now())
        check("an unreadable manifest is unavailable rather than zero",
              unreadable["status"] == "unobserved" and unreadable["observed_passes_24h"] is None
              and "private-source-value" not in json.dumps(unreadable))
        stack, _ = _freshness_guard(tmp)
        with stack:
            missing = module.report(os.path.join(tmp, "missing"), now=_freshness_now())
        check("a missing archive is unavailable rather than zero",
              missing["status"] == "unobserved" and missing["observed_passes_24h"] is None)


def test_snapshot_freshness_reuses_coverage_endings_failures_zero_rows_and_planned_gaps():
    print("\n[freshness] coverage keeps the collector's original meaning")
    import tempfile
    module = _freshness_module()
    if module is None:
        return
    stamp = "2026-10-18T11:00:00+00:00"
    ending = _snapshot_manifest(stamp)
    ending[1].update(outcome="end_of_listing")
    failure = _snapshot_manifest(stamp)
    failure[1].update(outcome="fetch_failed", diagnostics={"error": "network"})
    skipped = _snapshot_manifest(stamp)
    skipped[1].update(outcome="skipped", recovery_outcome="budget_exhausted")
    planned = [dict(row, chains=["base", "eth"]) for row in ending]
    past_end = [dict(ending[0], rows=0, pages=2, outcome="end_of_listing"),
                dict(ending[0], rows=0, pages=2, page=2, outcome="past_end_of_listing"),
                dict(ending[1], rows=1, outcome="ok")]
    cases = [ending, failure, skipped, planned, past_end,
             _snapshot_manifest(stamp, "end_of_listing", rows=0), ending[:1]]
    for index, rows in enumerate(cases):
        expected_rows, pages, gaps, causes = snapshot._coverage(rows)
        complete = expected_rows > 0 and gaps == 0 and not causes
        with tempfile.TemporaryDirectory() as tmp:
            _freshness_write(tmp, rows)
            stack, _ = _freshness_guard(tmp)
            with stack:
                result = module.report(tmp, now=_freshness_now())
            check("coverage case %d is identical to snapshot._coverage" % index,
                  result["coverage"] == {"complete": complete, "rows": expected_rows,
                                         "pages": pages, "gaps": gaps}
                  and result["causes"] == dict(causes)
                  and result["status"] == ("healthy" if complete else "incomplete")
                  and result["complete_passes_24h"] == int(complete))


def test_snapshot_freshness_is_read_only_redacted_and_validates_aware_clocks():
    print("\n[freshness] reporting never reads pools, writes files or contacts an upstream")
    import tempfile
    from datetime import datetime
    module = _freshness_module()
    if module is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        rows = _snapshot_manifest("2026-10-18T11:00:00+00:00")
        rows[0]["unused"] = "private-source-value"
        _freshness_write(tmp, rows, "runs-private-source-value.ndjson")
        with io.open(os.path.join(tmp, "pools-do-not-read.ndjson"), "w", encoding="utf-8") as fh:
            fh.write("private-source-value")
        before = {name: io.open(os.path.join(tmp, name), "rb").read() for name in os.listdir(tmp)}
        stack, reads = _freshness_guard(tmp)
        with stack:
            result = module.report(tmp, now=_freshness_now())
        after = {name: io.open(os.path.join(tmp, name), "rb").read() for name in os.listdir(tmp)}
        check("a report reads only manifests and preserves every original byte",
              result["status"] == "healthy" and reads == ["runs-private-source-value.ndjson"]
              and before == after and "private-source-value" not in json.dumps(result))
        stack, _ = _freshness_guard(tmp)
        with stack:
            try:
                module.report(tmp, now=datetime(2026, 10, 18, 12))
                rejected = False
            except ValueError:
                rejected = True
        check("a naive caller clock cannot claim current health", rejected)


def test_snapshot_freshness_cli_exit_codes_default_custom_duration_and_invalid_options():
    print("\n[freshness] machine-readable health is a hard CLI signal")
    import tempfile
    module = _freshness_module()
    if module is None:
        return
    cases = [("healthy", "2026-10-18T00:00:00+00:00", "ok", 0),
             ("stale", "2026-10-17T23:59:59+00:00", "ok", 1),
             ("incomplete", "2026-10-18T11:00:00+00:00", "fetch_failed", 1),
             ("unobserved", None, "ok", 2)]
    for label, stamp, outcome, expected in cases:
        with tempfile.TemporaryDirectory() as tmp:
            if stamp is not None:
                rows = _snapshot_manifest(stamp)
                if outcome != "ok":
                    rows[1]["outcome"] = outcome
                _freshness_write(tmp, rows)
            code, out, err = _freshness_cli(module, tmp)
            result = json.loads(out)
            check(label + " returns its distinct expected CLI signal and JSON",
                  code == expected and result["status"] == label and not err)
            if label == "stale":
                code, out, err = _freshness_cli(module, tmp, ["--max-age-hours", "13"])
                check("the explicit finite positive duration is honored",
                      code == 0 and json.loads(out)["status"] == "healthy" and not err)
    for value in ("0", "-1", "nan", "inf", "-inf", "not-a-duration"):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = _freshness_cli(module, tmp, ["--max-age-hours=" + value])
            check("invalid duration %s fails before reporting" % value,
                  code == 2 and not out and "finite" in err and "positive" in err)
    with tempfile.TemporaryDirectory() as tmp:
        for value in (0, -1, float("nan"), float("inf"), float("-inf")):
            stack, _ = _freshness_guard(tmp)
            with stack:
                try:
                    module.report(tmp, now=_freshness_now(), max_age_hours=value)
                    rejected = False
                except ValueError:
                    rejected = True
            check("the pure report also rejects invalid durations %r" % value, rejected)


def test_snapshot_freshness_workflow_runs_last_always_and_cannot_swallow_failure():
    print("\n[freshness] the observer preserves and generates before health can fail")
    import hashlib
    import re
    wf = io.open(os.path.join(ROOT, ".github", "workflows", "production.yml"), encoding="utf-8").read()
    marker = "      - name: Check snapshot freshness and coverage\n"
    exists = marker in wf
    check("the daily observer includes the required snapshot health step", exists)
    if not exists:
        return
    before, health = wf.split(marker, 1)
    check("all pre-existing observer bytes retain their original commands and order",
          hashlib.sha256(before.encode("utf-8")).hexdigest() ==
          "08fd9eb2690e50180a3c6dc2b9db45a3e209bb3c0e45549af44110c6e66f553a")
    steps = [part.splitlines()[0].strip() for part in re.split(r"- name: ", wf)[1:]]
    check("health runs after both observation commit and fixed-point generation",
          steps[-1] == "Check snapshot freshness and coverage"
          and steps.index("Commit") < steps.index("Regenerate the pages that quote it") < len(steps) - 1)
    check("health still executes when an earlier observer step failed",
          re.search(r"^        if: always\(\)$", health, re.M) is not None)
    check("the health command uses twelve hours and its exit cannot be swallowed",
          re.search(r"^        run: python bench/snapshot_health\.py --max-age-hours 12$", health, re.M)
          is not None and "continue-on-error" not in health and "||" not in health
          and len(re.findall(r"^        run:", health, re.M)) == 1)


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
