"""Finite W57 sessions, with the unchanged v1 module as the scientific boundary.

The legacy three-key source schema is retained explicitly: driver and probe are
raw-file SHA256 values; workflow is a COMPOSITE digest of the raw workflow,
session adapter and generator hashes, domain-separated by CONTROL_DOMAIN.
Every v2 envelope carries all five raw hashes. A raw workflow digest is never
presented as the composite. Historical v1 decoding/reporting remains available.

The immutable admission index is a copy of the terminal generation's core
files, with its exact ID/manifest digest in the transport envelope. It is not a
mutable latest pointer. An unresolved admission intent blocks new enrollment.
"""
import argparse
import copy
import datetime
import io
import json
import os
from pathlib import Path
import re
import sys
import time
import zipfile

import rugcheck_w57_ci as core

ROOT = Path(__file__).resolve().parents[1]
StudyError = core.StudyError
CONTROL_DOMAIN = "w57-session-control-composite-v2"
SOURCES = {"driver": "bench/rugcheck_w57_ci.py", "probe": "bench/rugcheck_coverage_probe.py",
           "session": "bench/rugcheck_w57_session.py", "workflow": core.WORKFLOW,
           "generator": ".github/scripts/render_w57_session_workflow.py"}
ADMISSION_NAMES = ("w57-intent-v1", "w57-result-v1",
                   "w57-admission-intent-v2", "w57-admission-result-v2")
NAME = re.compile(r"w57-(live|canary)-([a-z0-9][a-z0-9-]{0,47})-r([1-9][0-9]*)-g([0-9]{3})-(intent|result)-v2\Z")
CLOSURE_NAME = re.compile(r"w57-(live|canary)-closure-r([1-9][0-9]*)-v2\Z")
RESERVE = 300
JOB_SECONDS = 330 * 60
MAX_WAIT = 30
DRIFT = 2


def source_freeze():
    return {key: core.sha((ROOT / path).read_bytes()) for key, path in SOURCES.items()}


def composite(freeze):
    if (not isinstance(freeze, dict) or set(freeze) != set(SOURCES)
            or any(not isinstance(x, str) or not core.SHA.fullmatch(x) for x in freeze.values())):
        raise StudyError("invalid_control_sources")
    return {"driver": freeze["driver"], "probe": freeze["probe"],
            "workflow": core.sha(core.encoded({"domain": CONTROL_DOMAIN,
                                              **{key: freeze[key] for key in ("workflow", "session", "generator")}}))}


def source_hashes():
    return composite(source_freeze())


def _source_guard(expected):
    """Rehash changed files; module code already loaded for this bounded phase."""
    stamps = {key: ((ROOT / path).stat().st_mtime_ns, (ROOT / path).stat().st_size)
              for key, path in SOURCES.items()}
    if source_hashes() != expected:
        raise StudyError("source_changed")
    def check():
        current = {key: ((ROOT / path).stat().st_mtime_ns, (ROOT / path).stat().st_size)
                   for key, path in SOURCES.items()}
        if current != stamps:
            if source_hashes() != expected:
                raise StudyError("source_changed")
            stamps.update(current)
    return check


def context(env=None):
    env = os.environ if env is None else env
    try:
        # This check precedes construction of any transport, including the canary.
        if env.get("GITHUB_RUN_ATTEMPT") != "1":
            raise StudyError("rerun_refused")
        freeze = source_freeze()
        ctx = {"repository": env["GITHUB_REPOSITORY"], "workflow": core.WORKFLOW,
               "branch": env["GITHUB_REF_NAME"], "default_branch": env["W57_DEFAULT_BRANCH"],
               "head": env["GITHUB_SHA"], "run_id": int(env["GITHUB_RUN_ID"]), "attempt": 1,
               "source": composite(freeze), "control_sources": freeze}
        if (ctx["branch"] != ctx["default_branch"] or env.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
                or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", ctx["repository"])
                or not re.fullmatch(r"[0-9a-f]{40}", ctx["head"]) or ctx["run_id"] <= 0):
            raise StudyError("untrusted_run")
        return ctx
    except (KeyError, ValueError, TypeError):
        raise StudyError("ci_context_unavailable") from None


class Clock:
    def utc(self):
        return time.time()

    def monotonic(self):
        return time.monotonic()

    def sleep(self, seconds):
        time.sleep(seconds)


class Lease:
    """An absolute hosted-job limit; serialized once, never renewed by a step."""
    def __init__(self, clock, seconds=JOB_SECONDS, record=None):
        if not core.number(seconds) or not RESERVE < seconds <= JOB_SECONDS:
            raise StudyError("invalid_job_limit")
        self.record = record or {"utc": clock.utc(), "monotonic": clock.monotonic(), "seconds": seconds}
        if (set(self.record) != {"utc", "monotonic", "seconds"}
                or any(not core.number(x) for x in self.record.values())
                or not RESERVE < self.record["seconds"] <= JOB_SECONDS):
            raise StudyError("invalid_job_clock")

    def check(self, clock, request_seconds=0):
        elapsed = clock.monotonic() - self.record["monotonic"]
        wall = clock.utc() - self.record["utc"]
        if elapsed < 0 or abs(wall - elapsed) > DRIFT:
            raise StudyError("clock_changed")
        if elapsed + request_seconds + RESERVE >= self.record["seconds"]:
            raise StudyError("job_preservation_reserve")
        return self.record["seconds"] - RESERVE - elapsed


def wait_due(clock, due, lease, request_seconds=32, check=None):
    if not core.number(due):
        raise StudyError("invalid_due")
    while True:
        room = lease.check(clock, request_seconds)
        if check:
            check()
        delay = due - clock.utc()
        if delay <= 0:
            return
        if delay + request_seconds >= room:
            raise StudyError("due_outside_job_lease")
        clock.sleep(min(delay, MAX_WAIT))


