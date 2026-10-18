"""The frozen dataset must contain everything needed to re-derive its own labels.

The launch post's central claim is that the *method* is reproducible: "labels are frozen
in the tracked `bench/dataset.json`, the harness is `bench/run_benchmark.py`". The first
half was true and the second half was not checkable from the first, because the stored
oracle payload was a subset that left out four of the fifteen fields `goplus_label()`
reads -- `cannot_buy`, `cannot_sell_all`, `personal_slippage_modifiable` and `trust_list`.

Three of those four are adversarial traits. They decide the cohort the headline recall is
computed on, which makes them the worst four fields in the payload to have dropped.

Found by trying to replay the labeller against the committed dataset while checking
something else, and getting `None` back for all 576 rows.

This test compares what the labeller reads against what the writer stores, by reading both
out of `bench/labels.py` rather than by keeping a third list that would drift from both.

Run: python tests/test_dataset_replayable.py
"""

import ast
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bench"))

_PASSED = 0
_FAILURES = []
_UNCHECKED = []


def check(name, ok, detail=""):
    global _PASSED
    if ok:
        _PASSED += 1
        print("  PASS  %s" % name)
    else:
        _FAILURES.append((name, detail))
        print("  FAIL  %s  %s" % (name, detail))


def unchecked(name, why):
    _UNCHECKED.append((name, why))
    print("  ----  %s  (not checked here: %s)" % (name, why))


def _labeller_source():
    src = io.open(os.path.join(ROOT, "bench", "labels.py"), encoding="utf-8").read()
    return src[src.index("def goplus_label"):]


def test_the_stored_subset_covers_every_field_the_labeller_reads():
    print("\n[replay] the frozen payload carries what the labeller needs")
    body = _labeller_source()

    reads = set(re.findall(r'_flag\(d, "([a-z_]+)"\)', body))
    reads |= set(re.findall(r'_tax\(d, "([a-z_]+)"\)', body))
    check("the labeller's field list was found", len(reads) >= 10, str(sorted(reads)))

    stored_block = body[body.index("subset = {k: d.get(k) for k in ("):]
    stored_block = stored_block[:stored_block.index(") if k in d}")]
    stores = set(re.findall(r'"([a-z_]+)"', stored_block))
    check("the stored field list was found", len(stores) >= 15, str(len(stores)))

    missing = sorted(reads - stores)
    check("every field the labeller reads is stored", not missing,
          "a stranger cannot re-derive the label without: %s" % ", ".join(missing))


def test_the_committed_dataset_is_replayable():
    """The check above is about the code. This one is about the file on disk.

    A dataset built before the fix legitimately lacks the fields, so this reports rather
    than fails: the gap is real, it is the committed artifact, and it closes on the next
    `python bench/build_dataset.py`. Reporting it as unchecked keeps it visible instead of
    letting a green run imply the artifact was verified.
    """
    print("\n[replay] the committed dataset, as it stands today")
    path = os.path.join(ROOT, "bench", "dataset.json")
    if not os.path.exists(path):
        unchecked("the dataset is replayable", "bench/dataset.json is missing")
        return

    with io.open(path, encoding="utf-8") as f:
        data = json.load(f)
    rows = data if isinstance(data, list) else (data.get("tokens") or data.get("rows") or [])
    check("the dataset has rows", bool(rows), "0 rows")
    if not rows:
        return

    raw = rows[0].get("goplus_raw")
    if isinstance(raw, str):
        try:
            raw = ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            raw = None
    if not isinstance(raw, dict):
        unchecked("the dataset is replayable", "goplus_raw is not a readable mapping")
        return

    body = _labeller_source()
    reads = set(re.findall(r'_flag\(d, "([a-z_]+)"\)', body))
    reads |= set(re.findall(r'_tax\(d, "([a-z_]+)"\)', body))
    missing = sorted(reads - set(raw))

    if missing:
        unchecked("the committed dataset is replayable",
                  "built before the fix; missing %s. Closes on the next "
                  "`python bench/build_dataset.py`" % ", ".join(missing))
    else:
        check("the committed dataset carries every field the labeller reads", True)


