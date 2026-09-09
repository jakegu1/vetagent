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
    """Generated and committed must agree, apart from the date it was generated on."""
    print("\n[owner] the page says what the sources say")
    have = _committed()
    check("docs/OWNER.md exists", have is not None,
          "run: python tools/owner.py --write")
    if have is None:
        return
    want = owner.render()

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