def _valid_clock_proof(proof, source):
    """Validate the recorded sampling lease, never a new reporting-job lease."""
    try:
        lease = proof["lease"]
        if (proof.get("stable") is not True or set(lease) != {"utc", "monotonic", "seconds"}
                or any(not core.number(value) for value in lease.values())
                or not RESERVE < lease["seconds"] <= JOB_SECONDS
                or not core.number(proof["utc"]) or not core.number(proof["monotonic"])
                or composite(proof["control_sources"]) != source):
            return False
        elapsed = proof["monotonic"] - lease["monotonic"]
        wall = proof["utc"] - lease["utc"]
        return elapsed >= 0 and abs(wall - elapsed) <= DRIFT and elapsed + RESERVE < lease["seconds"]
    except (KeyError, TypeError, ValueError, StudyError):
        return False


def _state_clock_stable(state):
    controls = state["session"]
    return (_valid_clock_proof(controls.get("end_clock"), state["source"])
            and ("seal_clock" not in controls or _valid_clock_proof(controls["seal_clock"], state["source"])))


def _seal_clock(state, ctx, clock, lease, key="end_clock"):
    """A tail jump remains failed even if finalization later sees a healthy clock."""
    proof = {"lease": copy.deepcopy(lease.record), "utc": clock.utc(), "monotonic": clock.monotonic(),
             "control_sources": source_freeze(), "stable": False}
    failure = None
    try:
        lease.check(clock)
        if composite(proof["control_sources"]) != state["source"] or ctx["control_sources"] != proof["control_sources"]:
            raise StudyError("source_changed")
        proof["stable"] = True
    except StudyError as exc:
        failure = str(exc)
    controls = state["session"]
    earlier_failure = any(name in controls and not _valid_clock_proof(controls[name], state["source"])
                          for name in ("end_clock", "seal_clock"))
    if key not in controls or _valid_clock_proof(controls[key], state["source"]):
        controls[key] = proof
    if failure or earlier_failure:
        controls["failure"] = failure or controls.get("failure", "clock_changed")
        state["status"] = "source_changed" if controls["failure"] == "source_changed" else "failed"


def bind_state(state, ctx, namespace):
    state = copy.deepcopy(state)
    state["source"] = copy.deepcopy(ctx["source"])
    state["session"] = {"schema": 2, "namespace": namespace,
                        "freeze": copy.deepcopy(ctx["control_sources"])}
    return state


def _validate(state, namespace):
    session = state.get("session", {}) if isinstance(state, dict) else {}
    if (namespace not in ("live", "canary") or session.get("schema") != 2
            or session.get("namespace") != namespace or composite(session.get("freeze")) != state.get("source")):
        raise StudyError("invalid_session_state")
    if namespace == "live":
        core._validate_state(state)
    elif (state.get("schema") != 2 or state.get("status") not in core.TERMINAL | {"active"}
          or not core.STUDY_ID.fullmatch(str(state.get("study", "")))
          or type(state.get("generation")) is not int or not 0 <= state["generation"] <= 3
          or state.get("members") != ["synthetic-%02d" % x for x in range(63)]
          or not core.number(state.get("started_at")) or state.get("ends_at") != state["started_at"] + 1800
          or not isinstance(state.get("chunks"), list) or len(state["chunks"]) > 3
          or not isinstance(state.get("slots"), list) or len(state["slots"]) > 3
          or state.get("vendor_requests") != 0 or state.get("scientific_evidence") is not False
          or len(core.encoded(state)) > core.STATE_BYTES):
        raise StudyError("invalid_canary_state")


def canary_state(ctx, now):
    return bind_state({"schema": 2, "study": "canary-%d" % ctx["run_id"], "phase": "canary",
                       "status": "active", "generation": 0, "parent": None, "chunks": [], "slots": [],
                       "started_at": now, "ends_at": now + 1800, "vendor_requests": 0,
                       "scientific_evidence": False, "members": ["synthetic-%02d" % i for i in range(63)]}, ctx, "canary")


def artifact_name(state, kind, ctx, namespace="live"):
    if kind in ("admission-intent", "admission-result"):
        if namespace != "live":
            raise StudyError("canary_admission_forbidden")
        return "w57-%s-v2" % kind
    if kind not in ("intent", "result") or namespace not in ("live", "canary"):
        raise StudyError("artifact_identity")
    return "w57-%s-%s-r%d-g%03d-%s-v2" % (namespace, state["study"], ctx["run_id"], state["generation"], kind)


def _parse(data):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise StudyError("duplicate_json_key")
            value[key] = item
        return value
    return json.loads(data, object_pairs_hook=unique)


def _zip(files):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            entry = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, data)
    return stream.getvalue()


def _files(state, rows, kind, ctx, namespace, unverified=None):
    state = copy.deepcopy(state)
    dependency = state.get("session", {}).pop("last_durable", None) if kind == "admission-result" else None
    _validate(state, namespace)
    actual_kind = kind.removeprefix("admission-")
    if (actual_kind not in ("intent", "result") or not isinstance(rows, list) or len(rows) > 256
            or any(not isinstance(row, dict) or len(core.encoded(row)) > 2048 for row in rows)
            or (actual_kind == "intent" and rows)):
        raise StudyError("bundle_bounds")
    if namespace == "live":
        files = core._bundle_files(state, rows, actual_kind, ctx, unverified)
    else:
        data, body = core.encoded(state), b"".join(core.encoded(row) + b"\n" for row in rows)
        files = {"state.json": data, "observations.jsonl": body}
        if unverified is not None:
            files["unverified.jsonl"] = unverified
        files["manifest.json"] = core.encoded({"schema": 2, "kind": actual_kind, "study": state["study"],
                                              "generation": state["generation"], "parent": state["parent"],
                                              "context": ctx, "rows": len(rows),
                                              "files": {name: core.sha(value) for name, value in files.items()}})
    digest = core.sha(files["manifest.json"])
    if kind == "admission-result":
        if (not isinstance(dependency, dict) or set(dependency) != {"id", "digest"}
                or type(dependency["id"]) is not int or dependency["id"] <= 0 or dependency["digest"] != digest
                or state["status"] not in core.TERMINAL):
            raise StudyError("admission_dependency")
    transport = {"schema": 2, "namespace": namespace, "kind": kind, "study": state["study"],
                 "generation": state["generation"], "parent": state["parent"], "context": ctx,
                 "control_sources": state["session"]["freeze"], "core_digest": digest,
                 "last_durable": dependency}
    files["transport.json"] = core.encoded(transport)
    limit = core.INTENT_BYTES if actual_kind == "intent" else core.BUNDLE_BYTES
    if sum(map(len, files.values())) > limit:
        raise StudyError("bundle_overflow")
    return files


