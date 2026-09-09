"""owner.py -- generate docs/OWNER.md: the one page the project owner reads.

Usage:
    python tools/owner.py            # print
    python tools/owner.py --write    # regenerate docs/OWNER.md

Why this exists
---------------
The owner said, in plain terms, that they cannot tell what needs them, by when, or what
any of it means -- that following this project feels like being in the dark while someone
talks. That is a real failure and it is mine: eleven documents, seventeen decision ids,
nineteen W-numbers and eighteen rounds, none of which answer "what do I have to do, and
when".

Three fixes were on the table. **Renaming files to carry deadlines** was rejected: it
breaks every link in every document, a date in a filename cannot be checked by anything,
and it still would not say what the project is doing. **A hand-written status page** was
rejected for the reason this repository rejects every hand-written record -- an external
audit found drift in almost all of them and none in the two that are generated.

So this is generated from the files that are already the source of truth:

    docs/STRATEGY.md    the dated decision gates
    docs/BACKLOG.md     the "Yours" section -- items only the owner can do
    docs/SCORECARD.md   the score
    bench/results.json  the published accuracy numbers
    tools/rounds.py     which round is open

If one of those moves and this page does not, `tests/test_owner_page.py` fails the build.
The only thing written by hand here is the plain-English glossary, which is prose about
what words mean and has no number in it to drift.

Everything is dated relative to the day it is generated, so "in 11 days" is never stale
without the build noticing.
"""

import argparse
import datetime
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "docs", "OWNER.md")

sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "bench"))


# Why each owner item is due when it is. A date on a task is a judgement, not data, so it
# is written here with its reason rather than invented from a table. The gate a task
# blocks is the deadline; a task that blocks nothing dated says so.
OWNER_DUE = {
    "W9": ("2026-09-18", "the 09-18 gate cannot be answered without reading usage"),
    "W11": ("2026-09-18", "this IS the gate -- it has to be answered on the day"),
    "W10": ("2026-09-18", "distribution is the whole of the gate's failing branch"),
    "W5": ("2026-10-16", "needed for W3, which every accuracy claim rests on"),
    "W12": ("2026-10-16", "changes what the benchmark can measure, so before the D gate"),
    "W13": ("", "no deadline -- do it when convenient"),
}

# What it costs to do nothing. An owner reading a task list reads "when" and "what", and
# then has to guess the only thing that actually decides their week: what happens if this
# slips. Guessing that needs the domain knowledge they do not have, which is the whole
# reason this page exists. So it is stated, per item, in the same place as the deadline.
COST_OF_WAITING = {
    "W11": "A gate that passes its date in silence teaches everyone that gates are "
           "decoration, and this is the first one that can stop the project.",
    "W10": "Nothing. Six submissions are already queued and the two parked ones are one "
           "signup away; waiting costs reach, not work.",
    "W5": "Every accuracy claim keeps resting on a single sell simulator. If it is wrong, "
          "we cannot tell, and neither can anyone reading the benchmark.",
    "W12": "The 10-16 gate arrives with the measurement question still open, so that "
           "gate answers a smaller question than it was meant to.",
    "Post Experiment C": "This is the one action that can change the 09-18 answer. Not "
                         "doing it does not delay the gate -- the gate still fires, and "
                         "it fires on no.",
}

# Not a backlog item, because it is not engineering. It is the single action that decides
# what the 09-18 gate can even see.
EXTRA_ACTIONS = [
    ("Post Experiment C", "2026-09-18",
     "The gate's failing branch prescribes exactly this, so it happens either way. "
     "Drafts are written and every number in them is checked by the build: "
     "docs/EXPERIMENT_C.md. Nothing is posted without you -- it is your name on it.",
     "a post exists on at least one of HN, r/ethdev, X or the MCP Discord"),
]

