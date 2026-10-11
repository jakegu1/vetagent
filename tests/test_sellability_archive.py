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
