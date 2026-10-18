"""test_second_oracle.py -- the Owner's W5 check on the adversarial cohort, made safe to run.

WHY THIS FILE EXISTS

`bench/second_oracle.py` spends the Owner's Quick Intel allowance, a small monthly number of
calls on a free tier, and keeps the answers in a git-ignored file that nothing else copies. Its
first real run, on 2026-09-29, showed what a careless script costs there: it paced calls at
0.25 s against a tier that allows about one a second, so about every other call was rate
limited and had to be asked again by hand; it wrote its file once, at the end, over whatever
was there; and its report counted 143 calls that never reached Quick Intel as tokens Quick
Intel "could not answer", with a rate printed over them.

The one measurement W5 still needs is the adversarial cohort W3 rests on: the benchmark rows
GoPlus labels `unsafe`. This file pins what makes that run safe, on synthetic data only:

  - selection: `--set adversarial` asks about exactly that cohort, each row once, and without
    `--set` the script still asks about the disputed set, then the unknown set;
  - pacing: consecutive calls start at least PACE_SECONDS (2.0) apart;
  - the earlier answers: each selection has its own git-ignored output file, and --run refuses
    to start, before any call, when that file exists;
  - persistence: the file is rewritten after every call, so an interrupted run keeps the rows
    it was given, each with the time it was asked; a row on a chain Quick Intel has no name for
    here is recorded as not measured instead of vanishing;
  - the report: every row in exactly one class (not measured, no sell simulation, sell
    simulated), the not-measured rows kept out of every rate, a simulation's date and age, and
    no crash on a token symbol the console cannot encode.

Nothing here touches the network or waits. `urllib.request.urlopen`, socket connects and
`time.sleep` are replaced before the module is imported, and each test replaces the module's
clock, its fetch function and its paths, which point into a temporary directory. The raw
answers of the real runs are never read: every answer below is invented, in the shape Quick
Intel's API documents.

Run: python tests/test_second_oracle.py
"""

import hashlib
import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

_T0 = time.perf_counter()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BENCH = os.path.join(ROOT, "bench")

# Every attempt to reach the network or to wait for real, recorded here as well as refused:
# fetch() catches every Exception, so a refusal alone could be swallowed and read as an error
# answer. The list is checked once all the tests have run.
_TRIPPED = []


def _tripwire(what):
    def refuse(*args, **kwargs):
        _TRIPPED.append(what)
        raise AssertionError("%s was reached: this test must never touch the network or wait"
                             % what)
    return refuse


urllib.request.urlopen = _tripwire("urllib.request.urlopen")
socket.socket.connect = _tripwire("socket.socket.connect")
socket.create_connection = _tripwire("socket.create_connection")
time.sleep = _tripwire("time.sleep")


def _bench_listing():
    """bench/'s top level: a file's size and mtime, a directory's name."""
    listing = {}
    for entry in os.scandir(BENCH):
        if entry.is_dir(follow_symlinks=False):
            listing[entry.name] = "directory"
        else:
            st = entry.stat(follow_symlinks=False)
            listing[entry.name] = (st.st_size, st.st_mtime_ns)
    return listing


_BENCH_BEFORE = _bench_listing()

sys.dont_write_bytecode = True       # not even a bytecode cache may be written under bench/
sys.path.insert(0, BENCH)
import second_oracle as so  # noqa: E402

REAL_TIME = so.time
REAL_OUT = getattr(so, "OUT", None)
REAL_OUT_ADVERSARIAL = getattr(so, "OUT_ADVERSARIAL", None)
OUT_NAME = os.path.basename(REAL_OUT or "second_oracle.json")
OUT_ADVERSARIAL_NAME = os.path.basename(REAL_OUT_ADVERSARIAL
                                        or "second_oracle_adversarial.json")

KEY_VAR = "QUICKINTEL_API_KEY"
FAKE_KEY = "t005-synthetic-key"
DAY_MS = 86400000
WALL0 = 1790640000.0            # 2026-09-29 00:00:00 UTC: the fake clock's wall time at start
WALL0_MS = 1790640000000
MONO0 = 1000.0                  # the fake clock's monotonic time at start
ASKED_MS = 1789862400000        # 2026-09-20 00:00:00 UTC: when the hand-written rows were asked

NM, NSS, SS = "not measured", "no sell simulation", "sell simulated"
TODAYS_FIELDS = ("address", "symbol", "chain", "set", "our_verdict", "our_driver", "goplus",
                 "outcome", "quickintel", "error")
SENTINEL = b'{"n": 1, "results": ["the only copy of an earlier run\'s answers"]}\n'
ZERO_DAYS = re.compile(r"(?<![\d.])0(?:\.0+)? days?\b")

_PASSED = 0
_FAILURES = []


def check(name, ok, detail=""):
    global _PASSED
    if ok:
        _PASSED += 1
        print("  PASS  %s" % name)
    else:
        _FAILURES.append((name, detail))
        print("  FAIL  %s  %s" % (name, detail))


# --- synthetic data -------------------------------------------------------------------------

def address(symbol):
    """A synthetic 40-hex-digit address, fixed per symbol. Not a real token."""
    return "0x" + hashlib.sha1(symbol.encode("utf-8")).hexdigest()


def bench_row(symbol, chain, verdict, goplus, driver=None):
    """One row in the shape of bench/results.json."""
    return {"address": address(symbol), "symbol": symbol, "chain": chain, "verdict": verdict,
            "goplus_label": goplus, "driver": driver, "outcome_label": None, "score": 0,
            "confidence": "low"}


def dynamic(sim_ms, honeypot, buy, sell):
    """An answer in the shape Quick Intel's API documents; every value is invented."""
    details = {"buy_Tax": buy, "sell_Tax": sell, "transfer_Tax": sell}
    if honeypot is not None:
        details["is_Honeypot"] = honeypot
    if sim_ms is not None:
        details["lastUpdatedTimestamp"] = sim_ms
    return {"tokenDetails": {"tokenName": "Synthetic"}, "tokenDynamicDetails": details,
            "quickiAudit": {"contract_Verified": True}}


def simulated(sim_ms, honeypot, buy="0", sell="0"):
    return dynamic(sim_ms, honeypot, buy, sell)


def static_audit(honeypot, sim_ms=None):
    """A static audit only: no buy or sell was simulated, so both taxes are null."""
    return dynamic(sim_ms, honeypot, None, None)


def saved_row(symbol, set_name, chain="base", verdict="high", answer=None, error=None,
              asked_ms=ASKED_MS, driver=None):
    """One row in the shape --run saves; asked_ms=None gives today's shape, with no ask time."""
    row = {"address": address(symbol), "symbol": symbol, "chain": chain, "set": set_name,
           "our_verdict": verdict, "our_driver": driver, "goplus": None, "outcome": None,
           "quickintel": answer, "error": error}
    if asked_ms is not None:
        row["asked_ms"] = asked_ms
    return row


# A results file in file order, interleaved on purpose. ADVC is in two sets (GoPlus `unsafe`,
# engine `unknown`), as one real row is. ADVD is on a chain with no entry in CHAIN.
RUN_ROWS = [
    bench_row("ADVA", "base", "high", "unsafe", "honeypot"),
    bench_row("UNKA", "base", "unknown", "safe"),
    bench_row("OTHA", "base", "low", "safe"),
    bench_row("DISA", "base", "high", "safe", "honeypot"),
    bench_row("ADVB", "bsc", "medium", "unsafe", "liquidity"),
    bench_row("OTHB", "ethereum", "medium", "centralized"),
    bench_row("ADVC", "ethereum", "unknown", "unsafe"),
    bench_row("DISB", "bsc", "high", "safe", "honeypot"),
    bench_row("UNKB", "bsc", "unknown", None),
    bench_row("ADVD", "unlisted-chain", "high", "unsafe", "impersonation"),
    bench_row("OTHC", "bsc", "high", "centralized", "liquidity"),
    bench_row("DISC", "ethereum", "high", "safe", "impersonation"),
    bench_row("ADVE", "base", "high", "unsafe", "liquidity"),
    bench_row("UNKC", "base", "unknown", "centralized"),
    bench_row("OTHD", "base", "low", None),
    bench_row("ADVF", "bsc", "high", "unsafe", "honeypot"),
]
ADVERSARIAL = ["ADVA", "ADVB", "ADVC", "ADVD", "ADVE", "ADVF"]
ADVERSARIAL_ASKED = ["ADVA", "ADVB", "ADVC", "ADVE", "ADVF"]
DEFAULT_ASKED = ["DISA", "DISB", "DISC", "UNKA", "ADVC", "UNKB", "UNKC"]
MORE_UNSAFE = [bench_row("ADVG", "base", "high", "unsafe"),
               bench_row("ADVH", "bsc", "low", "unsafe"),
               bench_row("ADVI", "ethereum", "medium", "unsafe")]
SYMBOL_OF = {address(r["symbol"]): r["symbol"] for r in RUN_ROWS + MORE_UNSAFE}

RUN_ANSWERS = {
    "ADVA": (simulated(WALL0_MS - 3 * DAY_MS, True, "2.5", "97.5"), None),
    "ADVB": (static_audit(True), None),
    "ADVC": (None, "http 429"),
    "ADVE": (simulated(None, False), None),
    "ADVF": ({"tokenDetails": {"tokenName": "Synthetic"}}, None),
    "DISA": (simulated(WALL0_MS - 60 * DAY_MS, False, "0", "1.5"), None),
    "DISB": (None, "http 429"),
    "DISC": (static_audit(False), None),
    "UNKA": (simulated(WALL0_MS - DAY_MS, False), None),
    "UNKB": (None, "URLError"),
    "UNKC": (static_audit(None), None),
}

# A saved file written by hand, with its ask times, for the report and its classes.
REPORT_ROWS = [
    saved_row("ALPHA", "adversarial", "base", "high",
              simulated(ASKED_MS - 302400000, True, "3.25", "99.5")),       # 3.5 days old
    saved_row("BRAVO", "adversarial", "bsc", "medium",
              simulated(ASKED_MS, False, "0", "0.5")),                      # simulated when asked
    saved_row("CHARLIE", "adversarial", "ethereum", "high",
              static_audit(True, ASKED_MS - DAY_MS)),
    saved_row("DELTA", "adversarial", "base", "medium", static_audit(False)),
    saved_row("ECHO", "adversarial", "base", "unknown", error="http 429"),
    saved_row("FOXTROT", "adversarial", "unlisted-chain", "high",
              error="chain 'unlisted-chain' has no entry in CHAIN: not asked", asked_ms=None),
    saved_row("GOLF", "adversarial", "base", "high", simulated(None, None, "1.5", "2.5")),
    saved_row("HOTEL", "adversarial", "bsc", "high",
              simulated(ASKED_MS - 10 * DAY_MS, False, "4.75", "6.25"), asked_ms=None),
    saved_row("INDIA", "disputed", "base", "high",
              simulated(ASKED_MS - 40 * DAY_MS, False, "0", "7.5"), driver="honeypot"),
    saved_row("JULIET", "disputed", "bsc", "high", error="http 403", driver="honeypot"),
    saved_row("KILO", "disputed", "ethereum", "high", driver="impersonation"),
    saved_row("LIMA", "unknown", "base", "unknown", static_audit(False)),
    saved_row("MIKE", "unknown", "bsc", "unknown", simulated(ASKED_MS - 2 * DAY_MS, False)),
    saved_row("NOVEMBER", "unknown", "base", "unknown", error="http 500"),
]
REPORT_SELECTED = {"adversarial": 10, "disputed": 3, "unknown": 3}


# --- the harness ----------------------------------------------------------------------------

class FakeClock(object):
    """Stands in for the `time` module inside second_oracle. Nothing here ever waits.

    Start values and every step are multiples of 0.25 s, so the arithmetic is exact and a gap
    of exactly 2.0 s reads as 2.0, not as 1.9999999999999998."""

    def __init__(self):
        self.wall = WALL0
        self.mono = MONO0
        self.slept = []

    def time(self):
        return self.wall

    def time_ns(self):
        return int(self.wall * 1000) * 1000000

    def monotonic(self):
        return self.mono

    def monotonic_ns(self):
        return int(self.mono * 1000) * 1000000

    perf_counter = monotonic
    perf_counter_ns = monotonic_ns

    def sleep(self, seconds):
        if seconds < 0:
            raise ValueError("sleep length must be non-negative")
        self.slept.append(seconds)
        self.advance(seconds)

    def advance(self, seconds):
        self.wall += seconds
        self.mono += seconds

    def __getattr__(self, name):
        return getattr(time, name)