def bundle_bytes(state, rows, kind, ctx, namespace="live"):
    files = _files(state, rows, kind, ctx, namespace)
    data = _zip(files)
    if len(data) > (core.INTENT_BYTES if kind.endswith("intent") else core.BUNDLE_BYTES):
        raise StudyError("bundle_overflow")
    return data


def decode_bundle(data, provenance, expected):
    try:
        if not isinstance(data, bytes) or len(data) > core.BUNDLE_BYTES:
            raise StudyError("bundle_overflow")
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            names = [item.filename for item in entries]
            if len(names) != len(set(names)) or sum(item.file_size for item in entries) > core.BUNDLE_BYTES:
                raise StudyError("bundle_files")
            if any(item.flag_bits & 1 for item in entries):
                raise StudyError("bundle_files")
            if "transport.json" not in names:
                return core.decode_bundle(data, provenance, expected)
            required = {"state.json", "observations.jsonl", "manifest.json", "transport.json"}
            if set(names) not in (required, required | {"unverified.jsonl"}):
                raise StudyError("bundle_files")
            files = {name: archive.read(name) for name in names}
        transport = _parse(files.pop("transport.json"))
        manifest, state = _parse(files["manifest.json"]), _parse(files["state.json"])
        rows = [_parse(line) for line in files["observations.jsonl"].splitlines()]
        namespace, kind, ctx = transport["namespace"], transport["kind"], transport["context"]
        _validate(state, namespace)
        if (transport.get("schema") != 2 or transport.get("control_sources") != state["session"]["freeze"]
                or transport.get("core_digest") != core.sha(files["manifest.json"])
                or ctx != manifest.get("context") or ctx.get("attempt") != 1
                or composite(ctx.get("control_sources")) != ctx.get("source")
                or (state.get("status") != "source_changed" and
                    (ctx.get("source") != state["source"] or ctx.get("control_sources") != transport["control_sources"]))
                or kind not in ("intent", "result", "admission-intent", "admission-result")
                or (namespace == "canary" and kind.startswith("admission-"))
                or any(transport.get(key) != state.get(key) for key in ("study", "generation", "parent"))
                or len(rows) > 256 or any(not isinstance(row, dict) or len(core.encoded(row)) > 2048 for row in rows)):
            raise StudyError("bundle_manifest")
        actual_kind = kind.removeprefix("admission-")
        if manifest.get("kind") != actual_kind or (actual_kind == "intent" and rows):
            raise StudyError("bundle_manifest")
        for key in ("repository", "workflow", "branch", "run_id", "head"):
            if ctx.get(key) != provenance.get(key):
                raise StudyError("artifact_provenance")
        if (ctx.get("repository") != expected["repository"] or ctx.get("workflow") != core.WORKFLOW
                or ctx.get("branch") != expected["default_branch"]
                or ctx.get("default_branch") != expected["default_branch"]
                or type(ctx.get("run_id")) is not int or ctx["run_id"] <= 0
                or not re.fullmatch(r"[0-9a-f]{40}", str(ctx.get("head", "")))):
            raise StudyError("artifact_provenance")
        if namespace == "live":
            decoded = core.decode_bundle(_zip(files), provenance, expected)
        else:
            if (manifest.get("files") != {name: core.sha(value) for name, value in files.items() if name != "manifest.json"}
                    or manifest.get("rows") != len(rows) or manifest.get("study") != state["study"]
                    or manifest.get("generation") != state["generation"] or manifest.get("parent") != state["parent"]
                    or len({(row.get("slot"), row.get("member")) for row in rows}) != len(rows)):
                raise StudyError("bundle_manifest")
            decoded = {"state": state, "rows": rows, "manifest": manifest, "digest": core.sha(files["manifest.json"])}
        if kind == "admission-result":
            reference = transport.get("last_durable")
            if (not isinstance(reference, dict) or set(reference) != {"id", "digest"}
                    or type(reference["id"]) is not int or reference["id"] <= 0
                    or reference["digest"] != decoded["digest"] or state["status"] not in core.TERMINAL):
                raise StudyError("admission_dependency")
            decoded["state"]["session"]["last_durable"] = reference
        elif transport.get("last_durable") is not None:
            raise StudyError("admission_dependency")
        if actual_kind == "intent" and sum(map(len, files.values())) + len(core.encoded(transport)) > core.INTENT_BYTES:
            raise StudyError("intent_overflow")
        decoded["transport"] = transport
        decoded["zip_digest"] = core.sha(data)
        return decoded
    except StudyError:
        raise
    except (KeyError, ValueError, TypeError, AttributeError, OSError, RuntimeError, zipfile.BadZipFile):
        raise StudyError("artifact_malformed") from None


