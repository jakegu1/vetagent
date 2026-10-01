"""test_owner_page.py -- the owner's page has to be true on the day it is read.

`docs/OWNER.md` exists because the person paying for this project said, in plain terms,
that they could not tell what needed them, by when, or what any of it meant. It is the
one page in this repository written for someone who is not going to read the code.

That makes staleness worse here than anywhere else. A wrong deadline on the page whose
whole job is to carry deadlines is not a documentation bug; it is the page actively doing
the opposite of its purpose. So it is generated from the files that own each fact --
STRATEGY's gate table, BACKLOG's "Yours" section, SCORECARD's total, results.json -- and
this file fails the build the moment the generated text and the committed file disagree.

The second check is the one that matters more and is easy to forget: **every accuracy
number on the page must equal the benchmark's.** `publish_numbers.py` guards the files a
stranger reads. This page is what the owner reads, and it is the page they would quote.

Run:  python tests/test_owner_page.py
"""

import datetime
import io
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "bench"))

import owner  # noqa: E402
import publish_numbers  # noqa: E402

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


def _committed():
    p = os.path.join(ROOT, "docs", "OWNER.md")
    if not os.path.exists(p):
        return None
    return io.open(p, encoding="utf-8").read()


def test_the_page_is_current():
    """Generated and committed must agree, as of the day the page says it was generated.

    **It used to redden by itself every midnight, and did, at HEAD on 2026-09-12.**
    `tools/owner.py` renders "in N days" from `date.today()`, so a page generated yesterday
    disagrees with a regeneration today on every deadline it carries -- a red build from the
    clock, in the repository where CI was red for eight commits with nobody looking. A test
    that cries wolf on a schedule is worse than no test: it trains the owner to skip the one
    red that matters.

    So the comparison uses the date the page stamps on itself. Every number and every
    deadline is still compared exactly -- a wrong figure fails, a missed regeneration after
    a real change fails -- and only the passage of time is excused. Staleness is checked
    separately below, with slack, because "nobody has regenerated this in a week" and "this
    page is wrong" are different problems and deserve different alarms.
    """
    print("\n[owner] the page says what the sources say")
    have = _committed()
    check("docs/OWNER.md exists", have is not None,
          "run: python tools/owner.py --write")
    if have is None:
        return

    stamped = re.search(r"^> Generated (\d{4})-(\d{2})-(\d{2})", have, re.M)
    check("the page stamps the day it was generated", bool(stamped),
          "no '> Generated YYYY-MM-DD' line -- the comparison below needs it")
    if not stamped:
        return
    as_of = datetime.date(*(int(g) for g in stamped.groups()))

    # The page is only allowed to be behind the clock, never behind the sources. A week of
    # slack: the page is regenerated on essentially every commit, so seven quiet days means
    # the project is idle rather than that the page is wrong.
    age = (datetime.date.today() - as_of).days
    check("it was generated within the last 7 days", age <= 7,
          "stamped %s, %d days ago -- run: python tools/owner.py --write" % (as_of, age))

    want = owner.render(today=as_of)

    # Two blocks are a view of *now* rather than a claim derived from a file, so they
    # cannot be compared: the generation date, and the recent-commit list. The commit
    # list in particular cannot ever match at HEAD, because regenerating the page is
    # itself a commit that changes it -- the check would demand a state it destroys by
    # reaching. Everything else, which is every number and every date the owner acts on,
    # is compared exactly.
    def strip(t):
        t = re.sub(r"^> Generated .*$", "", t, flags=re.M)
        return re.sub(r"^## What changed in the last .*?(?=^## )", "", t,
                      flags=re.M | re.S)

    check("it is current", strip(have).strip() == strip(want).strip(),
          "regenerate it: python tools/owner.py --write")

    # The mask has to stay narrow, or the currency check quietly stops checking.
    masked = len(want) - len(strip(want))
    check("the exemption is a small part of the page, not most of it",
          masked < len(want) * 0.25, "%d of %d characters masked" % (masked, len(want)))
    check("only the two intended blocks are masked",
          "## Needs you" in strip(want) and "## What I got wrong" in strip(want))


def test_every_number_on_it_is_the_measured_one():
    """This is the page the owner would quote. It cannot carry a stale figure."""
    print("\n[owner] the numbers are the benchmark's, not last month's")
    have = _committed() or ""
    vals = publish_numbers.figures()
    for key, label in (("n", "tokens measured"),
                       ("fp_pct", "false positives"),
                       ("unknown_pct", "unknown rate"),
                       ("dead_high_pct", "dead rated high")):
        check("%s (%s) appears" % (label, vals[key]), vals[key] in have,
              "expected %s somewhere on the page" % vals[key])

    # The trap this guards: an older figure left behind next to the new one.
    for stale in ("3.7%", "11.3%", "21.0%", "17.2%", "6.7%"):
        if stale.rstrip("%") in (vals["fp_pct"], vals["unknown_pct"]):
            continue
        check("no stale %s" % stale, stale not in have)


def test_every_owner_item_has_a_reason_for_its_date():
    """A deadline with no reason is a guess, and the owner cannot argue with a guess."""
    print("\n[owner] each date says why it is that date")
    ids = {i["id"] for i in owner.yours()}
    missing = sorted(i for i in ids if i not in owner.OWNER_DUE)
    check("every open 'Yours' item is dated or explicitly undated", not missing,
          "add to OWNER_DUE in tools/owner.py: %s" % missing)
    for wid, (due, reason) in owner.OWNER_DUE.items():
        check("%s gives a reason" % wid, bool(reason and reason.strip()), wid)


def test_it_reads_the_real_gate_table():
    """If STRATEGY's dates move, this page moves. It does not keep its own copy."""
    print("\n[owner] the dates come from STRATEGY, not from a second list")
    gates = owner.gates()
    check("the gate table parsed", len(gates) >= 4, str(len(gates)))
    check("the 09-18 gate is in it",
          any(g["date"] == "2026-09-18" for g in gates), str(gates))
    src = io.open(os.path.join(ROOT, "tools", "owner.py"), encoding="utf-8").read()
    body = src.split("def gates(")[-1].split("def ")[0]
    check("it is parsed out of STRATEGY.md", "docs/STRATEGY.md" in body)