def load(path):
    """The saved document at `path`, or None when there is none or it does not parse."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def symbols(doc):
    return [r.get("symbol") for r in ((doc or {}).get("results") or [])]


def rows_in(path):
    """How many rows the file at `path` holds right now; None when it does not exist."""
    if not os.path.exists(path):
        return None
    doc = load(path)
    if not isinstance(doc, dict) or not isinstance(doc.get("results"), list):
        return "unreadable"
    return len(doc["results"])


class FakeFetch(object):
    """Stands in for second_oracle.fetch: answers from a table and records every call, with the
    clock at its start and end and how many rows each output file held when it started."""

    def __init__(self, clock, answers, durations, interrupt_at, watch):
        self.clock = clock
        self.answers = answers
        self.durations = durations
        self.interrupt_at = interrupt_at
        self.watch = watch
        self.calls = []

    def __call__(self, token_address, chain, key):
        n = len(self.calls) + 1
        call = {"address": token_address, "chain": chain, "key": key, "mono": self.clock.mono,
                "wall_start": self.clock.wall,
                "on_disk": dict((k, rows_in(p)) for k, p in self.watch.items())}
        self.calls.append(call)
        if self.interrupt_at == n:
            raise KeyboardInterrupt()
        self.clock.advance(self.durations[(n - 1) % len(self.durations)])
        call["wall_end"] = self.clock.wall
        return self.answers.get(token_address, (None, "no answer scripted"))

    def asked(self):
        return [SYMBOL_OF.get(c["address"], c["address"]) for c in self.calls]


_MISSING = object()


class Sandbox(object):
    """A temporary directory with a synthetic results file and both output files, and the
    module's paths, clock, fetch function and key pointed at it. Nothing touches bench/."""

    def __init__(self, rows=None, key=True, answers=None, durations=(0.25,),
                 interrupt_at=None):
        self.rows = RUN_ROWS if rows is None else rows
        self.key = key
        self.answers = dict((address(s), a) for s, a in
                            (RUN_ANSWERS if answers is None else answers).items())
        self.durations = durations
        self.interrupt_at = interrupt_at

    def __enter__(self):
        self.tmp = tempfile.mkdtemp(prefix="t005-second-oracle-")
        os.makedirs(os.path.join(self.tmp, "in"))
        self.outdir = os.path.join(self.tmp, "out")
        os.makedirs(self.outdir)
        self.results = os.path.join(self.tmp, "in", "results.json")
        with open(self.results, "w", encoding="utf-8") as f:
            json.dump({"n_evaluated": len(self.rows), "rows": self.rows}, f, indent=2)
        self.out = os.path.join(self.outdir, OUT_NAME)
        self.out_adv = os.path.join(self.outdir, OUT_ADVERSARIAL_NAME)
        self.clock = FakeClock()
        self.fetch = FakeFetch(self.clock, self.answers, self.durations, self.interrupt_at,
                               {"out": self.out, "out_adv": self.out_adv})
        self.saved = dict((n, getattr(so, n, _MISSING)) for n in
                          ("RESULTS", "OUT", "OUT_ADVERSARIAL", "time", "fetch"))
        so.RESULTS, so.OUT, so.OUT_ADVERSARIAL = self.results, self.out, self.out_adv
        so.time, so.fetch = self.clock, self.fetch
        self.saved_key = os.environ.get(KEY_VAR)
        if self.key:
            os.environ[KEY_VAR] = FAKE_KEY
        else:
            os.environ.pop(KEY_VAR, None)
        return self

    def __exit__(self, *exc):
        for name, value in self.saved.items():
            if value is _MISSING:
                if hasattr(so, name):
                    delattr(so, name)
            else:
                setattr(so, name, value)
        if self.saved_key is None:
            os.environ.pop(KEY_VAR, None)
        else:
            os.environ[KEY_VAR] = self.saved_key
        shutil.rmtree(self.tmp, ignore_errors=True)
        return False

    def write(self, name, doc):
        path = os.path.join(self.tmp, "in", name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2)
        return path


def capture(fn, *args):
    """Call fn(*args) with stdout and stderr going to an ASCII-only stream, as strict as a
    console that cannot encode a character. Returns (what fn returned, what it printed)."""
    stream = io.TextIOWrapper(io.BytesIO(), encoding="ascii", errors="strict", newline="\n")
    saved = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = stream
    try:
        result = fn(*args)
    finally:
        sys.stdout, sys.stderr = saved
    stream.flush()
    return result, stream.buffer.getvalue().decode("ascii")


def cli(*args):
    """`python bench/second_oracle.py ARGS`, run in this process so the fakes above apply.

    Returns (exit status, everything printed). An interrupt that escapes main() comes back as
    the status "KeyboardInterrupt"."""
    def call():
        try:
            return so.main()
        except SystemExit as e:
            return e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        except KeyboardInterrupt:
            return "KeyboardInterrupt"
    saved_argv = sys.argv
    sys.argv = ["second_oracle.py"] + list(args)
    try:
        return capture(call)
    finally:
        sys.argv = saved_argv


def git_ignores(rel_path):
    r = subprocess.run(["git", "check-ignore", "-q", "--", rel_path], cwd=ROOT,
                       capture_output=True)
    return r.returncode == 0


def rel(path):
    return os.path.relpath(path, ROOT).replace(os.sep, "/")


def same_file(a, b):
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def write_bytes(path, data):
    with open(path, "wb") as f:
        f.write(data)


def lines_with(text, needle):
    return [ln for ln in text.splitlines() if needle in ln]


def number_on_a_line(text, word, number):
    """True when one line names `word` (any case) and carries `number` as a whole number."""
    pattern = re.compile(r"(?<![\w.])%d(?![\w.])" % number)
    return any(word in ln.lower() and pattern.search(ln) for ln in text.splitlines())


def report_counts(rows, selected=None):
    """report()'s per-set counts, with what it printed kept off the console."""
    return capture(so.report, rows, selected)[0]


# --- 1. selection ---------------------------------------------------------------------------

def test_plan_counts_the_adversarial_cohort_from_the_results_file():
    """No count is hard-coded: the same command on two results files prints two counts."""
    print("\n[selection] --plan --set adversarial counts the rows GoPlus labels unsafe")
    for rows, expected in ((RUN_ROWS, 6), (RUN_ROWS + MORE_UNSAFE, 9)):
        with Sandbox(rows, key=False) as sb:
            status, out = cli("--plan", "--set", "adversarial")
            out = out.replace(sb.tmp, "<tmp>")   # a digit in the temp path is not a count
            check("%d unsafe rows: it exits 0 with no key set" % expected, status == 0,
                  "status %r: %s" % (status, out[-300:]))
            check("%d unsafe rows: a line naming the adversarial set carries %d"
                  % (expected, expected), number_on_a_line(out, "adversarial", expected),
                  out[-600:])
            check("%d unsafe rows: no call was made" % expected, not sb.fetch.calls,
                  sb.fetch.asked())
            check("%d unsafe rows: no output file was written" % expected,
                  not os.listdir(sb.outdir), os.listdir(sb.outdir))


def test_run_adversarial_asks_exactly_that_cohort_each_once():
    print("\n[selection] --run --set adversarial asks about exactly the cohort, each row once")
    with Sandbox() as sb:
        status, out = cli("--run", "--set", "adversarial")
        check("it exits 0", status == 0, "status %r: %s" % (status, out[-300:]))
        asked = sb.fetch.asked()
        check("it asked about every row with a chain name, in file order, and no other row",
              asked == ADVERSARIAL_ASKED, "asked %r" % asked)
        check("each of them once", len(asked) == len(set(asked)), asked)
        check("with the key from the environment",
              all(c["key"] == FAKE_KEY for c in sb.fetch.calls), "")
        doc = load(sb.out_adv)
        check("its file holds all 6 rows of the cohort, in order", symbols(doc) == ADVERSARIAL,
              symbols(doc))
        check("each labelled with the set it was selected for",
              doc is not None and all(r.get("set") == "adversarial" for r in doc["results"]),
              "")


def test_without_set_plan_and_run_select_what_they_select_today():
    print("\n[selection] without --set: the disputed set, then the unknown set, as today")
    with Sandbox(key=False) as sb:
        status, out = cli("--plan")
        out = out.replace(sb.tmp, "<tmp>")   # a digit in the temp path is not a count
        check("--plan exits 0 with no key set", status == 0, "status %r" % status)
        check("it counts the disputed set (3)", number_on_a_line(out, "disputed", 3),
              out[-800:])
        check("and the 2 of them the engine flags on honeypot",
              number_on_a_line(out, "honeypot", 2), out[-800:])
        check("it counts the unknown set (4)", number_on_a_line(out, "unknown", 4),
              out[-800:])
        check("and the total (7)", number_on_a_line(out, "total", 7), out[-800:])
        stale = [s for s in ("576", "121", "6.0%") if s in out]
        check("no figure is left over from the real results file", not stale, stale)
        check("no call was made", not sb.fetch.calls, sb.fetch.asked())
    with Sandbox() as sb:
        status, out = cli("--run")
        check("--run exits 0", status == 0, "status %r: %s" % (status, out[-300:]))
        asked = sb.fetch.asked()
        check("it asked about the disputed rows, then the unknown rows, each in file order",
              asked == DEFAULT_ASKED, "asked %r" % asked)
        doc = load(sb.out)
        sets = [r.get("set") for r in (doc or {}).get("results") or []]
        check("its file labels them disputed, then unknown",
              sets == ["disputed"] * 3 + ["unknown"] * 4, sets)


# --- 2. pacing ------------------------------------------------------------------------------

def test_consecutive_calls_start_at_least_pace_seconds_apart():
    print("\n[pacing] consecutive calls start at least PACE_SECONDS apart")
    pace = getattr(so, "PACE_SECONDS", None)
    check("PACE_SECONDS is a module constant equal to 2.0",
          pace == 2.0 and not isinstance(pace, bool), repr(pace))
    runs = (("the adversarial cohort", ("--run", "--set", "adversarial"),
             (0.25, 3.0, 0.5, 1.75, 0.0), 5),
            ("the default selection", ("--run",), (0.0,), 7))
    for label, args, durations, n in runs:
        with Sandbox(durations=durations) as sb:
            status, out = cli(*args)
            starts = [c["mono"] for c in sb.fetch.calls]
            check("%s: all %d calls were made" % (label, n), len(starts) == n,
                  "%d calls, status %r" % (len(starts), status))
            short = [(i + 2, starts[i + 1] - starts[i]) for i in range(len(starts) - 1)
                     if not starts[i + 1] - starts[i] >= 2.0]
            check("%s: every gap between call starts is at least 2.0 s" % label,
                  len(starts) > 1 and not short, "short gaps (call, seconds): %r" % short)
            check("%s: the waiting went through the replaced clock" % label,
                  sum(sb.clock.slept) > 0, repr(sb.clock.slept))


def test_max_calls_stays_a_hard_ceiling():
    print("\n[pacing] --max-calls is still a hard ceiling, and the rows it cut are counted")
    with Sandbox() as sb:
        status, out = cli("--run", "--set", "adversarial", "--max-calls", "2")
        check("--max-calls 2 makes exactly 2 calls", len(sb.fetch.calls) == 2,
              sb.fetch.asked())
        doc = load(sb.out_adv)
        check("its file holds the 2 rows asked", symbols(doc) == ["ADVA", "ADVB"],
              symbols(doc))
        counts = report_counts(doc["results"], doc.get("selected")) if doc else None
        adv = (counts or {}).get("adversarial") or {}
        check("the report counts the 4 rows of the cohort it never asked",
              adv.get("not_asked") == 4, repr(adv))


# --- 3. the earlier answers -----------------------------------------------------------------

def test_each_selection_has_its_own_git_ignored_output_file():
    print("\n[safety] each selection has its own output file under bench/, and git ignores it")
    check("without --set the output file is bench/second_oracle.json, as today",
          bool(REAL_OUT) and same_file(REAL_OUT, os.path.join(BENCH, "second_oracle.json")),
          repr(REAL_OUT))
    check("--set adversarial has an output file of its own (OUT_ADVERSARIAL)",
          bool(REAL_OUT_ADVERSARIAL), repr(REAL_OUT_ADVERSARIAL))
    if REAL_OUT_ADVERSARIAL:
        check("it is under bench/",
              same_file(os.path.dirname(os.path.abspath(REAL_OUT_ADVERSARIAL)), BENCH),
              REAL_OUT_ADVERSARIAL)
        check("and it is not the default one",
              not same_file(REAL_OUT_ADVERSARIAL, REAL_OUT or ""), REAL_OUT_ADVERSARIAL)
    for path in (REAL_OUT, REAL_OUT_ADVERSARIAL):
        if path:
            check("git check-ignore: %s is ignored" % rel(path), git_ignores(rel(path)),
                  rel(path))