class Artifacts(core.GitHubArtifacts):
    """Raw metadata is validated before the v1 scientific adapter sees a view."""
    def __init__(self, ctx, token, report=False, admission=False):
        super().__init__(ctx, token, max_reads=600 if report else 16 if admission else 12,
                         max_downloads=195 if report else 3 if admission else 2,
                         seconds=720 if report else 110)
        self.runs, self.seconds_spent = {}, 0

    def request(self, path, binary=False):
        started = time.monotonic()
        try:
            return super().request(path, binary)
        finally:
            self.seconds_spent += time.monotonic() - started

    def _meta(self, row):
        try:
            ident, name, run, created = row["id"], row["name"], row["workflow_run"], row["created_at"]
            match = NAME.fullmatch(name)
            fixed = name in ADMISSION_NAMES or bool(CLOSURE_NAME.fullmatch(name))
            if (type(ident) is not int or ident <= 0 or not isinstance(name, str) or not (match or fixed)
                    or type(row.get("size_in_bytes")) is not int or not 0 < row["size_in_bytes"] <= core.BUNDLE_BYTES
                    or row.get("expired") is not False
                    or not re.fullmatch(r"sha256:[0-9a-f]{64}", str(row.get("digest", "")))
                    or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)", created)
                    or type(run.get("id")) is not int or run["id"] <= 0
                    or not re.fullmatch(r"[0-9a-f]{40}", str(run.get("head_sha", "")))
                    or run.get("head_branch") != self.ctx["default_branch"]):
                raise StudyError("artifact_metadata")
            moment = datetime.datetime.fromisoformat(created.replace("Z", "+00:00")).timestamp()
            if match and (int(match[3]) != run["id"] or not 0 <= int(match[4]) <= 196):
                raise StudyError("artifact_identity")
            return moment, match
        except StudyError:
            raise
        except (KeyError, TypeError, ValueError, AttributeError):
            raise StudyError("artifact_metadata") from None

    def list(self, scope="run", namespace="live"):
        found, scans = [], 0
        names = ADMISSION_NAMES if scope == "admission" else (None,)
        for name in names:
            total, received = None, 0
            for page in range(1, 6):
                if scans >= 5:
                    raise StudyError("artifact_scan_limit")
                scans += 1
                prefix = "/repos/%s/actions/" % self.ctx["repository"]
                endpoint = "artifacts?name=%s&" % name if name else "runs/%d/artifacts?" % self.ctx["run_id"]
                body = self.request(prefix + endpoint + "per_page=100&page=%d" % page)
                if (not isinstance(body, dict) or type(body.get("total_count")) is not int
                        or body["total_count"] < 0 or not isinstance(body.get("artifacts"), list)
                        or len(body["artifacts"]) > 100):
                    raise StudyError("artifact_partial_page")
                if total is None:
                    total = body["total_count"]
                if body["total_count"] != total:
                    raise StudyError("artifact_partial_page")
                rows = body["artifacts"]
                for row in rows:
                    self._meta(row)
                    if name and row["name"] != name:
                        raise StudyError("artifact_unexpected_row")
                    if not name and row["workflow_run"]["id"] != self.ctx["run_id"]:
                        raise StudyError("artifact_provenance")
                found.extend(rows)
                received += len(rows)
                if received > total or (len(rows) < 100 and received != total):
                    raise StudyError("artifact_partial_page")
                if received == total:
                    break
            else:
                raise StudyError("artifact_scan_limit")
        seen, publications, ties, ordered = set(), set(), {}, []
        for row in found:
            moment, match = self._meta(row)
            run = row["workflow_run"]
            generation = int(match[4]) if match else -1
            kind = match[5] if match else "result" if "result" in row["name"] else "intent"
            publication = (run["id"], row["name"])
            if row["id"] in seen or publication in publications:
                raise StudyError("artifact_duplicate")
            seen.add(row["id"])
            publications.add(publication)
            ties.setdefault(moment, set()).add((run["id"], run["head_sha"]))
            ordered.append((moment, generation, kind == "result", row))
        # Same-run generations have an explicit logical order, even in one API second.
        if any(len(group) > 1 for group in ties.values()):
            raise StudyError("artifact_chronology_ambiguous")
        result = [row for _, _, _, row in sorted(ordered, key=lambda item: item[:3])]
        logical = {}
        for row in result:
            match = NAME.fullmatch(row["name"])
            if match:
                logical.setdefault((int(match[3]), match[1]), []).append((int(match[4]), match[5] == "result"))
        if any(value != sorted(value) for value in logical.values()):
            raise StudyError("artifact_chronology")
        self.metadata.update({row["id"]: row for row in result})
        return result

    def load(self, ident):
        if self.downloads >= self.max_downloads or type(ident) is not int or ident <= 0:
            raise StudyError("artifact_download_budget")
        base = "/repos/%s/actions/" % self.ctx["repository"]
        meta = self.metadata.get(ident)
        if meta is None:
            meta = self.request(base + "artifacts/%d" % ident)
        _, match = self._meta(meta)
        if meta["id"] != ident:
            raise StudyError("artifact_identity")
        run_id = meta["workflow_run"]["id"]
        if run_id not in self.runs:
            self.runs[run_id] = self.request(base + "runs/%d" % run_id)
        run = self.runs[run_id]
        try:
            legacy = meta["name"].endswith("-v1")
            if (run["id"] != run_id or run["head_sha"] != meta["workflow_run"]["head_sha"]
                    or run["repository"]["full_name"] != self.ctx["repository"]
                    or run["head_repository"]["full_name"] != self.ctx["repository"]
                    or run["path"] != core.WORKFLOW or run["head_branch"] != self.ctx["default_branch"]
                    or run["event"] not in (("schedule", "workflow_dispatch") if legacy else ("workflow_dispatch",))
                    or (not legacy and (run.get("run_attempt") != 1
                                        or run.get("status") not in ("in_progress", "completed")
                                        or run.get("conclusion") not in (None, "success")))):
                raise StudyError("artifact_provenance")
            provenance = {"repository": run["repository"]["full_name"], "workflow": run["path"],
                          "branch": run["head_branch"], "run_id": run_id, "head": run["head_sha"]}
            self.downloads += 1
            data = self.request(base + "artifacts/%d/zip" % ident, binary=True)
            if len(data) != meta["size_in_bytes"] or "sha256:" + core.sha(data) != meta["digest"]:
                raise StudyError("artifact_zip_digest")
            decoded = decode_bundle(data, provenance, self.ctx)
            if legacy:
                if decoded["manifest"]["kind"] != core.ARTIFACT.fullmatch(meta["name"])[1]:
                    raise StudyError("artifact_identity")
            else:
                transport = decoded["transport"]
                expected = artifact_name(decoded["state"], transport["kind"], transport["context"], transport["namespace"])
                if expected != meta["name"]:
                    raise StudyError("artifact_identity")
            return decoded
        except StudyError:
            raise
        except (KeyError, TypeError, ValueError, AttributeError):
            raise StudyError("artifact_metadata") from None


class _View:
    """Only already validated, ordered metadata is normalized for legacy science."""
    def __init__(self, store, metadata, cached=None):
        self.store, self.metadata, self.cached = store, metadata, cached or {}

    def list(self):
        return [{"id": row["id"], "name": "w57-%s-v1" % ("result" if "result" in row["name"] else "intent")}
                for row in self.metadata]

    def load(self, ident):
        if ident not in self.cached:
            self.cached[ident] = self.store.load(ident)
        value = copy.deepcopy(self.cached[ident])
        value["state"].get("session", {}).pop("last_durable", None)
        return value