def test_w40_plan_is_offline_source_bound_and_not_started(_support=False):
    import base64
    import copy
    import hashlib
    import importlib
    import pathlib
    import tempfile
    import contextlib
    from unittest.mock import patch
    core = importlib.import_module("w40_evidence")

    class Fixture:
        token = "0x" + "1" * 40
        pool = "0x" + "a" * 40

        def __enter__(self):
            self.environment = patch.dict(os.environ, {"CI": "", "GITHUB_ACTIONS": ""})
            self.environment.__enter__()
            try:
                self.temp = tempfile.TemporaryDirectory()
                self.root = pathlib.Path(self.temp.name)
                self.sources = []
                self.output = self.root / "safe"
                self.private = self.root / "private"
                return self
            except BaseException:
                self.environment.__exit__(*sys.exc_info())
                raise

        def __exit__(self, *args):
            try:
                self.temp.cleanup()
            finally:
                self.environment.__exit__(*args)

        def row(self, **changes):
            item = {"chain": "base", "base_token": "base_" + self.token,
                    "pool_address": self.pool, "pool_id": "base_" + self.pool,
                    "pool_created_at": "2026-10-01T00:00:00Z",
                    "seen_at": "2026-10-01T01:00:00Z", "reserve_usd": "1"}
            item.update(changes)
            return item

        def setup(self, rows=None, raw=None, **kwargs):
            path = self.root / "pools.ndjson"
            data = raw if raw is not None else b"".join(
                (json.dumps(r, allow_nan=False) + "\n").encode("utf-8")
                for r in (rows if rows is not None else [self.row()]))
            path.write_bytes(data)
            self.sources = [{"path": str(path), "bytes": len(data),
                             "sha256": hashlib.sha256(data).hexdigest()}]
            self.plan = core.plan("1" * 40, self.sources)
            core.enroll(self.plan, self.sources,
                        boundary=kwargs.get("boundary", "2026-10-01T02:00:00Z"),
                        ingested_at=kwargs.get("ingested_at", "2026-10-01T02:00:00Z"),
                        output=self.output)
            return core.report(self.output, now="2026-10-03T00:00:00Z")

        def stage(self, body, **changes):
            raw = json.dumps(body, allow_nan=False, separators=(",", ":")).encode("utf-8")
            value = {"state": "observed", "http_status": 200,
                     "request_at": "2026-10-02T00:00:00Z",
                     "response_at": "2026-10-02T00:00:02Z",
                     "raw": base64.b64encode(raw).decode("ascii"),
                     "sha256": hashlib.sha256(raw).hexdigest()}
            value.update(changes)
            return value

        def packet(self, ordinal=1):
            records = core.report(self.output, now="2026-10-03T00:00:00Z")["rows"]
            record = next(r for r in records if r["ordinal"] == ordinal)
            address = self.token if ordinal == 1 else "0x" + str(ordinal) * 40
            pool = self.pool if ordinal == 1 else "0x" + "b" * 40
            fields = {k: "0" for k in (
                "is_honeypot", "cannot_sell_all", "cannot_buy", "selfdestruct",
                "personal_slippage_modifiable", "transfer_pausable", "is_blacklisted",
                "slippage_modifiable", "can_take_back_ownership", "owner_change_balance",
                "is_mintable", "trust_list")}
            fields.update(is_open_source="1", holder_count="600", buy_tax="0",
                          sell_tax="0", owner_address="", is_in_cex={"listed": "0"})
            fields["is_honeypot"] = "1"
            reserve = {"data": {"id": "base_" + pool,
                                "attributes": {"address": pool, "reserve_in_usd": "5000"}}}
            ohlcv = {"data": {"attributes": {"ohlcv_list": [[1790899200, 1, 1, 1, 1, 2000]]}}}
            engine = {"address": address, "risk_level": "unknown", "signals": [],
                      "evidence": {"best_pair": {"chain": "base", "pair_address": pool}}}
            return {"schema": 1, "plan_sha256": self.plan["plan_sha256"],
                    "ordinal": ordinal, "source_ref": record["source_ref"],
                    "chain": "base", "token": address, "pool": pool,
                    "engine_source_commit": self.plan["source_commit"],
                    "engine_sha256": self.plan["engine_sha256"],
                    "engine_context_at": "2026-10-02T00:00:01Z",
                    "reserve": self.stage(reserve), "ohlcv": self.stage(ohlcv),
                    "oracle": self.stage({"code": 1, "result": {address: fields}}),
                    "engine": self.stage(engine),
                    "endpoints": {"label": ["https://api.gopluslabs.io/api/v1/token_security/8453?contract_addresses=" + address,
                                                "https://api.geckoterminal.com/api/v2/networks/base/pools/" + pool + "/ohlcv/day"],
                                  "engine": ["https://api.dexscreener.com/latest/dex/tokens/" + address],
                                  "eligibility": ["https://api.geckoterminal.com/api/v2/networks/base/pools/" + pool]}}

        def ingest(self, packet, **kwargs):
            raw = packet if isinstance(packet, bytes) else json.dumps(packet, allow_nan=False).encode("utf-8")
            return core.ingest(self.output, self.sources, raw,
                               private_dir=kwargs.get("private_dir", self.private),
                               imported_at="2026-10-03T00:00:00Z")

        def reject(self, operation, reason):
            try:
                operation()
            except core.EvidenceError as exc:
                return str(exc) == reason
            return False

    if _support:
        return core, Fixture, copy, patch, contextlib
    with Fixture() as f, patch("urllib.request.urlopen", side_effect=AssertionError("network")), patch("time.sleep", side_effect=AssertionError("sleep")):
        report = f.setup()
        check("W40 plans and reports never start a study", f.plan["state"] == report["state"] == "not_started")
        check("W40 original rules are fixed metadata", f.plan["rules"] == {"age_hours": 24, "reserve_usd": 5000, "days": 30, "unsafe_tokens": 18})
        check("W40 plan binds source, rule, label and engine hashes", all(len(f.plan[k]) == 64 for k in ("plan_sha256", "rule_sha256", "label_sha256", "engine_sha256")))
        source = pathlib.Path(f.sources[0]["path"])
        source.write_bytes(source.read_bytes() + b"{}\n")
        check("W40 append-only bytes do not rewrite the declared prefix", core.plan("1" * 40, f.sources)["plan_sha256"] == f.plan["plan_sha256"])
        source.write_bytes(b"X" + source.read_bytes()[1:])
        check("W40 changed source refuses before identity resolution", f.reject(lambda: core.plan("1" * 40, f.sources), "source_hash_mismatch"))
        safe = json.dumps(report) + json.dumps(f.plan)
        check("W40 source paths and addresses never enter safe outputs", f.token not in safe and str(f.root) not in safe and "https://" not in safe)
        default = core.main([])
        check("W40 default CLI is offline help", default == 0)


