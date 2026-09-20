"""Measure what RugCheck's per-mint coverage actually does, over mints and over time.

Why this is committed rather than run once from a scratchpad: DECISIONS E31 and backlog
W52 both rest on numbers this produced, and W52 names a re-run as the thing that decides
whether the moving score is a defect. A parked experiment whose instrument no longer
exists is indistinguishable from a forgotten one -- this repository has written that down
twice and paid for it once.

Two questions, two modes.

`--mode holders` is the E31 measurement. Does a missing holder distribution mean this
upstream stopped sending holders, or that it has none for this mint? Every sweep records
every mint, so "how many of N carry one" is a distribution at a known instant rather than
an anecdote, and HTTP status is recorded separately from the fields -- a 429 that decodes
to {} is an outage, and counting it as "this mint has no holders" is the exact conflation
this repository keeps finding. A rotating slice gets an immediate second request, which
tests the sixty-second retry claim on its own terms.

Measured with it on 2026-09-20: 64 mints x 8 sweeps over 109 minutes, 576 requests, zero
non-200. 24 of 64 carried a holder list in every sweep, not one mint changed state, 64 of
64 immediate retries agreed, and the split tracks age -- 14 of 18 established mints, 10 of
20 trending, 0 of 26 the probe itself caused RugCheck to detect.

Then, twelve hours later the same day, 0 of 16 -- all HTTP 200, BONK among them. So 109
minutes was long enough to establish the per-mint split and far too short to see the
level move, and a run of this probe should be measured in days, not hours. The `--hours`
default is 2 because that is a cheap sanity run; DECISIONS E31 and W53 both need a longer
one.

`--mode scores` is the W52 measurement. RugCheck's `score_normalised` is provisional for
up to an hour after its own `detectedAt`: 11 of those 64 mints moved score, and the last
move lands 18 to 65 minutes after that mint was detected (median 20). One read 80, 80, 1,
80, 80 -- it left a band and came back -- and another read 1 for four consecutive sweeps,
about 45 minutes, before reading 80. The engine bands that number at 50 and 20, so the swing crosses every boundary it
has. `risks` is recorded here and not in holders mode, because a score is explained by its
risk entries and the 1s came with an empty array.

Usage:
    python bench/rugcheck_coverage_probe.py --mode holders --hours 2
    python bench/rugcheck_coverage_probe.py --mode scores --hours 6 --mints <a> <b> ...
    python bench/rugcheck_coverage_probe.py --report bench/rugcheck_coverage.jsonl

Writes JSONL incrementally and flushes, so a run cut short is still a measurement. It
calls only RugCheck and reads nothing from this repository's own service.
"""
import argparse
import collections
import datetime
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.join(HERE, "rugcheck_coverage.jsonl")
UA = "vetagent-coverage-probe"
REPORT_URL = "https://api.rugcheck.xyz/v1/tokens/%s/report"
GECKO_NEW = "https://api.geckoterminal.com/api/v2/networks/solana/new_pools?page=%d"

# The bands `src/risk.py` sorts this number into today: >=50 a `critical` signal, >=20 a
# `warn`, below that a passing `ok`. Copied rather than imported on purpose -- a probe that
# followed the engine would silently restate whatever the engine currently does, and the
# question here is whether the *upstream number* is stable enough for any banding at all.
# The fourth boundary is `established`'s third clause, `score_normalised <= 5`, which sits
# inside the `ok` band and is invisible to band() -- so it is counted separately below.
BANDS = ((50, "critical"), (20, "warn"), (0, "ok"))
ESTABLISHED_AT = 5


def band(x):
    """Which engine band a score falls in, or None if there was no score to read."""
    if x is None:
        return None
    for floor, name in BANDS:
        if x >= floor:
            return name
    return "ok"