def test_run_refuses_to_start_when_its_output_file_exists():
    print("\n[safety] --run refuses to start when its output file exists, and makes no call")
    for label, args, which in (("--set adversarial", ("--run", "--set", "adversarial"),
                                "out_adv"),
                               ("without --set", ("--run",), "out")):
        with Sandbox() as sb:
            path = getattr(sb, which)
            write_bytes(path, SENTINEL)
            status, out = cli(*args)
            check("%s: exit status 2" % label, status == 2, "status %r" % status)
            check("%s: the message names the file" % label, os.path.basename(path) in out,
                  out[-400:])
            check("%s: no call was made" % label, not sb.fetch.calls, sb.fetch.asked())
            check("%s: the earlier file is byte for byte as it was" % label,
                  read_bytes(path) == SENTINEL, "")


def test_no_call_is_made_before_the_key_check_passes():
    print("\n[safety] no key: exit 2, no call, nothing written")
    for label, args, which in (("--set adversarial", ("--run", "--set", "adversarial"),
                                "out_adv"),
                               ("without --set", ("--run",), "out")):
        with Sandbox(key=False) as sb:
            status, out = cli(*args)
            check("%s: exit status 2" % label, status == 2, "status %r" % status)
            check("%s: the message names %s" % (label, KEY_VAR), KEY_VAR in out, out[-300:])
            check("%s: no call was made" % label, not sb.fetch.calls, sb.fetch.asked())
            check("%s: no output file was written" % label, not os.listdir(sb.outdir),
                  os.listdir(sb.outdir))
        with Sandbox(key=False) as sb:
            path = getattr(sb, which)
            write_bytes(path, SENTINEL)
            status, out = cli(*args)
            check("%s: no key and an existing file: exit 2, no call, the file untouched"
                  % label, status == 2 and not sb.fetch.calls
                  and read_bytes(path) == SENTINEL, "status %r" % status)


def test_one_selections_file_does_not_block_the_other():
    print("\n[safety] one selection's earlier file neither blocks nor is touched by the other")
    with Sandbox() as sb:
        write_bytes(sb.out, SENTINEL)
        status, out = cli("--run", "--set", "adversarial")
        check("with bench/second_oracle.json present, --set adversarial runs (exit 0)",
              status == 0, "status %r: %s" % (status, out[-300:]))
        check("and asks its 5 rows", sb.fetch.asked() == ADVERSARIAL_ASKED, sb.fetch.asked())
        check("and leaves the default file byte for byte as it was",
              read_bytes(sb.out) == SENTINEL, "")
        check("and writes its own file", rows_in(sb.out_adv) == 6, rows_in(sb.out_adv))
    with Sandbox() as sb:
        write_bytes(sb.out_adv, SENTINEL)
        status, out = cli("--run")
        check("with the adversarial file present, the default selection runs (exit 0)",
              status == 0, "status %r: %s" % (status, out[-300:]))
        check("and leaves the adversarial file byte for byte as it was",
              read_bytes(sb.out_adv) == SENTINEL, "")
        check("and writes its own file", rows_in(sb.out) == 7, rows_in(sb.out))


# --- 4. every call is kept, every row accounted for -----------------------------------------

def test_the_file_is_rewritten_after_every_call():
    print("\n[persistence] before every call, the file already holds every row before it")
    # Rows before each call. In the cohort the fourth row (ADVD) makes no call.
    for label, args, which, expected in (
            ("--set adversarial", ("--run", "--set", "adversarial"), "out_adv",
             [0, 1, 2, 4, 5]),
            ("without --set", ("--run",), "out", [0, 1, 2, 3, 4, 5, 6])):
        with Sandbox() as sb:
            cli(*args)
            seen = [c["on_disk"][which] for c in sb.fetch.calls]
            if seen and seen[0] is None:
                seen[0] = 0          # before the first call the file need not exist yet
            check("%s: rows on disk as each call starts: %r" % (label, expected),
                  seen == expected, "saw %r" % seen)


def test_an_interrupted_run_keeps_the_rows_before_it():
    print("\n[persistence] Ctrl+C during the Nth call leaves the rows before it in the file")
    for n, before in ((1, []), (3, ["ADVA", "ADVB"]),
                      (5, ["ADVA", "ADVB", "ADVC", "ADVD", "ADVE"])):
        with Sandbox(interrupt_at=n) as sb:
            status, out = cli("--run", "--set", "adversarial")
            doc = load(sb.out_adv)
            kept = (doc is None and not before and not os.path.exists(sb.out_adv)) \
                or (doc is not None and symbols(doc) == before)
            check("interrupted at call %d: the file holds the %d rows before it"
                  % (n, len(before)), kept, "file holds %r" % (symbols(doc) if doc else None))
            check("interrupted at call %d: no call after it" % n, len(sb.fetch.calls) == n,
                  sb.fetch.asked())
            check("interrupted at call %d: the run does not exit 0" % n, status != 0,
                  repr(status))


class InterruptedSave(dict):
    """An answer whose saving is interrupted halfway: json.dump asks a dict for its items()
    while it writes, and this one raises KeyboardInterrupt there, as Ctrl+C would."""

    def items(self):
        raise KeyboardInterrupt()


def test_an_interrupted_save_leaves_the_earlier_rows_readable():
    print("\n[persistence] Ctrl+C in the middle of a save loses no row saved before it")
    for label, args, which, victim, before in (
            ("--set adversarial", ("--run", "--set", "adversarial"), "out_adv", "ADVC",
             ["ADVA", "ADVB"]),
            ("without --set", ("--run",), "out", "DISC", ["DISA", "DISB"])):
        answers = dict(RUN_ANSWERS)
        answers[victim] = (InterruptedSave(simulated(WALL0_MS, False)), None)
        with Sandbox(answers=answers) as sb:
            status, out = cli(*args)
            path = getattr(sb, which)
            doc = load(path)
            check("%s: the file still parses and holds the %d rows saved before it"
                  % (label, len(before)), symbols(doc) == before,
                  "file holds %r" % (symbols(doc) if doc else None))
            left = sorted(n for n in os.listdir(sb.outdir) if n != os.path.basename(path))
            for name in left:
                check("%s: git would ignore the half-written %s under bench/"
                      % (label, name), git_ignores("bench/" + name), name)


def test_each_row_records_when_it_was_asked():
    print("\n[persistence] each row keeps today's fields and records when it was asked")
    with Sandbox(durations=(0.25, 3.0)) as sb:
        cli("--run", "--set", "adversarial")
        doc = load(sb.out_adv) or {"results": []}
        calls = dict((c["address"], c) for c in sb.fetch.calls)
        check("the file holds the cohort's 6 rows", len(doc["results"]) == 6,
              len(doc["results"]))
        for row in doc["results"]:
            sym = row.get("symbol")
            missing = [k for k in TODAYS_FIELDS if k not in row]
            check("%s: keeps today's fields" % sym, not missing, missing)
            call = calls.get(row.get("address"))
            if call is None:
                continue
            asked = row.get("asked_ms")
            check("%s: asked_ms is epoch milliseconds (UTC) inside its call" % sym,
                  isinstance(asked, int) and not isinstance(asked, bool)
                  and call["wall_start"] * 1000 <= asked <= call["wall_end"] * 1000,
                  "asked_ms %r, call from %r to %r ms" % (
                      asked, call["wall_start"] * 1000, call["wall_end"] * 1000))


def test_a_row_on_a_chain_with_no_quick_intel_name_is_recorded_not_skipped():
    print("\n[persistence] a row whose chain has no entry in CHAIN is kept, as not measured")
    check("the test's premise: CHAIN has no entry for 'unlisted-chain'",
          "unlisted-chain" not in so.CHAIN, sorted(so.CHAIN))
    with Sandbox() as sb:
        cli("--run", "--set", "adversarial")
        check("no call was made for it", "ADVD" not in sb.fetch.asked(), sb.fetch.asked())
        doc = load(sb.out_adv) or {"results": []}
        rows = [r for r in doc["results"] if r.get("symbol") == "ADVD"]
        check("it is in the file", len(rows) == 1, symbols(doc))
        err = rows[0].get("error") if rows else None
        check("with an error naming its chain and CHAIN",
              isinstance(err, str) and "unlisted-chain" in err and "CHAIN" in err, repr(err))
        if rows:
            check("classified as not measured", so.classify(rows[0])[0] == NM,
                  repr(so.classify(rows[0])))
        counts = report_counts(doc["results"], doc.get("selected")) if doc["results"] else {}
        adv = (counts or {}).get("adversarial") or {}
        check("the report counts it among the 3 not measured (with ADVC and ADVF)",
              adv.get("not_measured") == 3, repr(adv))


# --- 5. classification ----------------------------------------------------------------------

CLASSIFY_CASES = [
    ("an errored call", saved_row("C01", "adversarial", error="http 429"), NM),
    ("a call that raised", saved_row("C02", "adversarial", error="URLError"), NM),
    ("no answer and no error", saved_row("C03", "adversarial"), NM),
    ("an answer that is a string", saved_row("C04", "adversarial", answer="oops"), NM),
    ("an answer that is a list", saved_row("C05", "adversarial", answer=[1, 2]), NM),
    ("an answer without tokenDynamicDetails",
     saved_row("C06", "adversarial", answer={"tokenDetails": {}}), NM),
    ("tokenDynamicDetails null",
     saved_row("C07", "adversarial", answer={"tokenDynamicDetails": None}), NM),
    ("tokenDynamicDetails a string",
     saved_row("C08", "adversarial", answer={"tokenDynamicDetails": "x"}), NM),
    ("an error beside a complete simulation",
     saved_row("C09", "adversarial", answer=simulated(ASKED_MS, False), error="http 500"), NM),
    ("a row that is not an object", "not a row", NM),
    ("a static audit (both taxes null)",
     saved_row("C11", "adversarial", answer=static_audit(True, ASKED_MS)), NSS),
    ("sell_Tax null with buy_Tax set",
     saved_row("C12", "adversarial", answer=dynamic(ASKED_MS, False, "5", None)), NSS),
    ("no sell_Tax key at all",
     saved_row("C13", "adversarial", answer={"tokenDynamicDetails": {"is_Honeypot": True}}),
     NSS),
    ("a simulated honeypot",
     saved_row("C14", "adversarial", answer=simulated(ASKED_MS - DAY_MS, True, "0", "100")),
     SS),
    ("a simulated sellable token",
     saved_row("C15", "adversarial", answer=simulated(ASKED_MS - DAY_MS, False)), SS),
    ("sell_Tax set with buy_Tax null",
     saved_row("C16", "adversarial", answer=dynamic(ASKED_MS, False, None, "5")), SS),
    ("a simulation with no date",
     saved_row("C17", "adversarial", answer=simulated(None, False)), SS),
]


def test_each_row_is_in_exactly_one_class():
    print("\n[classes] not measured, no sell simulation, sell simulated: one each")
    for what, row, expected in CLASSIFY_CASES:
        got = so.classify(row)[0]
        check("%s: %s" % (what, expected), got == expected, "got %r" % (got,))
    rows = [row for _, row, _ in CLASSIFY_CASES]
    counts = report_counts(rows) or {}
    total = sum((counts.get(s) or {}).get(k, 0) for s in counts
                for k in ("not_measured", "no_sell_simulation", "sell_simulated"))
    check("report() counts each of the %d rows in exactly one class" % len(rows),
          total == len(rows) and sum(c.get("rows", 0) for c in counts.values()) == len(rows),
          repr(counts))


def test_the_simulation_date_and_its_age():
    print("\n[classes] a simulation is dated by lastUpdatedTimestamp and aged from the ask")
    cases = (
        ("3.5 days before the ask", saved_row("D1", "adversarial", answer=simulated(
            ASKED_MS - 302400000, True)), ASKED_MS - 302400000, 3.5),
        ("at the ask", saved_row("D2", "adversarial", answer=simulated(ASKED_MS, False)),
         ASKED_MS, 0.0),
        ("a quarter day after the ask", saved_row("D3", "adversarial", answer=simulated(
            ASKED_MS + 21600000, False)), ASKED_MS + 21600000, -0.25),
        ("with no lastUpdatedTimestamp", saved_row("D4", "adversarial", answer=simulated(
            None, False)), None, None),
        ("asked at a time not recorded (today's shape)", saved_row(
            "D5", "adversarial", answer=simulated(ASKED_MS - 10 * DAY_MS, False),
            asked_ms=None), ASKED_MS - 10 * DAY_MS, None),
    )
    for what, row, sim_ms, age in cases:
        cls, detail = so.classify(row)
        detail = detail or {}
        check("%s: sell simulated" % what, cls == SS, repr(cls))
        check("%s: dated %r" % (what, sim_ms), detail.get("sim_ms") == sim_ms,
              repr(detail.get("sim_ms")))
        got = detail.get("age_days")
        ok = (got is None) if age is None else (
            isinstance(got, (int, float)) and abs(got - age) < 1e-9)
        check("%s: age %s" % (what, "unknown" if age is None else "%r days" % age), ok,
              repr(got))