def test_w40_enrollment_uses_birth_utc_and_never_selects_after_results():
    core, Fixture, copy, patch, _ = test_w40_plan_is_offline_source_bound_and_not_started(True)
    with Fixture() as f:
        first = f.row(pool_created_at="2026-10-01T08:00:00+08:00", goplus_label="unsafe", risk_level="low")
        duplicate = f.row(pool_address="0x" + "c" * 40, fetched_at="2026-10-01T01:30:00Z", reserve_usd="999999")
        invalid = f.row(base_token="base_0x" + "3" * 40, pool_created_at="2026-10-01T00:00:00")
        future = f.row(base_token="base_0x" + "4" * 40, pool_created_at="2026-10-05T00:00:00Z")
        unsupported = f.row(chain="solana", base_token="solana_example")
        missed = f.row(base_token="base_0x" + "5" * 40, pool_created_at="2026-09-28T00:00:00Z", seen_at="2026-09-28T01:00:00Z")
        contradiction = f.row(base_token="base_0x" + "6" * 40, fetched_at="2026-09-30T00:00:00Z")
        report = f.setup([first, duplicate, invalid, future, unsupported, missed, contradiction])
        row = report["rows"][0]
        check("W40 target is normalized birth plus 24h, not first seen", row["target_at"] == "2026-10-02T00:00:00Z")
        check("W40 missing fetched_at stays missing", row["fetched_at"] is None and row["fetch_time_state"] == "missing")
        check("W40 first pool and raw source reference stay fixed", row["source_ref"]["line"] == 1 and report["enrolled"] == 1)
        counts = report["enrollment_counts"]
        check("W40 all excluded rows have named denominators", counts == {"enrolled": 1, "duplicate": 1, "invalid_clock": 2, "future_clock": 1, "unsupported": 1, "missed_before_enrollment": 1, "invalid_row": 0, "row_cap": 0, "cohort_cap": 0})
        check("W40 repeated enrollment cannot select a richer pool", f.reject(lambda: core.enroll(f.plan, f.sources, boundary="2026-10-01T02:00:00Z", ingested_at="2026-10-01T02:00:00Z", output=f.output), "existing_store"))
    with Fixture() as f, patch.object(core, "COHORT_CAP", 1):
        report = f.setup([f.row(), f.row(base_token="base_0x" + "2" * 40, pool_address="0x" + "b" * 40)])
        check("W40 operational cohort cap discloses every omitted row", report["enrolled"] == 1 and report["enrollment_counts"]["cohort_cap"] == 1 and report["limits"]["cohort"] == 1)
    with Fixture() as f:
        report = f.setup(raw=b"X" * (core.ROW_CAP + 1) + b"\n" + (json.dumps(f.row()) + "\n").encode())
        check("W40 bounds rows before parsing and preserves later valid rows", report["enrollment_counts"]["row_cap"] == 1 and report["enrolled"] == 1)

    # T045 round-two (b1) END regression block: bounded identity and real enrollment time.
    import pathlib
    import subprocess
    import sys
    import json as r2_json
    core, R2Fixture, _r2_copy, _r2_patch, _r2_context = test_w40_plan_is_offline_source_bound_and_not_started(True)
    for r2_bad_chain in ([], {}):
        with R2Fixture() as r2_f:
            r2_rows = [r2_f.row(), r2_f.row(chain=r2_bad_chain),
                       r2_f.row(base_token="base_0x" + "2" * 40,
                                pool_address="0x" + "b" * 40, pool_id="base_0x" + "b" * 40)]
            try:
                r2_report = r2_f.setup(r2_rows)
            except Exception as r2_exc:
                check("R2 malformed chain API counts and continues: " + type(r2_bad_chain).__name__, False, type(r2_exc).__name__)
            else:
                check("R2 malformed chain API counts and continues: " + type(r2_bad_chain).__name__,
                      r2_report["enrolled"] == 2 and r2_report["enrollment_counts"]["invalid_row"] == 1
                      and r2_report["enrollment_complete"] and r2_report["unprocessed_source_rows"] == 0
                      and [r["source_ref"]["line"] for r in r2_report["rows"]] == [1, 3])
            r2_sources = r2_f.root / "cli-sources.json"
            r2_plan = r2_f.root / "cli-plan.json"
            r2_sources.write_text(r2_json.dumps(r2_f.sources), encoding="utf-8")
            r2_plan.write_text(r2_json.dumps(r2_f.plan), encoding="utf-8")
            r2_cli = r2_f.root / "cli-safe"
            r2_run = subprocess.run([sys.executable, "-B", str(pathlib.Path(ROOT) / "bench/w40_evidence.py"),
                                     "enroll", "--plan", str(r2_plan), "--sources", str(r2_sources),
                                     "--boundary", "2026-10-01T02:00:00Z", "--ingested-at", "2026-10-01T02:00:00Z",
                                     "--output", str(r2_cli)], cwd=ROOT, capture_output=True, encoding="utf-8")
            r2_safe_text = r2_run.stdout + r2_run.stderr
            r2_cli_report = core.report(r2_cli, now="2026-10-03T00:00:00Z")
            check("R2 actual CLI survives malformed chain: " + type(r2_bad_chain).__name__,
                  r2_run.returncode == 0 and r2_cli_report["enrolled"] == 2
                  and r2_cli_report["enrollment_counts"]["invalid_row"] == 1
                  and r2_cli_report["enrollment_complete"] and "Traceback" not in r2_safe_text
                  and r2_f.token not in r2_safe_text)
    with R2Fixture() as r2_f:
        r2_report = r2_f.setup(boundary="2026-10-01T02:00:00Z", ingested_at="2026-10-03T00:00:00Z")
        check("R2 first ingestion after target cannot backdate fresh enrollment",
              r2_report["enrolled"] == 0 and r2_report["enrollment_counts"]["missed_before_enrollment"] == 1)
        check("R2 delayed enrollment preserves the boundary and first ingestion independently",
              r2_report.get("enrollment_boundary") == "2026-10-01T02:00:00Z"
              and r2_report.get("ingested_at") == "2026-10-03T00:00:00Z")
    # T045 round-two (b1) END regression block ends.



