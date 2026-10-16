"""The approved D deadline moves; its conclusion and review requirements do not.

Run the real guard and Owner-page generator on private copies of the current sources.
The old guard's synthetic Oct-16 scenarios remain its own independent contract.
Run: python tests/test_experiment_d_deadline.py
"""

from contextlib import contextmanager, redirect_stdout
import datetime
import io
from pathlib import Path
import re
import socket
import tempfile
import types
import unittest
from unittest.mock import patch
import warnings


ROOT = Path(__file__).resolve().parent.parent
QUESTION = "Does anyone want to pay"
DUE = "2026-10-20"
IDS = ("O2", "O8", "O9", "O11")
SCHEDULE = [
    ("2026-09-18", "Is anyone using it"),
    (DUE, QUESTION),
    ("2026-12-04", "Is further investment worth it"),
    ("2027-03-04", "Does the data asset hold up"),
]
D_ROW = ("| %s | %s | \u22653 trial commitments in Experiment D | Yes \u2192 build payments; "
         "no \u2192 pick a different customer segment and run D again |" % (DUE, QUESTION))
REAL_CONCLUSION = "Resolved: zero commitments measured -> run D with a different segment"
TEMPLATE = "Resolved: <what the measurement said> -> <decision>"


def _load(relative):
    """Compile current source directly, so mutations cannot hide behind stale bytecode."""
    path = ROOT / relative
    module = types.ModuleType("deadline_" + path.stem)
    module.__file__ = str(path)
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), module.__dict__)
    return module


def _sources():
    return tuple((ROOT / "docs" / name).read_text(encoding="utf-8")
                 for name in ("STRATEGY.md", "OPPORTUNITIES.md"))


def _d_row(strategy):
    rows = [line for line in strategy.splitlines()
            if line.startswith("| ") and "| %s |" % QUESTION in line]
    if len(rows) != 1:
        raise AssertionError("expected exactly one D row, got %r" % rows)
    return rows[0]


def _answered(strategy, conclusion):
    row = _d_row(strategy)
    return strategy.replace(row, row[:-1] + " " + conclusion + " |", 1)


def _reviewed(opportunities):
    """Move just D's four entries below the real closed heading in a private copy."""
    parked, marker, closed = opportunities.partition("## Reviewed and closed")
    if not marker:
        raise AssertionError("the opportunities file has no closed section")
    blocks = [match for match in re.finditer(
        r"^### (O\d+)\b.*?(?=^### |^## |\Z)", parked, re.M | re.S)
        if match.group(1) in IDS]
    if [match.group(1) for match in blocks] != list(IDS):
        raise AssertionError("D's four parked entries were not all found")
    for match in reversed(blocks):
        parked = parked[:match.start()] + parked[match.end():]
    reviews = "\n\n".join(match.group() + "\nSynthetic review: decided and closed.\n"
                             for match in blocks)
    return parked + marker + "\n\n" + reviews + closed


@contextmanager
def _private_sources(strategy, opportunities):
    watched = [ROOT / "docs" / name for name in
               ("STRATEGY.md", "OPPORTUNITIES.md", "OWNER.md")]
    before = {path: path.read_bytes() for path in watched}
    with tempfile.TemporaryDirectory(prefix="vetagent-d-deadline-") as scratch:
        folder = Path(scratch).resolve()
        if folder.is_relative_to(ROOT):
            raise AssertionError("guard controls must stay outside the checkout")
        paths = [folder / name for name in ("STRATEGY.md", "OPPORTUNITIES.md")]
        for path, content in zip(paths, (strategy, opportunities)):
            path.write_text(content, encoding="utf-8")
        try:
            yield paths
        finally:
            for path, content in before.items():
                if path.read_bytes() != content:
                    raise AssertionError("a control modified the real %s" % path.name)