def test_is_honeypot_is_read_only_for_sell_simulated_rows():
    print("\n[classes] is_Honeypot counts only where a sell was simulated")
    rows = [saved_row("HPA", "adversarial", answer=static_audit(True)),
            saved_row("HPB", "adversarial", answer=static_audit(False)),
            saved_row("HPC", "adversarial", answer=simulated(ASKED_MS, True, "0", "100")),
            saved_row("HPD", "adversarial", answer=simulated(ASKED_MS, False)),
            saved_row("HPE", "adversarial", answer=simulated(ASKED_MS, None))]
    counts, out = capture(so.report, rows, None)
    adv = (counts or {}).get("adversarial") or {}
    check("one honeypot: the simulated one, not the static audit saying true",
          adv.get("honeypot") == 1, repr(adv))
    check("one sellable: the simulated one, not the static audit saying false",
          adv.get("sellable") == 1, repr(adv))
    check("one simulation that does not state it", adv.get("honeypot_not_stated") == 1,
          repr(adv))
    check("two answers without a sell simulation", adv.get("no_sell_simulation") == 2,
          repr(adv))
    for sym in ("HPA", "HPB"):
        detail = so.classify(rows[0 if sym == "HPA" else 1])[1] or {}
        check("%s: classify() does not carry its is_Honeypot" % sym,
              detail.get("is_honeypot") is None, repr(detail))
        line = lines_with(out, sym)
        check("%s: its report line does not print is_Honeypot" % sym,
              len(line) == 1 and "is_Honeypot" not in line[0], line)


# --- 6. the report --------------------------------------------------------------------------

def test_the_report_counts_every_set_and_prints_a_line_per_token():
    print("\n[report] per-set counts, reasons apart, one line per adversarial or disputed token")
    with Sandbox(key=False) as sb:
        path = sb.write("saved.json", {"n": len(REPORT_ROWS), "selected": REPORT_SELECTED,
                                       "results": REPORT_ROWS})
        status, out = cli("--report", path)
        check("--report exits 0 with no key set", status == 0,
              "status %r: %s" % (status, out[-300:]))
        check("and makes no call", not sb.fetch.calls, sb.fetch.asked())
    counts = report_counts(REPORT_ROWS, REPORT_SELECTED) or {}
    expected = {
        "adversarial": dict(rows=8, not_measured=2, no_sell_simulation=2, sell_simulated=4,
                            honeypot=1, sellable=2, honeypot_not_stated=1, not_asked=2),
        "disputed": dict(rows=3, not_measured=2, no_sell_simulation=0, sell_simulated=1,
                         honeypot=0, sellable=1, honeypot_not_stated=0, not_asked=0),
        "unknown": dict(rows=3, not_measured=1, no_sell_simulation=1, sell_simulated=1,
                        honeypot=0, sellable=1, honeypot_not_stated=0, not_asked=0),
    }
    for name, want in expected.items():
        got = counts.get(name) or {}
        wrong = dict((k, (got.get(k), v)) for k, v in want.items() if got.get(k) != v)
        check("%s: %s" % (name, ", ".join("%s %d" % kv for kv in sorted(want.items()))),
              not wrong, "(got, wanted): %r" % wrong)
        reasons = got.get("reasons") or {}
        check("%s: the not-measured rows are counted apart, with their reasons" % name,
              sum(reasons.values()) == want["not_measured"], repr(reasons))
    for reason in ("http 429", "http 403", "http 500", "unlisted-chain"):
        check("the report prints the reason %r" % reason, reason in out, "")
    expect_lines = {
        "ALPHA": ["base", "high", SS, "2026-09-16", "3.5", "is_Honeypot", "True", "3.25",
                  "99.5"],
        "BRAVO": ["bsc", "medium", SS, "2026-09-20", "False", "0.5"],
        "CHARLIE": ["ethereum", "high", NSS],
        "DELTA": ["base", "medium", NSS],
        "ECHO": ["base", "unknown", NM, "http 429"],
        "FOXTROT": ["unlisted-chain", "high", NM],
        "GOLF": ["base", "high", SS, "unknown", "1.5", "2.5"],
        "HOTEL": ["bsc", "high", SS, "2026-09-10", "unknown", "False", "4.75", "6.25"],
        "INDIA": ["base", "high", SS, "2026-08-11", "40", "False", "7.5"],
        "JULIET": ["bsc", "high", NM, "http 403"],
        "KILO": ["ethereum", "high", NM],
    }
    for sym, parts in sorted(expect_lines.items()):
        found = lines_with(out, sym)
        check("%s: one line in the report" % sym, len(found) == 1, found)
        if len(found) != 1:
            continue
        line = found[0]
        missing = [p for p in parts if p not in line]
        check("%s: it carries %s" % (sym, ", ".join(parts)), not missing,
              "missing %r in %r" % (missing, line))
    for sym in ("CHARLIE", "DELTA"):
        found = lines_with(out, sym)
        check("%s: no is_Honeypot on a line without a sell simulation" % sym,
              len(found) == 1 and "is_Honeypot" not in found[0], found)
    for sym in ("GOLF", "HOTEL"):
        found = lines_with(out, sym)
        check("%s: a missing time reads unknown, never 0 days" % sym,
              len(found) == 1 and not ZERO_DAYS.search(found[0]), found)
    found = lines_with(out, "BRAVO")
    check("BRAVO: both times known, so nothing on its line is unknown",
          len(found) == 1 and "unknown" not in found[0], found)


def test_no_rate_is_printed_over_zero_measured_rows():
    """The 2026-09-29 report printed "0 of 122 (0%)" over calls that never reached Quick Intel."""
    print("\n[report] no rate or percentage over zero measured rows")
    rows = ([saved_row("ZU%d" % i, "unknown", verdict="unknown", error="http 403",
                       asked_ms=None) for i in range(4)]
            + [saved_row("ZD%d" % i, "disputed", error="http 403", asked_ms=None)
               for i in range(2)])
    with Sandbox(key=False) as sb:
        path = sb.write("blocked.json", {"n": len(rows), "results": rows})
        status, out = cli("--report", path)
        check("--report exits 0 on a file where every call failed", status == 0,
              "status %r: %s" % (status, out[-300:]))
        check("no percentage is printed anywhere", "%" not in out,
              [ln for ln in out.splitlines() if "%" in ln])
    counts = report_counts(rows) or {}
    for name, n in (("unknown", 4), ("disputed", 2)):
        got = counts.get(name) or {}
        check("%s: %d rows, all %d not measured, none answered" % (name, n, n),
              got.get("rows") == n and got.get("not_measured") == n
              and got.get("no_sell_simulation") == 0 and got.get("sell_simulated") == 0,
              repr(got))


def test_each_share_is_taken_over_the_rows_that_could_answer_it():
    """Named change (a), T-005 round 2. A share printed over rows that could not answer its
    question reads as a measured absence, which is the "0 of 122" this task replaces. The
    sell-simulated share is over the answered rows; the honeypot share is over the simulations
    that state is_Honeypot, and there is none when no simulation states it. report() returns
    each printed share as (numerator, denominator). Every value here is invented."""
    print("\n[report] each share is over the rows that could answer it, and returned as data")

    def printed(text, k, n, word):
        """True when one line carries `k of n` as whole numbers and names `word`."""
        share = re.compile(r"(?<!\d)%d of %d(?!\d)" % (k, n))
        return any(share.search(ln) and word in ln.lower() for ln in text.splitlines())

    mixed = [
        saved_row("MXNA", "adversarial", error="http 429"),
        saved_row("MXNB", "adversarial", error="http 403"),
        saved_row("MXNC", "adversarial", error="URLError"),
        saved_row("MXND", "adversarial"),
        saved_row("MXNE", "adversarial", answer={"tokenDetails": {"tokenName": "Synthetic"}}),
        saved_row("MXNF", "adversarial", chain="unlisted-chain",
                  error="chain 'unlisted-chain' has no entry in CHAIN: not asked",
                  asked_ms=None),
        saved_row("MXSA", "adversarial", answer=static_audit(True)),
        saved_row("MXSB", "adversarial", answer=static_audit(False)),
        saved_row("MXHT", "adversarial", answer=simulated(ASKED_MS - DAY_MS, True, "0", "95")),
        saved_row("MXHF", "adversarial", answer=simulated(ASKED_MS - DAY_MS, False)),
        saved_row("MXHU", "adversarial", answer=simulated(ASKED_MS - DAY_MS, None, "1", "2")),
    ]
    counts, out = capture(so.report, mixed, None)
    adv = (counts or {}).get("adversarial") or {}
    shares = adv.get("shares") or {}
    check("the mixed set: 11 rows, 6 not measured, 2 without a sell simulation, 3 simulated",
          (adv.get("rows"), adv.get("not_measured"), adv.get("no_sell_simulation"),
           adv.get("sell_simulated")) == (11, 6, 2, 3), repr(adv))
    check("returned: the sell-simulated share is 3 of the 5 answered",
          tuple(shares.get("sell_simulated") or ()) == (3, 5), repr(adv.get("shares")))
    check("returned: the honeypot share is 1 of the 2 simulations that state is_Honeypot",
          tuple(shares.get("honeypot") or ()) == (1, 2), repr(adv.get("shares")))
    check("printed: 3 of 5 sell simulated", printed(out, 3, 5, SS), out[-700:])
    check("printed: 1 of 2 honeypots", printed(out, 1, 2, "honeypot"), out[-700:])

    unstated = [
        saved_row("USTA", "disputed", answer=simulated(ASKED_MS - DAY_MS, None)),
        saved_row("USTB", "disputed", answer=simulated(ASKED_MS - 2 * DAY_MS, None, "1", "2")),
        saved_row("USTC", "disputed", answer=static_audit(True)),
        saved_row("USTD", "disputed", error="http 429"),
    ]
    counts, out = capture(so.report, unstated, None)
    dis = (counts or {}).get("disputed") or {}
    shares = dis.get("shares")
    check("simulations that all leave is_Honeypot unstated: the shares are returned as data",
          isinstance(shares, dict), repr(dis))
    shares = shares if isinstance(shares, dict) else {}
    check("... the sell-simulated share is 2 of the 3 answered",
          tuple(shares.get("sell_simulated") or ()) == (2, 3), repr(shares))
    check("... no honeypot share is returned", shares.get("honeypot") is None, repr(shares))
    over = [ln for ln in out.splitlines()
            if "honeypot" in ln.lower() and re.search(r"(?<!\d)\d+ of \d+(?!\d)", ln)]
    check("... and none is printed", not over, over)


def test_a_symbol_the_console_cannot_encode_does_not_crash_the_report():
    print("\n[report] a symbol outside the console's encoding is escaped, not fatal")
    sym = "X" + chr(0x4E2D) + chr(0x1F680)
    rows = [saved_row(sym, "adversarial", answer=simulated(ASKED_MS - DAY_MS, False, "8.125")),
            saved_row("PLAIN", "disputed", answer=simulated(ASKED_MS, False))]
    with Sandbox(key=False) as sb:
        path = sb.write("symbols.json", {"n": len(rows), "results": rows})
        status, out = cli("--report", path)    # cli() prints into an ASCII-only stream
        check("--report exits 0 printing to an ASCII-only stream", status == 0,
              "status %r: %s" % (status, out[-300:]))
        check("the token's line is there", len(lines_with(out, "8.125")) == 1,
              lines_with(out, "8.125"))


# --- 7. --report PATH -----------------------------------------------------------------------

def test_report_reads_a_saved_file_in_todays_shape():
    print("\n[report] --report reads a file in today's shape: no ask times, no selection")
    rows = [saved_row("TDA", "disputed", answer=simulated(ASKED_MS - DAY_MS, False),
                      asked_ms=None, driver="honeypot"),
            saved_row("TDB", "disputed", error="http 429", asked_ms=None),
            saved_row("TUA", "unknown", verdict="unknown", answer=static_audit(True),
                      asked_ms=None),
            saved_row("TUB", "unknown", verdict="unknown",
                      answer=simulated(ASKED_MS, True, "0", "100"), asked_ms=None)]
    with Sandbox(key=False) as sb:
        path = sb.write("today.json", {"n": len(rows), "results": rows})
        status, out = cli("--report", path)
        check("it exits 0 with no key set", status == 0,
              "status %r: %s" % (status, out[-300:]))
        check("and makes no call", not sb.fetch.calls, sb.fetch.asked())
        found = lines_with(out, "TDA")
        check("a simulation with no ask time: its age reads unknown, never 0 days",
              len(found) == 1 and "unknown" in found[0] and not ZERO_DAYS.search(found[0]),
              found)
    counts = report_counts(rows) or {}
    d, u = counts.get("disputed") or {}, counts.get("unknown") or {}
    check("disputed: 2 rows, 1 not measured, 1 sell simulated and sellable",
          (d.get("rows"), d.get("not_measured"), d.get("sell_simulated"), d.get("sellable"))
          == (2, 1, 1, 1), repr(d))
    check("unknown: 2 rows, 1 without a sell simulation, 1 simulated honeypot",
          (u.get("rows"), u.get("no_sell_simulation"), u.get("sell_simulated"),
           u.get("honeypot")) == (2, 1, 1, 1), repr(u))
    check("with no selection recorded, nothing is counted as not asked",
          d.get("not_asked") is None and u.get("not_asked") is None, repr((d, u)))