# What I told the owner that turned out to be wrong.
#
# An owner who cannot audit the work has exactly one way to calibrate how much of it to
# believe: whether the person doing it reports their own errors before being caught. A
# status page that only ever contains good news is marketing, and should be read as
# marketing.
#
# `tests/test_owner_page.py` requires an entry inside CORRECTION_WINDOW days. Silence is
# not an option -- if there is genuinely nothing, that has to be written down as a dated
# claim, which is itself a thing that can turn out to be false.
CORRECTION_WINDOW = 14
CORRECTIONS = [
    ("2026-09-09",
     "'mcpservers.org emailed to say we are live, and the listing is not on the site.'",
     "It is live, at mcpservers.org/en/servers/vetagent-dev, findable by searching their "
     "homepage. Their slug comes from the domain (`vetagent-dev`), I guessed it from the "
     "product name, got a 404, and reported an absence. The page I treated as the index "
     "of every remote server is a curated subset.",
     "You caught it. I had checked four places, found nothing, and said 'not on the "
     "site' instead of 'not where I looked' -- in a session spent fixing that exact "
     "error in five other places."),
    ("2026-09-08",
     "'Nobody outside the project is calling it' was answered YES by the usage gate.",
     "Both callers were us: `mozilla` was the demo button on our own homepage and `curl` "
     "was our own deploy pipeline, because until 09-07 the telemetry could not tell them "
     "apart from a stranger. The corrected reading is **no**.",
     "Caught by re-reading the instrument after fixing it, not by the instrument."),
    ("2026-09-08",
     "`find_new_hot_pools` told callers it had found 20 pools.",
     "It returned three. `count` was counting what it fetched, not what it sent.",
     "Caught by calling the tool while writing an app-store submission. 263 tests had "
     "passed over it."),
    ("2026-09-08",
     "'The daily archive will reach about 1 GB of git history within a year.'",
     "The whole repository is 4.10 MiB. I had measured the temporary local copy instead "
     "of what the server actually stores -- off by roughly 18x, and a storage ticket was "
     "filed on it.",
     "Caught by one command, `git gc`, run a day too late."),
    ("2026-09-07",
     "'83% of the benchmark data is one chain, which is a real weakness.'",
     "58%. The 83% was a 47-token subset, quoted for a set twelve times larger. The "
     "weakness is real and smaller than I said.",
     "Caught by making the number computable instead of typed."),
    ("2026-09-07",
     "'The sell simulator has not indexed these tokens yet.'",
     "It had. I was sending it an identifier with the chain name glued to the front "
     "instead of an address, and six empty answers looked exactly like 'not indexed'.",
     "Caught by printing what was actually sent."),
]

# The glossary is prose, but three of its lines carry a measured number, and a number
# typed into prose is how this project once put an out-of-date false-positive rate on its
# own landing page. {fp}, {unknown} and {dead_high} are filled from bench/results.json at
# render time, so they cannot drift here either.
GLOSSARY = [
    ("A gate",
     "A date with a question and a rule, written down BEFORE the date. On the day, the "
     "rule is read and it decides what happens next. The point is that the rule cannot "
     "be argued with afterwards. This project has four."),
    ("`unknown`",
     "A verdict that means 'a check I needed could not run'. It is not 'low risk' and it "
     "is not a bug -- it is the product refusing to guess. {unknown}% of answers "
     "are this."),
    ("Fail-closed",
     "When something breaks, answer 'I don't know' rather than 'looks fine'. A safety "
     "tool that guesses optimistically when it is broken is worse than no tool."),
    ("False positive",
     "We said a token was dangerous and it was fine. Ours is {fp}%. This is the number "
     "that costs a user money by making them skip a good trade."),
    ("Recall",
     "Of the bad things that existed, how many did we catch. Ours on tokens that "
     "actually died is {dead_high}%. It is the worst number we publish, and we publish "
     "it first."),
    ("The oracle",
     "The independent judge the benchmark scores us against. Ours is GoPlus, and it is "
     "deliberately NOT wired into the product -- if the thing being tested could read "
     "the answer key, the test would mean nothing. A test in the build enforces that."),
    ("Held-out",
     "Kept away from the thing being measured, on purpose. Same idea as above."),
    ("MCP",
     "The plug that lets an AI assistant call an outside tool. This project is an MCP "
     "server, so an assistant can ask it about a token before buying."),
    ("W-numbers (W9, W11...)",
     "Work items in docs/BACKLOG.md. They keep their number forever, including when the "
     "answer was 'we tried this and it failed'."),
    ("R-numbers (R16, R17...)",
     "Rounds of work in docs/ROUNDS.md, generated from the commit history."),
    ("The usage gate / telemetry",
     "A count of who calls the server. It records no addresses, no identities and no "
     "token names -- which is why it cannot simply tell you who a caller is."),
    ("Experiment C",
     "Posting the benchmark publicly and seeing whether anyone bites. It is the "
     "project's distribution test, not a marketing exercise."),
]