def test_w40_paired_packet_preserves_raw_sources_times_and_identities():
    core, Fixture, copy, patch, _ = test_w40_plan_is_offline_source_bound_and_not_started(True)
    with Fixture() as f:
        f.setup()
        packet = f.packet()
        receipt = f.ingest(packet)
        report = core.report(f.output, now="2026-10-03T00:00:00Z")
        check("W40 raw packet is private, source-bound and hashed", receipt["packet_sha256"] and len(list(f.private.glob("*.packet"))) == 1 and report["receipts"] == 1)
        check("W40 every stage retains its actual request and response times", all(receipt[k]["request_at"] == "2026-10-02T00:00:00Z" and receipt[k]["response_at"] == "2026-10-02T00:00:02Z" and len(receipt[k]["raw_sha256"]) == 64 for k in ("reserve", "ohlcv", "oracle", "engine")))
        check("W40 unknown engine remains a real unknown answer", receipt["engine"]["verdict"] == "unknown" and receipt["engine"]["state"] == "observed")
        safe = b"".join(p.read_bytes() for p in f.output.rglob("*.json"))
        check("W40 safe history never stores raw identity or answer prose", f.token.encode() not in safe and f.pool.encode() not in safe and b"risk_level" not in safe)
    for alteration, expected in (("hash", "invalid_evidence"), ("missing", "missing_raw"), ("parsed", "invalid_evidence"), ("pool", "invalid_evidence")):
        with Fixture() as f:
            f.setup()
            packet = f.packet()
            if alteration == "hash":
                packet["reserve"]["sha256"] = "f" * 64
            elif alteration == "missing":
                del packet["reserve"]["raw"]
            elif alteration == "parsed":
                packet["reserve"]["parsed"] = {"invented": True}
            else:
                packet["pool"] = "0x" + "f" * 40
            receipt = f.ingest(packet)
            check("W40 %s material never becomes an observed reserve" % alteration, receipt["reserve"]["state"] == expected and not receipt["qualified_unsafe_observed"])
    with Fixture() as f:
        f.setup()
        packet = f.packet()
        packet["plan_sha256"] = "f" * 64
        check("W40 packet cannot cross plans", f.reject(lambda: f.ingest(packet), "plan_mismatch"))
        packet = f.packet()
        packet["ordinal"] = 999
        check("W40 packet must name an enrolled ordinal", f.reject(lambda: f.ingest(packet), "ordinal_not_enrolled"))

    # T045 round-two (b2) END regression block: malformed bounded state containers.
    import pathlib
    import subprocess
    import sys
    import json as r2_json
    core, R2Fixture, _r2_copy, _r2_patch, _r2_context = test_w40_plan_is_offline_source_bound_and_not_started(True)
    for r2_bad_state in (["private_state_sentinel"], {"private_state_sentinel": True}):
        for r2_mode in ("api", "cli"):
            with R2Fixture() as r2_f:
                r2_f.setup([r2_f.row(), r2_f.row(base_token="base_0x" + "2" * 40,
                                               pool_address="0x" + "b" * 40, pool_id="base_0x" + "b" * 40)])
                r2_f.ingest(r2_f.packet())
                r2_prior = {p.name: p.read_bytes() for p in (r2_f.output / "events").glob("*.json")}
                r2_packet = r2_f.packet(2)
                r2_packet["oracle"]["state"] = r2_bad_state
                r2_receipt = None
                r2_native = 0
                r2_console = ""
                if r2_mode == "api":
                    try:
                        r2_receipt = r2_f.ingest(r2_packet)
                    except Exception as r2_exc:
                        check("R2 bounded state container API never raises: " + type(r2_bad_state).__name__, False, type(r2_exc).__name__)
                else:
                    r2_sources = r2_f.root / "cli-sources.json"
                    r2_packet_path = r2_f.root / "cli-packet.json"
                    r2_sources.write_text(r2_json.dumps(r2_f.sources), encoding="utf-8")
                    r2_packet_path.write_text(r2_json.dumps(r2_packet), encoding="utf-8")
                    r2_run = subprocess.run([sys.executable, "-B", str(pathlib.Path(ROOT) / "bench/w40_evidence.py"),
                                             "ingest", "--output", str(r2_f.output), "--sources", str(r2_sources),
                                             "--packet", str(r2_packet_path), "--private-dir", str(r2_f.private),
                                             "--imported-at", "2026-10-03T00:00:00Z"], cwd=ROOT, capture_output=True, encoding="utf-8")
                    r2_native = r2_run.returncode
                    r2_console = r2_run.stdout + r2_run.stderr
                    if r2_native == 0:
                        r2_receipt = r2_json.loads(r2_run.stdout)
                r2_report = core.report(r2_f.output, now="2026-10-03T00:00:00Z")
                check("R2 malformed state is invalid evidence with its known observations: " + r2_mode + type(r2_bad_state).__name__,
                      r2_native == 0 and r2_receipt is not None
                      and r2_receipt["oracle"]["state"] == "invalid_evidence"
                      and r2_receipt["oracle"]["http_status"] == 200
                      and r2_receipt["oracle"]["request_at"] == "2026-10-02T00:00:00Z"
                      and r2_receipt["oracle"]["response_at"] == "2026-10-02T00:00:02Z"
                      and r2_report["receipts"] == 2 and not r2_receipt["qualified_unsafe_observed"])
                check("R2 malformed state preserves earlier commits and safe diagnostics: " + r2_mode + type(r2_bad_state).__name__,
                      all((r2_f.output / "events" / name).read_bytes() == raw for name, raw in r2_prior.items())
                      and "Traceback" not in r2_console and "private_state_sentinel" not in r2_console
                      and r2_f.token not in r2_console)
    # T045 round-two (b2) END regression block ends.