def prepare_admission(phase, store, ctx, now, study, pilot_id=None):
    metadata = store.list(scope="admission")
    plan = core.prepare(phase, _View(store, metadata), ctx, now, study=study, pilot_id=pilot_id)
    plan["state"] = bind_state(plan["state"], ctx, "live")
    plan["namespace"], plan["admission"] = "live", True
    return plan


def _run_rows(store, ctx, namespace):
    metadata = store.list(scope="run", namespace=namespace)
    result = []
    for row in metadata:
        match = NAME.fullmatch(row["name"])
        if match and match[1] == namespace:
            if int(match[3]) != ctx["run_id"]:
                raise StudyError("artifact_provenance")
            result.append(row)
        elif row["name"] not in ADMISSION_NAMES and not CLOSURE_NAME.fullmatch(row["name"]) and not match:
            raise StudyError("artifact_identity")
    # Memory fixtures use the same metadata ordering rule as the real adapter.
    result.sort(key=lambda row: (int(NAME.fullmatch(row["name"])[4]), NAME.fullmatch(row["name"])[5] == "result"))
    if len({(NAME.fullmatch(row["name"])[2], int(NAME.fullmatch(row["name"])[3])) for row in result}) > 1:
        raise StudyError("multiple_run_studies")
    return result


def prepare_slot(store, ctx, clock, lease, slot, namespace="live"):
    maximum = 2 if namespace == "canary" else core.LAST_SLOT
    if type(slot) is not int or not 0 <= slot <= maximum:
        raise StudyError("invalid_slot")
    metadata = _run_rows(store, ctx, namespace)
    previous, reference = None, None
    if metadata:
        previous = store.load(metadata[-1]["id"])
        if previous.get("transport", {}).get("namespace") != namespace:
            raise StudyError("namespace_mismatch")
        state = copy.deepcopy(previous["state"])
        reference = {"id": metadata[-1]["id"], "digest": previous["digest"]}
        if state["status"] in core.TERMINAL:
            return {"action": "idle", "reason": "terminal"}
        if previous["manifest"]["kind"] == "intent":
            state["lost_intent"] = reference
            state["generation"] += 1
            state["status"] = "lost_checkpoint"
            return {"action": "checkpoint", "state": state, "namespace": namespace}
        last = state["slots"][-1]["slot"] if state["slots"] else -1
        if slot <= last:
            return {"action": "idle", "reason": "slot_already_seen"}
        state["generation"] += 1
        state["parent"] = reference
        state["chunks"].append(reference)
        state["session"]["previous_result_receipt"] = dict(reference, zip_digest=previous.get("zip_digest"))
        state["session"].pop("end_clock", None)
        state["session"].pop("seal_clock", None)
        if source_hashes() != state["source"]:
            state["status"] = "source_changed"
            state["session"]["failure"] = "source_changed"
            return {"action": "checkpoint", "state": state, "namespace": namespace}
        if slot != last + 1:
            raise StudyError("interrupted_handoff")
    elif namespace == "canary" and slot == 0:
        state = canary_state(ctx, clock.utc())
    else:
        raise StudyError("missing_running_session")
    if state.get("started_at") is None:
        raise StudyError("missing_study_clock")
    due = state["started_at"] + slot * core.INTERVAL
    state["slot"], state["phase"] = slot, "tick" if namespace == "live" else "canary"
    timing = {"due_at": due, "prepared_at": clock.utc(), "job_started_at": lease.record["utc"],
              "job_monotonic": lease.record["monotonic"], "slot": slot}
    state["session"]["timing"] = timing
    try:
        frozen = _source_guard(state["source"])
        if state["session"]["freeze"] != ctx["control_sources"]:
            raise StudyError("source_changed")
        wait_due(clock, due, lease, check=frozen)
    except StudyError as exc:
        state["status"] = "source_changed" if str(exc) == "source_changed" else "failed"
        state["session"]["failure"] = str(exc)
        timing["operation_completed_at"] = clock.utc()
        return {"action": "checkpoint", "state": state, "namespace": namespace}
    if clock.utc() >= due + core.INTERVAL:
        state["slots"].append({"slot": slot, "status": "not_observed"})
        if slot == maximum:
            state["status"] = "completed"
        timing.update(operation_started_at=None, operation_completed_at=clock.utc(), coverage="no_attempt_missed_due")
        return {"action": "checkpoint", "state": state, "namespace": namespace}
    _validate(state, namespace)
    return {"action": "collect", "state": state, "phase": "tick" if namespace == "live" else "canary",
            "prepared_at": clock.utc(), "namespace": namespace}


def collect(plan, intent_id, store, ctx, clock, lease, on_row=None):
    namespace, state = plan["namespace"], copy.deepcopy(plan["state"])
    intent = store.load(intent_id)
    if (plan.get("action") != "collect" or intent["state"] != state
            or intent["manifest"]["kind"] != "intent" or intent["manifest"]["context"] != ctx
            or intent.get("transport", {}).get("namespace") != namespace):
        raise StudyError("intent_mismatch")
    duration = {"pilot": 180, "start": 1080, "tick": 360, "canary": 360}[plan["phase"]]
    lease.check(clock, duration)
    if source_hashes() != state["source"]:
        raise StudyError("source_changed")
    frozen = _source_guard(state["source"])
    state["session"].setdefault("timing", {})["operation_started_at"] = clock.utc()
    # Preserve the exact prepared state for the unchanged collect() intent check.
    began = clock.utc()
    if namespace == "live":
        ceiling = {"pilot": 7, "start": 248, "tick": len(state["cohort"])}[plan["phase"]]
        if sum(state["requests"].values()) + ceiling > core.MAX_VENDOR_CALLS:
            raise StudyError("vendor_call_ceiling")
        cached = _View(store, [], {intent_id: intent})
        def guarded():
            lease.check(clock)
            frozen()
            return clock.utc()
        state, rows = core.collect(plan, intent_id, cached, ctx, guarded, clock.sleep, on_row)
    else:
        state["intent"] = {"id": intent_id, "digest": intent["digest"]}
        rows, slot = [], state["slot"]
        for member in state["members"]:
            lease.check(clock, 32)
            frozen()
            row = {"kind": "synthetic", "slot": slot, "member": member, "due_at": state["started_at"] + slot * 900,
                   "request_started_at": clock.utc(), "ts": clock.utc(), "body": "synthetic",
                   "vendor_request": False, "scientific_evidence": False}
            rows.append(row)
            if on_row:
                on_row(row)
            clock.sleep(2)
        state["slots"].append({"slot": slot, "status": "observed"})
        state["status"] = "completed" if slot == 2 else "active"
    state["session"].setdefault("timing", {}).update(operation_started_at=began,
                                                    operation_completed_at=clock.utc(),
                                                    late=began > state["session"].get("timing", {}).get("due_at", began) + 60)
    state["session"]["intent_receipt"] = {"id": intent_id, "digest": intent["digest"],
                                           "zip_digest": intent.get("zip_digest")}
    _seal_clock(state, ctx, clock, lease)
    _validate(state, namespace)
    return state, rows