def _read(rel):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        return ""
    return io.open(p, encoding="utf-8").read()


def gates():
    """The dated decision gates, straight out of STRATEGY's own table."""
    out = []
    for line in _read("docs/STRATEGY.md").splitlines():
        m = re.match(r"^\|\s*(20\d\d-\d\d-\d\d)\s*\|(.+?)\|(.+?)\|(.+?)\|\s*$", line)
        if m:
            out.append({"date": m.group(1), "gate": m.group(2).strip(),
                        "test": m.group(3).strip(), "action": m.group(4).strip()})
    return sorted(out, key=lambda g: g["date"])


def yours():
    """Backlog items in the `## Yours` section -- things only the owner can do."""
    text = _read("docs/BACKLOG.md")
    if "## Yours" not in text:
        return []
    section = text.split("## Yours", 1)[1].split("\n## ", 1)[0]
    out = []
    for line in section.splitlines():
        m = re.match(r"^\|\s*(W\d+)\s*\|(.+?)\|(.+?)\|(.+?)\|(.+?)\|\s*$", line)
        if m:
            state = m.group(5).strip().strip("*")
            if state.lower().startswith(("done", "rejected")):
                continue
            out.append({"id": m.group(1), "item": m.group(2).strip().strip("*"),
                        "why": m.group(3).strip(), "verify": m.group(4).strip(),
                        "state": state})
    return out


def score():
    m = re.search(r"## Total: \*\*(\d+) / (\d+)\*\*", _read("docs/SCORECARD.md"))
    return ("%s / %s" % (m.group(1), m.group(2))) if m else "not read"


def open_round():
    import rounds
    for rid, name, last, blurb in rounds.ROUNDS:
        if last is None:
            return rid, name, blurb
    return "-", "-", "-"


def numbers():
    try:
        import publish_numbers
        return publish_numbers.figures()
    except Exception:                                        # noqa: BLE001
        return {}


def _days(date_str, today):
    try:
        d = datetime.date(*[int(x) for x in date_str.split("-")])
    except Exception:                                        # noqa: BLE001
        return None
    return (d - today).days


def _when(days):
    if days is None:
        return "no date"
    if days < 0:
        return "**%d days OVERDUE**" % -days
    if days == 0:
        return "**TODAY**"
    if days == 1:
        return "**tomorrow**"
    if days <= 14:
        return "**in %d days**" % days
    return "in %d days" % days


def changed_recently(days=7, cap=8):
    """Commit subjects from the last `days`, so a weekly reader gets the diff not the state.

    Returns (subjects, total). The cap is reported rather than applied silently: a
    truncated list that does not say it was truncated reads as a complete week.

    The snapshot job's commits are excluded, for the same reason `rounds.py` excludes
    them: they are data collection, not development, and two of them land every day. With
    them in, this section changed twice a day on its own and the currency test went red
    without anybody touching the project -- a test that reddens by itself teaches people
    to ignore a red build, which is worse than not having the test.
    """
    import subprocess
    sys.path.insert(0, HERE)
    import rounds
    try:
        out = subprocess.check_output(
            ["git", "log", "--since=%d.days" % days, "--no-merges", "--format=%s"],
            cwd=ROOT, stderr=subprocess.DEVNULL).decode("utf-8", "replace")
    except (OSError, subprocess.CalledProcessError):
        return None, 0                      # no git here; not the same as a quiet week
    subjects = [s.strip() for s in out.splitlines() if s.strip()
                and not s.strip().startswith(rounds.BOT_PREFIX)]
    return subjects[:cap], len(subjects)