def test_w40_label_replay_preserves_existing_rules_and_observation_states():
    core, Fixture, copy, patch, _ = test_w40_plan_is_offline_source_bound_and_not_started(True)
    cases = (("valid", "observed", "unsafe"), ("429", "http_429", None),
             ("403", "http_refusal", None), ("timeout", "timeout", None),
             ("not_asked", "not_asked", None), ("interrupted", "interrupted_intent", None),
             ("wrong_result", "invalid_evidence", None), ("api_error", "invalid_body", None),
             ("empty_volume", "observed", None), ("bad_volume", "observed", None),
             ("missing_field", "observed", None), ("bad_tax", "observed", None))
    for kind, state, label in cases:
        with Fixture() as f:
            f.setup()
            packet = f.packet()
            oracle = json.loads(__import__("base64").b64decode(packet["oracle"]["raw"]))
            if kind in ("429", "403"):
                packet["oracle"]["http_status"] = int(kind)
            elif kind in ("timeout", "not_asked", "interrupted"):
                packet["oracle"]["state"] = {"interrupted": "interrupted_intent"}.get(kind, kind)
            elif kind == "wrong_result":
                oracle["result"] = {"0x" + "f" * 40: next(iter(oracle["result"].values()))}
                packet["oracle"] = f.stage(oracle)
            elif kind == "api_error":
                packet["oracle"] = f.stage({"code": 2, "result": oracle["result"]})
            elif kind == "empty_volume":
                packet["ohlcv"] = f.stage({"data": {"attributes": {"ohlcv_list": []}}})
            elif kind == "bad_volume":
                packet["ohlcv"] = f.stage({"data": {"attributes": {"ohlcv_list": [[1790899200, 1, 1, 1, 1, "NaN"]]}}})
            elif kind == "missing_field":
                del oracle["result"][f.token]["sell_tax"]
                packet["oracle"] = f.stage(oracle)
            elif kind == "bad_tax":
                oracle["result"][f.token]["sell_tax"] = "Infinity"
                packet["oracle"] = f.stage(oracle)
            receipt = f.ingest(packet)
            check("W40 %s retains independent HTTP/field/label availability" % kind, receipt["oracle"]["state"] == state and receipt["oracle"]["label"] == label)
            if kind == "valid":
                check("W40 young OHLCV supplies B11 volume without an outcome label", receipt["ohlcv"]["recent_volume_7d"] == 2000 and receipt["ohlcv"]["outcome_label"] is None)
            if kind in ("empty_volume", "bad_volume"):
                check("W40 unavailable volume never becomes zero", receipt["ohlcv"]["recent_volume_7d"] is None and receipt["oracle"]["label_state"] == "returned_null")
    with Fixture() as f:
        f.setup()
        packet = f.packet()
        packet["reserve"] = f.stage({"data": {"id": "base_" + f.pool, "attributes": {"address": f.pool, "reserve_in_usd": "4999.99"}}})
        receipt = f.ingest(packet)
        check("W40 below-floor reserve is measured, not missing or qualified", receipt["reserve"]["state"] == "observed" and receipt["reserve"]["reserve_usd"] == 4999.99 and not receipt["qualified_unsafe_observed"])

    # T045 round-two (b3) END regression block: acquisition-bound recent daily volume.
    from datetime import datetime as r2_datetime
    import json as r2_json
    core, R2Fixture, _r2_copy, r2_patch, _r2_context = test_w40_plan_is_offline_source_bound_and_not_started(True)
    def r2_candle(stamp, volume=2000):
        return [int(r2_datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()), 1, 1, 1, 1, volume]
    for r2_kind in ("one_year_old", "pre_birth", "historical_query", "outside_recent_window", "positive"):
        with R2Fixture() as r2_f:
            r2_f.setup()
            r2_packet = r2_f.packet()
            r2_rows = [r2_candle("2026-10-02T00:00:00Z")]
            r2_imported = "2026-10-03T00:00:00Z"
            if r2_kind == "one_year_old":
                r2_rows = [r2_candle("2025-10-02T00:00:00Z")]
            elif r2_kind == "pre_birth":
                r2_rows = [r2_candle("2026-09-30T00:00:00Z")]
            elif r2_kind == "historical_query":
                r2_packet["endpoints"]["label"][1] += "?before_timestamp=1759363200"
            r2_packet["ohlcv"] = r2_f.stage({"data": {"attributes": {"ohlcv_list": r2_rows}}})
            if r2_kind == "outside_recent_window":
                r2_packet["ohlcv"]["request_at"] = "2026-10-10T00:00:00Z"
                r2_packet["ohlcv"]["response_at"] = "2026-10-10T00:00:02Z"
                r2_imported = "2026-10-11T00:00:00Z"
            with r2_patch.object(core.labels, "goplus_label", wraps=core.labels.goplus_label) as r2_label:
                r2_receipt = core.ingest(r2_f.output, r2_f.sources, r2_json.dumps(r2_packet).encode("utf-8"),
                                         private_dir=r2_f.private, imported_at=r2_imported)
                r2_report = core.report(r2_f.output, now=r2_imported)
                r2_volume = r2_label.call_args.kwargs["recent_volume_7d"] if r2_label.call_count else "not_called"
            if r2_kind == "positive":
                check("R2 contemporaneous daily candle still uses unchanged helper and B11",
                      r2_receipt["ohlcv"]["recent_volume_7d"] == r2_volume == 2000
                      and r2_receipt["oracle"]["label"] == "unsafe"
                      and r2_report["qualified_unsafe_observed"] == 1)
                check("R2 sparse observed candles never claim full recent time coverage",
                      r2_receipt["ohlcv"].get("recent_days_observed") == 1
                      and r2_receipt["ohlcv"].get("recent_window_complete") is False)
            else:
                check("R2 historical volume cannot satisfy B11: " + r2_kind,
                      r2_receipt["ohlcv"]["recent_volume_7d"] is None and r2_volume is None
                      and r2_receipt["oracle"]["label"] is None
                      and r2_report["qualified_unsafe_observed"] == 0)
                check("R2 historical volume keeps raw and acquisition evidence: " + r2_kind,
                      r2_receipt["ohlcv"]["raw_sha256"] == r2_packet["ohlcv"]["sha256"]
                      and r2_receipt["ohlcv"]["request_at"] == r2_packet["ohlcv"]["request_at"]
                      and r2_receipt["ohlcv"]["response_at"] == r2_packet["ohlcv"]["response_at"]
                      and r2_report["state"] == "not_started")
    # T045 round-two (b3) END regression block ends.