def test_the_archive_is_still_collecting():
    """A missed day is permanently unrecoverable, so it must fail a build, not a glance.

    The owner said he had no sense of whether the collector was running. The strip on the
    page answers that when someone looks; this answers it when nobody does. Upstream
    serves the current state only -- a day not collected on the day cannot be filled in --
    which makes this the one failure in the project that no later work can repair.

    Tolerance is deliberately two days, not one: the job is scheduled four times daily and
    GitHub has run it four to five hours late on every single occurrence, so "newest is
    yesterday" is the normal state and failing on it would be a test that cries wolf.
    """
    print("\n[owner] the archive has no holes and is not stalled")
    import datetime
    days, missing = owner.snapshot_days()

    check("the archive has days in it at all", bool(days), "no pools-*.ndjson found")
    if not days:
        return

    check("no day is missing between the first and the last", not missing,
          "GONE FOREVER: %s" % ", ".join(missing))

    last = datetime.date(*[int(x) for x in days[-1].split("-")])
    age = (datetime.date.today() - last).days
    check("the newest snapshot is not stale", age <= 2,
          "newest is %s, %d days old -- the collector has stopped" % (days[-1], age))

    page = owner.render()
    check("the strip reaches the owner page", "Is the archive still collecting?" in page)
    check("and a hole would be legible on it, not just counted",
          "permanently" in page.split("Is the archive still collecting?")[1][:900])


def test_the_diagrams_are_generated_and_cannot_drift():
    """A diagram is more persuasive than the prose it contradicts, so it must be generated.

    That is the whole reason these are emitted from `backlog_items()` and `gates()` rather
    than drawn. A hand-drawn architecture picture is the most dangerous document in a repo
    like this one: nobody re-reads it, everybody believes it, and no test can fail on it.

    This checks the three things that would make the pictures lie: a node for a closed
    item, a date the gate table does not have, and a chain the backlog does not state.
    """
    print("\n[owner] the pictures come from the same files as the tables")
    page = owner.render()

    check("both diagrams reach the page", page.count("```mermaid") == 2,
          "%d mermaid blocks" % page.count("```mermaid"))
    check("the gantt is there", "gantt" in page)
    check("the blocker graph is there", "flowchart LR" in page)

    items = owner.backlog_items()
    closed = {i["id"] for i in items
              if i["state"].lower().startswith(("done", "rejected"))}
    check("something is actually closed, or this proves nothing", bool(closed),
          str(sorted(closed)))

    graph = page.split("flowchart LR")[1].split("```")[0]
    for wid in sorted(closed):
        # Word-boundary match: W1 must not match inside W17.
        check("%s is closed, so it is not in the graph" % wid,
              not re.search(r"\b%s\b" % wid, graph), wid)

    # Every arrow the graph draws must be a chain the backlog states.
    stated = set()
    for i in items:
        for b in i["blocked_on"]:
            stated.add((b, i["id"]))
    for a, b in re.findall(r"(W\d+) -->\|blocks\| (W\d+)", graph):
        check("the backlog states that %s blocks %s" % (a, b), (a, b) in stated,
              "the picture invented an edge")

    # Every gate date on the timeline comes from STRATEGY, not from a second list.
    gantt = page.split("gantt")[1].split("```")[0]
    gate_dates = {g["date"] for g in owner.gates()}
    for d in re.findall(r"(\d{4}-\d{2}-\d{2}), 0d", gantt):
        check("%s is a real gate date" % d, d in gate_dates, "not in STRATEGY's table")
    check("every gate is on the timeline",
          len(re.findall(r", 0d", gantt)) == len(gate_dates),
          "%d drawn, %d gates" % (len(re.findall(r", 0d", gantt)), len(gate_dates)))

    # A label carrying markdown means the renderer will show the markup. It happened.
    for label in re.findall(r"\[([^\]]*)\]", graph) + re.findall(r"\{\{([^}]*)\}\}", graph):
        check("label is mermaid-safe: %r" % label[:34],
              not re.search(r"[`*_|]", label), label)

    # Hiding unconnected rows is correct; hiding them silently is not.
    check("the count of items left out of the picture is stated",
          re.search(r"\*\*\d+ other open item", page) is not None,
          "a diagram that drops rows without saying so reads as complete")


def test_a_correction_says_something_checkable():
    """W23. The staleness window proves an entry EXISTS. Nothing proved it SAID anything.

    A dated one-word entry satisfied the 14-day check, which means the section that exists
    to show the owner how much of the page to believe could be kept green by typing
    nothing. That is the same defect as a scan reporting "no findings" without saying where
    it looked, in the one place on the page whose job is to be uncomfortable.

    **What this cannot do, stated plainly rather than implied: it cannot tell whether a
    correction is true, or whether the important one was left out.** No test can. It sets
    a floor -- each entry must name a claim, a correction, and how it surfaced, and the
    correction must point at something concrete -- and above that floor the section is
    still worth exactly as much as the honesty of whoever wrote it. Publishing that
    limitation is more useful than a check that implies it was covered.
    """
    print("\n[W23] each correction names a claim, a truth, and a concrete anchor")
    import datetime

    seen_truths = set()
    for row in owner.CORRECTIONS:
        when, claimed, truth, caught = row
        tag = when

        # A real correction has three distinct parts, each of them a sentence.
        check("%s: the claim is stated, not gestured at" % tag, len(claimed.strip()) >= 30,
              repr(claimed[:40]))
        check("%s: the correction is stated" % tag, len(truth.strip()) >= 40,
              repr(truth[:40]))
        check("%s: how it surfaced is stated" % tag, len(caught.strip()) >= 25,
              repr(caught[:40]))

        # "I said X, and actually X" is not a correction.
        check("%s: the correction differs from the claim" % tag,
              claimed.strip().lower() != truth.strip().lower())

        # A correction with no referent is a gesture. Require the truth to point at
        # something a reader could go and check: a number, a path, an identifier, a date.
        anchored = bool(re.search(r"\d", truth) or "`" in truth or "/" in truth
                        or ".py" in truth or ".md" in truth)
        check("%s: the correction points at something checkable" % tag, anchored,
              repr(truth[:60]))

        # Two entries that say the same thing are one entry and a filler.
        key = truth.strip().lower()[:80]
        check("%s: it is not a repeat of another entry" % tag, key not in seen_truths,
              repr(truth[:50]))
        seen_truths.add(key)

        # "noticed it" is not a mechanism.
        vacuous = ("noticed", "found it", "by accident", "saw it", "realised")
        bare = caught.strip().lower().rstrip(".")
        check("%s: the mechanism is named, not waved at" % tag,
              bare not in vacuous and len(bare.split()) >= 4, repr(caught[:40]))

    # The list claims to be newest first, and a reader trusts the top entry is recent.
    dates = [datetime.date(*[int(x) for x in r[0].split("-")]) for r in owner.CORRECTIONS]
    check("the list is ordered newest first", dates == sorted(dates, reverse=True),
          str([d.isoformat() for d in dates]))