def verify_result(store, ident, state, ctx, namespace):
    try:
        result = store.load(ident)
    except (KeyError, StudyError):
        raise StudyError("failed_persistence") from None
    if (result["state"] != state or result["manifest"]["kind"] != "result"
            or result["manifest"]["context"] != ctx
            or result.get("transport", {}).get("namespace") != namespace):
        raise StudyError("failed_persistence")
    return {"id": ident, "digest": result["digest"]}


def reconstruct(store, ctx, study, namespace="live"):
    metadata = _run_rows(store, ctx, namespace)
    if not metadata:
        raise StudyError("no_study_results")
    latest_meta = metadata[-1]
    latest = store.load(latest_meta["id"])
    if latest["manifest"]["kind"] != "result" or latest["state"]["study"] != study:
        raise StudyError("unresolved_intent_or_foreign_study")
    state = latest["state"]
    if len(state["chunks"]) + 1 > 195:
        raise StudyError("history_limit")
    rows, timings, previous = [], [], state.get("pilot")
    chain = []
    for reference in state["chunks"]:
        part = store.load(reference["id"])
        chain.append((reference, part))
    chain.append(({"id": latest_meta["id"], "digest": latest["digest"]}, latest))
    seen, generations = set(), set()
    for reference, part in chain:
        current = part["state"]
        if (reference["id"] in seen or current["generation"] in generations or part["digest"] != reference["digest"]
                or part["manifest"]["kind"] != "result" or current["study"] != study
                or current["parent"] != previous or current["source"] != state["source"]
                or current.get("cohort") != state.get("cohort")
                or current["started_at"] != state["started_at"] or current["ends_at"] != state["ends_at"]
                or part.get("transport", {}).get("namespace") != namespace):
            raise StudyError("history_chain")
        seen.add(reference["id"])
        generations.add(current["generation"])
        rows.extend(part["rows"])
        if "timing" in current["session"] and "slot" in current["session"]["timing"]:
            timings.append(current["session"]["timing"])
        previous = reference
    if namespace == "live":
        answer = core.readout(state, rows)
        answer["session_timings"] = timings
        answer["sampling_completion_inferred_from_job"] = False
        answer["session_clock_stable"] = _state_clock_stable(state)
        answer["session_clock_proof_coverage"] = {"generations": len(chain),
                                                 "valid": sum(_state_clock_stable(part["state"]) for _, part in chain)}
        return answer
    cells = {(row["slot"], row["member"]) for row in rows}
    passed = (state["status"] == "completed" and len(chain) == 3 and len(cells) == len(rows) == 189
              and [item["slot"] for item in timings] == [0, 1, 2]
              and timings[0]["job_started_at"] == timings[1]["job_started_at"] < timings[2]["job_started_at"]
              and all(_state_clock_stable(part["state"]) for _, part in chain)
              and all(core.number(item.get("operation_started_at"))
                      and 0 <= item["operation_started_at"] - item["due_at"] <= 60 for item in timings))
    return {"study": study, "namespace": "canary", "readiness": "passed" if passed else "failed",
            "vendor_requests": 0, "observed_cells": len(cells), "scientific_evidence": False,
            "timings": timings, "last_durable": previous,
            "disclosure": "Synthetic delivery canary only; thirty minutes does not establish 48-hour reliability or scientific evidence."}


def _atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def write_bundle(folder, state, rows, kind, ctx, namespace, unverified=None):
    files = _files(state, rows, kind, ctx, namespace, unverified)
    for name, data in files.items():
        _atomic(folder / name, data)


def _local(folder, ctx):
    names = {"state.json", "observations.jsonl", "manifest.json", "transport.json", "unverified.jsonl"}
    files = {path.name: path.read_bytes() for path in folder.iterdir() if path.name in names}
    return decode_bundle(_zip(files), ctx, ctx)


def _output(key, value):
    core._output(key, value)


def _stats(store):
    return {"reads": store.reads, "downloads": store.downloads, "seconds": store.seconds_spent,
            "runs": store.runs}


def _store(ctx, plan=None, report=False, admission=False):
    store = Artifacts(ctx, os.environ.get("GITHUB_TOKEN", ""), report=report, admission=admission)
    if plan and "artifact_budget" in plan:
        stats = plan["artifact_budget"]
        store.reads, store.downloads = stats["reads"], stats["downloads"]
        store.runs = {int(key): value for key, value in stats.get("runs", {}).items()}
        store.seconds_spent = stats["seconds"]
        store.deadline -= stats["seconds"]
        if store.reads > store.max_reads or store.downloads > store.max_downloads or stats["seconds"] >= (720 if report else 110):
            raise StudyError("artifact_budget")
    return store


def _lease(clock):
    path = Path(os.environ["RUNNER_TEMP"]) / "w57-job-clock.json"
    return Lease(clock, record=_parse(path.read_bytes()))


def _save_plan(out, plan, store, ctx):
    if out.exists() and any(out.iterdir()):
        raise StudyError("output_exists")
    out.mkdir(parents=True, exist_ok=True)
    plan["artifact_budget"] = _stats(store)
    _atomic(out / "plan.json", core.encoded(plan))
    state, namespace = plan["state"], plan["namespace"]
    if plan["action"] == "collect":
        write_bundle(out / "intent", state, [], "intent", ctx, namespace)
        fallback = copy.deepcopy(state)
        fallback["status"] = "lost_checkpoint"
        write_bundle(out / "result", fallback, [], "result", ctx, namespace)
        _output("intent-name", artifact_name(state, "intent", ctx, namespace))
        if plan.get("admission"):
            write_bundle(out / "admission-intent", state, [], "admission-intent", ctx, namespace)
    else:
        write_bundle(out / "result", state, [], "result", ctx, namespace)
    _output("action", plan["action"])
    _output("result-name", artifact_name(state, "result", ctx, namespace))
    _output("ready", "true")