def _guard_run(strategy, opportunities, day):
    """Run the complete real guard, including its existing self-tests, with a fixed day."""
    guard = _load("tests/test_gates_get_reviewed.py")
    records = []
    real_check = guard.check

    def record(name, condition, detail=""):
        records.append((name, bool(condition), detail))
        real_check(name, condition, detail)

    with _private_sources(strategy, opportunities) as (strategy_path, opportunities_path):
        guard.STRATEGY = str(strategy_path)
        guard.OPPS = str(opportunities_path)
        guard.datetime = guard._ForcedClock(datetime, day)
        guard.check = record
        with redirect_stdout(io.StringIO()):
            status = guard.main()
    due = [ok for name, ok, _ in records
           if name.startswith("gate ") and QUESTION in name and "is due" in name]
    parked = {entry: [ok for name, ok, _ in records
                       if re.match(r"^%s\b" % entry, name)] for entry in IDS}
    failed = [name for name, ok, _ in records if not ok]
    return status, due, parked, failed


def _render(strategy, opportunities, day):
    owner = _load("tools/owner.py")
    # The generator calls the actual guard's rule, loaded directly from current source.
    owner._GUARD[:] = [_load("tests/test_gates_get_reviewed.py")]
    read = owner._read
    with _private_sources(strategy, opportunities) as paths:
        copies = dict(zip(("docs/STRATEGY.md", "docs/OPPORTUNITIES.md"), paths))
        owner._read = lambda rel: (copies[rel].read_text(encoding="utf-8")
                                   if rel in copies else read(rel))
        try:
            return owner.render(today=day)
        finally:
            owner._read = read


def _section(page, heading):
    match = re.search(r"^## %s[^\n]*\n(.*?)(?=^## |\Z)" % re.escape(heading),
                      page, re.M | re.S)
    return match.group(1) if match else ""