def test_a_cost_of_waiting_is_a_consequence_not_a_restatement():
    """W23. The orphan check proved a line EXISTS for every item. Not that it said anything.

    The cost line is the one an owner actually plans around, and it is the hardest thing
    on the page to write, so it is the likeliest to decay into a restatement of the task.
    This checks the two failures that would make it useless -- too short to carry a
    consequence, or merely echoing the item it belongs to -- and cannot check the third,
    which is being wrong.
    """
    print("\n[W23] the cost of waiting is its own sentence")
    items = {i["id"]: i["item"] for i in owner.yours()}
    items.update({a[0]: a[0] for a in owner.EXTRA_ACTIONS})

    seen = set()
    for key, cost in owner.COST_OF_WAITING.items():
        c = cost.strip()
        check("%s: the cost is a sentence, not a label" % key, len(c) >= 45, repr(c[:40]))
        check("%s: it ends as a sentence" % key, c.endswith("."), repr(c[-30:]))

        # A restatement of the task tells the owner nothing they did not already read.
        title = items.get(key, "")
        if title:
            tw = set(re.findall(r"[a-z]{4,}", title.lower()))
            cw = set(re.findall(r"[a-z]{4,}", c.lower()))
            overlap = len(tw & cw) / float(len(tw)) if tw else 0.0
            check("%s: it is not an echo of the item title" % key, overlap < 0.6,
                  "%.0f%% of the title's words reappear" % (overlap * 100))

        check("%s: it is not a copy of another item's cost" % key, c[:60] not in seen,
              repr(c[:50]))
        seen.add(c[:60])


def test_the_page_admits_recent_mistakes():
    """A status page that only ever carries good news should be read as marketing.

    The owner cannot audit this work. The one honest signal available to them is whether
    the errors arrive before someone else finds them, so the section reporting them is
    not optional and silence is not allowed to be free: if there were genuinely no
    mistakes in the window, that has to be written down as a dated claim, which is itself
    a thing that can turn out to be false.
    """
    print("\n[owner] recent mistakes are reported, and silence is not free")
    import datetime
    today = datetime.date.today()

    check("there is a corrections list at all", len(owner.CORRECTIONS) > 0)
    dates = []
    for row in owner.CORRECTIONS:
        check("every entry has date / claim / truth / how it surfaced", len(row) == 4,
              str(row)[:80])
        try:
            dates.append(datetime.date(*[int(x) for x in row[0].split("-")]))
        except (ValueError, TypeError):
            check("the date parses", False, row[0])

    if dates:
        newest = max(dates)
        age = (today - newest).days
        check("an entry inside the window, or the silence is on the record",
              age <= owner.CORRECTION_WINDOW,
              "newest is %s, %d days old, window is %d -- add an entry, or add a dated "
              "'nothing to report'" % (newest, age, owner.CORRECTION_WINDOW))
        check("nothing is dated in the future", newest <= today, str(newest))

    page = owner.render()
    check("the section reaches the page", "## What I got wrong" in page)
    check("and the freeze window is stated in it, not just in code",
          "every %d days" % owner.CORRECTION_WINDOW in page)


def test_every_owner_item_says_what_waiting_costs():
    """"When" and "what" are not enough to plan a week; "what if it slips" is.

    Judging that needs the domain knowledge the owner does not have, which is the reason
    this page exists at all. An item with no stated cost of waiting renders a visible
    placeholder rather than nothing, so the gap is legible on the page.
    """
    print("\n[owner] the cost of doing nothing is stated per item")
    page = owner.render()
    check("no item is silently missing its cost", "_not stated" not in page,
          "an owner item has no COST_OF_WAITING entry")
    check("the line is actually rendered", "**If you do nothing:**" in page)

    ids = set(owner.COST_OF_WAITING)
    live = set(t["id"] for t in owner.yours()) | set(a[0] for a in owner.EXTRA_ACTIONS)
    orphans = ids - live
    check("no cost is written for an item that no longer exists", not orphans,
          str(sorted(orphans)))


def test_no_jargon_reaches_the_owner_undefined():
    """Every specialist word on the page has an entry in the page's own glossary.

    This checks one direction only, on purpose. The first version also asserted the
    reverse -- that every glossary entry appears in the body -- and it went red on seven
    correct entries, which is how it was found to be wrong: `fail-closed`, `recall` and
    `held-out` are words the owner meets in the backlog, in commit messages and in
    conversation, not only here. A glossary is allowed to be a reference for terms
    encountered elsewhere. It is not allowed to be missing one that is used here.
    """
    print("\n[owner] no specialist word reaches the owner undefined")
    page = owner.render()
    body = page.split("## The words I keep using")[0]
    defined = " ".join(t for t, _ in owner.GLOSSARY).lower()

    # Each of these was a word the owner had to ask about, or one that carries a meaning
    # in this project which is not its ordinary English meaning.
    jargon = ("gate", "fail-closed", "recall", "held-out", "oracle", "mcp",
              "unknown", "false positive", "telemetry")
    for word in jargon:
        if word in body.lower():
            check("'%s' is used, so it must be defined" % word, word in defined,
                  "used on the page, missing from the glossary")


# ---------------------------------------------------------------------------------------
# T-009: the gates as the Owner reads them.
#
# The page generated on 2026-09-30 showed the answered 2026-09-18 gate as "**12 days
# OVERDUE**" in its gate table and in its timeline, the same alarm as a gate nobody answered,
# and no gate ever reached "Needs you", although from a gate's date
# tests/test_gates_get_reviewed.py fails the build, and so every deploy, until the gate's row
# carries a written conclusion and the entries parked until it are decided. Whether a row
# carries a conclusion is T-007's gate_row_answered, the one statement of that rule, and the
# page is judged against it here.
#
# None of these can turn red by itself as the calendar moves. Dates are forced on synthetic
# gate tables, parked entries and owner items, which reach the page through owner._read, the
# reader every source on it goes through, so nothing is written to disk. The real files are
# asked only what stays true: the 2026-09-18 gate is answered, and whatever the real table and
# the real parked entries say, the page and the guard read them alike. No test depends on the
# 2026-10-16 row staying unanswered: the Owner answers it on that date.

GUARD_FILE = os.path.join(ROOT, "tests", "test_gates_get_reviewed.py")
_RIGHT_ARROW = chr(0x2192)                   # the arrow the real table's action cells use
_COUNTDOWN = re.compile(r"OVERDUE|TODAY|tomorrow|in \d+ days")
# The template the page hands the Owner, inside its code span (the spec's Amendment).
_TEMPLATE = "`Resolved: <what the measurement said> -> <decision>`"

# Conclusions the rule accepts...
_ANSWERS = ("**Resolved:** the test said no -> continue per section 7",
            "Resolved: 0 trial commitments -> pick a different segment and run D again")
# ...and texts it refuses: nothing, a bare or placeholder Resolved:, the table's own U+2192
# arrow, and the page's own template pasted as it stands, with and without its code span.
_NOT_ANSWERS = ("", "Resolved:", "**Resolved:**", "Resolved: TBD", "Resolved: -> continue",
                "Resolved: 0 trial commitments %s pick a different segment" % _RIGHT_ARROW,
                _TEMPLATE.strip("`"), _TEMPLATE)

