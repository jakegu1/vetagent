"""The approved D deadline moves; its conclusion and review requirements do not.

Run the real guard and Owner-page generator on private copies of the current sources.
Historical pending fixtures keep every calendar boundary after a live checkpoint.
The old guard's synthetic Oct-16 scenarios remain its own independent contract.
Run: python tests/test_experiment_d_deadline.py
"""

from contextlib import contextmanager, redirect_stdout
import datetime
import hashlib
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
CHECKPOINT_FINDING = "Experiment D measurement is not yet available"
CHECKPOINT_DECISION = ("undecided; retain the current validation direction and the existing "
                       "payment gate; Experiment D remains open")
CHECKPOINT = "Resolved: %s -> %s" % (CHECKPOINT_FINDING, CHECKPOINT_DECISION)
REVIEW_LABEL = "**Reviewed 2026-10-20:**"
REVIEW_NOTE = (REVIEW_LABEL + " No new direction is adopted. Reconsideration\n"
               "still depends on actual Experiment D evidence. This records the due review,\n"
               "without closing this idea or its original experiment.\n\n")
# Hash the complete original heading/evidence/rationale, including its final blank line.
# A review may append to these bodies, never replace the evidence with a fixture's result.
ORIGINAL_BODY_SHA256 = {
    "O2": "3fd4e7b553daedbe3da6df5dbff97397f140def63b81a372005a8448db560a3e",
    "O8": "a4f43d6992d8fb238b69b2a9787ebb395e49874924b7bafcb7942685a289d651",
    "O9": "cf256866f56f9204e70b0c64e659fe9a3a1af739bf19fae66e0d1e369e04b497",
    "O11": "a669227cb6bcec5983e2f574f5a2e7fa233885e1d25db967b0d48ac12c2cd376",
}


def _load(relative):
    """Compile current source directly, so mutations cannot hide behind stale bytecode."""
    path = ROOT / relative
    module = types.ModuleType("deadline_" + path.stem)
    module.__file__ = str(path)
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), module.__dict__)
    return module


def _actual_sources():
    return tuple((ROOT / "docs" / name).read_text(encoding="utf-8")
                 for name in ("STRATEGY.md", "OPPORTUNITIES.md"))


def _d_blocks(opportunities):
    """Find exactly one original body per D ID, across both opportunity sections."""
    blocks = [match for match in re.finditer(
        r"^### (O\d+)\b.*?(?=^### |^## |^---$|\Z)", opportunities, re.M | re.S)
        if match.group(1) in IDS]
    if sorted(match.group(1) for match in blocks) != sorted(IDS):
        raise AssertionError("expected exactly one body for each D opportunity")
    return blocks


def _original_d_body(match):
    body = match.group().partition(REVIEW_LABEL)[0]
    if hashlib.sha256(body.encode("utf-8")).hexdigest() != ORIGINAL_BODY_SHA256[match.group(1)]:
        raise AssertionError("the original %s body changed" % match.group(1))
    return body


def _without_d_blocks(opportunities):
    for match in reversed(_d_blocks(opportunities)):
        opportunities = opportunities[:match.start()] + opportunities[match.end():]
    return opportunities


def _pending_sources(strategy, opportunities):
    """Reconstruct only the original pending state, entirely in private strings."""
    row = _d_row(strategy)
    if row != D_ROW and not (row.startswith(D_ROW[:-1] + "Resolved: ")
                             and row.endswith(" |")):
        raise AssertionError("the original D question, rule or action changed")
    pending_strategy = strategy.replace(row, D_ROW, 1)
    bodies = {match.group(1): _original_d_body(match) for match in _d_blocks(opportunities)}
    unchanged = _without_d_blocks(opportunities)
    if unchanged.count("## Reviewed and closed") != 1:
        raise AssertionError("expected one reviewed section")
    parked, marker, closed = unchanged.partition("## Reviewed and closed")
    pending_opportunities = parked + "".join(bodies[entry] for entry in IDS) + marker + closed
    if _without_d_blocks(pending_opportunities) != unchanged:
        raise AssertionError("a pending fixture changed a non-D opportunity")
    return pending_strategy, pending_opportunities