def test_w40_timing_and_endpoint_overlap_never_become_passes():
    core, Fixture, copy, patch, _ = test_w40_plan_is_offline_source_bound_and_not_started(True)
    for kind in ("late", "overlap", "empty", "pool"):
        with Fixture() as f:
            f.setup()
            packet = f.packet()
            if kind == "late":
                packet["oracle"]["request_at"] = "2026-10-02T00:10:00Z"
                packet["oracle"]["response_at"] = "2026-10-02T00:10:02Z"
            elif kind == "overlap":
                packet["endpoints"]["engine"].append(packet["endpoints"]["label"][1])
            elif kind == "empty":
                packet["endpoints"]["label"] = []
            else:
                engine = {"address": f.token, "risk_level": "low", "signals": [],
                          "evidence": {"best_pair": {"chain": "base", "pair_address": "0x" + "f" * 40}}}
                packet["engine"] = f.stage(engine)
            receipt = f.ingest(packet)
            if kind == "late":
                check("W40 actual lateness and skew remain numeric without a tolerance claim", receipt["timing"]["lateness_seconds"] == 600 and receipt["timing"]["skew_seconds"] == 602 and receipt["timing"]["tolerance"] is None)
            elif kind == "overlap":
                check("W40 real endpoint intersection fails independence", receipt["independence"]["state"] == "independence_failed" and len(receipt["independence"]["overlap"]) == 1 and not receipt["qualified_unsafe_observed"])
            elif kind == "empty":
                check("W40 missing endpoint set is unobserved, never empty-intersection success", receipt["independence"]["state"] == "independence_unobserved" and not receipt["qualified_unsafe_observed"])
            else:
                check("W40 different selected engine pool stays visible", receipt["pool_mismatch"] is True and not receipt["qualified_unsafe_observed"])
            check("W40 shared eligibility evidence remains disclosed", receipt["independence"]["eligibility_shared"] in (True, False) and receipt["timing"]["simultaneous_claim"] is False)

    # T045 round-two (b4) END regression block: independent availability and clocks.
    core, R2Fixture, _r2_copy, _r2_patch, _r2_context = test_w40_plan_is_offline_source_bound_and_not_started(True)
    for r2_kind in ("timeout", "transport_error", "429", "invalid_request", "reversed"):
        with R2Fixture() as r2_f:
            r2_f.setup()
            r2_packet = r2_f.packet()
            if r2_kind in ("timeout", "transport_error", "429"):
                r2_packet["oracle"] = {"state": "observed" if r2_kind == "429" else r2_kind,
                                       "request_at": "2026-10-02T00:00:00Z", "response_at": None,
                                       "http_status": 429 if r2_kind == "429" else None}
            elif r2_kind == "invalid_request":
                r2_packet["oracle"]["request_at"] = "invalid_clock_sentinel"
            else:
                r2_packet["oracle"]["response_at"] = "2026-10-01T23:59:59Z"
            r2_receipt = r2_f.ingest(r2_packet)
            r2_stage = r2_receipt["oracle"]
            if r2_kind in ("timeout", "transport_error", "429"):
                r2_expected = "http_429" if r2_kind == "429" else r2_kind
                check("R2 missing response preserves availability and known request: " + r2_kind,
                      r2_stage["state"] == r2_expected
                      and r2_stage["http_status"] == (429 if r2_kind == "429" else None)
                      and r2_stage["request_at"] == "2026-10-02T00:00:00Z"
                      and r2_stage["response_at"] is None and r2_stage.get("response_time_state") == "missing"
                      and r2_stage.get("timing_state") == "missing_clock")
            else:
                check("R2 actual invalid or reversed clocks remain invalid: " + r2_kind,
                      r2_stage.get("timing_state") == "invalid_clock")
                if r2_kind == "invalid_request":
                    check("R2 invalid request does not erase the valid response clock",
                          r2_stage["request_at"] is None and r2_stage["response_at"] == "2026-10-02T00:00:02Z")
            check("R2 incomplete or invalid clock never qualifies or invents simultaneity: " + r2_kind,
                  not r2_receipt["qualified_unsafe_observed"]
                  and r2_receipt["timing"]["simultaneous_claim"] is False)
    # T045 round-two (b4) END regression block ends.