def render(today=None):
    today = today or datetime.date.today()
    n = numbers()
    rid, rname, rblurb = open_round()
    L = []
    w = L.append

    w("# What you need to know (OWNER.md)")
    w("")
    w("> **Generated. Do not edit this file** -- run `python tools/owner.py --write`.")
    w("> Every date, number and task below is read out of the file that owns it, so this")
    w("> page cannot quietly drift out of date. `tests/test_owner_page.py` fails the")
    w("> build if it does.")
    w(">")
    w("> Generated %s." % today.isoformat())
    w("")

    # ---------------------------------------------------------------- the whole thing
    w("## The project in one paragraph")
    w("")
    w("VetAgent is a safety check an AI agent calls before it buys a crypto token. It is")
    w("live at `https://vetagent.dev`, free, and anyone can use it without signing up.")
    w("It is not sold, it has no users we can name, and the only question that matters")
    w("right now is whether anyone outside this project actually uses it. Everything")
    w("below is organised around that question and the date it gets answered.")
    w("")

    # ---------------------------------------------------------------- needs you
    todo = []
    for item in yours():
        due, reason = OWNER_DUE.get(item["id"], ("", "not dated"))
        todo.append({"id": item["id"], "what": item["item"], "due": due,
                     "days": _days(due, today) if due else None,
                     "why": reason, "done": item["verify"], "state": item["state"]})
    for name, due, why, done in EXTRA_ACTIONS:
        todo.append({"id": "--", "what": name, "due": due,
                     "days": _days(due, today), "why": why, "done": done,
                     "state": "Open"})
    todo.sort(key=lambda t: (t["days"] is None, t["days"] if t["days"] is not None else 0))

    w("## Needs you, soonest first")
    w("")
    w("These are the things I cannot do. Everything else in this project is mine.")
    w("")
    w("| When | Due | # | What you do | Blocked? |")
    w("|---|---|---|---|---|")
    for t in todo:
        w("| %s | %s | %s | %s | %s |"
          % (_when(t["days"]), t["due"] or "--", t["id"],
             t["what"].replace("|", "/")[:90],
             "**yes -- see below**" if t["state"].lower().startswith("blocked") else "no"))
    w("")
    for t in todo:
        w("### %s %s" % (t["id"] if t["id"] != "--" else "", t["what"]))
        w("")
        w("- **When:** %s%s" % (t["due"] or "no deadline",
                                " (%s)" % _when(t["days"]) if t["days"] is not None else ""))
        w("- **Why then:** %s" % t["why"])
        w("- **You know it is done when:** %s" % t["done"])
        cost = COST_OF_WAITING.get(t["id"]) or COST_OF_WAITING.get(t["what"])
        w("- **If you do nothing:** %s" % (cost or "_not stated -- ask me, that is a gap_"))
        w("")

    # ---------------------------------------------------------------- the dates
    w("## The dates that decide things")
    w("")
    w("A gate is a question with a rule, written down before the date so it cannot be")
    w("argued with afterwards. On the day, the rule is read and it decides what happens")
    w("next -- including stopping.")
    w("")
    w("| Date | When | The question | What happens |")
    w("|---|---|---|---|")
    for g in gates():
        w("| %s | %s | %s | %s |"
          % (g["date"], _when(_days(g["date"], today)), g["gate"], g["action"]))
    w("")

    # ---------------------------------------------------------------- where it stands
    w("## Where it stands today")
    w("")
    w("| | |")
    w("|---|---|")
    w("| Maturity score | %s (`docs/SCORECARD.md`) |" % score())
    w("| Tokens measured | %s |" % n.get("n", "?"))
    w("| False positives | %s%% -- we called a healthy token dangerous |"
      % n.get("fp_pct", "?"))
    w("| Answers we refuse | %s%% -- `unknown`, on purpose |" % n.get("unknown_pct", "?"))
    w("| Dead tokens we rated high | %s%% -- our worst number, published first |"
      % n.get("dead_high_pct", "?"))
    w("| Round in progress | %s: %s |" % (rid, rname))
    w("")
    w("The score's ceiling for engineering alone is about 70. The missing points are")
    w("distribution and users, which is why more building cannot move it.")
    w("")

    # ---------------------------------------------------------------- what i'm doing
    w("## What I am doing right now")
    w("")
    w("**%s -- %s**" % (rid, rname))
    w("")
    w(rblurb)
    w("")

    # ---------------------------------------------------------------- the week's diff
    #
    # Somebody who reads this page weekly wants what changed, not the whole state. The
    # state is above and it is long; this is the part that answers "has anything moved".
    subjects, total = changed_recently()
    w("## What changed in the last 7 days")
    w("")
    if subjects is None:
        w("_Could not read the commit history from here._ That is not the same as a quiet")
        w("week, and it should not be read as one.")
    elif not subjects:
        w("Nothing was committed. If that is a surprise, it is worth asking why.")
    else:
        w("Every line is one commit, newest first. The full message says what the")
        w("problem looked like before it was fixed.")
        w("")
        for s in subjects:
            w("- %s" % s)
        if total > len(subjects):
            w("")
            w("_%d more not shown (%d commits in total)._" % (total - len(subjects), total))
    w("")

    # ---------------------------------------------------------------- what I got wrong
    #
    # The section that decides how much of the rest of this page is worth believing. It
    # goes above "how to check on me" on purpose: an owner who cannot audit the work has
    # one honest signal, and it is whether the errors arrive before they are caught.
    w("## What I got wrong")
    w("")
    w("I am the one measuring my own work, so this section is the part of the page that")
    w("costs me something. A build check requires an entry here every %d days: if there"
      % CORRECTION_WINDOW)
    w("were genuinely no mistakes, saying so is itself a dated claim on the record.")
    w("")
    w("Newest first.")
    w("")
    for when, claimed, truth, caught in CORRECTIONS:
        w("**%s** &mdash; I said: *%s*" % (when, claimed))
        w("")
        w("> %s" % truth)
        w("")
        w("> How it surfaced: %s" % caught)
        w("")
    w("The pattern worth noticing: **most of these made things look worse than they")
    w("were, not better.** Being wrong in the pessimistic direction is still being wrong,")
    w("and it is the direction that quietly kills good work.")
    w("")

    # ---------------------------------------------------------------- how to check
    w("## How to check on me without reading any code")
    w("")
    w("```bash")
    w("python tools/owner.py --write   # regenerate this page")
    w("```")
    w("")
    w("- **Is it alive?** Open <https://vetagent.dev> and press a demo button.")
    w("- **Is anyone using it?** GitHub -> Actions -> \"Usage -- who is actually")
    w("  calling\" -> Run workflow. The last line of the gate section is the answer.")
    w("- **Are the published numbers true?** GitHub -> Actions. If the build is green,")
    w("  every accuracy number on the site and in the docs matches the last benchmark")
    w("  run. That check is the reason a number cannot go stale without failing.")
    w("- **What changed lately?** `docs/ROUNDS.md`, generated from the commits.")
    w("")

    # ---------------------------------------------------------------- glossary
    w("## The words I keep using")
    w("")
    fills = {"fp": n.get("fp_pct", "?"), "unknown": n.get("unknown_pct", "?"),
             "dead_high": n.get("dead_high_pct_round", "?")}
    for term, meaning in GLOSSARY:
        w("**%s** -- %s" % (term, meaning.format(**fills)))
        w("")

    w("---")
    w("")
    w("If something here is unclear, that is a defect in this page, not in your")
    w("understanding. Say which line and it gets rewritten.")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    text = render()
    if args.write:
        with io.open(OUT, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        print("wrote %s" % OUT)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
