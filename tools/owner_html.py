"""owner_html.py -- render docs/OWNER.md's data as a standalone page.

Usage:
    python tools/owner_html.py            # write to the path given by --out
    python tools/owner_html.py --out X.html

Why this exists, and why it is generated
----------------------------------------
The owner reads Markdown in a GitHub repository, which is friction for someone who does
not otherwise open GitHub. This emits the same page as a single self-contained HTML file
that can be published or opened on a phone.

It reads `tools/owner.py` and nothing else. That is the whole point: a hand-built dashboard
would be the twelfth hand-maintained document in a repository where an audit found drift in
almost all eleven, and a *picture* that has gone stale is worse than stale prose, because
it is more persuasive than the text it contradicts. Regenerating is one command, and the
figures cannot disagree with docs/OWNER.md because neither is typed.

Mermaid needs no library here: the Artifact runtime renders `<pre class="mermaid">` natively.
"""

import argparse
import datetime
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "bench"))

import owner  # noqa: E402


def _md(text):
    """The narrow slice of Markdown that appears in these fields, made safe for HTML."""
    t = (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
    t = re.sub(r"\*(.+?)\*", r"<em>\1</em>", t)
    return t


def _plain(text):
    return re.sub(r"[*`]", "", text)


# Severity by how soon it is due -- the annunciator convention: the nearest thing is the
# loudest, and something with no date is not an alarm, it is a note.
def _urgency(days):
    if days is None:
        return "none"
    if days <= 10:
        return "now"
    if days <= 45:
        return "soon"
    return "later"


def build(today=None):
    today = today or datetime.date.today()
    n = owner.numbers()
    rid, rname, rblurb = owner.open_round()
    gates = owner.gates()

    todo = []
    for item in owner.yours():
        due, why = owner.OWNER_DUE.get(item["id"], ("", "not dated"))
        days = owner._days(due, today) if due else None
        todo.append({"id": item["id"], "what": item["item"], "due": due, "days": days,
                     "why": why, "done": item["verify"], "state": item["state"],
                     "cost": owner.COST_OF_WAITING.get(item["id"], "")})
    for name, due, why, done in owner.EXTRA_ACTIONS:
        todo.append({"id": "", "what": name, "due": due,
                     "days": owner._days(due, today), "why": why, "done": done,
                     "state": "Open", "cost": owner.COST_OF_WAITING.get(name, "")})
    todo.sort(key=lambda t: (t["days"] is None, t["days"] if t["days"] is not None else 0))

    nearest = min([g for g in gates], key=lambda g: owner._days(g["date"], today))
    nearest_days = owner._days(nearest["date"], today)

    H = []
    A = H.append

    A('<title>Is anyone using VetAgent</title>')
    A('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
      'family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans+Condensed:wght@500;600;700'
      '&family=IBM+Plex+Serif:ital,wght@0,400;0,600;1,400&display=swap">')
    A("<style>%s</style>" % CSS)

    # ---------------------------------------------------------------- the thesis
    A('<header class="top">')
    A('  <p class="eyebrow">VetAgent &middot; owner\'s page &middot; generated %s</p>'
      % today.isoformat())
    A('  <h1>The only question that matters right now is whether anyone outside this '
      'project actually uses it.</h1>')
    A('  <p class="lede">VetAgent is a safety check an AI agent calls before it buys a '
      'crypto token. It is live, free, and anyone can use it without signing up. It is '
      'not sold and it has no users we can name. On <strong>%s</strong> a rule written '
      'in advance reads the usage data and decides what happens next.</p>' % nearest["date"])
    A('  <div class="countdown">')
    A('    <span class="cd-num">%d</span>' % nearest_days)
    A('    <span class="cd-unit">days until<br>that answer</span>')
    A('    <span class="cd-rule">The rule is frozen in code and was written before the '
      'date, so it cannot be argued with afterwards. Read on the evidence available '
      'today it says <strong>no</strong>.</span>')
    A('  </div>')
    A('</header>')
    A('<main>')

    # ---------------------------------------------------------------- needs you
    A('<section id="do">')
    A('  <h2>What do I have to do?</h2>')
    A('  <p class="note">These are the things nobody else can do. Everything else in this '
      'project belongs to Claude.</p>')
    A('  <ol class="tasks">')
    for t in todo:
        u = _urgency(t["days"])
        blocked = t["state"].lower().startswith("blocked")
        parked = t["state"].lower().startswith("parked")
        A('    <li class="task u-%s">' % u)
        A('      <div class="t-head">')
        A('        <span class="t-when">%s</span>'
          % (("%d days" % t["days"]) if t["days"] is not None else "no date"))
        A('        <h3>%s%s</h3>' % (_md(t["what"]),
                                     ' <span class="tag">%s</span>' % t["state"]
                                     if (blocked or parked) else ""))
        A('      </div>')
        A('      <dl>')
        if t["due"]:
            A('        <dt>Due</dt><dd><code>%s</code> &mdash; %s</dd>'
              % (t["due"], _md(t["why"])))
        A('        <dt>Done when</dt><dd>%s</dd>' % _md(t["done"]))
        if t["cost"]:
            A('        <dt>If you do nothing</dt><dd class="cost">%s</dd>' % _md(t["cost"]))
        A('      </dl>')
        A('    </li>')
    A('  </ol>')
    A('</section>')

    # ---------------------------------------------------------------- gates
    A('<section id="when">')
    A('  <h2>When does anything get decided?</h2>')
    A('  <p class="note">Four dates, each with a question and a rule written down '
      '<em>before</em> the date. At least one branch of every one of them shrinks or '
      'stops the project &mdash; otherwise it would be a ceremony, not a decision.</p>')
    A('  <ul class="gates">')
    for g in gates:
        d = owner._days(g["date"], today)
        A('    <li class="gate u-%s">' % _urgency(d))
        A('      <span class="g-date">%s</span>' % g["date"])
        A('      <span class="g-days">%s</span>'
          % (("in %d days" % d) if d > 0 else "today" if d == 0 else "passed"))
        A('      <span class="g-q">%s</span>' % _md(g["gate"]))
        A('      <span class="g-act">%s</span>' % _md(g["action"]))
        A('    </li>')
    A('  </ul>')
    A('  <figure><figcaption>The same four dates on an axis &mdash; the spacing is the '
      'shape of the plan, and a list cannot show that the first one is close.</figcaption>')
    A('  <pre class="mermaid">%s</pre></figure>'
      % "\n".join(owner.mermaid_gate_timeline(today)[1:-1]))
    A('</section>')

    # ---------------------------------------------------------------- blockers
    A('<section id="stuck">')
    A('  <h2>Why is something stuck?</h2>')
    A('  <p class="note">Hexagons are not work items &mdash; they are what a row is '
      'waiting on from outside the backlog. Rounded means you parked it deliberately.</p>')
    blockers = owner.mermaid_blockers(today)
    graph = "\n".join(blockers[1:blockers.index("```")])
    A('  <figure><pre class="mermaid">%s</pre></figure>' % graph)
    A('  <p class="note">%s</p>' % _md(blockers[-1]))
    A('</section>')

    # ---------------------------------------------------------------- state
    A('<section id="state">')
    A('  <h2>Where does it stand?</h2>')
    A('  <div class="score">')
    A('    <div class="s-bar" role="img" aria-label="Maturity %s out of 100, with an '
      'engineering ceiling near 70">' % n["maturity"])
    A('      <span class="s-fill" style="width:%s%%"></span>' % n["maturity"])
    A('      <span class="s-ceil" style="left:70%%"><span>ceiling for code alone &middot; '
      '70</span></span>')
    A('    </div>')
    A('    <p class="s-read"><strong>%s / 100.</strong> Roughly 70 is the most that '
      'writing code can reach. The remaining 30 is users, revenue and elapsed time, and '
      'no amount of engineering moves it &mdash; which is precisely why the score is '
      'built this way.</p>' % n["maturity"])
    A('  </div>')
    A('  <table class="nums"><caption>Measured over %s tokens, labelled from sources the '
      'engine itself never reads. The worst number is first.</caption>' % n["n"])
    A('    <tbody>')
    for label, val, kind in (
            ("Dead tokens we rate <em>high</em>", n["dead_high_pct"] + "%", "bad"),
            ("Healthy tokens we flag high (false positives)", n["fp_pct"] + "%", "ok"),
            ("Answers returned as <code>unknown</code>", n["unknown_pct"] + "%", "unk"),
            ("Legitimate centralised assets flagged high", n["centralized_high_pct"] + "%",
             "warn")):
        A('      <tr><th scope="row">%s</th><td class="v %s">%s</td></tr>'
          % (label, kind, val))
    A('    </tbody></table>')
    A('  <h3>What Claude is doing right now</h3>')
    A('  <p class="round"><span class="rid">%s</span> %s</p>' % (rid, _md(rname)))
    A('  <p class="note">%s</p>' % _md(rblurb[:520] + ("..." if len(rblurb) > 520 else "")))
    A('</section>')

    # ---------------------------------------------------------------- trust
    A('<section id="believe">')
    A('  <h2>How much of this page should I believe?</h2>')
    A('  <p class="note">Claude measures its own work here, so this is the section that '
      'costs it something. A build check requires an entry inside %d days: if there were '
      'genuinely no mistakes, saying so is itself a dated claim. A status page that has '
      'never carried bad news should be read as marketing.</p>' % owner.CORRECTION_WINDOW)
    A('  <ol class="corrections">')
    for when, claimed, truth, caught in owner.CORRECTIONS:
        A('    <li><span class="c-date">%s</span>' % when)
        A('      <p class="c-said">Claude said: %s</p>' % _md(claimed))
        A('      <p class="c-true">%s</p>' % _md(truth))
        A('      <p class="c-how">How it surfaced: %s</p>' % _md(caught))
        A('    </li>')
    A('  </ol>')
    A('  <p class="note">The pattern worth noticing: most of these made things look '
      '<em>worse</em> than they were. Being wrong in the pessimistic direction is still '
      'being wrong, and it is the direction that quietly kills good work.</p>')
    A('</section>')

    # ---------------------------------------------------------------- checks
    A('<section id="check">')
    A('  <h2>How do I check on Claude without reading any code?</h2>')
    A('  <ul class="checks">')
    for q, how in (
        ("Is it alive?",
         'Open <a href="https://vetagent.dev">vetagent.dev</a> and press a demo button.'),
        ("Is anyone using it?",
         "GitHub &rarr; Actions &rarr; &ldquo;Usage &mdash; who is actually calling&rdquo; "
         "&rarr; Run workflow. The last line of the gate section is the answer."),
        ("Are the published numbers true?",
         "GitHub &rarr; Actions. If the build is green, every accuracy number on the site "
         "and in the docs matches the last benchmark run. That check is the reason a "
         "number cannot go stale without failing."),
        ("What changed lately?",
         "<code>docs/ROUNDS.md</code>, generated from the commit messages."),
    ):
        A('    <li><span class="q">%s</span><span class="a">%s</span></li>' % (q, how))
    A('  </ul>')
    A('</section>')

    # ---------------------------------------------------------------- glossary
    A('<section id="words">')
    A('  <h2>The words Claude keeps using</h2>')
    A('  <dl class="gloss">')
    for term, definition in owner.GLOSSARY:
        A('    <dt>%s</dt><dd>%s</dd>'
          % (_md(term), _md(definition.format(fp=n["fp_pct"], unknown=n["unknown_pct"],
                                              dead_high=n["dead_high_pct_round"]))))
    A('  </dl>')
    A('</section>')

    A('<footer><p>If something here is unclear, that is a defect in this page, not in '
      'your understanding. Say which line and it gets rewritten.</p>'
      '<p class="gen">Generated from <code>tools/owner.py</code>, which reads '
      '<code>docs/STRATEGY.md</code>, <code>docs/BACKLOG.md</code>, '
      '<code>docs/SCORECARD.md</code> and <code>bench/results.json</code>. Nothing on '
      'this page is typed by hand, so it cannot disagree with them.</p></footer>')
    A('</main>')
    return "\n".join(H)


CSS = """
:root{
  --ground:#eef2f1; --surface:#ffffff; --sunk:#e3e9e7;
  --ink:#131d1c; --body:#2c3a38; --dim:#5d6d6a; --rule:#ccd6d3;
  --teal:#0f6e63; --teal-soft:#dcebe8;
  --now:#a63a29; --soon:#8a6a12; --later:#4c6360; --none:#7b8a87;
  --bad:#a63a29; --warn:#8a6a12; --ok:#1f6b4f; --unk:#5d6d6a;
  --display:"IBM Plex Sans Condensed","Helvetica Neue",Arial,sans-serif;
  --serif:"IBM Plex Serif",Georgia,"Times New Roman",serif;
  --mono:"IBM Plex Mono",ui-monospace,"SFMono-Regular",Menlo,monospace;
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --ground:#0f1618; --surface:#161f21; --sunk:#1d2729;
    --ink:#e6edeb; --body:#c3cfcd; --dim:#8b9a97; --rule:#2a3739;
    --teal:#4bbdad; --teal-soft:#12312e;
    --now:#e8836f; --soon:#d4ac4a; --later:#8b9a97; --none:#75837f;
    --bad:#e8836f; --warn:#d4ac4a; --ok:#5fbf95; --unk:#8b9a97;
  }
}
:root[data-theme="dark"]{
  --ground:#0f1618; --surface:#161f21; --sunk:#1d2729;
  --ink:#e6edeb; --body:#c3cfcd; --dim:#8b9a97; --rule:#2a3739;
  --teal:#4bbdad; --teal-soft:#12312e;
  --now:#e8836f; --soon:#d4ac4a; --later:#8b9a97; --none:#75837f;
  --bad:#e8836f; --warn:#d4ac4a; --ok:#5fbf95; --unk:#8b9a97;
}
*{box-sizing:border-box}
body{background:var(--ground);color:var(--body);font-family:var(--serif);
  font-size:16.5px;line-height:1.66;margin:0;-webkit-font-smoothing:antialiased}
main,.top{max-width:47rem;margin:0 auto;padding:0 1.5rem}
h1,h2,h3,.eyebrow,.t-when,.g-date,.g-days,.tag,.q{font-family:var(--display)}
h1{font-size:clamp(1.7rem,4.4vw,2.5rem);line-height:1.16;font-weight:700;color:var(--ink);
  letter-spacing:-.012em;text-wrap:balance;margin:.5rem 0 1rem}
h2{font-size:1.42rem;font-weight:600;color:var(--ink);letter-spacing:-.006em;
  text-wrap:balance;margin:0 0 .35rem}
h3{font-size:1.06rem;font-weight:600;color:var(--ink);margin:0;text-wrap:balance}
code{font-family:var(--mono);font-size:.87em;background:var(--sunk);
  padding:.08em .34em;border-radius:2px}
a{color:var(--teal)}
a:focus-visible,button:focus-visible{outline:2px solid var(--teal);outline-offset:2px}

.top{padding-top:3rem;padding-bottom:.5rem}
.eyebrow{font-size:.76rem;text-transform:uppercase;letter-spacing:.13em;
  color:var(--dim);margin:0;font-weight:600}
.lede{font-size:1.09rem;color:var(--body);margin:0 0 1.6rem}
.countdown{display:grid;grid-template-columns:auto 1fr;gap:.2rem 1rem;align-items:center;
  background:var(--surface);border:1px solid var(--rule);border-left:4px solid var(--now);
  padding:1.15rem 1.35rem}
.cd-num{font-family:var(--display);font-size:3.3rem;font-weight:700;line-height:.9;
  color:var(--now);font-variant-numeric:tabular-nums;grid-row:span 2}
.cd-unit{font-family:var(--display);font-size:.86rem;text-transform:uppercase;
  letter-spacing:.09em;color:var(--dim);font-weight:600;line-height:1.25}
.cd-rule{font-size:.94rem;color:var(--body);grid-column:2}

main{padding-bottom:4rem}
section{padding:2.7rem 0;border-top:1px solid var(--rule)}
section:first-child{border-top:none}
.note{font-size:.95rem;color:var(--dim);margin:.35rem 0 1.3rem;max-width:63ch}

/* Tasks: a left stripe by urgency, one object repeated exactly. */
.tasks{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:1rem}
.task{background:var(--surface);border:1px solid var(--rule);
  border-left:4px solid var(--none);padding:1rem 1.2rem}
.task.u-now{border-left-color:var(--now)}
.task.u-soon{border-left-color:var(--soon)}
.task.u-later{border-left-color:var(--later)}
.t-head{display:flex;flex-wrap:wrap;align-items:baseline;gap:.2rem .85rem;
  margin-bottom:.55rem}
.t-when{font-size:.78rem;text-transform:uppercase;letter-spacing:.1em;font-weight:700;
  color:var(--dim);font-variant-numeric:tabular-nums;min-width:5.2rem}
.u-now .t-when{color:var(--now)}
.tag{font-size:.7rem;text-transform:uppercase;letter-spacing:.09em;font-weight:700;
  color:var(--dim);border:1px solid var(--rule);padding:.06em .4em;vertical-align:.12em}
.task dl{display:grid;grid-template-columns:auto 1fr;gap:.3rem .9rem;margin:0;
  font-size:.94rem}
.task dt{font-family:var(--display);font-size:.74rem;text-transform:uppercase;
  letter-spacing:.09em;font-weight:600;color:var(--dim);padding-top:.28em}
.task dd{margin:0}
.cost{color:var(--ink)}

/* Gates: a table-like list, not cards -- they are one sequence, not five objects. */
.gates{list-style:none;margin:0 0 1.8rem;padding:0}
.gate{display:grid;grid-template-columns:6.4rem 5.6rem 1fr;gap:.15rem .9rem;
  padding:.8rem 0 .8rem .85rem;border-top:1px solid var(--rule);
  border-left:3px solid var(--none)}
.gate.u-now{border-left-color:var(--now)}
.gate.u-soon{border-left-color:var(--soon)}
.gate.u-later{border-left-color:var(--later)}
.g-date{font-family:var(--mono);font-size:.88rem;color:var(--ink);font-weight:500}
.g-days{font-size:.78rem;text-transform:uppercase;letter-spacing:.08em;color:var(--dim);
  font-weight:600;font-variant-numeric:tabular-nums}
.g-q{grid-column:3;color:var(--ink);font-weight:600}
.g-act{grid-column:3;font-size:.9rem;color:var(--dim)}

figure{margin:0 0 1rem;background:var(--surface);border:1px solid var(--rule);
  padding:1rem}
figcaption{font-size:.86rem;color:var(--dim);margin-bottom:.7rem;max-width:60ch}
pre.mermaid{overflow-x:auto;margin:0;font-family:var(--mono);font-size:.8rem;
  background:none;padding:0}

/* Score: one bar with the ceiling drawn on it, because the ceiling is the point. */
.score{margin-bottom:1.9rem}
.s-bar{position:relative;height:2.1rem;background:var(--sunk);
  border:1px solid var(--rule);display:block}
.s-fill{position:absolute;inset:0 auto 0 0;background:var(--teal);display:block}
.s-ceil{position:absolute;top:-.15rem;bottom:-.15rem;width:2px;background:var(--ink)}
/* The label sits at 70% and is nowrap, so on a narrow screen it would run off the right
   edge. Anchor its right edge to the rule instead once there is not room to the right. */
.s-ceil span{position:absolute;left:.45rem;top:-1.4rem;white-space:nowrap;
  font-family:var(--display);font-size:.72rem;text-transform:uppercase;
  letter-spacing:.08em;font-weight:700;color:var(--ink)}
@media (max-width:40rem){
  .s-ceil span{left:auto;right:.45rem;text-align:right}
}
.s-read{font-size:.95rem;margin:1.9rem 0 0;max-width:63ch}

.nums{width:100%;border-collapse:collapse;margin:0 0 1.9rem;font-size:.95rem}
.nums caption{text-align:left;font-size:.86rem;color:var(--dim);padding-bottom:.6rem;
  max-width:60ch}
.nums th{text-align:left;font-weight:400;padding:.5rem 0;border-top:1px solid var(--rule);
  color:var(--body)}
.nums .v{text-align:right;padding:.5rem 0;border-top:1px solid var(--rule);
  font-family:var(--mono);font-weight:500;font-variant-numeric:tabular-nums}
.nums .v.bad{color:var(--bad)} .nums .v.warn{color:var(--warn)}
.nums .v.ok{color:var(--ok)}
/* `unknown` is not a warning -- it is the tool refusing to guess. Hollow, not coloured. */
.nums .v.unk{color:var(--unk);border-bottom:none;
  text-decoration:underline;text-decoration-style:dotted;text-underline-offset:.3em}
.round{margin:.2rem 0 .3rem;font-weight:600;color:var(--ink)}
.rid{font-family:var(--mono);font-size:.85rem;color:var(--teal);margin-right:.5rem}

.corrections{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;
  gap:1.35rem;counter-reset:none}
.corrections li{border-left:3px solid var(--rule);padding-left:1.1rem}
.c-date{font-family:var(--mono);font-size:.82rem;color:var(--dim)}
.c-said{margin:.15rem 0 .5rem;font-style:italic;color:var(--ink)}
.c-true{margin:0 0 .45rem;font-size:.96rem}
.c-how{margin:0;font-size:.89rem;color:var(--dim)}

.checks{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:.95rem}
.checks li{display:grid;grid-template-columns:11rem 1fr;gap:.2rem .9rem;
  padding-top:.85rem;border-top:1px solid var(--rule)}
.checks .q{font-weight:600;color:var(--ink);font-size:.98rem}
.checks .a{font-size:.94rem}

.gloss{margin:0;display:flex;flex-direction:column;gap:.9rem}
.gloss dt{font-family:var(--display);font-weight:700;color:var(--ink);font-size:1rem}
.gloss dd{margin:.1rem 0 0;font-size:.95rem}

footer{border-top:1px solid var(--rule);margin-top:2.5rem;padding-top:1.5rem}
footer p{font-size:.93rem;color:var(--dim);max-width:60ch}
footer .gen{font-size:.85rem;margin-bottom:0}

@media (max-width:34rem){
  .gate{grid-template-columns:1fr}
  .gate .g-q,.gate .g-act{grid-column:1}
  .checks li{grid-template-columns:1fr}
  .countdown{grid-template-columns:1fr}
  .cd-num{grid-row:auto}
}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "owner-page.html"))
    args = ap.parse_args()
    html = build()
    with io.open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    print("wrote %s (%.1f KB)" % (args.out, len(html) / 1024.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
