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
    ("R11", "Number the rounds", "4a1c27c",
     "A generated development log and a backlog whose every open item names how it "
     "will be verified, after an audit found drift in almost every hand-maintained "
     "record here and none in the two that are generated."),
    ("R12", "Measure a feature, then refuse to score it", "7a1a1c2",
     "Owner powers read from contract bytecode. Keccak-256 implemented so selectors "
     "are computed rather than remembered; measured over 417 contracts; found not to "
     "discriminate at n=9; disclosed as unscored evidence instead."),
    ("R13", "Withdraw a conclusion, and double the cohort it rested on", "0d390a8",
     "Told the sell simulator which chain we meant, which rescued Base WETH and its "
     "peers; found and fixed the regression that fix introduced an hour later; "
     "withdrew R12's finding after measuring the instrument at 31% recall; and grew "
     "the adversarial cohort from 9 to 17 by harvesting recent days."),
    ("R14", "Stop the token from writing inside our verdict", "4870424",
     "Deployed the P0 chain-hint fix that had sat unshipped since R10, then cleared "
     "all fourteen engine findings from the second external audit. The largest was "
     "not on the list: a token's own ticker was interpolated verbatim into the "
     "sentences an agent reads as this tool's verdict, so anyone could deploy a "
     "contract whose name argues for itself inside our output. Also: a request the "
     "JSON-RPC spec permits crashed /mcp, 53 of 53 minimal proxies read as 'not a "
     "proxy', a $0.000000000019 reserve was spent as a measured depth, the "
     "no-trace verdict was reached without knowing which chain it searched, and the "
     "bytecode cache the comments promised did not exist. Two verdicts moved out of "
     "572 -- the round corrected what the tool says, not what it concludes."),
    ("R15", "Guards that guard, and numbers that are watched", "83e34a6",
     "Cleared the audit's twelve M and G findings. Four published figures were guarded "
     "by nothing and all four flattered -- centralised-flagged-high read 6.7% against a "
     "measured 21.8% -- so the check was inverted to ask 'is every number guarded', not "
     "just 'does each guarded number match'. Four hand-maintained test runners were "
     "hiding tests from themselves, including CI's own step list. The 09-18 gate could "
     "be deleted with CI staying green, and a crawler could have passed it. And W1 was "
     "reopened: the measurement that closed it could not be re-run, so the script and "
     "250 contracts of bytecode are now committed -- measured against GoPlus's per-flag "
     "fields the scan finds 0% of pausable and 6% of mutable-tax (corrected in R17: that was 250 Base contracts holding 3 of the 19 pausable ones; on all of them it is 37%), and the selectors that "
     "would reproduce the original table detect a launch gate, not a pause switch."),
    ("R16", "Make the gate readable, then stop", "49d7548",
     "Instrumented /assess. `_record_call` was reachable only from `_handle_mcp`, so "
     "every HTTP request was invisible and the gate deciding whether to keep building "
     "had been reading one of the two interfaces the product exposes -- and the one an "
     "integrator reaches for first. Pinned the invariant that made adding telemetry "
     "safe: the token address is still never recorded. Then wrote Experiment C, the "
     "post that publishes the benchmark, and put its figures under the same guard as "
     "every other published number -- including the 10% dead-token recall it is built "
     "around, which was quoted in three places and computed in none. No engine "
     "features: every branch of the 09-18 gate says do Experiment C."),
    ("R17", "Fix the instrument, then freeze it", "b078d65",
     "An external audit read the gate's own output and found it printing YES on the "
     "developer's verification call made eight minutes earlier: SELF_CLIENTS was an "
     "exact-match set and `vetagent-r16-verify` was not in it. Three more of the same "
     "shape. `mozilla`, read for four days as a possible first adopter, is this "
     "project's own landing-page demo button. `request.cf` is a JsProxy, so "
     "`(cf or {}).get('country')` threw on every request ever served and STRATEGY "
     "reasoned three times from the premise that Cloudflare withheld the field. And "
     "`clientInfo` labels the handshake, not the tool call, because no session id is "
     "issued -- so R15's de-mushing applied only to the rows the gate discards. Fixed "
     "all four, plus the batch path and the LIMIT that printed a cap as a count, then "
     "froze the decision in `gate_verdict()` with the five conditions pinned in a test. "
     "Four counting rules have now been written for one gate, each after seeing what "
     "the last one produced. This is the last. Then the gate printed YES anyway -- on "
     "our own deploy pipeline, because CI smoke-tests production five times per deploy "
     "from a US runner under no client name. Fixed by naming our tooling rather than by "
     "moving the bar, and the landing page is now attributed by Origin so a cached copy "
     "of its JavaScript cannot hide browser clicks in `mozilla`. Also docs/OWNER.md, "
     "generated: the owner said they could not tell what needed them or by when, which "
     "was a fair complaint about eleven documents and nineteen W-numbers that answer "
     "everything except that."),
    ("R18", "Make the archive worth waiting for", "a3c52ad",
     "Listed the server where it can be found -- GitHub topics, mcp.so, Docker's MCP "
     "registry, two awesome lists -- then reviewed the daily collector across seven "
     "dimensions. It was discarding 14 of the 18 time-resolution buckets every response "
     "already carried, storing 5 of honeypot.is's 13 branches, recording an empty "
     "`flags` list because the real ones live under `summary`, blacklisting tokens it "
     "had never received an answer about, and letting an optional probe run between the "
     "irreplaceable pool rows being written and their commit. E11 again in two more "
     "places, one written the day before. W20 was rejected on a bad measurement, then "
     "the rejection was corrected on three of its own numbers. The archive's ceiling was "
     "measured and it is lower than claimed: 69% of new pools never trade $50k in a "
     "week, so they can never be labelled dead however long we wait. And the review "
     "itself cost 233 agents and the account's session limit, which produced "
     "`.claude/workflows/budgeted-review.js` and the rule that an agent count must never "
     "be a function of model output. **What that run did not cover was never written "
     "down, and is now:** its verify stage died with the session limit, so five of the "
     "seven dimensions were never adversarially checked at all. The findings were acted "
     "on anyway -- so some of the fixes above rest on findings nothing challenged, and "
     "whatever those five dimensions would have caught is still there. A review that "
     "reports its conclusions without its coverage is the same defect as a scan that "
     "says 'nothing found' without saying where it looked, and it was committed by the "
     "round that fixed that defect in two other places."),
    ("R19", "Point it outward, and correct what would be found", None,
     "The gate's failing branch says distribution, so the server was pointed at the "
     "places an agent might find it -- and everything it was pointed at turned out to "
     "need correcting first. The landing page carried a claim a commenter disproves in "
     "one minute, in three surfaces. The README asserted a directory grade as a frozen "
     "string. `find_new_hot_pools` answered `count: 20` beside three pools. There was no "
     "way to reach a person and no terms page. And the gate itself said YES on `mozilla` "
     "and `curl` -- our own homepage demo and our own deploy pipeline -- because thirteen "
     "of its fourteen days were written before the attribution fix; floored to rows the "
     "fixed instrument wrote, it reads no. Glama and Smithery went live, six more "
     "submissions are queued, and two were parked at a signup. The owner page gained the "
     "sections that let someone who cannot read the code decide whether to believe it."),
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
    """Map each commit to a round.

    Returns (order, meta, unassigned, bots). `meta[rid]["missing_last"]` is True when a
    closed round names a commit that is not in the history.

    That case is why this returns more than it used to. A round's closing hash can stop
    existing -- a rebase, an amend, a hash typed with a slip -- and then the cursor never
    advances past it, so every later commit piles into that one round. Nothing is left
    *unassigned*, which was the only thing the test checked, so the log silently reported
    thirty-five commits as one round and stayed green. The guard written to stop this
    project's records drifting had the same hole as the records.
    """
    rows = commits()
    order = [r[0] for r in ROUNDS]
    meta = {r[0]: {"name": r[1], "last": r[2], "blurb": r[3], "commits": []}
            for r in ROUNDS}

    seen_hashes = {c["hash"] for c in rows}
    for rid in order:
        last = meta[rid]["last"]
        meta[rid]["missing_last"] = bool(
            last and not any(h.startswith(last[:7]) for h in seen_hashes))

    idx = 0
    bots = 0
    unassigned = []
    closed = True          # bot commits are only counted while rounds are still closing
    for c in rows:
        if c["subject"].startswith(BOT_PREFIX):
            # Counted only up to the last closed round.
            #
            # The snapshot job commits every day, so a running total put a number in the
            # generated file that went stale every day -- and a guard that is red by
            # default is one people learn to ignore. Everything else in this document
            # changes only when a round closes; this now does too.
            if closed:
                bots += 1
            continue
        if idx >= len(order):
            unassigned.append(c)
            continue
        rid = order[idx]
        meta[rid]["commits"].append(c)
        if meta[rid]["last"] and c["hash"].startswith(meta[rid]["last"][:7]):
            idx += 1
        closed = idx < len(order) and meta[order[idx]]["last"] is not None
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
    A("\n%d snapshot-job commits are excluded up to the last closed round: they are "
      "data collection, not development, and would bury the rounds. The job commits "
      "daily, so counting them past that point would date this file every morning.\n"
      % bots)

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