def _sources():
    return _pending_sources(*_actual_sources())


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
        strategy, _ = _actual_sources()
        row = _d_row(strategy)
        self.assertTrue(row.startswith(D_ROW[:-1]), row)
        self.assertEqual(row[len(D_ROW[:-1]):], CHECKPOINT + " |")
        guard = _load("tests/test_gates_get_reviewed.py")
        self.assertEqual(guard.PINNED_GATES, SCHEDULE)
        section = _section(strategy, "8. Decision gates")
        self.assertEqual(guard._GATE_ROW.findall(section), SCHEDULE)
        self.assertTrue(guard.gate_row_answered(row))

    def test_actual_checkpoint_is_unavailable_and_undecided_without_a_fabricated_result(self):
        strategy, _ = _actual_sources()
        _, marker, conclusion = _d_row(strategy).partition("Resolved: ")
        self.assertEqual(marker, "Resolved: ")
        finding, arrow, decision = conclusion.removesuffix(" |").partition(" -> ")
        self.assertEqual(finding, CHECKPOINT_FINDING)
        self.assertEqual(arrow, " -> ")
        self.assertEqual(decision, CHECKPOINT_DECISION)
        self.assertNotRegex(conclusion.lower(),
                            r"\b(?:0|zero) (?:trial )?commitments\b|outreach (?:sent|completed)"
                            r"|trials? (?:succeeded|successful)|payments? (?:built|successful)"
                            r"|experiment d (?:completed|failed)|demand (?:validated|proven)")

    def test_actual_four_reviews_append_to_original_bodies_without_adopting_a_direction(self):
        _, opportunities = _actual_sources()
        closed = opportunities.index("## Reviewed and closed")
        blocks = _d_blocks(opportunities)
        for match in blocks:
            with self.subTest(entry=match.group(1)):
                self.assertGreater(match.start(), closed)
                original = _original_d_body(match)
                self.assertEqual(match.group(), original + REVIEW_NOTE)
        guard = _load("tests/test_gates_get_reviewed.py")
        self.assertFalse(any(re.match(r"%s\b" % entry, heading)
                             for heading, _, _ in guard.parse_entries(opportunities)
                             for entry in IDS))

    def test_pending_fixture_preserves_non_d_sources_and_refuses_lost_or_changed_evidence(self):
        strategy, opportunities = _actual_sources()
        pending_strategy, pending_opportunities = _pending_sources(strategy, opportunities)
        self.assertEqual(pending_strategy.replace(D_ROW, "", 1),
                         strategy.replace(_d_row(strategy), "", 1))
        self.assertEqual(_without_d_blocks(pending_opportunities),
                         _without_d_blocks(opportunities))
        first = _d_blocks(opportunities)[0]
        missing = opportunities[:first.start()] + opportunities[first.end():]
        duplicate = opportunities + first.group()
        changed = opportunities.replace("Changing the target segment", "Changing a target segment", 1)
        self.assertNotEqual(changed, opportunities)
        changed_rule = strategy.replace("\u22653 trial commitments in Experiment D",
                                        "\u22652 trial commitments in Experiment D", 1)
        self.assertNotEqual(changed_rule, strategy)
        for label, contents in (("missing body", (strategy, missing)),
                                ("duplicate body", (strategy, duplicate)),
                                ("changed evidence", (strategy, changed)),
                                ("changed rule", (changed_rule, opportunities))):
            with self.subTest(control=label):
                with self.assertRaises(AssertionError):
                    _pending_sources(*contents)

    def test_actual_checkpoint_and_each_review_are_required_by_the_unchanged_guard(self):
        strategy, opportunities = _actual_sources()
        day = datetime.date(2026, 10, 20)
        status, due, parked, failed = _guard_run(strategy, opportunities, day)
        self.assertEqual((status, due, parked, failed),
                         (0, [True], {entry: [] for entry in IDS}, []))
        pending_strategy, _ = _sources()
        for conclusion in (None, "Resolved: pending", TEMPLATE,
                           "<!-- " + CHECKPOINT + " -->"):
            with self.subTest(conclusion=conclusion):
                copy = (pending_strategy if conclusion is None
                        else _answered(pending_strategy, conclusion))
                status, due, parked, failed = _guard_run(copy, opportunities, day)
                self.assertEqual(due, [False])
                self.assertEqual(parked, {entry: [] for entry in IDS})
                self.assertEqual(len(failed), 1 if conclusion is None else 2, failed)
                self.assertTrue(any(name.startswith("gate %s " % DUE) and "is due" in name
                                    for name in failed), failed)
                self.assertEqual("the real %s row is accepted" % DUE in failed,
                                 conclusion is not None)
                self.assertEqual(status, 1)
        # Undo each recorded review: restore its retained original body above the
        # closed marker, rather than deleting the evidence or changing the guard.
        for match in _d_blocks(opportunities):
            with self.subTest(unreviewed=match.group(1)):
                copy = opportunities[:match.start()] + opportunities[match.end():]
                parked_text, marker, closed_text = copy.partition("## Reviewed and closed")
                copy = parked_text + _original_d_body(match) + marker + closed_text
                status, due, parked, failed = _guard_run(strategy, copy, day)
                self.assertEqual(due, [True])
                self.assertEqual(parked, {entry: [False] if entry == match.group(1) else []
                                          for entry in IDS})
                self.assertEqual(len(failed), 1, failed)
                self.assertEqual(status, 1)

    def test_pending_controls_still_reject_a_moved_or_deleted_d_gate(self):
        strategy, opportunities = _sources()
        reviewed = _reviewed(opportunities)
        answered = _answered(strategy, REAL_CONCLUSION)
        row = _d_row(answered)
        for label, copy in (("deleted gate", answered.replace(row, "", 1)),
                            ("moved gate", answered.replace(row, row.replace(DUE, "2027-10-20"), 1))):
            with self.subTest(control=label):
                status, due, parked, failed = _guard_run(
                    copy, reviewed, datetime.date(2026, 10, 20))
                self.assertEqual(due, [])
                self.assertEqual(parked, {entry: [] for entry in IDS})
                self.assertEqual(len(failed), 1, failed)
                self.assertEqual(status, 1)

    def test_actual_undecided_checkpoint_uses_the_existing_owner_page_conclusion_rule(self):
        strategy, opportunities = _actual_sources()
        page = _render(strategy, opportunities, datetime.date(2026, 10, 20))
        table = _section(page, "The dates that decide things")
        self.assertIn("| %s | answered | %s |" % (DUE, QUESTION), table)
        self.assertIn(CHECKPOINT, table)
        self.assertIn("%s - answered :milestone, %s, 0d" % (QUESTION, DUE), page)
        self.assertNotIn(QUESTION, _section(page, "Needs you"))

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