def test_a_selected_set_with_no_rows_is_reported_as_never_asked():
    """Named change (b), T-005 round 2. A run interrupted during its first call, or run with
    --max-calls 0, leaves a file that records its selection and holds no rows. The report must
    account for every selected row: it names each selected set with its count as never asked,
    and never prints "0 rows in 0 sets: none." for such a file. Every count is invented."""
    print("\n[report] a selected set with no rows in the file is reported as never asked")
    doc = {"n": 0, "selection": "adversarial", "selected": {"adversarial": 17}, "results": []}
    with Sandbox(key=False) as sb:
        path = sb.write("stopped.json", doc)
        status, out = cli("--report", path)
        check("--report exits 0 on a file with a selection and no rows", status == 0,
              "status %r: %s" % (status, out[-300:]))
        check("it does not print 0 rows in 0 sets", "0 sets" not in out, out[-300:])
        never = [ln for ln in out.splitlines()
                 if "adversarial" in ln.lower() and re.search(r"(?<![\w.])17(?![\w.])", ln)
                 and re.search(r"\b(none|not|never)\b", ln.lower()) and "asked" in ln]
        check("a line names the adversarial set, its 17 selected rows, and none of them asked",
              bool(never), out[-400:])
    adv = (report_counts([], {"adversarial": 17}) or {}).get("adversarial") or {}
    check("report() returns the adversarial set: 17 selected, 0 rows, 17 not asked",
          (adv.get("selected"), adv.get("rows"), adv.get("not_asked")) == (17, 0, 17),
          repr(adv))
    rows = [saved_row("PSDA", "disputed", error="http 429"),
            saved_row("PSDB", "disputed", answer=static_audit(False))]
    counts = report_counts(rows, {"disputed": 3, "unknown": 4}) or {}
    unk = counts.get("unknown") or {}
    check("stopped inside the disputed set: the unknown set is returned, 4 selected, 0 rows, "
          "4 not asked",
          (unk.get("selected"), unk.get("rows"), unk.get("not_asked")) == (4, 0, 4),
          repr(sorted(counts)))


def test_run_ends_with_the_report_that_report_prints():
    print("\n[report] --run prints, when it finishes, the report --report prints")
    with Sandbox() as sb:
        status, run_out = cli("--run", "--set", "adversarial")
        rstatus, report_out = cli("--report", sb.out_adv)
        check("both exit 0", status == 0 and rstatus == 0, repr((status, rstatus)))
        check("--run's output ends with the same report",
              bool(report_out.strip()) and run_out.rstrip().endswith(report_out.rstrip()),
              "report:\n%s\nrun ends:\n%s" % (report_out[-300:], run_out[-300:]))


def test_report_on_an_unreadable_file_exits_non_zero_without_a_traceback():
    print("\n[report] --report on a missing or unreadable file fails cleanly")
    with Sandbox(key=False) as sb:
        bad_json = os.path.join(sb.tmp, "in", "bad.json")
        write_bytes(bad_json, b"{not json")
        no_rows = sb.write("norows.json", {"n": 3})
        for what, path in (("a missing file", os.path.join(sb.tmp, "missing.json")),
                           ("a file that is not JSON", bad_json),
                           ("JSON with no results", no_rows)):
            status, out = cli("--report", path)
            check("%s: exit status non-zero" % what, isinstance(status, int) and status != 0,
                  "status %r" % status)


def test_report_survives_odd_shapes():
    print("\n[report] odd rows and odd values are counted, never fatal")
    rows = ["not a row", 42, None,
            {"set": ["not", "a", "name"], "quickintel": {"tokenDynamicDetails": {
                "sell_Tax": "1", "lastUpdatedTimestamp": "yesterday", "is_Honeypot": "no"}}},
            {"set": "adversarial", "symbol": "ODDA", "error": {"code": 429}},
            {"set": "adversarial", "symbol": "ODDB", "asked_ms": -5, "quickintel": {
                "tokenDynamicDetails": {"sell_Tax": "1", "lastUpdatedTimestamp": 10 ** 30}}},
            {"set": "adversarial", "symbol": "ODDC", "asked_ms": ASKED_MS, "quickintel": {
                "tokenDynamicDetails": {"sell_Tax": "1",
                                        "lastUpdatedTimestamp": float("nan")}}}]
    with Sandbox(key=False) as sb:
        for what, doc in (("a bare list of rows", rows),
                          ("the usual object", {"n": len(rows), "results": rows})):
            path = sb.write("odd.json", doc)
            status, out = cli("--report", path)
            check("%s: --report exits 0" % what, status == 0,
                  "status %r: %s" % (status, out[-300:]))
    counts = report_counts(rows) or {}
    check("every one of the %d rows is counted in some set" % len(rows),
          sum(c.get("rows", 0) for c in counts.values()) == len(rows), repr(counts))


# --- 8. the contract ------------------------------------------------------------------------

def the_run_touched_nothing():
    """Checked after every test has run, so it covers all of them."""
    print("\n[contract] no network, no real sleep, nothing written under bench/, under 5 s")
    check("nothing reached the network or a real sleep", not _TRIPPED, repr(_TRIPPED))
    after = _bench_listing()
    changed = sorted(n for n in set(after) | set(_BENCH_BEFORE)
                     if after.get(n) != _BENCH_BEFORE.get(n))
    check("bench/ is as it was before the tests", not changed, changed)
    check("the module's clock is the real one again", so.time is REAL_TIME, repr(so.time))
    elapsed = time.perf_counter() - _T0
    check("the whole file ran in under 5 s (%.2f s)" % elapsed, elapsed < 5.0,
          "%.2f s" % elapsed)


def test_goplus_quota_plan_is_offline_fixed_and_source_bound():
    import copy
    import goplus_quota_probe as q

    def context(count=318):
        tokens = [{"chain": "base", "address": "0x%040x" % (i + 1),
                   "goplus_label": "unsafe" if i % 2 else "safe"} for i in range(count)]
        raw = json.dumps({"tokens": tokens}).encode()
        return q.context_from_bytes(raw, "a" * 40, hashlib.sha256(raw).hexdigest(), "b" * 64)

    ctx = context()
    plan = q.make_plan(ctx)
    check("quota queue takes exactly the first 316 original indices", plan["indices"] == list(range(316)))
    check("quota plan binds source, dataset and label code", plan["source_commit"] == "a" * 40
          and plan["dataset_sha256"] == ctx["dataset_sha256"] and plan["label_code_sha256"] == "b" * 64)
    check("quota plan is byte deterministic", q.make_plan(ctx) == plan)
    check("quota plan contains no identity", all(t["address"] not in json.dumps(plan) for t in ctx["tokens"]))
    altered = copy.deepcopy(ctx)
    for row in altered["tokens"]:
        row["goplus_label"] = "centralized"
    check("quota selection does not inspect labels", q.make_plan(altered)["indices"] == plan["indices"])
    for change in (dict(indices=list(reversed(plan["indices"]))), dict(indices=plan["indices"] + [316]),
                   dict(indices=[0] * 316), dict(dataset_sha256="c" * 64),
                   dict(label_code_sha256="c" * 64), dict(source_commit="c" * 40)):
        bad = dict(plan, **change)
        try:
            q.validate_plan(bad, ctx)
        except ValueError:
            refused = True
        else:
            refused = False
        check("changed/reordered/duplicate/oversize quota plans refuse", refused)
    for count in (0, 315):
        try:
            q.make_plan(context(count))
        except ValueError:
            refused = True
        else:
            refused = False
        check("underfilled quota source refuses before calls", refused)
    raw = json.dumps({"tokens": ctx["tokens"]}).encode()
    try:
        q.context_from_bytes(raw, "a" * 40, "c" * 64, "b" * 64)
    except ValueError:
        refused = True
    else:
        refused = False
    check("source bytes must match declared hash", refused)