def finalize(out, ctx, clock):
    plan = _parse((out / "plan.json").read_bytes())
    namespace = plan["namespace"]
    folder = out / "result"
    if namespace == "live":
        # The legacy finalizer reads only its original core files. Its interrupted
        # journal salvage is reused unchanged, then wrapped with the v2 envelope.
        core.finalize(out, ctx)
        files = {name: (folder / name).read_bytes() for name in
                 ("state.json", "observations.jsonl", "manifest.json", "unverified.jsonl") if (folder / name).exists()}
        value = core.decode_bundle(_zip(files), ctx, ctx)
        state, rows = value["state"], value["rows"]
        unverified = files.get("unverified.jsonl")
    else:
        try:
            value = _local(folder, ctx)
            if value["state"]["status"] == "lost_checkpoint" and (out / "collection.json").exists():
                raise StudyError("collection_interrupted")
            state, rows = value["state"], value["rows"]
            unverified = (folder / "unverified.jsonl").read_bytes() if (folder / "unverified.jsonl").exists() else None
        except StudyError:
            state = copy.deepcopy(plan["state"])
            journal = (folder / "observations.jsonl").read_bytes()
            rows, offset = [], 0
            for line in journal.splitlines(keepends=True):
                try:
                    row = _parse(line)
                    if (len(rows) >= 63 or len(line) > 2049 or core.encoded(row) + b"\n" != line
                            or row.get("kind") != "synthetic" or row.get("slot") != state["slot"]
                            or row.get("member") not in state["members"]):
                        break
                except (ValueError, TypeError, StudyError):
                    break
                rows.append(row)
                offset += len(line)
            unverified = journal[offset:] or None
            state["status"] = "failed"
            state["session"]["failure"] = "collection_interrupted"
    _seal_clock(state, ctx, clock, Lease(clock, record=plan["lease"]), key="seal_clock")
    timing = state["session"].setdefault("timing", {})
    if state["status"] in ("lost_checkpoint", "failed", "overflow"):
        timing.setdefault("operation_completed_at", clock.utc())
        timing["coverage"] = "failed_or_unknown_persistence"
    write_bundle(folder, state, rows, "result", ctx, namespace, unverified)
    for path in folder.glob("*.tmp"):
        path.unlink()


def _receipt(store, ident, digest, state, ctx, namespace):
    if type(ident) is not int or ident <= 0 or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise StudyError("failed_persistence")
    meta = store.request("/repos/%s/actions/artifacts/%d" % (ctx["repository"], ident))
    store._meta(meta)
    if (meta["id"] != ident or meta["digest"] != "sha256:" + digest
            or meta["name"] != artifact_name(state, "result", ctx, namespace)
            or meta["workflow_run"]["id"] != ctx["run_id"]
            or meta["workflow_run"]["head_sha"] != ctx["head"]):
        raise StudyError("failed_persistence")
    # The pinned uploader's ZIP digest is checked against fresh GitHub metadata.
    # A second download here would exceed the ordinary two-download cap; the
    # next generation and final read-only reconstruction verify the raw ZIP too.
    return {"id": ident, "zip_digest": digest}


def _summary(value):
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as stream:
            allowed = ("status", "namespace", "coverage", "readiness", "vendor_requests", "scientific_evidence",
                       "last_durable", "timing", "reason", "command", "no_further_acquisition")
            safe = {key: value[key] for key in allowed if key in value and
                    (key != "coverage" or isinstance(value[key], str))}
            stream.write("W57 finite session: " + core.encoded(safe).decode("utf-8") + "\n")


