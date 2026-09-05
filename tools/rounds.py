"""rounds.py -- generate docs/ROUNDS.md from git history.

Usage:
    python tools/rounds.py            # print, and report unassigned commits
    python tools/rounds.py --write    # regenerate docs/ROUNDS.md

Why this is generated rather than written
-----------------------------------------
The ask was for a numbered development log: what each round changed, what it left
behind, what comes next. The obvious way to do that is an eighth hand-maintained
document, and this repository has just finished paying for the first seven.

An external audit went through every hand-maintained record here and found drift in
almost all of them: four decision ids used twice, three stale test counts, a misspelled
domain, a comment claiming figures were verified against a registry nobody had checked,
and accuracy numbers on the public site three generations out of date. The only two
documents that had never drifted -- SCORECARD.md and results.md -- are the two nobody
types.

So the round log is generated. The source of truth is the commit history, which already
carries the reasoning, the measurements and the admissions of error, and which cannot
drift from itself. The score trajectory is read out of `docs/SCORECARD.md` **as it stood
at each round's final commit**, so even the numbers are recovered rather than restated.

What has to be maintained by hand is one line per round: its name and its last commit.
`ROUNDS` below is that list. The final entry has `last=None`, meaning "everything since
the previous round" -- so new work lands in the open round automatically and the log is
never incomplete. Closing a round is filling in one hash and opening the next.

tests/test_rounds.py checks that every commit belongs to exactly one round and that the
generated file is current.
"""

import argparse
import io
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "docs", "ROUNDS.md")

# Commits made by the snapshot job. They are data collection, not development, and
# grouping them into rounds would bury the rounds in them.
BOT_PREFIX = "Snapshot 20"

# (id, name, last commit of the round, one line on what it was for).
# The last entry's `last` is None: the round still open.
ROUNDS = [
    ("R1", "Ship something that answers", "05ebfc5",
     "A working MCP server on its own domain: risk engine, landing page, registry "
     "manifest, integration guide."),
    ("R2", "Find out it was lying", "17a52ae",
     "The honeypot check read a key upstream does not have, so it had always passed. "
     "First test suite, and a handoff document written because the record was wrong."),
    ("R3", "Measure instead of assert", "652d56e",
     "Accuracy benchmark with held-out labels and an ablation column, an operating "
     "strategy with dated decision gates, English throughout, deploys moved to CI."),
    ("R4", "Look outward, and find three more defects", "d237c62",
     "Market research, a maturity scorecard, usage measurement, the site rewritten for "
     "citation -- and the discovery that the benchmark's independence assertion had been "
     "comparing against an empty set."),
    ("R5", "Stop the analysis from redirecting the project", "92dbc63",
     "The parking rule and its test, after research nearly repositioned the product "
     "fourteen days before the gate that would have answered the question."),
    ("R6", "Detect the loss agents actually take", "932c39d",
     "Same-ticker impersonation, and an end to answering unknown for tokens the engine "
     "could see in full."),
    ("R7", "Audit my own work, adversarially", "59d5be2",
     "Seventy-two agents told to refute rather than confirm. Two critical defects, both "
     "shipped that morning under a green suite."),
    ("R8", "Make recall measurable", "bbefed8",
     "Pool history recovered from the chain, so the dead cohort could exist at all. "
     "Labelled set 207 -> 558, and the first recall figure -- which turned out to mean "
     "something other than expected."),
    ("R9", "Stop the instrument reporting its own failures", "90ec3cb",
     "The harness was provoking upstream refusals and scoring them as the engine "
     "declining to judge. LP-burn detection measured and rejected."),
    ("R10", "External audit, and closing all seventeen findings", "cfa6cb5",
     "A stronger model audited the repository against a brief written for it. Two HIGH "
     "regressions from that same day, and an oracle whose own flag was unfalsifiable."),
    ("R11", "Number the rounds", None,
     "This one."),
]