def test_goplus_quota_run_caps_pacing_and_utc_bounds():
    import datetime
    import goplus_quota_probe as q

    class Clock:
        def __init__(self, wall=1792281600.0): self.wall, self.mono = wall, 0.0
        def time(self): return self.wall
        def monotonic(self): return self.mono
        def sleep(self, n): self.wall += n; self.mono += n
    class Sink:
        def begin(self, plan): self.plan = plan; self.events = []
        def append(self, event): self.events.append(event)
        def save(self, report): self.report = report
    raw = json.dumps({"tokens": [{"chain": "base", "address": "0x%040x" % (i+1)} for i in range(317)]}).encode()
    ctx = q.context_from_bytes(raw, "a"*40, hashlib.sha256(raw).hexdigest(), "b"*64)
    plan = q.make_plan(ctx)
    clock, sink, starts = Clock(), Sink(), []
    def transport(chain, addr, *, timeout):
        starts.append(clock.monotonic())
        check("quota transport timeout is thirty seconds", timeout == 30)
        return {"http_status": 429, "body": b'{"code":2,"message":"PRIVATE-QUOTA"}'}
    report = q.run_plan(plan, ctx, sink=sink, transport=transport, clock=clock)
    check("all quota attempts are capped at 316 with no 429 retry", len(starts) == 316
          and report["counts"]["claimed"] == 316 and report["counts"]["rate_limited"] == 316)
    check("quota calls obey start spacing without real waits", all(b-a >= 2.1-1e-9 for a,b in zip(starts,starts[1:])))
    check("a 429 observation is non-success, never a label", report["available"] is False
          and report["counts"]["label_returned"] == 0)
    before = len(starts)
    try:
        q.run_plan(dict(plan, indices=plan["indices"]+[316]), ctx, sink=Sink(), transport=transport, clock=clock)
    except ValueError:
        refused = True
    else:
        refused = False
    check("317th planned attempt refuses before transport", refused and len(starts) == before)
    close = datetime.datetime(2026,10,18,23,59,45,tzinfo=datetime.timezone.utc).timestamp()
    stopped = q.run_plan(plan, ctx, sink=Sink(), transport=transport, clock=Clock(close))
    check("full timeout must fit before UTC midnight", stopped["counts"]["claimed"] == 0
          and stopped["counts"]["not_asked"] == 316 and stopped["stop_reason"] == "utc_day_end")
    for status in (401,403):
        calls = []
        def auth(chain, addr, *, timeout): calls.append(addr); return {"http_status":status,"body":b'{}'}
        result=q.run_plan(plan,ctx,sink=Sink(),transport=auth,clock=Clock())
        check("first permission refusal stops remaining quota",len(calls)==1 and result["counts"]["not_asked"]==315
              and result["stop_reason"]=="permission_refused")
    slow_clock=Clock()
    def slow(chain,addr,*,timeout): slow_clock.sleep(1771); return {"http_status":500,"body":b'{}'}
    result=q.run_plan(plan,ctx,sink=Sink(),transport=slow,clock=slow_clock)
    check("elapsed run budget stops before another full timeout",result["counts"]["claimed"]==1
          and result["stop_reason"]=="run_deadline")

    # Native total-deadline regression pin authorized by T044 clarification (d).
    def pin_native_total_deadline_supervisor():
        class Clock:
            def __init__(self): self.now=0.0
            def monotonic(self): return self.now
        clock=Clock()
        workers=[]
        class Worker:
            def __init__(self): self.live=False; self.terminated=False; self.killed=False; self.closed=False; self.waits=[]
            def start(self):
                assert not any(w.live for w in workers if w is not self)
                self.live=True
            def is_alive(self): return self.live
            def join(self,timeout):
                self.waits.append(timeout)
                if self.live: clock.now+=timeout
            def terminate(self): self.terminated=True
            def kill(self): self.killed=True; self.live=False
            def status(self): return 403
            def result(self): raise AssertionError("expired worker body must stay unavailable")
            def close(self): assert not self.live; self.closed=True
        def factory(chain,address,timeout):
            assert chain=="base" and timeout==30
            worker=Worker(); workers.append(worker); return worker
        replies=[q._supervised_request("base","0x"+"1"*40,timeout=30,worker_factory=factory,clock=clock)
                 for _ in range(2)]
        check("native deadline retires each worker with bounded cleanup before another starts",
              len(workers)==2 and all(w.terminated and w.killed and w.closed and not w.live for w in workers)
              and all(len(w.waits)==3 and 0<w.waits[0]<=30+1e-9
                      and all(0<=wait<=0.05 for wait in w.waits[1:]) for w in workers)
              and all(reply=={"http_status":403,"error":"timeout"} for reply in replies)
              and 60<=clock.now<=60.11)
        original=q._supervised_request
        routed=[]
        def supervised(chain,address,*,timeout,**kwargs):
            routed.append(timeout); return {"http_status":403,"error":"timeout"}
        try:
            q._supervised_request=supervised
            reply=q.request_once("base","0x"+"1"*40)
        finally:
            q._supervised_request=original
        safe=q.classify(reply,"0x"+"1"*40)
        check("default native transport always uses the bounded supervisor without public raw output",
              routed==[30] and safe["http_status"]==403 and safe["body_state"]=="timeout"
              and safe["captured_body_sha256"] is None and safe["label_state"]=="unobserved"
              and "PRIVATE" not in json.dumps(safe))
        interrupted=[]
        class InterruptWorker(Worker):
            def join(self,timeout):
                if not self.terminated:
                    interrupted.append(True)
                    raise KeyboardInterrupt()
                return super().join(timeout)
        def interrupted_factory(chain,address,timeout):
            worker=InterruptWorker(); workers.append(worker); return worker
        try:
            q._supervised_request("base","0x"+"1"*40,timeout=30,worker_factory=interrupted_factory,clock=clock)
        except KeyboardInterrupt:
            propagated=True
        else:
            propagated=False
        check("native supervisor interruption retires its worker and propagates",
              propagated and interrupted==[True] and workers[-1].closed and not workers[-1].live)
    pin_native_total_deadline_supervisor()

    # Bounded first-review correction authorized by T044 clarification (e).
    def pin_round2_durable_timing_boundaries():
        import datetime
        from pathlib import Path
        class Clock:
            def __init__(self,wall,backward_sleep=False): self.wall=wall; self.mono=0.0; self.backward_sleep=backward_sleep
            def time(self): return self.wall
            def monotonic(self): return self.mono
            def sleep(self,n):
                self.wall+=n; self.mono+=n
                if self.backward_sleep: self.wall-=86400
        raw=json.dumps({"tokens":[{"chain":"base","address":"0x%040x"%(i+1)} for i in range(316)]}).encode()
        context=q.context_from_bytes(raw,"a"*40,hashlib.sha256(raw).hexdigest(),"b"*64)
        plan=q.make_plan(context)
        window=q.REQUEST_TIMEOUT+2*q._CLEANUP_SECONDS
        base=1792281600.0
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            def run_case(name,wall,latency_wall,latency_mono,statuses=(403,),backward_sleep=False):
                clock=Clock(wall,backward_sleep); starts=[]; replies=iter(statuses)
                class SlowIntent(q.FileSink):
                    def append(self,event):
                        super().append(event)
                        if event["kind"]=="intent" and event["index"]==0:
                            clock.wall+=latency_wall; clock.mono+=latency_mono
                def transport(chain,address,*,timeout):
                    starts.append((clock.monotonic(),clock.time()))
                    return {"http_status":next(replies),"body":b'{}'}
                path=root/name
                report=q.run_plan(plan,context,sink=SlowIntent(path),transport=transport,clock=clock)
                return report,q.read_report(path),starts,[json.loads(line) for line in (path/"receipts.jsonl").read_bytes().splitlines()]
            report,restored,starts,events=run_case("spacing",base+100,3,3,(429,403))
            actual=[datetime.datetime.fromtimestamp(wall,datetime.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00","Z")
                    for mono,wall in starts]
            intents=[event for event in events if event["kind"]=="intent"]
            receipts=[event for event in events if event["kind"]=="receipt"]
            check("durable intent latency preserves actual transport spacing and truthful persisted starts",
                  len(starts)==2 and starts[1][0]-starts[0][0]>=2.1-1e-9
                  and [cell.get("request_at") for cell in restored["cells"][:2]]==actual
                  and [event.get("request_at") for event in receipts]==actual
                  and all("claimed_at" in event and "request_at" not in event for event in intents)
                  and restored["cells"][0].get("claimed_at")==intents[0].get("claimed_at")
                  and restored["cells"][0].get("claimed_at")!=actual[0]
                  and all(cell["duration_seconds"]==0 for cell in restored["cells"][:2]))
            cases=[("exact-day",base+86400-window,0,0,1,"permission_refused"),
                   ("late-day",base+86400-window-0.1,0.2,0.2,0,"utc_day_end"),
                   ("exact-run",base+100,q.RUN_SECONDS-window,q.RUN_SECONDS-window,1,"permission_refused"),
                   ("late-run",base+100,q.RUN_SECONDS-window+0.2,q.RUN_SECONDS-window+0.2,0,"run_deadline"),
                   ("backward-intent",base+0.1,-1,0.2,0,"utc_day_end")]
            for name,wall,delay_wall,delay_mono,expected,reason in cases:
                report,restored,starts,events=run_case(name,wall,delay_wall,delay_mono)
                counts=restored["counts"]
                check("post-intent admission retains exact day/run edges and consumed unopened claims: "+name,
                      len(starts)==expected and report["stop_reason"]==reason
                      and counts["claimed"]==1 and counts["attempted"]==expected
                      and counts["uncertain"]==1-expected and counts["not_asked"]==315
                      and (expected==1 or "request_at" not in restored["cells"][0]))
            report,restored,starts,events=run_case("backward-pacing",base+100,0,0,(429,403),True)
            counts=restored["counts"]
            check("pacing wait rechecks the chosen UTC date after a backward wall step",
                  len(starts)==1 and report["stop_reason"]=="utc_day_end"
                  and counts["attempted"]==1 and counts["claimed"] in (1,2)
                  and counts["uncertain"]==counts["claimed"]-1 and counts["not_asked"]==316-counts["claimed"])
    pin_round2_durable_timing_boundaries()


def test_goplus_quota_http_and_exact_result_stages():
    import goplus_quota_probe as q

    addr="0x"+"1"*40
    called=[]
    def labeler(payload, address, recent_volume_7d=None):
        called.append((payload,address,recent_volume_7d)); return "safe",[],{}
    def reply(status,body): return {"http_status":status,"body":json.dumps(body).encode()}
    data={"buy_tax":"0","sell_tax":"0.01","holder_count":"500"}
    good=reply(200,{"code":1,"result":{addr:data}})
    cell=q.classify(good,addr,recent_volume=1234,labeler=labeler)
    check("matching GoPlus data has separate observed stages",cell["http_state"]=="observed"
          and cell["result_state"]=="matched" and cell["label_state"]=="returned"
          and cell["field_states"]=={"buy_tax":"finite","sell_tax":"finite","holder_count":"integer"})
    check("labeler gets actual finite volume",called[-1][2]==1234)
    for body in ({"code":2,"message":"PRIVATE-QUOTA","result":{}},
                 {"code":1,"result":{"0x"+"2"*40:data}}, {"code":1,"result":{}},
                 {"code":1,"result":{addr:[]}}):
        before=len(called); bad=q.classify(reply(200,body),addr,labeler=labeler)
        check("error or another contract never reaches label fallback",len(called)==before
              and bad["label_state"]=="unobserved")
    for status,state in ((429,"rate_limited"),(403,"permission_refused"),(500,"http_error"),(302,"redirect")):
        before=len(called); bad=q.classify(reply(status,{"code":1,"result":{addr:data}}),addr,labeler=labeler)
        check("HTTP failures keep their measured stage",bad["http_state"]==state
              and bad["label_state"]=="unobserved" and len(called)==before)
    for raw,state in ((b'',"empty"),(b'PRIVATE-QUOTA',"malformed"),(b'\xff',"malformed"),
                      (b'x'*(q.BODY_CAP+1),"truncated")):
        bad=q.classify({"http_status":200,"body":raw},addr,labeler=labeler)
        check("body gaps are distinct",bad["body_state"]==state and bad["label_state"]=="unobserved")
    bad=q.classify(reply(200,{"code":1,"result":{addr:{"buy_tax":"NaN","sell_tax":None}}}),addr,
                   recent_volume=float("inf"),labeler=labeler)
    check("missing/nonfinite fields are not zero",bad["field_states"]=={
          "buy_tax":"invalid","sell_tax":"missing","holder_count":"missing"} and called[-1][2] is None)
    for error in ("timeout","transport"):
        bad=q.classify({"http_status":0,"error":error},addr,labeler=labeler)
        check("transport absence remains unobserved",bad["http_state"]==error and bad["body_state"]=="unobserved")
    class Response:
        status=429
        def __enter__(self): return self
        def __exit__(self,*a): pass
        def read(self,n): check("GoPlus bounded read includes overflow byte",n==q.BODY_CAP+1); return b'{}'
    class Opener:
        def __init__(self): self.calls=[]
        def open(self,req,timeout): self.calls.append((req,timeout)); return Response()
    opener=Opener(); got=q.request_once("base",addr,opener=opener)
    check("native transport performs exactly one GET",len(opener.calls)==1 and opener.calls[0][0].get_method()=="GET"
          and opener.calls[0][1]==30 and got["http_status"]==429)
    check("quota redirect handler never follows",q.NoRedirect().redirect_request(None,None,302,"x",{},"https://example.invalid") is None)

    # Retrospective ordinary-CI pin authorized by T044 clarification (c).
    def pin_permission_headers_then_body_timeout():
        class Clock:
            def __init__(self): self.now=0.0
            def time(self): return 1792281600.0+self.now
            def monotonic(self): return self.now
            def sleep(self,n): self.now+=n
        class Sink:
            def begin(self,plan): pass
            def append(self,event): pass
            def save(self,report): pass
        class Response:
            status=403
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self,n): raise TimeoutError("PRIVATE-BODY-TIMEOUT")
        class Opener:
            def __init__(self): self.calls=0
            def open(self,*args,**kwargs): self.calls+=1; return Response()
        raw=json.dumps({"tokens":[{"chain":"base","address":"0x%040x"%(i+1)} for i in range(316)]}).encode()
        context=q.context_from_bytes(raw,"a"*40,hashlib.sha256(raw).hexdigest(),"b"*64)
        opener=Opener()
        def transport(chain,address,*,timeout):
            return q.request_once(chain,address,timeout=timeout,opener=opener)
        report=q.run_plan(q.make_plan(context),context,sink=Sink(),transport=transport,clock=Clock())
        first=report["cells"][0]
        check("permission headers survive a body timeout without a second attempt",
              opener.calls==1 and report["counts"]["claimed"]==1 and report["counts"]["attempted"]==1
              and report["counts"]["completed_http"]==1 and report["counts"]["transport_errors"]==1
              and report["counts"]["not_asked"]==315 and report["stop_reason"]=="permission_refused"
              and first["http_status"]==403 and first["http_state"]=="permission_refused"
              and first["body_state"]=="timeout" and first["captured_body_sha256"] is None
              and first["body_complete"] is None and first["label_state"]=="unobserved"
              and all(cell["state"]=="not_asked" for cell in report["cells"][1:]))
    pin_permission_headers_then_body_timeout()

    # Native body-exception regression pin authorized by T044 clarification (d).
    def pin_native_permission_body_exception():
        import http.client
        class Clock:
            def __init__(self): self.now=0.0
            def time(self): return 1792281600.0+self.now
            def monotonic(self): return self.now
            def sleep(self,n): self.now+=n
        class Sink:
            def begin(self,plan): pass
            def append(self,event): pass
            def save(self,report): pass
        class Response:
            status=403
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self,n): raise http.client.IncompleteRead(b'PRIVATE-PARTIAL',19)
        class Opener:
            def __init__(self,response): self.calls=0; self.response=response
            def open(self,*args,**kwargs): self.calls+=1; return self.response()
        raw=json.dumps({"tokens":[{"chain":"base","address":"0x%040x"%(i+1)} for i in range(316)]}).encode()
        context=q.context_from_bytes(raw,"a"*40,hashlib.sha256(raw).hexdigest(),"b"*64)
        opener=Opener(Response)
        def transport(chain,address,*,timeout): return q.request_once(chain,address,timeout=timeout,opener=opener)
        report=q.run_plan(q.make_plan(context),context,sink=Sink(),transport=transport,clock=Clock())
        first=report["cells"][0]
        check("native HTTPException keeps permission evidence and stops after one attempt",
              opener.calls==1 and report["counts"]["claimed"]==1 and report["counts"]["attempted"]==1
              and report["counts"]["not_asked"]==315 and report["stop_reason"]=="permission_refused"
              and first["http_status"]==403 and first["http_state"]=="permission_refused"
              and first["body_state"]=="transport" and first["captured_body_sha256"] is None
              and first["label_state"]=="unobserved" and "PRIVATE-PARTIAL" not in json.dumps(report))
        class InterruptedResponse(Response):
            def read(self,n): raise KeyboardInterrupt()
        opener=Opener(InterruptedResponse)
        report=q.run_plan(q.make_plan(context),context,sink=Sink(),transport=transport,clock=Clock())
        check("native body interruption reaches the run interruption handler without retry",
              opener.calls==1 and report["stop_reason"]=="interrupted" and report["counts"]["uncertain"]==1
              and report["counts"]["attempted"]==0 and report["counts"]["not_asked"]==315)
    pin_native_permission_body_exception()

    # Bounded first-review correction authorized by T044 clarification (e).
    def pin_round2_deep_json_cli():
        import contextlib
        from pathlib import Path
        deep=b'['*20000+b'"PRIVATE-DEEP-BODY"'+b']'*20000
        try:
            json.loads(deep)
        except RecursionError:
            native_recursion=True
        else:
            native_recursion=False
        check("within-cap nested JSON reaches the native decoder recursion boundary",native_recursion and len(deep)<q.BODY_CAP)
        address="0x"+"1"*40; labels_called=[]
        def labeler(*args,**kwargs): labels_called.append(True); return "safe",[],{}
        try:
            cell=q.classify({"http_status":403,"body":deep},address,labeler=labeler)
        except RecursionError:
            cell={}
        check("bounded decoder recursion retains the known permission stage and malformed body",
              cell.get("http_status")==403 and cell.get("http_state")=="permission_refused"
              and cell.get("body_state")=="malformed" and cell.get("label_state")=="unobserved"
              and cell.get("captured_body_sha256")==hashlib.sha256(deep).hexdigest() and not labels_called)
        control=q.classify({"http_status":200,"body":b'PRIVATE-ORDINARY-MALFORMED'},address,labeler=labeler)
        check("ordinary HTTP200 malformed JSON remains unavailable to API and labels",
              control["http_state"]=="observed" and control["body_state"]=="malformed"
              and control["api_state"]=="unobserved" and control["label_state"]=="unobserved" and not labels_called)
        class Clock:
            def time(self): return 1792281600.0
            def monotonic(self): return 0.0
            def sleep(self,n): raise AssertionError("permission recursion must stop before another request")
        raw=json.dumps({"tokens":[{"chain":"base","address":"0x%040x"%(i+1)} for i in range(316)]}).encode()
        context=q.context_from_bytes(raw,"a"*40,hashlib.sha256(raw).hexdigest(),"b"*64)
        original=q.labels.goplus_label
        q.labels.goplus_label=labeler
        try:
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory); dataset=root/"dataset.json"; dataset.write_bytes(raw); plan=root/"plan.json"; output=root/"run"
                def loader(path,source):
                    if Path(path).read_bytes()!=raw or source!="a"*40: raise ValueError("PRIVATE-DEEP-SOURCE")
                    return context
                calls=[]
                def transport(chain,requested,*,timeout): calls.append(requested); return {"http_status":403,"body":deep}
                console=io.StringIO(); errors=io.StringIO(); escaped=False
                with contextlib.redirect_stdout(console),contextlib.redirect_stderr(errors):
                    planned=q.main(["plan","--dataset",str(dataset),"--source","a"*40,"--output",str(plan)],context_loader=loader)
                    try:
                        status=q.main(["run","--dataset",str(dataset),"--plan",str(plan),"--output",str(output)],
                                      context_loader=loader,transport=transport,clock=Clock())
                    except RecursionError:
                        escaped=True; status=None
                    read_status=q.main(["report","--output",str(output)])
                restored=q.read_report(output); first=restored["cells"][0]
                check("real CLI retains one deep-body refusal and315unasked without decoder escape",
                      planned==0 and status==1 and read_status==1 and not escaped and len(calls)==1
                      and restored["counts"]["claimed"]==1 and restored["counts"]["attempted"]==1
                      and restored["counts"]["not_asked"]==315 and restored["counts"]["label_returned"]==0
                      and first.get("http_status")==403 and first.get("body_state")=="malformed" and not labels_called)
                deep_path=root/"deep.json"; deep_path.write_bytes(deep)
                bad_report=root/"deep-report"; bad_report.mkdir()
                (bad_report/"plan.json").write_bytes(deep); (bad_report/"receipts.jsonl").write_bytes(b'')
                def deep_loader(path,source):
                    return q.context_from_bytes(deep,"a"*40,hashlib.sha256(deep).hexdigest(),"b"*64)
                inputs=[(["plan","--dataset",str(deep_path),"--source","a"*40,"--output",str(root/"deep-plan")],deep_loader),
                        (["run","--dataset",str(dataset),"--plan",str(deep_path),"--output",str(root/"deep-run")],loader),
                        (["report","--output",str(bad_report)],None)]
                for argv,chosen_loader in inputs:
                    with contextlib.redirect_stdout(console),contextlib.redirect_stderr(errors):
                        try:
                            rejected=q.main(argv,context_loader=chosen_loader,transport=transport,clock=Clock())
                        except RecursionError:
                            rejected=None
                    check("CLI source/plan/report decoder recursion stays inside the safe failure boundary",rejected==1 and len(calls)==1)
                emitted=console.getvalue()+errors.getvalue()
                check("deep JSON console excludes tracebacks body text addresses and private paths",
                      all(marker not in emitted for marker in ("Traceback","RecursionError","PRIVATE-DEEP",str(root),address,"https://"))
                      and errors.getvalue()=="")
        finally:
            q.labels.goplus_label=original
    pin_round2_deep_json_cli()