# Long-lived mints with stable identities, so a re-run months from now is comparable.
# Deliberately mixed: USDC, USDT, PYUSD and WSOL carry no holder list while BONK, JUP and
# TRUMP carry a full one, which is the split being measured.
MAJORS = [
    ("USDC", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"),
    ("USDT", "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"),
    ("BONK", "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"),
    ("PYUSD", "2b1kV6DkPAnxd5ixfnxCpjxmKwqjjaYmCZfHsFu24GXo"),
    ("BERN", "CKfatsPMUf8SkiURsDXs7eK6GWb4Jsd6UDbs7twMCWxo"),
    ("TRUMP", "6p6xgHyF7AeE6TZkSmFsko444wqoP15icUSqi2jfGiPN"),
    ("W", "85VBFQZC9TZkfaptBWjvUw7YbZjy52A6mjtPGjstQAmQ"),
    ("JUP", "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN"),
    ("WIF", "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm"),
    ("JTO", "jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL"),
    ("RAY", "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R"),
    ("PYTH", "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3"),
    ("ORCA", "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE"),
    ("mSOL", "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So"),
    ("jitoSOL", "J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn"),
    ("RENDER", "rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof"),
    ("HNT", "hntyVP6YFm1Hg25TN9WGLqM12b8TQmcknKrdu1oxWux"),
    ("WSOL", "So11111111111111111111111111111111111111112"),
]


def curl(url):
    """(http_status, parsed_body_or_None). Status is kept apart from the body on purpose."""
    r = subprocess.run(["curl", "-s", "-m", "30", "-A", UA, "-w", "\n%{http_code}", url],
                       capture_output=True, encoding="utf-8", errors="replace")
    text = r.stdout or ""
    code = text.rpartition("\n")[2].strip() or "0"
    try:
        return code, json.loads(text.rpartition("\n")[0] or "null")
    except json.JSONDecodeError:
        return code, None


def gecko_new_mints(want):
    """Freshly listed Solana mints, so the sample spans token age rather than fame."""
    out = []
    for path in ("new_pools", "trending_pools"):
        code, d = curl("https://api.geckoterminal.com/api/v2/networks/solana/%s" % path)
        for row in ((d or {}).get("data") or []):
            rel = ((row.get("relationships") or {}).get("base_token") or {}).get("data") or {}
            ident = rel.get("id") or ""
            if ident.startswith("solana_"):
                mint = ident[len("solana_"):]
                name = ((row.get("attributes") or {}).get("name") or "")[:28]
                if len(mint) >= 32 and mint not in [m for _, m in out]:
                    out.append((name or mint[:8], mint))
            if len(out) >= want:
                return out
        time.sleep(3.0)
    return out


def age_minutes(detected_at, now=None):
    """Minutes since RugCheck first saw this mint, or None if it did not say.

    None is not zero and not "old": a mint with no `detectedAt` is one whose age we could
    not observe, and W52's sample rule is defined on the measured field, so an unreadable
    one keeps the mint out of the fresh cohort rather than into it.
    """
    if not detected_at:
        return None
    try:
        t = datetime.datetime.strptime(str(detected_at)[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None
    t = t.replace(tzinfo=datetime.timezone.utc)
    now = now or datetime.datetime.now(datetime.timezone.utc)
    return (now - t).total_seconds() / 60.0


def recruit_fresh(want, max_age_min, pages=8, gap=2.0):
    """Mints RugCheck detected within `max_age_min`, each one checked rather than assumed.

    W52 pre-registers its re-run over ">=40 mints caught within 10 minutes of their
    `detectedAt`", so membership of that cohort is a measurement. GeckoTerminal's "new
    pools" listing is only a proxy for age -- this asks RugCheck for the mint and reads the
    field. Asking is also what *creates* a fresh mint: a mint RugCheck has never seen is
    detected by this very request, which is how the 2026-09-20 run got 26 of them, and it
    is why the cohort has to be rebuilt per run instead of pinned to a list.
    """
    kept, seen = [], set()
    for page in range(1, pages + 1):
        code, d = curl(GECKO_NEW % page)
        rows = (d or {}).get("data") or []
        if not rows:
            print("  new_pools page %d: http %s, %d rows -- stopping" % (page, code, len(rows)))
            break
        for row in rows:
            rel = ((row.get("relationships") or {}).get("base_token") or {}).get("data") or {}
            ident = rel.get("id") or ""
            if not ident.startswith("solana_"):
                continue
            mint = ident[len("solana_"):]
            if len(mint) < 32 or mint in seen:
                continue
            seen.add(mint)
            name = ((row.get("attributes") or {}).get("name") or "")[:28]
            rec = observe(name or mint[:8], mint, "scores")
            age = age_minutes(rec.get("detectedAt"))
            if rec.get("body") == "ok" and age is not None and age <= max_age_min:
                kept.append((name or mint[:8], mint))
            time.sleep(gap)
            if len(kept) >= want:
                print("  recruited %d fresh mints from %d pages" % (len(kept), page))
                return kept
        time.sleep(gap)
    print("  recruited %d fresh mints (wanted %d) from %d pages" % (len(kept), want, pages))
    return kept


def observe(label, mint, mode):
    code, d = curl(REPORT_URL % mint)
    rec = {"mint": mint, "label": label, "http": code, "ts": time.time()}
    if not isinstance(d, dict) or not d:
        rec["body"] = "empty"
        return rec
    th = d.get("topHolders")
    rec.update({
        "body": "ok",
        "totalHolders": d.get("totalHolders"),
        "topHolders_n": len(th) if isinstance(th, list) else -1,
        "score_normalised": d.get("score_normalised"),
        "verification": bool(d.get("verification")),
        "detectedAt": d.get("detectedAt"),
    })
    if mode == "scores":
        rec["risks"] = [{"name": x.get("name"), "level": x.get("level")}
                        for x in (d.get("risks") or []) if isinstance(x, dict)]
        # The four powers `risk.established` gates, recorded because that flag's third
        # clause reads the same moving number this mode measures. Without them the probe
        # can report that a score moved and not whether the move reached anything: a mint
        # that dips under 5 while holding none of these is a number changing, and one that
        # dips while holding a permanent delegate is a critical signal turning into info.
        te = d.get("token_extensions")
        te = te if isinstance(te, dict) else {}
        rec["gated"] = {
            "permanentDelegate": bool(te.get("permanentDelegate")),
            "pausableConfig": bool(te.get("pausableConfig")),
            "mintCloseAuthority": bool(te.get("mintCloseAuthority")),
            "freeze_or_mint": bool(d.get("freezeAuthority") or d.get("mintAuthority")),
        }
    return rec


def run_probe(args):
    if args.mints:
        sample = [(m[:8], m) for m in args.mints]
    else:
        sample = [(l, m) for l, m in MAJORS]
        if args.mode == "holders":
            sample += gecko_new_mints(args.fresh)
        else:
            # Scores mode used to take the 18 MAJORS and nothing else, which made the
            # command W52 pre-registers -- `--mode scores --hours 6` -- incapable of
            # answering it: every mint in that list was detected years ago, so a run could
            # only ever report "no oscillation" and the rule could not fire whatever
            # RugCheck did. That is the cohort error the `established` comment in
            # src/risk.py describes, in the instrument this time. The majors stay as a
            # control -- if established mints oscillate too, the age story is wrong.
            fresh = recruit_fresh(args.fresh_scores, args.max_age_min, gap=args.gap)
            if len(fresh) < args.min_fresh:
                print("ABORT: recruited %d fresh mints, rule needs >=%d. Not starting a run "
                      "that cannot answer the question." % (len(fresh), args.min_fresh))
                return 2
            sample += fresh
    print("probing %d mints, mode=%s, up to %.1f h" % (len(sample), args.mode, args.hours))

    started, sweep = time.time(), 0
    with open(args.out, "a", encoding="utf-8") as f:
        while time.time() - started < args.hours * 3600:
            sweep += 1
            t0 = time.time()
            for i, (label, mint) in enumerate(sample):
                rec = observe(label, mint, args.mode)
                rec["sweep"] = sweep
                f.write(json.dumps(rec) + "\n")
                # A rotating slice asks twice, seconds apart: the 60-second retry claim.
                if args.mode == "holders" and i % 8 == (sweep % 8):
                    time.sleep(3.0)
                    again = observe(label, mint, args.mode)
                    again.update({"sweep": sweep, "immediate_retry": True})
                    f.write(json.dumps(again) + "\n")
                f.flush()
                time.sleep(args.gap)
            print("sweep %d in %.0fs" % (sweep, time.time() - t0), flush=True)
            time.sleep(max(0.0, args.every * 60 - (time.time() - t0)))
    return 0


def _leaves_and_returns(seq):
    """True if a value appears, is replaced, and comes back: B ... notB ... B.

    This is the shape W52 pre-registered as the thing that decides, and it is deliberately
    narrower than "the score moved". A score that settles in one direction is RugCheck
    finishing its work and needs nothing from us; a score that leaves a band and returns to
    it cannot be a re-evaluation, because the second reading agreed with the first.
    """
    for i, v in enumerate(seq):
        if v is None:
            continue
        left = False
        for w in seq[i + 1:]:
            if w is None:
                continue
            if w != v:
                left = True
            elif left:
                return True
    return False


def _score_verdict(by):
    """W52's pre-registered rule, and the `established` question folded into the same data.

    The rule was written before the re-run's data existed and is evaluated here mechanically
    rather than read off a chart, because this repository has a decision rule that was
    rewritten four times after seeing what the previous version produced. It is not edited
    in the light of what comes out below.
    """
    print("\n--- W52 pre-registered rule ------------------------------------------------")
    fresh, old, ageless = [], [], []
    for m, g in by.items():
        g = sorted(g, key=lambda r: r["sweep"])
        age = age_minutes(g[0].get("detectedAt"),
                          datetime.datetime.fromtimestamp(g[0]["ts"], datetime.timezone.utc))
        (fresh if (age is not None and age <= 10.0)
         else ageless if age is None else old).append(m)
    print("cohort: %d mints caught within 10 min of detectedAt, %d older, %d with no "
          "detectedAt to read" % (len(fresh), len(old), len(ageless)))
    if len(fresh) < 40:
        print("  NOTE: the rule is defined on >=40 such mints; this run has %d, so a "
              "non-firing result below is under-powered, not a negative." % len(fresh))

    osc = []
    for m in fresh:
        g = sorted(by[m], key=lambda r: r["sweep"])
        if _leaves_and_returns([band(r.get("score_normalised")) for r in g]):
            osc.append((m, g))
    print("FIRE CONDITION: %d of %d fresh mints left a band and returned (rule: >=3)"
          % (len(osc), len(fresh)))
    for m, g in osc:
        print("   %-30s %s" % (g[0]["label"][:30], [r.get("score_normalised") for r in g]))
    print("VERDICT: %s" % ("FIRES -- oscillation, not settling. Fix per W52."
                           if len(osc) >= 3 else
                           "does not fire on oscillation (>=3 required)"))

    # ------------------------------------------------------------------ the `established`
    # question, answered from the same rows. `score_normalised <= 5` is the third clause of
    # `risk.established`, which gates permanentDelegate, pausableConfig, mintCloseAuthority
    # and freeze/mint between `critical` and `info`. Band oscillation cannot see it: 1 and
    # 19 are both `ok`, and only one of them silences a permanent delegate.
    print("\n--- established's third clause (score_normalised <= %d) --------------------"
          % ESTABLISHED_AT)
    GATED = ("permanentDelegate", "pausableConfig", "mintCloseAuthority", "freeze_or_mint")
    ever_under, under_and_gated, flipped = [], [], []
    for m in fresh:
        g = sorted(by[m], key=lambda r: r["sweep"])
        under = [r for r in g
                 if r.get("score_normalised") is not None
                 and r["score_normalised"] <= ESTABLISHED_AT]
        if not under:
            continue
        ever_under.append(m)
        powers = sorted({k for r in under for k in GATED
                         if (r.get("gated") or {}).get(k)})
        if powers:
            under_and_gated.append((m, g, powers))
        side = [None if r.get("score_normalised") is None
                else r["score_normalised"] <= ESTABLISHED_AT for r in g]
        if len({s for s in side if s is not None}) > 1:
            flipped.append((m, g))
    print("fresh mints that read <=%d in at least one sweep: %d of %d"
          % (ESTABLISHED_AT, len(ever_under), len(fresh)))
    print("  ...of which also held an `established`-gated power at that moment: %d"
          % len(under_and_gated))
    for m, g, powers in under_and_gated:
        print("     %-28s %-34s %s" % (g[0]["label"][:28], ",".join(powers),
                                        [r.get("score_normalised") for r in g]))
    print("fresh mints that CROSSED the <=%d line during the run (established flipped): %d"
          % (ESTABLISHED_AT, len(flipped)))
    for m, g in flipped:
        print("     %-28s %s" % (g[0]["label"][:28], [r.get("score_normalised") for r in g]))
    print("Reading: a mint in the last list had four contract powers graded `critical` in "
          "one sweep and `info` in another, on nothing but this number.")


def report(path):
    rows = []
    for line in open(path, encoding="utf-8"):
        if line.strip():
            rows.append(json.loads(line))
    ok = [r for r in rows if r.get("body") == "ok"]
    first = [r for r in ok if not r.get("immediate_retry")]
    if not first:
        print("no usable rows in %s" % path)
        return 1
    span = (max(r["ts"] for r in first) - min(r["ts"] for r in first)) / 60.0
    mints = {r["mint"] for r in first}
    sweeps = sorted({r["sweep"] for r in first})
    bad = [r for r in rows if str(r.get("http")) != "200"]
    print("%d mints x %d sweeps = %d observations over %.0f min; %d of %d requests non-200"
          % (len(mints), len(sweeps), len(first), span, len(bad), len(rows)))

    for s in sweeps:
        g = [r for r in first if r["sweep"] == s]
        print("  sweep %-3d %2d of %2d carry a holder list"
              % (s, sum(1 for r in g if r.get("topHolders_n", 0) > 0), len(g)))

    by = collections.defaultdict(list)
    for r in first:
        by[r["mint"]].append(r)
    flips = [m for m, g in by.items()
             if len({r.get("topHolders_n", 0) > 0 for r in g}) > 1]
    print("mints whose holder coverage changed: %d" % len(flips))
    for m in flips:
        g = sorted(by[m], key=lambda r: r["sweep"])
        print("   %-44s %s" % (g[0]["label"][:44],
                               [(r["sweep"], r.get("topHolders_n", 0) > 0) for r in g]))

    moved = [m for m, g in by.items()
             if len({r.get("score_normalised") for r in g}) > 1]
    print("mints whose score_normalised moved: %d" % len(moved))
    for m in moved:
        g = sorted(by[m], key=lambda r: r["sweep"])
        print("   %-44s %s" % (g[0]["label"][:44],
                               [r.get("score_normalised") for r in g]))

    _score_verdict(by)

    agree = sum(1 for r in ok if r.get("immediate_retry")
                and any((x.get("topHolders_n", 0) > 0) == (r.get("topHolders_n", 0) > 0)
                        for x in first
                        if x["mint"] == r["mint"] and x["sweep"] == r["sweep"]))
    total = sum(1 for r in ok if r.get("immediate_retry"))
    print("immediate retries agreeing with their own sweep: %d of %d" % (agree, total))
    return 0


def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=("holders", "scores"), default="holders")
    p.add_argument("--hours", type=float, default=2.0)
    p.add_argument("--every", type=float, default=15.0, help="minutes between sweeps")
    p.add_argument("--gap", type=float, default=2.0, help="seconds between calls")
    p.add_argument("--fresh", type=int, default=46, help="freshly listed mints to add")
    # W52's rule, as parameters, so a run states the cohort it was judged against rather
    # than leaving it in a sentence: ">=40 mints caught within 10 minutes of detectedAt".
    p.add_argument("--fresh-scores", type=int, default=45,
                   help="fresh mints to recruit in scores mode (rule needs >=40)")
    p.add_argument("--min-fresh", type=int, default=40,
                   help="abort rather than run a scores probe too small to answer W52")
    p.add_argument("--max-age-min", type=float, default=10.0,
                   help="a mint joins the fresh cohort only this many minutes after detectedAt")
    p.add_argument("--mints", nargs="*", default=None)
    p.add_argument("--out", default=DEFAULT_OUT)
    p.add_argument("--report", default=None, help="analyse an existing jsonl and exit")
    args = p.parse_args(argv)
    if args.report:
        return report(args.report)
    return run_probe(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