# One gate at each distance from _DAY, and what its countdown says that day.
_DAY = datetime.date(2026, 10, 16)
_DISTANCES = (("2026-10-15", "Gate one day past", "**1 days OVERDUE**"),
              ("2026-10-16", "Gate due today", "**TODAY**"),
              ("2026-10-17", "Gate due the next day", "**tomorrow**"),
              ("2026-10-26", "Gate in ten days", "**in 10 days**"),
              ("2026-10-30", "Gate in fourteen days", "**in 14 days**"),
              ("2026-10-31", "Gate in fifteen days", "in 15 days"))

# Owner items dated around 2026-10-16 for a gate row to be sorted among, in EXTRA_ACTIONS'
# shape: (what, due, why, done).
_OTHER_ROWS = [("Something due before the gate", "2026-10-10", "a reason", "a check"),
               ("Something due after the gate", "2026-10-20", "a reason", "a check"),
               ("Something with no date", "", "a reason", "a check")]

# A docs/BACKLOG.md with nothing under "## Yours", so no real item shares the list with a gate.
_NO_OWNER_ITEMS = "\n".join(["# Backlog (synthetic, written by tests/test_owner_page.py)", "",
                             "## Yours", "", "| # | Item | Why | Verify | State |",
                             "|---|---|---|---|---|", "", "## Mine", ""])


def _strategy(*rows):
    """A docs/STRATEGY.md whose section 8 table holds `rows`, each (date, question, text put
    after its action text). The action cells carry U+2192 arrows, as the real ones do."""
    lines = ["# Strategy (synthetic, written by tests/test_owner_page.py)", "",
             "## 8. Decision gates, and the standard we hold ourselves to", "",
             "| Date | Gate | Test | Action |", "|---|---|---|---|"]
    for date, question, text in rows:
        action = "Yes %s continue; no %s stop" % (_RIGHT_ARROW, _RIGHT_ARROW)
        lines.append("| %s | %s | a measurement | %s |"
                     % (date, question, (action + " " + text) if text else action))
    return "\n".join(lines + ["", "## 9. Metrics board", ""])


def _four_gates(text_1016=""):
    """The real table's four dates and questions: the 2026-09-18 row answered, the
    2026-10-16 row ending in `text_1016`, the two later rows unanswered."""
    return _strategy(("2026-09-18", "Is anyone using it", _ANSWERS[0]),
                     ("2026-10-16", "Does anyone want to pay", text_1016),
                     ("2026-12-04", "Is further investment worth it", ""),
                     ("2027-03-04", "Does the data asset hold up", ""))


def _opportunities(parked=(), closed=()):
    """A docs/OPPORTUNITIES.md. Each entry is (id, the gate date it waits for, or None for
    one that is not blocked): `parked` above "## Reviewed and closed", `closed` below it.
    Headings alternate the real file's two separators, a middle dot and a hyphen."""
    def entry(i, oid, date):
        wait = ("**Blocked until: gate %s** (a question)" % date if date
                else "**Not blocked** -- a tactic for the current product.")
        return ["### %s %s An idea written by a test" % (oid, "-" if i % 2 else chr(0xB7)),
                "", wait, "", "Why it waits, in one sentence.", ""]
    lines = ["# Parked Opportunities (synthetic, written by tests/test_owner_page.py)", "",
             "## Parked", ""]
    for i, (oid, date) in enumerate(parked):
        lines += entry(i, oid, date)
    lines += ["---", "", "## Reviewed and closed", ""]
    for i, (oid, date) in enumerate(closed):
        lines += entry(i, oid, date)
    return "\n".join(lines)


def _page(day, strategy=None, opportunities=None, backlog=None, extra=None):
    """owner.render(today=day), reading `strategy`, `opportunities` and `backlog` as
    docs/STRATEGY.md, docs/OPPORTUNITIES.md and docs/BACKLOG.md when they are given, and
    `extra` as EXTRA_ACTIONS; every other file is the real one. Both are put back after."""
    real_read, real_extra = owner._read, owner.EXTRA_ACTIONS
    swap = {"docs/STRATEGY.md": strategy, "docs/OPPORTUNITIES.md": opportunities,
            "docs/BACKLOG.md": backlog}

    def read(rel):
        return real_read(rel) if swap.get(rel) is None else swap[rel]

    owner._read = read
    if extra is not None:
        owner.EXTRA_ACTIONS = extra
    try:
        return owner.render(today=day)
    finally:
        owner._read, owner.EXTRA_ACTIONS = real_read, real_extra


_REFERENCE = []


