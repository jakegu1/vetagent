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