def test_w40_partial_history_is_append_only_private_and_recoverable():
    core, Fixture, copy, patch, contextlib = test_w40_plan_is_offline_source_bound_and_not_started(True)
    import hashlib
    import pathlib
    import io as stream
    with Fixture() as f:
        f.setup([f.row(), f.row(base_token="base_0x" + "2" * 40, pool_address="0x" + "b" * 40)])
        first = f.packet()
        f.ingest(first)
        before = {str(p.relative_to(f.output)): p.read_bytes() for p in f.output.rglob("*.json")}
        check("W40 committed ordinal cannot be overwritten", f.reject(lambda: f.ingest(first), "existing_receipt"))
        check("W40 refusal leaves every previous safe byte exact", before == {str(p.relative_to(f.output)): p.read_bytes() for p in f.output.rglob("*.json")})
        real = core._atomic_index
        def fail_commit(path, index):
            if index["last"] == 7:
                raise OSError("private sentinel must not be printed")
            return real(path, index)
        with patch.object(core, "_atomic_index", side_effect=fail_commit):
            check("W40 failed final persistence is fixed-category failure", f.reject(lambda: f.ingest(f.packet(2)), "persistence_failed"))
        report = core.report(f.output, now="2026-10-03T00:00:00Z")
        check("W40 earlier receipt survives uncertain second import", report["receipts"] == 1 and report["pending_intents"] == 1 and report["orphan_events"] == 1)
        check("W40 repeat uncertain import cannot resume or overwrite", f.reject(lambda: f.ingest(f.packet(2)), "incomplete_history"))
    for location in ("nested", "git", "ci"):
        with Fixture() as f:
            f.setup()
            raw = f.private
            if location == "nested":
                raw = f.output / "raw"
            elif location == "git":
                raw = f.root / "checkout" / "raw"
                raw.parent.mkdir()
                (raw.parent / ".git").write_text("gitdir: example", encoding="utf-8")
            environment = {"CI": "true"} if location == "ci" else {"CI": "", "GITHUB_ACTIONS": ""}
            with patch.dict(os.environ, environment):
                check("W40 %s raw location refuses before raw writes" % location, f.reject(lambda: f.ingest(f.packet(), private_dir=raw), "raw_directory_refused") and not raw.exists())
    with Fixture() as f:
        f.setup()
        lock = f.output / ".writer"
        lock.write_bytes(b"occupied")
        check("W40 overlapping writer is refused", f.reject(lambda: f.ingest(f.packet()), "writer_busy"))
        lock.unlink()
        check("W40 packet is bounded before JSON parsing", f.reject(lambda: f.ingest(b"X" * (core.PACKET_CAP + 1)), "packet_limit"))
        packet = f.packet()
        packet["reserve"]["raw"] = __import__("base64").b64encode(b"X" * (core.RAW_CAP + 1)).decode()
        check("W40 raw field is bounded before decoding/parsing", f.reject(lambda: f.ingest(packet), "raw_limit"))