def git(*args):
    return subprocess.run(["git"] + list(args), cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8", errors="replace").stdout


def commits():
    """Every commit, oldest first, in parent order rather than by date.

    Topological order matters: rebases and the snapshot bot leave timestamps that do not
    match the order things actually landed, and a log ordered by date would put commits
    in rounds that had already closed.
    """
    out = git("log", "--reverse", "--topo-order", "--pretty=format:%h%x1f%ad%x1f%s",
              "--date=format:%Y-%m-%d")
    rows = []
    for line in out.splitlines():
        parts = line.split("\x1f")
        if len(parts) == 3:
            rows.append({"hash": parts[0], "date": parts[1], "subject": parts[2]})
    return rows


def assign():
    """Map each commit to a round. Returns (ordered rounds, unassigned, bot count)."""
    rows = commits()
    order = [r[0] for r in ROUNDS]
    meta = {r[0]: {"name": r[1], "last": r[2], "blurb": r[3], "commits": []}
            for r in ROUNDS}

    idx = 0
    bots = 0
    unassigned = []
    for c in rows:
        if c["subject"].startswith(BOT_PREFIX):
            bots += 1
            continue
        if idx >= len(order):
            unassigned.append(c)
            continue
        rid = order[idx]
        meta[rid]["commits"].append(c)
        if meta[rid]["last"] and c["hash"].startswith(meta[rid]["last"][:7]):
            idx += 1
    return order, meta, unassigned, bots


def score_at(commit):
    """The maturity score as it stood at that commit, read out of git."""
    if not commit:
        blob = io.open(os.path.join(ROOT, "docs", "SCORECARD.md"),
                       encoding="utf-8").read()
    else:
        blob = git("show", "%s:docs/SCORECARD.md" % commit)
    m = re.search(r"## Total: \*\*(\d+) / 100\*\*", blob or "")
    return int(m.group(1)) if m else None


def render():
    order, meta, unassigned, bots = assign()
    L = []
    A = L.append
    A("# Development rounds (ROUNDS.md)\n")
    A("> Generated by `python tools/rounds.py --write`. **Do not edit by hand.**\n")
    A("> The source is the commit history. Every commit belongs to exactly one round, "
      "and `tests/test_rounds.py` fails if one does not -- so this log cannot be "
      "incomplete, rather than relying on someone remembering to append to it.\n")
    A("\nThe maturity score for each round is read from `docs/SCORECARD.md` **as it "
      "stood at that round's final commit**, so the trajectory is recovered from git "
      "rather than restated here.\n")

    A("\n## At a glance\n")
    A("| Round | Name | Commits | Dates | Score after |")
    A("|---|---|---|---|---|")
    prev = None
    for rid in order:
        m = meta[rid]
        cs = m["commits"]
        # The open round is skipped here as well as below. Its commit count changes with
        # every commit, so including it would leave this file stale by construction --
        # and a guard that is red by default is one people learn to ignore.
        if not cs or m["last"] is None:
            continue
        sc = score_at(m["last"])
        delta = ""
        if sc is not None and prev is not None:
            delta = " (%+d)" % (sc - prev)
        if sc is not None:
            prev = sc
        span = cs[0]["date"] if cs[0]["date"] == cs[-1]["date"] \
            else "%s to %s" % (cs[0]["date"], cs[-1]["date"])
        A("| **%s** | %s | %d | %s | %s%s |"
          % (rid, m["name"], len(cs), span,
             ("%d/100" % sc) if sc is not None else "not scored yet", delta))
    A("\n%d snapshot-job commits are excluded: they are data collection, not "
      "development, and would bury the rounds.\n" % bots)

    open_id = next((r for r in order if meta[r]["last"] is None), None)
    if open_id:
        A("\n**%s -- %s** is open: %s Its commits are listed here once it closes."
          % (open_id, meta[open_id]["name"], meta[open_id]["blurb"]))

    for rid in order:
        m = meta[rid]
        if not m["commits"] or m["last"] is None:
            continue
        A("\n---\n")
        A("\n## %s -- %s%s\n" % (rid, m["name"], "" if m["last"] else "  *(open)*"))
        A("\n%s\n" % m["blurb"])
        A("\n| Commit | Date | Change |")
        A("|---|---|---|")
        for c in m["commits"]:
            A("| `%s` | %s | %s |" % (c["hash"], c["date"], c["subject"]))
        A("\nFull reasoning for any line above: `git show <hash>`. The commit messages "
          "carry the measurement that motivated each change, and several admissions of "
          "error.\n")

    if unassigned:
        A("\n---\n")
        A("\n## Not yet assigned to a round\n")
        A("\n**This should be empty.** Add these to the open round in `tools/rounds.py`.\n")
        for c in unassigned:
            A("- `%s` %s -- %s" % (c["hash"], c["date"], c["subject"]))
    return "\n".join(L) + "\n", unassigned


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    text, unassigned = render()
    if args.write:
        io.open(OUT, "w", encoding="utf-8", newline="").write(text)
        print("wrote %s" % OUT)
    else:
        print(text)

    if unassigned:
        print("\n%d commit(s) belong to no round." % len(unassigned))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