def test_goplus_quota_safe_output_and_private_raw():
    import contextlib
    import types
    from pathlib import Path
    import goplus_quota_probe as q

    class Clock:
        def time(self): return 1792281600.0
        def monotonic(self): return 0.0
        def sleep(self,n): raise AssertionError("one permission call must not sleep")
    raw=json.dumps({"tokens":[{"chain":"base","address":"0x%040x"%(i+1)} for i in range(316)]}).encode()
    ctx=q.context_from_bytes(raw,"a"*40,hashlib.sha256(raw).hexdigest(),"b"*64); plan=q.make_plan(ctx)
    body=b'{"message":"PRIVATE-QUOTA-RAW","account":"ACCOUNT-SENTINEL"}'
    calls=[]
    def transport(chain,addr,*,timeout): calls.append(addr); return {"http_status":403,"body":body}
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory); output=root/"safe"; private=root/"private"
        real_os=q.os
        real_environ=os.environ
        environment_before=dict(real_environ)
        local_os=types.SimpleNamespace(**vars(real_os))
        local_os.environ=dict(real_environ,GITHUB_ACTIONS="false")
        try:
            q.os=local_os
            result=q.run_plan(plan,ctx,sink=q.FileSink(output),transport=transport,clock=Clock(),private_raw_dir=private)
        finally:
            q.os=real_os
        check("synthetic raw fixture restores the real OS dependency and process environment",
              q.os is real_os and os.environ is real_environ and dict(os.environ)==environment_before)
        safe=b''.join(p.read_bytes() for p in output.iterdir() if p.is_file())
        check("public quota bundle stays below one MiB",len(safe)<=q.SAFE_CAP==1024*1024)
        check("public bundle excludes raw text/addresses/URLs",all(s not in safe for s in (
              body,b"PRIVATE-QUOTA-RAW",b"ACCOUNT-SENTINEL",ctx["tokens"][0]["address"].encode(),b"https://")))
        check("explicit private raw directory retains captured bytes",any(p.read_bytes()==body for p in private.rglob("*") if p.is_file()))
        before=len(calls)
        try:
            q.run_plan(plan,ctx,sink=q.FileSink(root/"ci-safe"),transport=transport,clock=Clock(),
                       private_raw_dir=root/"ci-raw",ci=True)
        except ValueError:
            refused=True
        else:
            refused=False
        check("CI refuses raw retention before calls",refused and len(calls)==before)
        nested=root/"worktree"; nested.mkdir(); (nested/".git").write_text("gitdir: sentinel",encoding="utf-8")
        try:
            q.run_plan(plan,ctx,sink=q.FileSink(root/"nested-safe"),transport=transport,clock=Clock(),private_raw_dir=nested/"raw")
        except ValueError:
            refused=True
        else:
            refused=False
        check("raw retention refuses any Git worktree ancestor",refused and len(calls)==before)

    # Retrospective ordinary-CI pin authorized by T044 clarification (c).
    def pin_nested_private_raw():
        from pathlib import Path
        class Clock:
            def time(self): return 1792281600.0
            def monotonic(self): return 0.0
            def sleep(self,n): raise AssertionError("nested raw must refuse before calls")
        raw=json.dumps({"tokens":[{"chain":"base","address":"0x%040x"%(i+1)} for i in range(316)]}).encode()
        context=q.context_from_bytes(raw,"a"*40,hashlib.sha256(raw).hexdigest(),"b"*64)
        calls=[]
        def transport(chain,address,*,timeout):
            calls.append(address)
            return {"http_status":403,"body":b'PRIVATE-NESTED-RAW'}
        with tempfile.TemporaryDirectory() as directory:
            safe=Path(directory)/"safe"
            try:
                q.run_plan(q.make_plan(context),context,sink=q.FileSink(safe),transport=transport,
                           clock=Clock(),private_raw_dir=safe/"raw")
            except ValueError:
                refused=True
            else:
                refused=False
            check("private raw nested in the safe bundle refuses before calls",
                  refused and not calls and not safe.exists())
    pin_nested_private_raw()