def test_w40_readout_keeps_original_calendar_bar_and_every_denominator():
    core, Fixture, copy, patch, contextlib = test_w40_plan_is_offline_source_bound_and_not_started(True)
    with Fixture() as f:
        f.setup([f.row(), f.row(base_token="base_0x" + "2" * 40, pool_address="0x" + "b" * 40)])
        f.ingest(f.packet())
        report = core.report(f.output, now="2026-11-02T00:00:00Z")
        check("W40 even complete-looking imported evidence cannot start the clock", report["state"] == "not_started" and report["original_unsafe_target"] == 18 and report["qualified_unsafe_observed"] == 1)
        check("W40 unasked denominator survives independently of label counts", report["enrolled"] == 2 and report["receipts"] == 1 and report["unasked"] == 1 and report["outcome"] == "not_evaluated")
        start = {"schema": 1, "plan_sha256": f.plan["plan_sha256"], "source_commit": f.plan["source_commit"],
                 "started_at": "2026-10-03T00:00:00Z", "evidence_sha256": "e" * 64}
        before = core.report(f.output, now="2026-11-01T23:59:59Z", live_start=start)
        after = core.report(f.output, now="2026-11-02T00:00:00Z", live_start=start)
        check("W40 thirty-day boundary is exact and external receipt stays declared", before["state"] == "not_due" and after["state"] == "readout_due" and after["clock_evidence"] == "declared_external_observation")
        check("W40 due readout never automatically declares W40 success", after["outcome"] == "not_evaluated" and after["original_unsafe_target"] == 18)
        check("W40 reports stay within their byte bound", len(json.dumps(after).encode()) <= core.REPORT_CAP)
        altered = copy.deepcopy(start)
        altered["plan_sha256"] = "f" * 64
        check("W40 unrelated quota or old-study receipt cannot start this plan", f.reject(lambda: core.report(f.output, now="2026-11-02T00:00:00Z", live_start=altered), "invalid_live_start"))
        packet = f.packet(2)
        packet["oracle"]["http_status"] = 429
        f.ingest(packet)
        final = core.report(f.output, now="2026-11-02T00:00:00Z")
        check("W40 refusal never contributes an unsafe observation", final["qualified_unsafe_observed"] == 1 and final["oracle_states"]["http_429"] == 1 and final["unasked"] == 0)
    with Fixture() as f:
        report = f.setup([])
        check("W40 zero denominators stay zero, without fabricated rates", report["enrolled"] == report["receipts"] == report["unasked"] == report["qualified_unsafe_observed"] == 0 and report["enrollment_complete"])


def main():
    print("=" * 68)
    print("The frozen dataset can re-derive its own labels")
    print("=" * 68)
    for _, fn in sorted((k, v) for k, v in globals().items() if k.startswith("test_")):
        fn()
    print("\n" + "=" * 68)
    print("%d passed, %d failed, %d not checked here"
          % (_PASSED, len(_FAILURES), len(_UNCHECKED)))
    for name, why in _UNCHECKED:
        print("  ----  %s  (%s)" % (name, why))
    if _FAILURES:
        print("\nFailures:")
        for name, detail in _FAILURES:
            print("  - %s  %s" % (name, detail))
        return 1
    print("All passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