class ExperimentDDeadlineTests(unittest.TestCase):
    def setUp(self):
        # The existing guard/generator use text reads without context managers. Unittest
        # enables ResourceWarning by default; keep that legacy noise local to this run.
        self.enterContext(warnings.catch_warnings())
        warnings.filterwarnings("ignore", category=ResourceWarning,
                                module=r"deadline_(test_gates_get_reviewed|owner)")
        self.network = patch.object(socket, "create_connection",
                                    side_effect=AssertionError("offline test attempted network"))
        self.connect = patch.object(socket.socket, "connect",
                                    side_effect=AssertionError("offline test attempted network"))
        self.network.start()
        self.connect.start()
        self.addCleanup(self.network.stop)
        self.addCleanup(self.connect.stop)

    def test_strategy_and_pin_keep_the_original_question_threshold_and_action(self):
        strategy, _ = _sources()
        self.assertEqual(_d_row(strategy), D_ROW)
        self.assertNotIn("Resolved:", _d_row(strategy))
        guard = _load("tests/test_gates_get_reviewed.py")
        self.assertEqual(guard.PINNED_GATES, SCHEDULE)
        section = _section(strategy, "8. Decision gates")
        self.assertEqual(guard._GATE_ROW.findall(section), SCHEDULE)

    def test_all_four_entries_remain_parked_until_oct20(self):
        _, opportunities = _sources()
        guard = _load("tests/test_gates_get_reviewed.py")
        actual = [(re.match(r"O\d+", heading).group(), due, unblocked)
                  for heading, due, unblocked in guard.parse_entries(opportunities)
                  if re.match(r"O\d+", heading) and re.match(r"O\d+", heading).group() in IDS]
        self.assertEqual(actual, [(entry, DUE, False) for entry in IDS])

    def test_real_guard_obeys_both_sides_of_the_calendar_boundary(self):
        strategy, opportunities = _sources()
        for date, is_due in ((16, False), (19, False), (20, True), (21, True)):
            with self.subTest(day=date):
                status, due, parked, failed = _guard_run(
                    strategy, opportunities, datetime.date(2026, 10, date))
                self.assertEqual(due, [False] if is_due else [])
                self.assertEqual(parked, {entry: [not is_due] for entry in IDS})
                self.assertEqual(len(failed), 5 if is_due else 0, failed)
                self.assertEqual(status, int(is_due))

    def test_a_conclusion_alone_still_requires_all_four_entry_reviews(self):
        strategy, opportunities = _sources()
        status, due, parked, failed = _guard_run(
            _answered(strategy, REAL_CONCLUSION), opportunities, datetime.date(2026, 10, 20))
        self.assertEqual(due, [True])
        self.assertEqual(parked, {entry: [False] for entry in IDS})
        self.assertEqual(len(failed), 4, failed)
        self.assertEqual(status, 1)

    def test_closed_entries_cannot_answer_a_placeholder_conclusion(self):
        strategy, opportunities = _sources()
        for placeholder in ("Resolved: pending", TEMPLATE):
            with self.subTest(conclusion=placeholder):
                status, due, parked, failed = _guard_run(
                    _answered(strategy, placeholder), _reviewed(opportunities),
                    datetime.date(2026, 10, 20))
                self.assertEqual(due, [False])
                self.assertEqual(parked, {entry: [] for entry in IDS})
                self.assertEqual(len(failed), 2, failed)
                self.assertTrue(any("is due" in name for name in failed), failed)
                self.assertEqual(status, 1)

    def test_a_real_conclusion_and_all_four_reviews_complete_the_gate(self):
        strategy, opportunities = _sources()
        status, due, parked, failed = _guard_run(
            _answered(strategy, REAL_CONCLUSION), _reviewed(opportunities),
            datetime.date(2026, 10, 20))
        self.assertEqual(due, [True])
        self.assertEqual(parked, {entry: [] for entry in IDS})
        self.assertEqual(failed, [])
        self.assertEqual(status, 0)

    def test_other_gate_and_parked_entry_rules_still_run(self):
        strategy, opportunities = _sources()
        old_gate = "| 2026-12-04 | Is further investment worth it |"
        self.assertEqual(strategy.count(old_gate), 1)
        changed_gate = strategy.replace(old_gate, old_gate.replace("12-04", "12-05"), 1)
        old_entry = "**Blocked until: gate 2026-12-04**"
        self.assertGreater(opportunities.count(old_entry), 0)
        changed_entry = opportunities.replace(old_entry, old_entry.replace("12-04", "10-15"), 1)
        for label, contents in (("another pinned gate", (changed_gate, opportunities)),
                                ("another parked entry", (strategy, changed_entry))):
            with self.subTest(control=label):
                status, due, parked, failed = _guard_run(
                    *contents, datetime.date(2026, 10, 16))
                self.assertEqual(due, [])
                self.assertEqual(parked, {entry: [True] for entry in IDS})
                self.assertEqual(len(failed), 1, failed)
                self.assertEqual(status, 1)

    def test_real_owner_render_has_oct20_in_every_gate_surface(self):
        strategy, opportunities = _sources()
        for date, when in ((16, "**in 4 days**"), (19, "**tomorrow**"),
                           (20, "**TODAY**"), (21, "**1 days OVERDUE**")):
            with self.subTest(day=date):
                page = _render(strategy, opportunities, datetime.date(2026, 10, date))
                table = _section(page, "The dates that decide things")
                self.assertIn("| %s | %s | %s |" % (DUE, when, QUESTION), table)
                self.assertIn("%s - %s :milestone, %s, 0d" %
                              (QUESTION, when.replace("*", ""), DUE), page)
                needs = _section(page, "Needs you")
                self.assertIn("| %s | %s | gate | Answer the gate: %s |" %
                              (when, DUE, QUESTION), needs)
                match = re.search(r"^### The %s gate: %s\n(.*?)(?=^### |\Z)" %
                                  (DUE, re.escape(QUESTION)), needs, re.M | re.S)
                self.assertIsNotNone(match)
                body = match.group(1)
                self.assertIn("`%s`" % TEMPLATE, body)
                self.assertEqual(re.findall(r"\bO\d+\b", body), list(IDS))
                self.assertIn("decided and moved under `## Reviewed and closed`", body)
                self.assertIn("From %s, `tests/test_gates_get_reviewed.py` fails the build" % DUE,
                              body)
                self.assertIn("blocks every deploy", body)

    def test_workflow_runs_this_offline_file_before_the_deploy_guard(self):
        workflow = (ROOT / ".github/workflows/test.yml").read_text(encoding="utf-8")
        job = workflow.split("\n  test:\n", 1)[1].split("\n  upstream-contract:", 1)[0]
        command = "        run: python tests/test_experiment_d_deadline.py"
        self.assertEqual(job.count(command), 1)
        self.assertLess(job.index(command), job.index("run: python tests/test_deploy_gate.py"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