def closure(out, ctx, clock, phase):
    namespace = "canary" if phase == "canary" else "live"
    store = _store(ctx, report=True)
    metadata = _run_rows(store, ctx, namespace)
    report = {"namespace": namespace, "scientific_evidence": False,
              "coverage": "no_run_or_no_attempt", "readiness": "failed", "vendor_requests": 0 if namespace == "canary" else None}
    out.mkdir(parents=True, exist_ok=True)
    if not metadata:
        _atomic(out / "summary.json", core.encoded(report))
        _output("index-ready", "false")
        return report
    latest = store.load(metadata[-1]["id"])
    state = copy.deepcopy(latest["state"])
    reference = {"id": metadata[-1]["id"], "digest": latest["digest"]}
    rescue = latest["manifest"]["kind"] == "intent" or state["status"] not in core.TERMINAL
    rows = latest["rows"]
    if rescue:
        if latest["manifest"]["kind"] == "intent":
            state["lost_intent"] = reference
            state["intent"] = reference
        else:
            state["generation"] += 1
            state["chunks"].append(reference)
            state["parent"] = reference
            rows = []
        state["status"] = "lost_checkpoint"
        state["session"]["failure"] = "interrupted_handoff_or_persistence"
        state["session"].setdefault("timing", {})["operation_completed_at"] = clock.utc()
        report.update(coverage="failed_or_unknown_persistence", last_durable=reference)
    else:
        # Full reconstruction is the proof, not a successful infrastructure job.
        class Cached:
            def list(self, **kwargs):
                return metadata
            def load(self, ident):
                return latest if ident == reference["id"] else store.load(ident)
        report = reconstruct(Cached(), ctx, state["study"], namespace)
    write_bundle(out / "result", state, rows, "result", ctx, namespace)
    _atomic(out / "closure.json", core.encoded({"state": state, "rows": rows, "last": reference,
                                               "rescue": rescue, "namespace": namespace,
                                               "artifact_budget": _stats(store)}))
    _atomic(out / "summary.json", core.encoded(report))
    _output("rescue", str(rescue).lower())
    _output("result-name", artifact_name(state, "result", ctx, namespace))
    _output("index-ready", str(namespace == "live").lower())
    _output("ready", "true")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Explicit finite W57 pilot/start/report and unarmed canary; no default network action")
    parser.add_argument("command", nargs="?", choices=("admit", "prepare", "collect", "finalize", "finish",
                                                       "closure", "close-index", "closure-finish"))
    parser.add_argument("--out")
    parser.add_argument("--slot", type=int)
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    out = Path(args.out).resolve()
    if out.is_relative_to(ROOT):
        print("W57 protected output refused")
        return 1
    try:
        ctx, clock = context(), Clock()
        phase = os.environ.get("W57_PHASE", "canary")
        if phase not in ("canary", "pilot", "start", "report", "legacy-report"):
            raise StudyError("invalid_phase")
        if args.command == "admit":
            if phase == "canary":
                _output("action", "idle")
                return 0
            if phase in ("report", "legacy-report"):
                if phase == "legacy-report":
                    legacy_store = core.GitHubArtifacts(ctx, os.environ.get("GITHUB_TOKEN", ""), 600, 195, 720)
                    answer = core.reconstruct(legacy_store, ctx, os.environ.get("W57_STUDY", ""))
                else:
                    target = int(os.environ["W57_SOURCE_RUN"])
                    report_ctx = dict(ctx, run_id=target)
                    answer = reconstruct(_store(report_ctx, report=True), report_ctx, os.environ.get("W57_STUDY", ""),
                                         namespace=os.environ.get("W57_REPORT_NAMESPACE", "canary"))
                _atomic(out / "report.json", core.encoded(answer))
                _summary(answer)
                _output("report-ready", "true")
                return 0
            lease, store = _lease(clock), _store(ctx, admission=True)
            lease.check(clock, 1080 if phase == "start" else 180)
            pilot = int(os.environ["W57_PILOT"]) if os.environ.get("W57_PILOT") else None
            plan = prepare_admission(phase, store, ctx, clock.utc(), os.environ.get("W57_STUDY", ""), pilot)
            plan["lease"] = lease.record
            _save_plan(out, plan, store, ctx)
        elif args.command == "prepare":
            namespace = "canary" if phase == "canary" else "live"
            if phase not in ("canary", "start"):
                raise StudyError("sampling_mode_refused")
            lease, store = _lease(clock), _store(ctx)
            plan = prepare_slot(store, ctx, clock, lease, args.slot, namespace)
            _output("action", plan["action"])
            if plan["action"] == "idle":
                return 0
            plan["lease"] = lease.record
            _save_plan(out, plan, store, ctx)
        elif args.command in ("collect", "finalize", "finish"):
            plan = _parse((out / "plan.json").read_bytes())
            if (plan["namespace"] == "canary") != (phase == "canary"):
                raise StudyError("namespace_mismatch")
            if args.command == "finalize":
                finalize(out, ctx, clock)
                return 0
            store = _store(ctx, plan, admission=plan.get("admission", False))
            if args.command == "collect":
                ident = int(os.environ["W57_INTENT_ID"])
                _atomic(out / "collection.json", core.encoded({"id": ident, "verified_operation_started_at": None}))
                try:
                    with (out / "result/observations.jsonl").open("wb") as stream:
                        def append(row):
                            stream.write(core.encoded(row) + b"\n")
                            stream.flush()
                            os.fsync(stream.fileno())
                        state, rows = collect(plan, ident, store, ctx, clock,
                                              Lease(clock, record=plan["lease"]), append)
                    write_bundle(out / "result", state, rows, "result", ctx, plan["namespace"])
                finally:
                    plan["artifact_budget"] = _stats(store)
                    _atomic(out / "plan.json", core.encoded(plan))
            else:
                result = _local(out / "result", ctx)
                state = result["state"]
                if os.environ.get("W57_UPLOADED") != "success":
                    raise StudyError("failed_persistence")
                reference = _receipt(store, int(os.environ["W57_RESULT_ID"]), os.environ["W57_RESULT_DIGEST"],
                                     state, ctx, plan["namespace"])
                reference["digest"] = result["digest"]
                _atomic(out / "receipt.json", core.encoded({"last_durable": reference, "artifact_budget": _stats(store)}))
                _summary({"status": state["status"], "namespace": plan["namespace"], "last_durable": reference,
                          "timing": state["session"].get("timing"), "scientific_completion_inferred": False})
                if state["status"] not in ("active", "completed", "pilot_passed"):
                    return 2
        elif args.command == "closure":
            if phase in ("report", "legacy-report"):
                return 0
            closure(out, ctx, clock, phase)
        elif args.command == "close-index":
            value = _parse((out / "closure.json").read_bytes())
            if value["namespace"] != "live":
                return 0
            state, reference = value["state"], value["last"]
            if value["rescue"]:
                store = _store(ctx, value, report=True)
                if os.environ.get("W57_UPLOADED") != "success":
                    raise StudyError("failed_persistence")
                _receipt(store, int(os.environ["W57_RESULT_ID"]), os.environ["W57_RESULT_DIGEST"], state, ctx, "live")
                reference = {"id": int(os.environ["W57_RESULT_ID"]), "digest": _local(out / "result", ctx)["digest"]}
            state["session"]["last_durable"] = reference
            write_bundle(out / "admission-result", state, value["rows"], "admission-result", ctx, "live")
            _output("ready", "true")
        else:
            report = _parse((out / "summary.json").read_bytes())
            _summary(report)
            if os.environ.get("W57_UPLOADED") != "success":
                raise StudyError("failed_persistence")
            if phase == "canary" and report.get("readiness") != "passed":
                raise StudyError("canary_readiness_failed")
            if report.get("coverage") in ("no_run_or_no_attempt", "failed_or_unknown_persistence"):
                return 2
        return 0
    except (StudyError, KeyError, OSError, ValueError, TypeError) as exc:
        reason = str(exc) if isinstance(exc, StudyError) else "local_or_transport_unavailable"
        # Only bounded diagnostics; never print raw URLs, input IDs, or exceptions.
        diagnostic = {"reason": reason, "coverage": "failed_or_unknown", "command": args.command,
                      "recorded_at": time.time(), "no_further_acquisition": True}
        try:
            _atomic(out / "failure.json", core.encoded(diagnostic))
            _summary(diagnostic)
        except OSError:
            pass
        print("::error::W57 stopped: " + reason)
        return 1


if __name__ == "__main__":
    sys.exit(main())