def test_goplus_quota_partial_intents_and_persistence():
    from pathlib import Path
    import goplus_quota_probe as q

    class Clock:
        def time(self): return 1792281600.0
        def monotonic(self): return 0.0
        def sleep(self,n): raise AssertionError("interrupted quota never retries")
    raw=json.dumps({"tokens":[{"chain":"base","address":"0x%040x"%(i+1)} for i in range(316)]}).encode()
    ctx=q.context_from_bytes(raw,"a"*40,hashlib.sha256(raw).hexdigest(),"b"*64); plan=q.make_plan(ctx)
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/"interrupted"; calls=[]
        def interrupted(chain,addr,*,timeout):
            calls.append(addr)
            journal=(path/"receipts.jsonl").read_text(encoding="utf-8")
            check("durable intent exists before transport",'"kind":"intent"' in journal)
            raise KeyboardInterrupt()
        result=q.run_plan(plan,ctx,sink=q.FileSink(path),transport=interrupted,clock=Clock())
        restored=q.read_report(path)
        check("intent-only interruption stays uncertain",len(calls)==1 and restored["counts"]["claimed"]==1
              and restored["counts"]["uncertain"]==1 and restored["counts"]["not_asked"]==315
              and restored["available"] is False)
        before={p.name:p.read_bytes() for p in path.iterdir() if p.is_file()}
        try:
            q.run_plan(plan,ctx,sink=q.FileSink(path),transport=interrupted,clock=Clock())
        except (ValueError,FileExistsError):
            refused=True
        else:
            refused=False
        check("restart refuses and preserves all earlier files",refused and len(calls)==1
              and before=={p.name:p.read_bytes() for p in path.iterdir() if p.is_file()})
        class Broken:
            def begin(self,plan): pass
            def append(self,event): raise OSError("PRIVATE-PERSISTENCE")
            def save(self,report): pass
        result=q.run_plan(plan,ctx,sink=Broken(),transport=interrupted,clock=Clock())
        check("intent persistence failure stops before any call",len(calls)==1 and result["stop_reason"]=="persistence_failed"
              and result["counts"]["claimed"]==0 and result["counts"]["not_asked"]==316)

    # Retrospective ordinary-CI pin authorized by T044 clarification (c).
    def pin_torn_final_receipt():
        from pathlib import Path
        class Clock:
            def __init__(self): self.now=0.0
            def time(self): return 1792281600.0+self.now
            def monotonic(self): return self.now
            def sleep(self,n): self.now+=n
        raw=json.dumps({"tokens":[{"chain":"base","address":"0x%040x"%(i+1)} for i in range(316)]}).encode()
        context=q.context_from_bytes(raw,"a"*40,hashlib.sha256(raw).hexdigest(),"b"*64)
        calls=[]
        def transport(chain,address,*,timeout):
            calls.append(address)
            if len(calls)==2: raise KeyboardInterrupt()
            return {"http_status":429,"body":b'{}'}
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"torn"
            q.run_plan(q.make_plan(context),context,sink=q.FileSink(path),transport=transport,clock=Clock())
            ledger=path/"receipts.jsonl"
            lines=ledger.read_bytes().splitlines(keepends=True)
            assert json.loads(lines[-1])["kind"]=="stop"
            ledger.write_bytes(b''.join(lines[:-1])+b'{"kind":"receipt","index":1')
            before={p.name:p.read_bytes() for p in path.iterdir() if p.is_file()}
            try:
                restored=q.read_report(path)
                preserved=(restored["counts"]["claimed"]==2 and restored["counts"]["completed_http"]==1
                           and restored["counts"]["rate_limited"]==1 and restored["counts"]["uncertain"]==1
                           and restored["counts"]["not_asked"]==314 and restored["available"] is False
                           and restored["ledger_tail_state"]=="incomplete"
                           and restored["cells"][0]["http_status"]==429
                           and restored["cells"][1]["reason"]=="missing_receipt")
            except (ValueError,KeyError):
                preserved=False
            check("torn final quota receipt retains complete prior evidence and bytes",
                  preserved and len(calls)==2
                  and before=={p.name:p.read_bytes() for p in path.iterdir() if p.is_file()})
    pin_torn_final_receipt()

    # Bounded first-review correction authorized by T044 clarification (e).
    def pin_round2_partial_receipt_error():
        import contextlib
        import os
        from pathlib import Path
        class Clock:
            def __init__(self): self.now=0.0
            def time(self): return 1792281600.0+self.now
            def monotonic(self): return self.now
            def sleep(self,n): self.now+=n
        raw=json.dumps({"tokens":[{"chain":"base","address":"0x%040x"%(i+1)} for i in range(316)]}).encode()
        context=q.context_from_bytes(raw,"a"*40,hashlib.sha256(raw).hexdigest(),"b"*64)
        calls=[]
        def transport(chain,address,*,timeout): calls.append(address); return {"http_status":429,"body":b'{}'}
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"partial"
            class PartialReceipt(q.FileSink):
                def append(self,event):
                    if event["kind"]=="receipt" and event["index"]==1:
                        encoded=q._encode(event)
                        with (self.path/"receipts.jsonl").open("ab") as handle:
                            handle.write(encoded[:47]); handle.flush(); os.fsync(handle.fileno())
                        self.torn=(self.path/"receipts.jsonl").read_bytes()
                        raise OSError("PRIVATE-PARTIAL-WRITE")
                    return super().append(event)
            sink=PartialReceipt(path)
            result=q.run_plan(q.make_plan(context),context,sink=sink,transport=transport,clock=Clock())
            ledger=path/"receipts.jsonl"
            check("receipt append failure retains the original torn bytes without terminal concatenation",
                  len(calls)==2 and result["stop_reason"]=="persistence_failed" and ledger.read_bytes()==sink.torn)
            console=io.StringIO(); errors=io.StringIO()
            with contextlib.redirect_stdout(console),contextlib.redirect_stderr(errors):
                status=q.main(["report","--output",str(path)])
            try:
                restored=q.read_report(path)
                readable=(restored["counts"]["claimed"]==2 and restored["counts"]["completed_http"]==1
                          and restored["counts"]["rate_limited"]==1 and restored["counts"]["uncertain"]==1
                          and restored["counts"]["not_asked"]==314 and restored["available"] is False
                          and restored["ledger_tail_state"]=="incomplete"
                          and restored["cells"][0]["http_status"]==429
                          and restored["cells"][1]["reason"]=="missing_receipt"
                          and restored["receipt_bytes_sha256"]==hashlib.sha256(sink.torn).hexdigest())
            except (ValueError,KeyError):
                readable=False
            decoded=json.loads(console.getvalue())
            check("real offline CLI recovers prior429 both claims uncertain slot and314unasked after partial error",
                  status==1 and readable and decoded.get("counts")==restored["counts"]
                  and ledger.read_bytes()==sink.torn and len(calls)==2 and errors.getvalue()=="")
            corrupt=Path(directory)/"corrupt"; corrupt.mkdir()
            (corrupt/"plan.json").write_bytes((path/"plan.json").read_bytes())
            lines=ledger.read_bytes().splitlines(keepends=True)
            invalid=lines[0]+b'{"kind":\n'+b''.join(lines[1:])
            (corrupt/"receipts.jsonl").write_bytes(invalid)
            try:
                q.read_report(corrupt)
            except ValueError:
                refused=True
            else:
                refused=False
            check("partial-tail recovery never skips a corrupt interior record",
                  refused and (corrupt/"receipts.jsonl").read_bytes()==invalid)

            # Same-finding terminal-time correction authorized by T044 clarification (e2).
            def pin_unobserved_elapsed_after_partial_append():
                command=[sys.executable,"-B",str(Path(ROOT)/"bench/goplus_quota_probe.py"),"report","--output",str(path)]
                standalone=subprocess.run(command,capture_output=True,text=True,encoding="utf-8",timeout=5)
                recovered=json.loads(standalone.stdout)
                observed=q.read_report(path)
                expected=(2,1,1,1,314)
                keys=("claimed","attempted","rate_limited","uncertain","not_asked")
                check("partial append immediate and standalone readout keep unobserved elapsed null",
                      result["ended_at"] is None and result["elapsed_seconds"] is None and result["elapsed_minutes"] is None
                      and result["started_at"] is not None and tuple(result["counts"][key] for key in keys)==expected
                      and standalone.returncode==1 and standalone.stderr==""
                      and "elapsed_seconds" in recovered and "elapsed_minutes" in recovered
                      and recovered["ended_at"] is None and recovered["elapsed_seconds"] is None and recovered["elapsed_minutes"] is None
                      and recovered["started_at"]==result["started_at"]
                      and tuple(recovered.get("counts",{}).get(key) for key in keys)==expected
                      and observed["cells"][0]["http_status"]==429 and observed["cells"][0].get("request_at") is not None
                      and observed["cells"][1].get("claimed_at") is not None and "request_at" not in observed["cells"][1]
                      and ledger.read_bytes()==sink.torn and len(calls)==2)
                positive_calls=[]
                def positive_transport(chain,address,*,timeout):
                    positive_calls.append(address)
                    return {"http_status":429 if len(positive_calls)==1 else 403,"body":b'{}'}
                positive_path=Path(directory)/"valid-terminal"
                positive=q.run_plan(q.make_plan(context),context,sink=q.FileSink(positive_path),transport=positive_transport,clock=Clock())
                positive_cli=subprocess.run(command[:-1]+[str(positive_path)],capture_output=True,text=True,encoding="utf-8",timeout=5)
                positive_read=json.loads(positive_cli.stdout)
                check("valid terminal immediate and standalone readout retain actual positive elapsed",
                      len(positive_calls)==2 and positive["ended_at"] is not None and positive["elapsed_seconds"]>0
                      and abs(positive["elapsed_seconds"]-q.GAP_SECONDS)<1e-9
                      and positive["elapsed_minutes"]==positive["elapsed_seconds"]/60
                      and positive_cli.returncode==1 and positive_cli.stderr==""
                      and positive_read["elapsed_seconds"]==positive["elapsed_seconds"]
                      and positive_read["elapsed_minutes"]==positive["elapsed_minutes"])
            pin_unobserved_elapsed_after_partial_append()
    pin_round2_partial_receipt_error()


def test_goplus_quota_readout_denominators_and_limits():
    import goplus_quota_probe as q

    class Clock:
        def __init__(self): self.now=0.0
        def time(self): return 1792281600.0+self.now
        def monotonic(self): return self.now
        def sleep(self,n): self.now+=n
    class Sink:
        def begin(self,plan): self.plan=plan; self.events=[]
        def append(self,event): self.events.append(event)
        def save(self,report): self.report=report
    raw=json.dumps({"tokens":[{"chain":"base","address":"0x%040x"%(i+1)} for i in range(316)]}).encode()
    ctx=q.context_from_bytes(raw,"a"*40,hashlib.sha256(raw).hexdigest(),"b"*64); plan=q.make_plan(ctx)
    statuses=iter([429,500,403]); sink=Sink()
    def transport(chain,addr,*,timeout): return {"http_status":next(statuses),"body":b'{}'}
    result=q.run_plan(plan,ctx,sink=sink,transport=transport,clock=Clock())
    counts=result["counts"]
    check("quota readout preserves every denominator",(counts["requested"],counts["claimed"],counts["attempted"],
          counts["completed_http"],counts["rate_limited"],counts["not_asked"],counts["unobserved_label"])
          ==(316,3,3,3,1,313,3))
    check("quota cells have exactly the frozen queue indices",[r["index"] for r in result["cells"]]==plan["indices"])
    check("short quota run reports actual elapsed minutes",0<result["elapsed_seconds"]<60
          and result["last_observation_at"] is not None and result["first_observation_at"] is not None)
    text=json.dumps(result)
    check("quota limitations expressly reject daily and prospective claims",all(term in text for term in (
          "not continuous 24-hour", "daily reset unobserved", "not a T+24h", "30-day", "shared usage unknown")))
    check("quota report never computes demand or unsafe yield",all(term not in result for term in ("unsafe_yield","external_users","build_decision")))


def test_goplus_quota_cli_and_existing_runner_contract():
    import ast
    import contextlib
    from pathlib import Path
    import goplus_quota_probe as q

    class Clock:
        def time(self): return 1792281600.0
        def monotonic(self): return 0.0
        def sleep(self,n): raise AssertionError("CLI permission refusal stops immediately")
    raw=json.dumps({"tokens":[{"chain":"base","address":"0x%040x"%(i+1)} for i in range(316)]}).encode()
    ctx=q.context_from_bytes(raw,"a"*40,hashlib.sha256(raw).hexdigest(),"b"*64)
    calls=[]
    def loader(path,source):
        if Path(path).read_bytes()!=raw or source!="a"*40: raise ValueError("PRIVATE-SOURCE")
        return ctx
    def transport(chain,addr,*,timeout): calls.append(addr); return {"http_status":403,"body":b'{"message":"PRIVATE-CLI"}'}
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory); dataset=root/"dataset.json"; dataset.write_bytes(raw); plan=root/"plan.json"; output=root/"run"
        console=io.StringIO()
        with contextlib.redirect_stdout(console),contextlib.redirect_stderr(console):
            default=q.main([])
            planned=q.main(["plan","--dataset",str(dataset),"--source","a"*40,"--output",str(plan)],context_loader=loader)
            run_status=q.main(["run","--dataset",str(dataset),"--plan",str(plan),"--output",str(output)],
                              context_loader=loader,transport=transport,clock=Clock())
            report_status=q.main(["report","--output",str(output)])
        check("real quota CLI is default offline and plan/run/report usable",default!=0 and planned==0
              and run_status!=0 and report_status!=0 and len(calls)==1 and (output/"report.json").is_file())
        check("real quota CLI output is sanitized",all(s not in console.getvalue() for s in (
              "PRIVATE-CLI","PRIVATE-SOURCE",ctx["tokens"][0]["address"],str(dataset),"https://")))
        dataset.write_bytes(raw+b' ')
        with contextlib.redirect_stdout(io.StringIO()):
            status=q.main(["run","--dataset",str(dataset),"--plan",str(plan),"--output",str(root/"wrong")],
                          context_loader=loader,transport=transport,clock=Clock())
        check("CLI source mismatch refuses before transport",status!=0 and len(calls)==1)
        actual=Path(ROOT)/"bench/dataset.json"
        context=q.load_context(actual,"00a9a5c4c9c51dbb532b1f7696c88fd58a11ac66")
        check("real source loader binds the actual Git dataset blob",context["dataset_sha256"]==hashlib.sha256(actual.read_bytes()).hexdigest())
        try:
            q.load_context(dataset,"00a9a5c4c9c51dbb532b1f7696c88fd58a11ac66")
        except ValueError:
            refused=True
        else:
            refused=False
        check("real Git source mismatch is refused",refused)
    base=subprocess.check_output(["git","show","00a9a5c4c9c51dbb532b1f7696c88fd58a11ac66:tests/test_second_oracle.py"],cwd=ROOT).decode()
    current=Path(__file__).read_text(encoding="utf-8")
    prefix,suffix=base.split("\ndef main():\n",1)
    left,right=current.split("\ndef main():\n",1)
    check("all original oracle test bytes and runner remain frozen",left.startswith(prefix) and suffix==right)
    additions=ast.parse(left[len(prefix):]).body
    expected={"test_goplus_quota_plan_is_offline_fixed_and_source_bound", "test_goplus_quota_run_caps_pacing_and_utc_bounds",
              "test_goplus_quota_http_and_exact_result_stages", "test_goplus_quota_safe_output_and_private_raw",
              "test_goplus_quota_partial_intents_and_persistence", "test_goplus_quota_readout_denominators_and_limits",
              "test_goplus_quota_cli_and_existing_runner_contract"}
    check("exactly seven named additive functions run through the existing dynamic runner",len(additions)==7
          and all(isinstance(n,ast.FunctionDef) for n in additions) and {n.name for n in additions}==expected)


def main():
    print("=" * 70)
    print("second_oracle.py: the W5 check on the adversarial cohort, run safely")
    print("=" * 70)
    for name, fn in sorted((k, v) for k, v in globals().items() if k.startswith("test_")):
        try:
            fn()
        except Exception as e:  # noqa: BLE001 -- a crash is a failure, and the rest still run
            check("%s ran to the end" % name, False, "%s: %s" % (type(e).__name__, e))
    the_run_touched_nothing()
    print("\n" + "=" * 70)
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