def _reference_guard():
    """tests/test_gates_get_reviewed.py loaded here from its file, apart from the copy
    tools/owner.py loads: the reference for the rule, its parser and T-007's own cases."""
    if not _REFERENCE:
        import importlib.util
        spec = importlib.util.spec_from_file_location("t009_reference_guard", GUARD_FILE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _REFERENCE.append(module)
    return _REFERENCE[0]


def _real_gate_rows():
    """The rows of the real docs/STRATEGY.md section 8 table, whole, as the guard judges them."""
    whole = io.open(os.path.join(ROOT, "docs", "STRATEGY.md"), encoding="utf-8").read()
    start = whole.find("## 8. Decision gates")
    end = whole.find("\n## ", start + 1)
    section = whole[start:end if end > 0 else len(whole)] if start >= 0 else ""
    return [ln for ln in section.splitlines()
            if re.match(r"^\|\s*\d{4}-\d{2}-\d{2}\s*\|", ln)]


def _section(page, title):
    """The body of the page's `## <title>...` section, up to the next `## ` heading, or ""."""
    m = re.search(r"^## %s[^\n]*\n(.*?)(?=^## |\Z)" % re.escape(title), page, re.M | re.S)
    return m.group(1) if m else ""


def _gate_table_when(page, date):
    """The "When" cell of the gate table's row for `date`, or None."""
    m = re.search(r"^\| %s \| (.*?) \| " % re.escape(date),
                  _section(page, "The dates that decide things"), re.M)
    return m.group(1) if m else None


def _timeline_label(page, date):
    """The label of the timeline's milestone on `date`, or None."""
    parts = page.split("```mermaid\ngantt", 1)
    gantt = parts[1].split("```", 1)[0] if len(parts) == 2 else ""
    m = re.search(r"^    (.*) :milestone, %s, 0d$" % re.escape(date), gantt, re.M)
    return m.group(1) if m else None


def _reads_answered(label):
    """Whether a label says the gate is answered, with no countdown left in it."""
    return bool(label) and "answered" in label.lower() and not _COUNTDOWN.search(label)


def _needs_you_rows(page):
    """The rows of the "Needs you" table, each a list of its cells."""
    return [[c.strip() for c in ln.strip()[1:-1].split("|")]
            for ln in _section(page, "Needs you").splitlines()
            if ln.startswith("| ") and not ln.startswith("| When |")]


def _subsections(page):
    """Each `### ` subsection of "Needs you", as (heading, body)."""
    parts = re.split(r"^### ", _section(page, "Needs you"), flags=re.M)[1:]
    return [(p.split("\n", 1)[0].strip(), p.split("\n", 1)[1] if "\n" in p else "")
            for p in parts]


def _listed(page, question):
    """Whether "Needs you" names this gate question, in its table or a subsection heading."""
    return (any(question in " | ".join(r) for r in _needs_you_rows(page))
            or any(question in heading for heading, _ in _subsections(page)))


def _gate_subsection(page, question):
    """The body of the "Needs you" subsection whose heading names this question, or None."""
    bodies = [body for heading, body in _subsections(page) if question in heading]
    return bodies[0] if bodies else None


def _line(body, label):
    """What a subsection's `- **<label>:**` line says, or None."""
    m = re.search(r"^- \*\*%s:\*\* (.*)$" % re.escape(label), body, re.M)
    return m.group(1) if m else None


def _ids(text):
    return re.findall(r"\bO\d+\b", text)


def _shown(text):
    return ascii(text) if text else "no Resolved text"


def test_an_answered_gate_reads_as_answered():
    """T-009, AC 1: a gate whose row the rule accepts reads as answered, in the gate table's
    "When" cell and in its timeline label, with no OVERDUE, TODAY, tomorrow or "in N days".

    On 2026-09-30 the page said "**12 days OVERDUE**" of the answered 2026-09-18 gate in both
    places.
    """
    print("\n[T-009] an answered gate reads as answered")
    page = owner.render()
    for where, label in (("its When cell", _gate_table_when(page, "2026-09-18")),
                         ("its timeline label", _timeline_label(page, "2026-09-18"))):
        check("real files, today: the 2026-09-18 gate is answered, and %s says so" % where,
              _reads_answered(label), "got %s" % ascii(label))
    for text in _ANSWERS:
        page = _page(_DAY, _strategy(*[(d, q, text) for d, q, _ in _DISTANCES]),
                     _opportunities(), _NO_OWNER_ITEMS)
        for where, read in (("the gate table", _gate_table_when),
                            ("the timeline", _timeline_label)):
            wrong = [(d, read(page, d)) for d, _, _ in _DISTANCES
                     if not _reads_answered(read(page, d))]
            check("answered with %s: %s says answered, past, today, tomorrow and ahead"
                  % (ascii(text), where), not wrong, ascii(wrong))


def test_an_unanswered_gate_keeps_its_countdown():
    """T-009, AC 2: a gate whose row the rule refuses, a bare Resolved: included, shows in
    both places exactly what _when shows: OVERDUE after its date, TODAY, tomorrow, in N days.
    """
    print("\n[T-009] an unanswered gate keeps its countdown")
    for text in _NOT_ANSWERS:
        page = _page(_DAY, _strategy(*[(d, q, text) for d, q, _ in _DISTANCES]),
                     _opportunities(), _NO_OWNER_ITEMS)
        wrong = [(d, _gate_table_when(page, d), want) for d, _, want in _DISTANCES
                 if _gate_table_when(page, d) != want]
        check("%s: the gate table counts down as before" % _shown(text), not wrong,
              ascii(wrong))
        wrong = [(d, _timeline_label(page, d)) for d, q, want in _DISTANCES
                 if _timeline_label(page, d) != "%s - %s" % (q, want.replace("*", ""))]
        check("%s: the timeline counts down as before" % _shown(text), not wrong,
              ascii(wrong))


def test_a_gate_coming_due_is_in_needs_you():
    """T-009, AC 3 and the Amendment. An unanswered gate 14 days or less from its date, on it
    or past it is a row of "Needs you", sorted by date with the other rows, with a subsection
    of its own: what to do, what done looks like, and what doing nothing costs.

    On 2026-09-30 the list held the Owner's backlog items only, while from 2026-10-16 the build
    is red until that gate is answered and O2, O8, O9 and O11 are decided. The template is
    written inside a code span, never with &lt; and &gt;: T-007's guard removes entities
    without decoding them, so an entity-escaped template pasted into the row passes as a
    conclusion while it reads as the template (lead/reviews/T-007.md, round 2, minor note 1).
    """
    print("\n[T-009] a gate coming due is in Needs you")
    question = "Does anyone want to pay"
    opps = _opportunities(parked=(("O2", "2026-10-16"), ("O1", "2026-12-04"),
                                  ("O8", "2026-10-16"), ("O3", None)),
                          closed=(("O6", "2026-10-16"),))
    for day, when in ((datetime.date(2026, 10, 2), "**in 14 days**"),
                      (_DAY, "**TODAY**"),
                      (datetime.date(2026, 10, 17), "**1 days OVERDUE**")):
        tag = "%s, the 2026-10-16 gate unanswered" % day
        page = _page(day, _four_gates(), opps, _NO_OWNER_ITEMS, _OTHER_ROWS)
        rows = [r for r in _needs_you_rows(page) if question in " | ".join(r)]
        check("%s: it is a row of the table, due 2026-10-16, %s" % (tag, when.strip("*")),
              len(rows) == 1 and rows[0][:2] == [when, "2026-10-16"], ascii(rows))
        dues = [r[1] for r in _needs_you_rows(page) if len(r) > 1]
        check("%s: sorted by date with the other rows" % tag,
              dues == ["2026-10-10", "2026-10-16", "2026-10-20", "--"], ascii(dues))
        body = _gate_subsection(page, question)
        check("%s: it has a subsection of its own" % tag, body is not None,
              "no subsection heading names it")
        if body is None:
            continue
        do = _line(body, "What you do") or ""
        check("%s: it says what to do: read the question, write the conclusion" % tag,
              "question" in do and "conclusion" in do, ascii(do))
        done = _line(body, "You know it is done when") or ""
        for part in ("docs/STRATEGY.md", "section 8", _TEMPLATE, "docs/OPPORTUNITIES.md",
                     "decided", "moved under", "Reviewed and closed"):
            check("%s: 'done' says %s" % (tag, ascii(part)), part in done, ascii(done))
        check("%s: 'done' lists the two entries parked until it, O2 and O8" % tag,
              sorted(_ids(done)) == ["O2", "O8"], ascii(_ids(done)))
        cost = _line(body, "If you do nothing") or ""
        check("%s: doing nothing is a sentence of 45 characters or more" % tag,
              len(cost) >= 45 and cost.endswith("."), ascii(cost))
        for part in ("2026-10-16", "tests/test_gates_get_reviewed.py", "fails the build",
                     "every deploy"):
            check("%s: doing nothing says %s" % (tag, ascii(part)), part in cost, ascii(cost))
        listed = _section(page, "Needs you")
        check("%s: the list writes no entity-escaped bracket" % tag,
              "&lt;" not in listed and "&gt;" not in listed)
        outside = re.sub(r"`[^`\n]*`", "", body)
        check("%s: the template appears only inside a code span" % tag,
              "<what the measurement said>" not in outside and "<decision>" not in outside,
              ascii(outside))


def test_needs_you_has_no_answered_or_distant_gate():
    """T-009, AC 4: an answered (row and entries) gate, or one more than 14 days away, is not
    in "Needs you"."""
    print("\n[T-009] an answered or distant gate is not in Needs you")
    check("real files, today: the answered 2026-09-18 gate is not in Needs you",
          not _listed(owner.render(), "Is anyone using it"))
    opps = _opportunities(parked=(("O2", "2026-10-16"),))
    answered = _opportunities(closed=(("O2", "2026-10-16"),))
    for day, text, how, files in (
            (datetime.date(2026, 10, 2), _ANSWERS[1], "answered, 14 days away", answered),
            (_DAY, _ANSWERS[1], "answered, due today", answered),
            (datetime.date(2026, 10, 17), _ANSWERS[1], "answered, a day past", answered),
            (datetime.date(2026, 10, 1), "", "unanswered, 15 days away", opps),
            (datetime.date(2026, 9, 30), "Resolved:", "with a bare Resolved:, 16 days away",
             opps)):
        page = _page(day, _four_gates(text), files, _NO_OWNER_ITEMS)
        check("the 2026-10-16 gate %s (%s) is not in Needs you" % (how, day),
              not _listed(page, "Does anyone want to pay"))
        others = [q for q in ("Is anyone using it", "Is further investment worth it",
                              "Does the data asset hold up") if _listed(page, q)]
        check("  nor is the answered 2026-09-18 gate, or a gate 48 days away or more",
              not others, ascii(others))


def test_the_parked_entries_are_read_not_typed():
    """T-009, AC 5: the entries a gate's row lists are read from docs/OPPORTUNITIES.md: those
    above "## Reviewed and closed" whose "Blocked until: gate <date>" is the gate's date. A
    file with a different set gives a different list, and a gate with none says so. On the
    real file, at each real gate's date, the list is the guard's own reading of that file.
    """
    print("\n[T-009] the entries listed are read from docs/OPPORTUNITIES.md, not typed")
    question, day = "Does anyone want to pay", datetime.date(2026, 10, 2)

    def done_of(page, q=question):
        return _line(_gate_subsection(page, q) or "", "You know it is done when") or ""

    for how, opps, want in (
            ("two parked until it, among others", _opportunities(
                parked=(("O2", "2026-12-04"), ("O9", "2026-10-16"), ("O3", None),
                        ("O21", "2026-10-16")),
                closed=(("O8", "2026-10-16"),)), ["O21", "O9"]),
            ("one parked until it", _opportunities(parked=(("O13", "2026-10-16"),)),
             ["O13"])):
        done = done_of(_page(day, _four_gates(), opps, _NO_OWNER_ITEMS))
        check("a file with %s: the row lists %s" % (how, " and ".join(want)),
              sorted(_ids(done)) == want, ascii(done))
    none = _opportunities(parked=(("O1", "2026-12-04"), ("O3", None)),
                          closed=(("O2", "2026-10-16"),))
    done = done_of(_page(day, _four_gates(), none, _NO_OWNER_ITEMS))
    check("a file with none parked until it: the row says so, and lists none",
          re.search(r"\bno entr(?:y|ies)\b", done, re.I) is not None and not _ids(done),
          ascii(done))

    ref = _reference_guard()
    real = io.open(os.path.join(ROOT, "docs", "OPPORTUNITIES.md"), encoding="utf-8").read()
    dates = [re.match(r"^\|\s*(\d{4}-\d{2}-\d{2})", ln).group(1) for ln in _real_gate_rows()]
    check("the real gate table has dates to read the real file at", bool(dates))
    table = _strategy(*[(d, "Real gate %d" % i, "") for i, d in enumerate(dates)])
    for i, d in enumerate(dates):
        want = []
        for heading, gate, unblocked in ref.parse_entries(real):
            m = re.match(r"(O\d+)\b", heading)
            if gate == d and not unblocked and m:
                want.append(m.group(1))
        done = done_of(_page(datetime.date.fromisoformat(d), table, None, _NO_OWNER_ITEMS),
                       "Real gate %d" % i)
        if want:
            check("the real file, on %s: the row lists %s, as the guard reads it"
                  % (d, " ".join(sorted(want))), sorted(_ids(done)) == sorted(want),
                  ascii(done))
        else:
            check("the real file, on %s: nothing is parked until it, and the row says so" % d,
                  re.search(r"\bno entr(?:y|ies)\b", done, re.I) is not None
                  and not _ids(done), ascii(done))


def test_one_rule_says_whether_a_gate_is_answered():
    """T-009, AC 6: whether a gate is answered is T-007's gate_row_answered, called from
    tools/owner.py, not restated there.

    owner.gate_guard() is tests/test_gates_get_reviewed.py loaded from its file, and the page
    follows the rule in it both ways: a stand-in saying yes makes every gate answered, one
    saying no puts every gate back on its countdown and into "Needs you". Then the page and
    the rule, loaded here apart from the page's copy, agree on every row of T-007's
    acceptance criteria 1 and 2 and on every row of the real table.
    """
    print("\n[T-009] one rule says whether a gate is answered")
    loader = getattr(owner, "gate_guard", None)
    check("tools/owner.py loads the build's gate guard (owner.gate_guard)", callable(loader),
          "owner.gate_guard is not defined")
    if callable(loader):
        guard = loader()
        where = getattr(guard, "__file__", "") or ""
        check("  from tests/test_gates_get_reviewed.py",
              os.path.normcase(os.path.realpath(where))
              == os.path.normcase(os.path.realpath(GUARD_FILE)), ascii(where))
        rule, day = guard.gate_row_answered, datetime.date(2026, 10, 17)
        try:
            for answer in (True, False):
                guard.gate_row_answered = lambda row, answer=answer: answer
                page = _page(day, _four_gates(), _opportunities(), _NO_OWNER_ITEMS)
                for date, q, when in (
                        ("2026-09-18", "Is anyone using it", "**29 days OVERDUE**"),
                        ("2026-10-16", "Does anyone want to pay", "**1 days OVERDUE**")):
                    cell, label = _gate_table_when(page, date), _timeline_label(page, date)
                    if answer:
                        check("a stand-in rule saying yes: the %s gate reads as answered"
                              % date, _reads_answered(cell) and _reads_answered(label),
                              ascii((cell, label)))
                        check("  and is not in Needs you", not _listed(page, q))
                    else:
                        check("a stand-in rule saying no: the %s gate counts down, %s"
                              % (date, when.strip("*")),
                              cell == when and label == "%s - %s" % (q, when.strip("*")),
                              ascii((cell, label)))
                        check("  and is in Needs you", _listed(page, q))
        finally:
            guard.gate_row_answered = rule

    ref = _reference_guard()
    refused = getattr(ref, "_NOT_A_CONCLUSION", ())
    accepted = getattr(ref, "_A_CONCLUSION", ())
    build = getattr(ref, "_synthetic_strategy", None)
    check("T-007's acceptance-criteria 1 and 2 rows are there to compare on",
          bool(refused) and bool(accepted) and callable(build),
          "_NOT_A_CONCLUSION, _A_CONCLUSION or _synthetic_strategy is missing")
    if callable(build):
        for text, want in [(t, False) for t in refused] + [(t, True) for t in accepted]:
            strategy = build({"2026-10-16": text})
            row = [ln for ln in strategy.split("\n") if ln.startswith("| 2026-10-16 ")][0]
            said = ref.gate_row_answered(row)
            page = _page(datetime.date(2026, 10, 17), strategy, _opportunities(),
                         _NO_OWNER_ITEMS)
            shown = [_reads_answered(_gate_table_when(page, "2026-10-16")),
                     _reads_answered(_timeline_label(page, "2026-10-16"))]
            check("T-007's row with %s: the rule says %s, and so does the page"
                  % (_shown(text), want), said is want and shown == [want, want],
                  "the rule says %r, the page %r" % (said, shown))

    page = owner.render()
    rows = _real_gate_rows()
    check("the real gate table has rows to compare on", bool(rows))
    for row in rows:
        date = re.match(r"^\|\s*(\d{4}-\d{2}-\d{2})", row).group(1)
        said = ref.gate_row_answered(row)
        shown = [_reads_answered(_gate_table_when(page, date)),
                 _reads_answered(_timeline_label(page, date))]
        check("the real %s row: the page says what the rule says (%s)" % (date, said),
              shown == [said, said], "the page %r" % (shown,))


# ---------------------------------------------------------------------------------------
# T-010: the page lists a gate in "Needs you" for exactly as long as the guard would fail the
# build on it, says which half is left, and reads its gates from the section the guard reads.
#
# T-009's review (lead/reviews/T-009.md) found that a gate whose row is answered left "Needs
# you" while entries parked until it still turned the build red -- the real case is 2026-10-16,
# if the Owner writes the conclusion before deciding O2, O8, O9 and O11 -- and that the page
# took any four-cell dated row anywhere in docs/STRATEGY.md for a gate, while the guard reads
# section 8 only. Every case here is synthetic and its date forced, so none turns red by itself.

_Q = "Does anyone want to pay"


def _with_sources(fn, strategy=None, opportunities=None):
    """fn() with `strategy` and `opportunities` read as docs/STRATEGY.md and
    docs/OPPORTUNITIES.md when given; owner._read is put back after."""
    real_read = owner._read
    swap = {"docs/STRATEGY.md": strategy, "docs/OPPORTUNITIES.md": opportunities}
    owner._read = lambda rel: real_read(rel) if swap.get(rel) is None else swap[rel]
    try:
        return fn()
    finally:
        owner._read = real_read


def test_a_half_answered_gate_stays_in_needs_you():
    """T-010, AC 1: a gate in the window whose row is answered but which still has entries
    parked until it is a row of "Needs you", with a subsection that says the conclusion is
    written and that what is left is those entries, by id."""
    print("\n[T-010] a half-answered gate stays in Needs you")
    opps = _opportunities(parked=(("O2", "2026-10-16"), ("O1", "2026-12-04"),
                                  ("O8", "2026-10-16"), ("O3", None)),
                          closed=(("O6", "2026-10-16"),))
    for day, when in ((datetime.date(2026, 10, 2), "**in 14 days**"),
                      (_DAY, "**TODAY**"),
                      (datetime.date(2026, 10, 17), "**1 days OVERDUE**")):
        tag = "%s, the 2026-10-16 row answered, O2 and O8 still parked" % day
        page = _page(day, _four_gates(_ANSWERS[1]), opps, _NO_OWNER_ITEMS, _OTHER_ROWS)
        rows = [r for r in _needs_you_rows(page) if _Q in " | ".join(r)]
        check("%s: it is a row of the table, due 2026-10-16, %s" % (tag, when.strip("*")),
              len(rows) == 1 and rows[0][:2] == [when, "2026-10-16"], ascii(rows))
        body = _gate_subsection(page, _Q)
        check("%s: it has a subsection of its own" % tag, body is not None,
              "no subsection heading names it")
        if body is None:
            continue
        do = _line(body, "What you do") or ""
        check("%s: 'what you do' says the conclusion is written" % tag,
              "conclusion" in do and "written" in do, ascii(do))
        check("%s: 'what you do' names what is left, O2 and O8" % tag,
              sorted(_ids(do)) == ["O2", "O8"], ascii(do))
        check("%s: it does not ask for the conclusion again" % tag,
              re.search(r"\bwrite\b", do) is None and _TEMPLATE not in body
              and "Resolved:" not in body, ascii(body))
        done = _line(body, "You know it is done when") or ""
        check("%s: 'done' names only the entries, O2 and O8" % tag,
              sorted(_ids(done)) == ["O2", "O8"] and "docs/STRATEGY.md" not in done
              and "decided" in done and "Reviewed and closed" in done, ascii(done))
        cost = _line(body, "If you do nothing") or ""
        for part in ("From 2026-10-16", "tests/test_gates_get_reviewed.py", "fails the build",
                     "every deploy"):
            check("%s: doing nothing keeps T-009's sentence, %s" % (tag, ascii(part)),
                  part in cost, ascii(cost))
        for where, read in (("the gate table", _gate_table_when),
                            ("the timeline", _timeline_label)):
            check("%s: %s still reads the row as answered" % (tag, where),
                  _reads_answered(read(page, "2026-10-16")), ascii(read(page, "2026-10-16")))


def test_entries_done_row_not_is_listed_as_before():
    """T-010, AC 2: a gate in the window with no entry parked until it and an unanswered row
    is listed as T-009 lists it: write the conclusion, and nothing else."""
    print("\n[T-010] entries done, row not: listed as T-009 lists it")
    opps = _opportunities(parked=(("O1", "2026-12-04"),), closed=(("O2", "2026-10-16"),))
    page = _page(_DAY, _four_gates(), opps, _NO_OWNER_ITEMS)
    check("the 2026-10-16 gate is in Needs you", _listed(page, _Q))
    body = _gate_subsection(page, _Q) or ""
    do = _line(body, "What you do") or ""
    check("'what you do' asks for the conclusion",
          "question" in do and "conclusion" in do, ascii(do))
    done = _line(body, "You know it is done when") or ""
    want = ("its row in `docs/STRATEGY.md` section 8 carries %s, and nothing else: no entry "
            "of `docs/OPPORTUNITIES.md` is parked until this gate." % _TEMPLATE)
    check("'done' is T-009's line", done == want, ascii(done))


def test_a_fully_answered_gate_leaves_needs_you():
    """T-010, AC 3: an answered row with no entry parked until it is not in "Needs you", on
    any date; its labels read answered."""
    print("\n[T-010] a fully answered gate leaves Needs you")
    opps = _opportunities(closed=(("O2", "2026-10-16"),))
    for day in (datetime.date(2026, 10, 2), _DAY, datetime.date(2026, 10, 17),
                datetime.date(2027, 1, 1)):
        page = _page(day, _four_gates(_ANSWERS[1]), opps, _NO_OWNER_ITEMS)
        check("%s: the fully answered 2026-10-16 gate is not in Needs you" % day,
              not _listed(page, _Q))
        check("%s: and reads as answered" % day,
              _reads_answered(_gate_table_when(page, "2026-10-16"))
              and _reads_answered(_timeline_label(page, "2026-10-16")))


def test_one_entry_reads_as_one():
    """T-010, AC 4: one parked entry is "the entry ... is decided"; two or more are "the
    entries ... are each decided"."""
    print("\n[T-010] one entry reads as one")
    for ids in (("O13",), ("O2", "O8"), ("O2", "O8", "O9", "O11")):
        opps = _opportunities(parked=tuple((i, "2026-10-16") for i in ids))
        for how, text in (("unanswered", ""), ("answered", _ANSWERS[1])):
            page = _page(datetime.date(2026, 10, 2), _four_gates(text), opps, _NO_OWNER_ITEMS)
            done = _line(_gate_subsection(page, _Q) or "", "You know it is done when") or ""
            tag = "%s, %d entr%s" % (how, len(ids), "y" if len(ids) == 1 else "ies")
            check("%s: 'done' lists %s" % (tag, " ".join(ids)),
                  _ids(done) == list(ids), ascii(done))
            if len(ids) == 1:
                ok = ("%s, the entry of `docs/OPPORTUNITIES.md` parked until this gate, is "
                      "decided and moved under `## Reviewed and closed`" % ids[0]) in done
                ok = ok and "entries" not in done and "are each" not in done
            else:
                ok = ("the entries of `docs/OPPORTUNITIES.md` parked until this gate, are "
                      "each decided and moved under `## Reviewed and closed`") in done
                ok = ok and "%s, the entries" % ids[-1] in done
            check("%s: the grammar agrees with the count" % tag, ok, ascii(done))


def _stray_strategy(section_8=True):
    """A docs/STRATEGY.md with a four-cell dated row above section 8 and one in section 9,
    both in the window on 2026-10-16 and unanswered. Without `section_8`, its heading is
    renamed so that no section 8 exists."""
    action = "Yes %s continue; no %s stop" % (_RIGHT_ARROW, _RIGHT_ARROW)
    head = ("## 8. Decision gates, and the standard we hold ourselves to" if section_8
            else "## 8. Dates we decide on")
    return "\n".join([
        "# Strategy (synthetic, written by tests/test_owner_page.py)", "",
        "## 7. Roadmap", "",
        "| Date | Step | Test | Action |", "|---|---|---|---|",
        "| 2026-10-14 | Stray question above section 8 | a measurement | %s |" % action, "",
        head, "",
        "| Date | Gate | Test | Action |", "|---|---|---|---|",
        "| 2026-10-16 | %s | a measurement | %s |" % (_Q, action),
        "| 2026-12-04 | Is further investment worth it | a measurement | %s |" % action, "",
        "### 8.1 A subsection inside section 8", "",
        "Text that stays inside section 8.", "",
        "## 9. Metrics board", "",
        "| Date | Metric | Test | Action |", "|---|---|---|---|",
        "| 2026-10-20 | Stray question in section 9 | a measurement | %s |" % action, ""])


def test_gates_come_from_section_8_only():
    """T-010, AC 5: gates() reads section 8 only, bounded as the guard bounds it, so a dated
    row elsewhere reaches neither the gate table, the timeline nor "Needs you"; and with no
    section 8 there are no gates. On the real file the four gates are unchanged."""
    print("\n[T-010] gates come from section 8 only")
    got = [g["date"] for g in _with_sources(owner.gates, _stray_strategy())]
    check("a synthetic file: gates() returns the two section 8 rows only",
          got == ["2026-10-16", "2026-12-04"], ascii(got))
    page = _page(_DAY, _stray_strategy(), _opportunities(), _NO_OWNER_ITEMS)
    check("  and the page never shows a stray row",
          "Stray question" not in page, ascii(re.findall(r".*Stray question.*", page)))
    for date in ("2026-10-14", "2026-10-20"):
        check("  %s is in neither the gate table nor the timeline" % date,
              _gate_table_when(page, date) is None and _timeline_label(page, date) is None)
    check("  while the section 8 gate due that day is in Needs you", _listed(page, _Q))
    got = _with_sources(owner.gates, _stray_strategy(section_8=False))
    check("without a section 8 heading, gates() returns no gates", got == [], ascii(got))
    page = _page(_DAY, _stray_strategy(section_8=False), _opportunities(), _NO_OWNER_ITEMS)
    check("  and the page shows none of the dated rows",
          "Stray question" not in page and not _listed(page, _Q))
    real = [g["date"] for g in owner.gates()]
    check("the real file: the four gates are unchanged",
          real == ["2026-09-18", "2026-10-16", "2026-12-04", "2027-03-04"], ascii(real))


def test_the_page_agrees_with_the_guard():
    """T-010, AC 6: from 14 days before a gate's date on, it is in "Needs you" exactly when,
    run on its date or later, the guard's due-gate check (gate_row_answered on its row) or
    its parked-entry check (parse_entries) would fail on it. Both are the guard's own,
    loaded here apart from the page's copy."""
    print("\n[T-010] the page lists a gate exactly when the guard would fail on it")
    ref = _reference_guard()
    rows = (("answered", _ANSWERS[1]), ("unanswered", ""), ("a bare Resolved:", "Resolved:"))
    files = (("an entry parked until it", _opportunities(parked=(("O2", "2026-10-16"),))),
             ("its entry closed", _opportunities(closed=(("O2", "2026-10-16"),))),
             ("an entry parked until another gate",
              _opportunities(parked=(("O1", "2026-12-04"),))),
             ("no entries at all", _opportunities()))
    days = ((15, datetime.date(2026, 10, 1)), (14, datetime.date(2026, 10, 2)),
            (0, _DAY), (-1, datetime.date(2026, 10, 17)))
    for row_how, text in rows:
        strategy = _four_gates(text)
        row = [ln for ln in strategy.split("\n") if ln.startswith("| 2026-10-16 ")][0]
        for file_how, opps in files:
            open_entries = [h for h, gate, unblocked in ref.parse_entries(opps)
                            if gate == "2026-10-16" and not unblocked]
            fails = ref.gate_row_answered(row) is not True or bool(open_entries)
            for away, day in days:
                want = away <= owner.GATE_NOTICE_DAYS and fails
                got = _listed(_page(day, strategy, opps, _NO_OWNER_ITEMS), _Q)
                check("row %s, %s, %d days away: listed %s, as the guard says"
                      % (row_how, file_how, away, want), got == want,
                      "the page listed it: %s" % got)


def main():
    print("=" * 68)
    print("Owner page: the one document written for someone not reading code")
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
