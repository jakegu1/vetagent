"""Finite W57 CI jobs. No default network action; measurement policy stays outside src.

The workflow uploads an intent before collect and a result even when collect fails.
Artifacts are immutable chunks, not a mutable cache. Only explicit start recruits.
"""
import argparse
import copy
import datetime
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import zipfile

import rugcheck_coverage_probe as probe

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ".github/workflows/rugcheck-w57.yml"
SCHEMA = 1
FRESH_MIN, FRESH_TARGET, MAX_AGE_MIN = 40, 45, 10
DURATION, INTERVAL, LAST_SLOT = 48 * 3600, 15 * 60, 192
MAX_VENDOR_CALLS = 12414
STATE_BYTES, INTENT_BYTES, BUNDLE_BYTES = 64 * 1024, 64 * 1024, 1024 * 1024
STUDY_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,47}\Z")
MINT = re.compile(r"[1-9A-HJ-NP-Za-km-z]{32,44}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
ARTIFACT = re.compile(r"w57-(intent|result|report)-v1\Z")
TERMINAL = {"pilot_passed", "pilot_failed", "insufficient_cohort", "completed",
            "failed", "lost_checkpoint", "source_changed", "overflow"}


class StudyError(Exception):
    """A bounded diagnostic. Raw transport errors and signed URLs never reach stdout."""


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def source_hashes():
    return {key: sha((ROOT / path).read_bytes()) for key, path in
            (("driver", "bench/rugcheck_w57_ci.py"), ("probe", "bench/rugcheck_coverage_probe.py"),
             ("workflow", WORKFLOW))}


def artifact_name(state, kind, ctx):
    # Fixed names allow GitHub's exact-name filter to exclude unrelated CI artifacts.
    # Each immutable run contains at most one intent and one result with these names.
    return "w57-%s-v1" % kind


def _validate_state(state):
    if (not isinstance(state, dict) or state.get("schema") != SCHEMA
            or not isinstance(state.get("study"), str) or not STUDY_ID.fullmatch(state["study"])
            or state.get("status") not in TERMINAL | {"pilot_pending", "starting", "active"}
            or not isinstance(state.get("source"), dict)
            or set(state["source"]) != {"driver", "probe", "workflow"}
            or any(not isinstance(x, str) or not SHA.fullmatch(x) for x in state["source"].values())
            or type(state.get("generation")) is not int or not 0 <= state["generation"] <= 196):
        raise StudyError("invalid_state")
    cohort, chunks, slots = state.get("cohort"), state.get("chunks"), state.get("slots")
    if (not isinstance(cohort, list) or len(cohort) > 63 or not isinstance(chunks, list)
            or len(chunks) > 195 or not isinstance(slots, list) or len(slots) > 193):
        raise StudyError("invalid_state")
    used = state.get("used_studies")
    if (not isinstance(used, list) or not 1 <= len(used) <= 128 or state["study"] not in used
            or any(not isinstance(x, str) or not STUDY_ID.fullmatch(x) for x in used)
            or len(set(used)) != len(used)):
        raise StudyError("invalid_study_history")
    seen = set()
    for member in cohort:
        if (not isinstance(member, dict) or not isinstance(member.get("mint"), str)
                or not MINT.fullmatch(member["mint"]) or member["mint"] in seen
                or member.get("group") not in ("fresh", "control")):
            raise StudyError("invalid_cohort")
        seen.add(member["mint"])
        if member["group"] == "fresh":
            rec = member.get("enrollment", {})
            try:
                age = probe.age_minutes(rec.get("detectedAt"),
                                        datetime.datetime.fromtimestamp(rec["ts"], datetime.timezone.utc))
            except (KeyError, TypeError, ValueError, OverflowError):
                raise StudyError("invalid_enrollment") from None
            if rec.get("http") != "200" or rec.get("body") != "ok" or age is None or not 0 <= age <= MAX_AGE_MIN:
                raise StudyError("invalid_enrollment")
    ids = [x.get("id") for x in chunks if isinstance(x, dict)]
    if (len(ids) != len(chunks) or len(set(ids)) != len(ids)
            or any(type(x) is not int or x <= 0 for x in ids)
            or any(not isinstance(x.get("digest"), str) or not SHA.fullmatch(x["digest"]) for x in chunks)):
        raise StudyError("invalid_chain")
    indices = [s.get("slot") for s in slots if isinstance(s, dict)]
    if (len(indices) != len(slots) or indices != sorted(set(indices))
            or any(type(s) is not int or not 0 <= s <= LAST_SLOT for s in indices)):
        raise StudyError("invalid_slots")
    if state.get("started_at") is not None:
        if not number(state["started_at"]) or state.get("ends_at") != state["started_at"] + DURATION:
            raise StudyError("invalid_clock")
        fresh = [m for m in cohort if m["group"] == "fresh"]
        controls = [m["mint"] for m in cohort if m["group"] == "control"]
        if not FRESH_MIN <= len(fresh) <= FRESH_TARGET or controls != [m for _, m in probe.MAJORS]:
            raise StudyError("invalid_frozen_population")
    elif state["status"] == "active":
        raise StudyError("invalid_clock")
    if len(encoded(state)) > STATE_BYTES:
        raise StudyError("state_overflow")


def _bundle_files(state, rows, kind, ctx):
    _validate_state(state)
    if kind not in ("intent", "result") or not isinstance(rows, list) or len(rows) > 256:
        raise StudyError("bundle_bounds")
    row_data = b"".join(encoded(row) + b"\n" for row in rows)
    state_data = encoded(state)
    manifest = {"schema": SCHEMA, "kind": kind, "study": state["study"],
                "generation": state["generation"], "parent": state["parent"], "context": ctx,
                "rows": len(rows), "files": {"state.json": sha(state_data), "observations.jsonl": sha(row_data)}}
    files = {"state.json": state_data, "observations.jsonl": row_data, "manifest.json": encoded(manifest)}
    limit = INTENT_BYTES if kind == "intent" else BUNDLE_BYTES
    if sum(map(len, files.values())) > limit:
        raise StudyError("bundle_overflow")
    return files


def bundle_bytes(state, rows, kind, ctx):
    target = io.BytesIO()
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in _bundle_files(state, rows, kind, ctx).items():
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    if len(target.getvalue()) > (INTENT_BYTES if kind == "intent" else BUNDLE_BYTES):
        raise StudyError("bundle_overflow")
    return target.getvalue()


def decode_bundle(data, provenance, expected):
    try:
        if len(data) > BUNDLE_BYTES:
            raise StudyError("bundle_overflow")
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            names = [x.filename for x in entries]
            if (set(names) != {"state.json", "manifest.json", "observations.jsonl"}
                    or len(entries) != 3 or sum(x.file_size for x in entries) > BUNDLE_BYTES
                    or any(x.flag_bits & 1 for x in entries)):
                raise StudyError("bundle_files")
            files = {name: archive.read(name) for name in names}
        manifest = json.loads(files["manifest.json"])
        state = json.loads(files["state.json"])
        rows = [json.loads(line) for line in files["observations.jsonl"].splitlines()]
        _validate_state(state)
        ctx = manifest["context"]
        if (manifest.get("schema") != SCHEMA or manifest.get("kind") not in ("intent", "result")
                or manifest.get("study") != state["study"] or manifest.get("generation") != state["generation"]
                or manifest.get("parent") != state["parent"] or manifest.get("rows") != len(rows)
                or len(rows) > 256 or any(not isinstance(row, dict) for row in rows)
                or manifest.get("files") != {"state.json": sha(files["state.json"]),
                                             "observations.jsonl": sha(files["observations.jsonl"])}):
            raise StudyError("bundle_manifest")
        keys = []
        for row in rows:
            if row.get("kind") == "listing":
                key = ("listing", row.get("phase"), row.get("page"))
            elif row.get("kind") in ("report", "overflow_receipt"):
                key = ("report", row.get("phase"), row.get("slot"), row.get("mint"), row.get("attempt"))
            else:
                raise StudyError("invalid_observation")
            keys.append(key)
        if len(set(keys)) != len(keys):
            raise StudyError("duplicate_observation")
        for key in ("repository", "workflow", "branch"):
            if ctx.get(key) != provenance.get(key) or ctx.get(key) != expected.get(key):
                raise StudyError("artifact_provenance")
        if (ctx["workflow"] != WORKFLOW or ctx["branch"] != expected["default_branch"]
                or ctx.get("default_branch") != expected["default_branch"]
                or ctx.get("run_id") != provenance.get("run_id") or ctx.get("head") != provenance.get("head")
                or not re.fullmatch(r"[0-9a-f]{40}", str(ctx.get("head")))
                or type(ctx.get("run_id")) is not int or ctx["run_id"] <= 0):
            raise StudyError("artifact_provenance")
        if manifest["kind"] == "intent" and sum(map(len, files.values())) > INTENT_BYTES:
            raise StudyError("intent_overflow")
        return {"state": state, "rows": rows, "manifest": manifest, "digest": sha(encoded(manifest))}
    except StudyError:
        raise
    except (KeyError, ValueError, TypeError, OverflowError, OSError, zipfile.BadZipFile, RuntimeError):
        raise StudyError("artifact_malformed") from None


class GitHubArtifacts:
    """Read-only GitHub adapter. The workflow's pinned action owns uploads."""
    def __init__(self, ctx, token, max_reads=12, max_downloads=2, seconds=110):
        self.ctx, self.token = ctx, token
        self.reads, self.downloads = 0, 0
        self.max_reads, self.max_downloads = max_reads, max_downloads
        self.deadline = time.monotonic() + seconds
        self.metadata = {}

    def _count(self, amount=1):
        self.reads += amount
        if self.reads > self.max_reads or time.monotonic() + 30 > self.deadline:
            raise StudyError("artifact_read_budget")

    def request(self, path, binary=False):
        # A ZIP read includes GitHub's documented redirect. Never accept an Artifact URL.
        self._count(2 if binary else 1)
        if not path.startswith("/repos/" + self.ctx["repository"] + "/actions/"):
            raise StudyError("artifact_endpoint")
        try:
            result = subprocess.run(["gh", "api", "--hostname", "github.com", "--method", "GET", "-H", "Accept: application/vnd.github+json",
                                     "-H", "X-GitHub-Api-Version: 2022-11-28", path],
                                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30,
                                    env=dict(os.environ, GH_TOKEN=self.token))
            if result.returncode:
                raise StudyError("artifact_transport_unavailable")
            data = result.stdout
            if len(data) > BUNDLE_BYTES:
                raise StudyError("artifact_response_overflow")
            return data if binary else json.loads(data)
        except StudyError:
            raise
        except (OSError, ValueError, subprocess.SubprocessError):
            raise StudyError("artifact_transport_unavailable") from None

    def list(self):
        found, pages = [], 0
        for kind in ("result", "intent"):
            for page in range(1, 6):
                if pages >= 5:
                    raise StudyError("artifact_scan_limit")
                pages += 1
                name = "w57-%s-v1" % kind
                body = self.request("/repos/%s/actions/artifacts?name=%s&per_page=100&page=%d" %
                                    (self.ctx["repository"], name, page))
                rows = body.get("artifacts") if isinstance(body, dict) else None
                if not isinstance(rows, list):
                    raise StudyError("artifact_metadata")
                matched = [row for row in rows if isinstance(row, dict) and row.get("name") == name]
                found.extend(matched)
                self.metadata.update({row["id"]: row for row in matched if type(row.get("id")) is int})
                if len(rows) < 100:
                    break
            else:
                raise StudyError("artifact_scan_limit")
        return found

    def load(self, ident):
        if self.downloads >= self.max_downloads or type(ident) is not int or ident <= 0:
            raise StudyError("artifact_download_budget")
        self.downloads += 1
        base = "/repos/%s/actions/" % self.ctx["repository"]
        meta = self.metadata.get(ident)
        if meta is None:
            meta = self.request(base + "artifacts/%d" % ident)
        try:
            if meta["id"] != ident or meta.get("expired") or meta["size_in_bytes"] > BUNDLE_BYTES:
                raise StudyError("artifact_unavailable")
            parts = ARTIFACT.fullmatch(meta["name"])
            if not parts:
                raise StudyError("artifact_identity")
            run_id = meta["workflow_run"]["id"]
            run = self.request(base + "runs/%d" % run_id)
            if (run["repository"]["full_name"] != self.ctx["repository"]
                    or run["head_repository"]["full_name"] != self.ctx["repository"]
                    or run["path"] != WORKFLOW or run["head_branch"] != self.ctx["default_branch"]
                    or run["event"] not in ("schedule", "workflow_dispatch") or run["id"] != run_id
                    or meta["workflow_run"]["head_sha"] != run["head_sha"]):
                raise StudyError("artifact_provenance")
            provenance = {"repository": run["repository"]["full_name"], "workflow": run["path"],
                          "branch": run["head_branch"], "run_id": run_id, "head": run["head_sha"]}
            decoded = decode_bundle(self.request(base + "artifacts/%d/zip" % ident, binary=True), provenance, self.ctx)
            if decoded["manifest"]["kind"] != parts[1]:
                raise StudyError("artifact_identity")
            return decoded
        except StudyError:
            raise
        except (KeyError, TypeError, ValueError):
            raise StudyError("artifact_metadata") from None


def _new_state(study, phase, ctx, now):
    if not isinstance(study, str) or not STUDY_ID.fullmatch(study):
        raise StudyError("invalid_study_id")
    return {"schema": SCHEMA, "study": study, "phase": phase, "status": "pilot_pending" if phase == "pilot" else "starting",
            "source": copy.deepcopy(ctx["source"]), "origin_head": ctx["head"], "origin_run": ctx["run_id"],
            "used_studies": [study],
            "generation": 0, "parent": None, "chunks": [], "cohort": [], "slots": [],
            "started_at": None, "ends_at": None, "requests": {"rugcheck": 0, "gecko": 0}}


def prepare(phase, store, ctx, now, study=None, pilot_id=None):
    if phase not in ("pilot", "start", "tick") or not number(now):
        raise StudyError("invalid_phase")
    metadata = [m for m in store.list() if ARTIFACT.fullmatch(str(m.get("name", "")))
                and ARTIFACT.fullmatch(m["name"])[1] != "report"]
    metadata.sort(key=lambda m: m["id"])
    loaded = {}
    def load(ident):
        if ident not in loaded:
            loaded[ident] = store.load(ident)
        return loaded[ident]
    if phase in ("pilot", "start"):
        known_studies = []
        if metadata:
            latest = load(metadata[-1]["id"])
            known_studies = latest["state"]["used_studies"]
            if latest["state"]["status"] not in TERMINAL or latest["manifest"]["kind"] == "intent":
                raise StudyError("study_active")
        if not study or study in known_studies or len(known_studies) >= 128:
            raise StudyError("study_exists_or_missing_id")
        state = _new_state(study, phase, ctx, now)
        state["used_studies"] = known_studies + [study]
        if phase == "start":
            if type(pilot_id) is not int or pilot_id <= 0:
                raise StudyError("pilot_required")
            pilot = load(pilot_id)
            if (pilot["state"]["phase"] != "pilot" or pilot["state"]["status"] != "pilot_passed"
                    or pilot["manifest"]["kind"] != "result" or pilot["state"]["source"] != ctx["source"]
                    or pilot["manifest"]["context"]["run_id"] == ctx["run_id"]):
                raise StudyError("pilot_not_qualified")
            state["pilot"] = {"id": pilot_id, "digest": pilot["digest"]}
            state["parent"] = copy.deepcopy(state["pilot"])
    else:
        if not metadata:
            return {"action": "idle", "reason": "no_state"}
        meta = metadata[-1]
        previous = load(meta["id"])
        if study and previous["state"]["study"] != study:
            return {"action": "idle", "reason": "no_active_named_study"}
        state = copy.deepcopy(previous["state"])
        if state["status"] in TERMINAL:
            return {"action": "idle", "reason": "terminal"}
        reference = {"id": meta["id"], "digest": previous["digest"]}
        state["parent"] = reference
        state["generation"] += 1
        if previous["manifest"]["kind"] == "intent":
            # The intent already contains the durable result-chain parent/chunks.
            # Preserve that chain and name the lost intent as separate evidence.
            state["parent"] = copy.deepcopy(previous["state"]["parent"])
            state["lost_intent"] = reference
            if "slot" in state:
                state["slots"].append({"slot": state["slot"], "status": "not_observed"})
            state.setdefault("losses", []).append({"reason": "lost_checkpoint", "slot": state.get("slot"),
                                                     "intent": reference, "recorded_at": now})
            state["status"] = "lost_checkpoint"
            return {"action": "checkpoint", "state": state, "phase": "tick", "prepared_at": now}
        state["chunks"].append(reference)
        if state["source"] != ctx["source"]:
            state["status"] = "source_changed"
            return {"action": "checkpoint", "state": state, "phase": "tick", "prepared_at": now}
        if state.get("started_at") is None:
            raise StudyError("missing_study_clock")
        if now > state["ends_at"] + INTERVAL:
            state["slots"].extend({"slot": i, "status": "not_observed"}
                                  for i in range((state["slots"][-1]["slot"] + 1) if state["slots"] else 0, LAST_SLOT + 1))
            state["status"] = "completed"
            return {"action": "checkpoint", "state": state, "phase": "tick", "prepared_at": now}
        slot = min(LAST_SLOT, int((now - state["started_at"]) // INTERVAL))
        last = state["slots"][-1]["slot"] if state["slots"] else -1
        if slot < 0 or slot <= last:
            return {"action": "idle", "reason": "slot_already_seen_or_not_due"}
        state["slots"].extend({"slot": i, "status": "not_observed"} for i in range(last + 1, slot))
        state["slot"] = slot
        state["phase"] = "tick"
    _validate_state(state)
    return {"action": "collect", "state": state, "phase": phase, "prepared_at": now}


def _observe_fields(label, mint):
    """Keep availability from the same response which the unchanged probe observes.

    observe() intentionally exposes Boolean summaries. Its default False cannot tell
    a missing source value from a measured negative, so capture only these fields while
    its single existing transport call runs. There is no second upstream request.
    """
    transport, captured = probe.curl, {}
    def capture(url):
        code, body = transport(url)
        if str(code) == "200" and isinstance(body, dict):
            extensions = body.get("token_extensions")
            extensions = extensions if isinstance(extensions, dict) else {}
            captured.update({key: extensions.get(key) if type(extensions.get(key)) is bool else None
                             for key in ("permanentDelegate", "pausableConfig", "mintCloseAuthority")})
            authorities = [body.get("freezeAuthority"), body.get("mintAuthority")]
            captured["freeze_or_mint"] = (True if any(type(x) is bool and x for x in authorities)
                                           else False if all(type(x) is bool and not x for x in authorities) else None)
        return code, body
    probe.curl = capture
    try:
        observed = probe.observe(label, mint, "scores")
    finally:
        probe.curl = transport
    observed["gated"] = {key: captured.get(key) for key in
                         ("permanentDelegate", "pausableConfig", "mintCloseAuthority", "freeze_or_mint")}
    return observed


def _row(raw, state, label, mint, now, slot=None):
    usable = (isinstance(raw, dict) and str(raw.get("http")) == "200"
              and raw.get("body") == "ok" and probe._has_report_fields(raw))
    raw = raw if isinstance(raw, dict) else {}
    score = raw.get("score_normalised")
    valid_score = usable and probe.band(score) is not None
    detected = raw.get("detectedAt")
    detected = detected if isinstance(detected, str) and len(detected) <= 128 else None
    rec = {"kind": "report", "study": state["study"], "phase": state["phase"], "slot": slot,
           "sweep": slot + 1 if slot is not None else 0, "attempt": 0, "mint": mint, "label": label,
           "ts": now, "http": str(raw.get("http", "0"))[:3],
           "body": "ok" if usable else raw.get("body") if raw.get("body") in
           ("unavailable", "empty", "invalid", "not_observed") else "unavailable",
           "score_normalised": score if valid_score else None,
           "score_state": "observed" if valid_score else "unavailable_or_invalid",
           "detectedAt": detected,
           "gated": {k: (raw.get("gated") or {}).get(k) if usable and type((raw.get("gated") or {}).get(k)) is bool else None for k in
                     ("permanentDelegate", "pausableConfig", "mintCloseAuthority", "freeze_or_mint")}}
    for key in ("totalHolders", "topHolders_n"):
        value = raw.get(key)
        rec[key] = value if usable and type(value) is int and value >= 0 else None
    rec["age_minutes"] = probe.age_minutes(detected, datetime.datetime.fromtimestamp(now, datetime.timezone.utc))
    if len(encoded(rec)) > 2048:
        raise StudyError("row_overflow")
    return rec


def collect(plan, intent_id, store, ctx, clock=time.time, sleep=time.sleep, on_row=None):
    if plan.get("action") != "collect":
        raise StudyError("intent_required")
    try:
        intent = store.load(intent_id)
    except (KeyError, StudyError):
        raise StudyError("intent_unavailable") from None
    if (intent["manifest"]["kind"] != "intent" or intent["state"] != plan["state"]
            or intent["manifest"]["context"]["run_id"] != ctx["run_id"]):
        raise StudyError("intent_mismatch")
    state, rows = copy.deepcopy(plan["state"]), []
    state["intent"] = {"id": intent_id, "digest": intent["digest"]}
    phase = plan["phase"]
    deadline = plan["prepared_at"] + {"pilot": 180, "start": 1080, "tick": 360}[phase]
    if phase == "tick":
        deadline = min(deadline, state["ends_at"] + INTERVAL)
    def emit(rec):
        rows.append(rec)
        if on_row:
            on_row(rec)
    def room():
        return clock() + 30 + 2 <= deadline
    def report(label, mint, slot=None):
        requested_at = None
        if not room():
            raw = {"http": "0", "body": "not_observed"}
        else:
            requested_at = clock()
            state["requests"]["rugcheck"] += 1
            raw = _observe_fields(label, mint)
        try:
            rec = _row(raw, state, label, mint, clock(), slot)
        except StudyError as exc:
            if str(exc) != "row_overflow":
                raise
            receipt = {"kind": "overflow_receipt", "reason": "row_overflow", "study": state["study"],
                       "phase": phase, "slot": slot, "sweep": slot + 1 if slot is not None else 0,
                       "mint": mint, "label": label, "attempt": 0, "ts": clock(),
                       "http": str(raw.get("http", "0"))[:3], "body": "invalid",
                       "score_normalised": None, "score_state": "overflow", "request_started_at": requested_at,
                       "raw_score_type": type(raw.get("score_normalised")).__name__,
                       "raw_score_digest": sha(repr(raw.get("score_normalised")).encode("utf-8"))}
            emit(receipt)
            state.setdefault("losses", []).append({"reason": "row_overflow", "slot": slot, "mint": mint})
            raise
        rec["request_started_at"] = requested_at
        if slot is not None:
            rec["due_at"] = state["started_at"] + slot * INTERVAL
            rec["job_started_at"] = plan["prepared_at"]
            rec["outside_window"] = rec["ts"] > state["ends_at"]
        emit(rec)
        if raw.get("body") != "not_observed":
            sleep(2)
        return rec
    def listing(page):
        if not room():
            emit({"kind": "listing", "phase": phase, "page": page, "ts": clock(), "http": "0", "body": "not_observed"})
            return None
        state["requests"]["gecko"] += 1
        code, body = probe.curl(probe.GECKO_NEW % page)
        data = body.get("data") if isinstance(body, dict) else None
        usable = str(code) == "200" and isinstance(data, list)
        emit({"kind": "listing", "phase": phase, "page": page, "ts": clock(), "http": str(code)[:3],
              "body": "ok" if usable else "unavailable", "rows_returned": len(data) if usable else None})
        sleep(2)
        return data if usable else None
    try:
        if phase == "pilot":
            listed = listing(1)
            measured = [report(label, mint) for label, mint in probe.MAJORS[:6]]
            good = (listed is not None and len(measured) == 6 and all(r["body"] == "ok"
                    and probe.band(r["score_normalised"]) is not None and r["age_minutes"] is not None
                    and r["age_minutes"] >= 0 for r in measured))
            state["status"] = "pilot_passed" if good else "pilot_failed"
        elif phase == "start":
            seen, fresh = set(), []
            counts = {"duplicate": 0, "invalid_identity": 0, "truncated": 0, "excluded": 0, "unobserved": 0}
            controls = {m for _, m in probe.MAJORS}
            for page in range(1, 9):
                data = listing(page)
                if not data:
                    break
                used = 0
                for item in data:
                    try:
                        ident = item["relationships"]["base_token"]["data"]["id"]
                        candidate = ident.removeprefix("solana_") if ident.startswith("solana_") else ""
                    except (KeyError, TypeError, AttributeError):
                        candidate = ""
                    if not MINT.fullmatch(candidate):
                        counts["invalid_identity"] += 1
                        continue
                    if candidate in seen or candidate in controls:
                        counts["duplicate"] += 1
                        continue
                    if used >= 30:
                        counts["truncated"] += 1
                        continue
                    seen.add(candidate)
                    used += 1
                    rec = report("candidate-%d" % len(seen), candidate)
                    age = rec["age_minutes"]
                    if rec["body"] == "ok" and age is not None and 0 <= age <= MAX_AGE_MIN:
                        # Identity is already on the member; the complete enrollment row
                        # remains in this immutable chunk. Avoid duplicating routing IDs
                        # in every later 64-KiB intent while retaining its actual evidence.
                        enrollment = {k: v for k, v in rec.items() if k not in
                                      ("kind", "study", "phase", "slot", "sweep", "attempt", "mint", "label")}
                        fresh.append({"mint": candidate, "label": "fresh-%d" % len(fresh),
                                      "group": "fresh", "enrollment": enrollment})
                    else:
                        counts["unobserved" if rec["body"] != "ok" or age is None else "excluded"] += 1
                    if len(fresh) >= FRESH_TARGET or not room():
                        counts["truncated"] += max(0, len(data) - data.index(item) - 1)
                        break
                if len(fresh) >= FRESH_TARGET or not room():
                    break
            state["recruitment"] = counts
            if len(fresh) < FRESH_MIN:
                state["status"] = "insufficient_cohort"
                state["cohort"] = fresh
            else:
                state["cohort"] = fresh + [{"mint": m, "label": label, "group": "control"} for label, m in probe.MAJORS]
                state["started_at"] = clock()
                state["ends_at"] = state["started_at"] + DURATION
                state["status"] = "active"
        else:
            slot = state["slot"]
            for member in state["cohort"]:
                report(member["label"], member["mint"], slot)
            state["slots"].append({"slot": slot, "status": "partial" if any(r["body"] == "not_observed" for r in rows) else "observed"})
            state["status"] = "completed" if slot == LAST_SLOT else "active"
    except StudyError as exc:
        state["status"] = "overflow" if str(exc) == "row_overflow" else "failed"
        state["failure"] = "row_overflow" if str(exc) == "row_overflow" else "collection_unavailable"
        if phase == "tick" and not any(s["slot"] == state["slot"] for s in state["slots"]):
            state["slots"].append({"slot": state["slot"], "status": "partial"})
    except Exception:
        # Preserve already written measurements; the unexpected local failure is terminal.
        state["status"] = "failed"
        state["failure"] = "collection_interrupted"
        if phase == "tick" and not any(s["slot"] == state["slot"] for s in state["slots"]):
            state["slots"].append({"slot": state["slot"], "status": "partial"})
    _validate_state(state)
    return state, rows


def _attempted(row):
    if "request_started_at" in row:
        return number(row["request_started_at"])
    return row.get("body") != "not_observed"


def _missing_intervals(state):
    missing = [s["slot"] for s in state["slots"] if s["status"] == "not_observed"]
    groups = []
    for slot in missing:
        if groups and groups[-1][-1] + 1 == slot:
            groups[-1].append(slot)
        else:
            groups.append([slot])
    return [{"slots": group, "due_start": state["started_at"] + group[0] * INTERVAL,
             "due_end": min(state["ends_at"], state["started_at"] + (group[-1] + 1) * INTERVAL)}
            for group in groups] if state["started_at"] is not None else []


def _coverage(state, rows):
    powers = ("permanentDelegate", "pausableConfig", "mintCloseAuthority", "freeze_or_mint")
    fields = ("score_normalised", "detectedAt", "totalHolders", "topHolders_n", *powers)
    result = {}
    for group in ("fresh", "control"):
        members = {m["mint"] for m in state["cohort"] if m["group"] == group}
        expected = len(members) * (LAST_SLOT + 1)
        item = {"population": len(members), "scheduled_slots": LAST_SLOT + 1, "expected_cells": expected,
                "attempted_cells": 0, "never_attempted_cells": expected, "attempted_failed_requests": 0,
                "fields": {key: {"usable": 0, "attempted_unavailable_or_invalid": 0,
                                  "outside_window": 0, "never_attempted": expected} for key in fields},
                "slots": {str(s["slot"]): {"attempted_cells": 0, "never_attempted_cells": len(members)} for s in state["slots"]},
                "observation_intervals": []}
        seen, intervals = set(), {}
        for row in rows:
            if row.get("phase") != "tick" or row.get("mint") not in members:
                continue
            slot = row.get("slot")
            if type(slot) is not int or not 0 <= slot <= LAST_SLOT or not number(row.get("ts")):
                raise StudyError("invalid_observation")
            key = (slot, row["mint"], row.get("attempt"))
            if key in seen:
                raise StudyError("duplicate_observation")
            seen.add(key)
            counts = item["slots"].setdefault(str(slot), {"attempted_cells": 0, "never_attempted_cells": len(members)})
            if not _attempted(row):
                continue
            item["attempted_cells"] += 1
            item["never_attempted_cells"] -= 1
            counts["attempted_cells"] += 1
            counts["never_attempted_cells"] -= 1
            intervals.setdefault(slot, []).append(row["ts"])
            envelope = str(row.get("http")) == "200" and row.get("body") == "ok"
            if not envelope:
                item["attempted_failed_requests"] += 1
            outside = state["started_at"] is None or not state["started_at"] <= row["ts"] <= state["ends_at"]
            for field in fields:
                field_counts = item["fields"][field]
                field_counts["never_attempted"] -= 1
                value = (row.get("gated") or {}).get(field) if field in powers else row.get(field)
                if field in powers:
                    valid = type(value) is bool
                elif field in ("totalHolders", "topHolders_n"):
                    valid = type(value) is int and value >= 0
                elif field == "detectedAt":
                    age = probe.age_minutes(value, datetime.datetime.fromtimestamp(row["ts"], datetime.timezone.utc))
                    valid = age is not None and age >= 0
                else:
                    valid = probe.band(value) is not None
                field_counts["outside_window" if outside else "usable" if envelope and valid else "attempted_unavailable_or_invalid"] += 1
        item["observation_intervals"] = [{"slot": slot, "first_response_at": min(values), "last_response_at": max(values),
                                           "responses": len(values)} for slot, values in sorted(intervals.items())]
        result[group] = item
    return result


def _index_time(value):
    if not isinstance(value, str) or "T" not in value:
        return None
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=datetime.timezone.utc)
        return parsed.timestamp()
    except (ValueError, OverflowError, OSError):
        return None


def readout(state, rows):
    _validate_state(state)
    fresh = [m for m in state["cohort"] if m["group"] == "fresh"]
    by = {m["mint"]: [] for m in fresh}
    start, end = state.get("started_at"), state.get("ends_at")
    answer = {"study": state["study"], "fresh_enrolled": len(fresh), "started_at": start, "ends_at": end,
              "duration_seconds": DURATION, "final_tenth_start": None if start is None else start + DURATION * 0.9,
              "events": [], "outside_window_observations": 0, "unavailable_score_cells": 0,
              "censored": True, "negative_tail_established": False, "proposal": "inconclusive",
              "coverage": _coverage(state, rows), "missing_slot_intervals": _missing_intervals(state),
              "losses": copy.deepcopy(state.get("losses", []))}
    if start is None:
        return answer
    keys = set()
    for row in rows:
        if row.get("phase") != "tick" or row.get("mint") not in by:
            continue
        key = (row.get("slot"), row["mint"], row.get("attempt"))
        if key in keys:
            raise StudyError("duplicate_observation")
        keys.add(key)
        if not number(row.get("ts")) or type(row.get("slot")) is not int or not 0 <= row["slot"] <= LAST_SLOT:
            raise StudyError("invalid_observation")
        if not _attempted(row):
            continue
        if row["ts"] > end or row["ts"] < start:
            answer["outside_window_observations"] += 1
            continue
        usable = str(row.get("http")) == "200" and row.get("body") == "ok" and probe.band(row.get("score_normalised")) is not None
        if usable:
            by[row["mint"]].append(row)
        else:
            answer["unavailable_score_cells"] += 1
    observed = 0
    for member in fresh:
        clean = None
        records = sorted(by[member["mint"]], key=lambda row: (row["ts"], row["slot"]))
        observed += len(records)
        for row in records:
            if probe.band(row["score_normalised"]) == "ok":
                clean = row
            elif clean is not None:
                left_age = probe.age_minutes(clean.get("detectedAt"),
                                             datetime.datetime.fromtimestamp(clean["ts"], datetime.timezone.utc))
                right_age = probe.age_minutes(row.get("detectedAt"),
                                              datetime.datetime.fromtimestamp(row["ts"], datetime.timezone.utc))
                origins = [_index_time(r.get("detectedAt")) for r in (clean, row, member["enrollment"])]
                compatible = (all(x is not None for x in origins) and len(set(origins)) == 1
                              and left_age is not None and right_age is not None and 0 <= left_age <= right_age)
                boundary = start + DURATION * 0.9
                location = ("within_final_tenth" if clean["ts"] >= boundary else
                            "before_final_tenth" if row["ts"] < boundary else "ambiguous")
                answer["events"].append({"mint": member["mint"], "interval_start": clean["ts"],
                    "interval_end": row["ts"], "elapsed_minutes": (row["ts"] - start) / 60,
                    "elapsed_interval_minutes": [(clean["ts"] - start) / 60, (row["ts"] - start) / 60],
                    "index_age_interval_minutes": [left_age, right_age], "index_origin_compatible": compatible,
                    "lower_bound_minutes": left_age if compatible else None, "tail_location": location,
                    "gap_censored": row["slot"] != clean["slot"] + 1})
                clean = None
    expected = len(fresh) * (LAST_SLOT + 1)
    answer["observed_score_cells"] = observed
    answer["expected_score_cells"] = expected
    answer["not_observed_score_cells"] = answer["coverage"]["fresh"]["fields"]["score_normalised"]["never_attempted"]
    answer["unavailable_score_cells"] = answer["coverage"]["fresh"]["fields"]["score_normalised"]["attempted_unavailable_or_invalid"]
    answer["censored"] = observed != expected or bool(answer["outside_window_observations"])
    if answer["events"]:
        latest = max(answer["events"], key=lambda row: row["interval_end"])
        answer["latest_flip"] = latest
        answer["proposed_lower_bound_minutes"] = latest["lower_bound_minutes"]
        answer["proposal"] = ("different_rule_e14_review" if latest["tail_location"] == "within_final_tenth"
                              else "larger_window_lower_bound_with_censoring" if latest["tail_location"] == "before_final_tenth"
                              and latest["lower_bound_minutes"] is not None else "inconclusive")
    elif not answer["censored"] and len(fresh) >= FRESH_MIN:
        answer["proposal"] = "no_flip_observed"
    return answer


def reconstruct(store, ctx, study):
    candidates = [m for m in store.list() if (match := ARTIFACT.fullmatch(str(m.get("name", ""))))
                  and match[1] == "result"]
    if not candidates:
        raise StudyError("no_study_results")
    latest = None
    for meta in sorted(candidates, key=lambda m: m["id"], reverse=True)[:195]:
        candidate = store.load(meta["id"])
        if candidate["state"]["study"] == study:
            latest = candidate
            break
    if latest is None:
        raise StudyError("no_study_results")
    chunks = latest["state"]["chunks"]
    if len(chunks) + 1 > 195:
        raise StudyError("history_limit")
    rows, previous = [], latest["state"].get("pilot")
    for reference in chunks:
        part = store.load(reference["id"])
        if (part["digest"] != reference["digest"] or part["state"]["study"] != study
                or part["manifest"]["kind"] != "result" or part["state"]["parent"] != previous
                or part["state"]["source"] != latest["state"]["source"]):
            raise StudyError("history_chain")
        if part["state"]["cohort"] != latest["state"]["cohort"]:
            raise StudyError("cohort_changed")
        rows.extend(part["rows"])
        previous = reference
    if latest["state"]["parent"] != previous:
        raise StudyError("history_chain")
    rows.extend(latest["rows"])
    return readout(latest["state"], rows)


def _context_env():
    try:
        ctx = {"repository": os.environ["GITHUB_REPOSITORY"], "workflow": WORKFLOW,
               "branch": os.environ["GITHUB_REF_NAME"], "default_branch": os.environ["W57_DEFAULT_BRANCH"],
               "run_id": int(os.environ["GITHUB_RUN_ID"]), "head": os.environ["GITHUB_SHA"], "source": source_hashes()}
        if ctx["branch"] != ctx["default_branch"] or os.environ.get("GITHUB_EVENT_NAME") not in ("schedule", "workflow_dispatch"):
            raise StudyError("untrusted_run")
        return ctx
    except (KeyError, ValueError):
        raise StudyError("ci_context_unavailable") from None


def write_bundle(folder, state, rows, kind, ctx):
    folder.mkdir(parents=True, exist_ok=True)
    for name, data in _bundle_files(state, rows, kind, ctx).items():
        temporary = folder / (name + ".tmp")
        temporary.write_bytes(data)
        os.replace(temporary, folder / name)


def _output(name, value):
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
            stream.write(name + "=" + str(value) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description="W57 explicit pilot/start; cron only resumes a frozen study")
    sub = parser.add_subparsers(dest="command")
    p = sub.add_parser("prepare")
    p.add_argument("--phase", choices=("pilot", "start", "tick", "report"), required=True)
    p.add_argument("--study", default="")
    p.add_argument("--pilot", default="")
    p.add_argument("--out", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--out", required=True)
    c.add_argument("--intent", type=int, required=True)
    f = sub.add_parser("finish")
    f.add_argument("--out", required=True)
    f.add_argument("--uploaded", required=True)
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    try:
        out = Path(args.out).resolve()
        if out.is_relative_to(ROOT):
            raise StudyError("protected_output")
        if args.command == "finish":
            if args.uploaded != "success":
                raise StudyError("checkpoint_upload_failed")
            state = json.loads((out / "result/state.json").read_text(encoding="utf-8"))
            return 0 if state["status"] in ("pilot_passed", "active", "completed") else 2
        ctx = _context_env()
        store = GitHubArtifacts(ctx, os.environ.get("GITHUB_TOKEN", ""),
                                max_reads=600 if getattr(args, "phase", None) == "report" else 12,
                                max_downloads=195 if getattr(args, "phase", None) == "report" else 2,
                                seconds=720 if getattr(args, "phase", None) == "report" else 110)
        if args.command == "prepare":
            if out.exists() and any(out.iterdir()):
                raise StudyError("output_exists")
            out.mkdir(parents=True, exist_ok=True)
            if args.phase == "report":
                answer = reconstruct(store, ctx, args.study)
                folder = out / "result"
                folder.mkdir()
                (folder / "report.json").write_bytes(encoded(answer))
                # A report is not a checkpoint and is never resumed by cron.
                (folder / "state.json").write_bytes(encoded({"status": "completed"}))
                _output("action", "report")
                _output("result-name", "w57-report-v1")
                _output("ready", "true")
                return 0
            plan = prepare(args.phase, store, ctx, time.time(), study=args.study or None,
                           pilot_id=int(args.pilot) if args.pilot else None)
            plan["artifact_reads"] = store.reads
            plan["artifact_downloads"] = store.downloads
            _output("action", plan["action"])
            if plan["action"] == "idle":
                print("W57 idle")
                return 0
            (out / "plan.json").write_bytes(encoded(plan))
            if plan["action"] == "collect":
                write_bundle(out / "intent", plan["state"], [], "intent", ctx)
                fallback = copy.deepcopy(plan["state"])
                fallback["status"] = "lost_checkpoint"
                write_bundle(out / "result", fallback, [], "result", ctx)
                _output("intent-name", artifact_name(plan["state"], "intent", ctx))
            else:
                write_bundle(out / "result", plan["state"], [], "result", ctx)
            _output("result-name", artifact_name(plan["state"], "result", ctx))
            _output("ready", "true")
            print("W57 checkpoint prepared")
        else:
            plan = json.loads((out / "plan.json").read_text(encoding="utf-8"))
            store.reads = plan.get("artifact_reads", 0)
            store.downloads = plan.get("artifact_downloads", 0)
            with (out / "result/observations.jsonl").open("wb") as stream:
                def append(rec):
                    stream.write(encoded(rec) + b"\n")
                    stream.flush()
                state, rows = collect(plan, args.intent, store, ctx, on_row=append)
            write_bundle(out / "result", state, rows, "result", ctx)
            print("W57 collection recorded")
        return 0
    except (StudyError, OSError, ValueError, TypeError):
        print("W57 unavailable; prior checkpoints retained")
        return 1


if __name__ == "__main__":
    sys.exit(main())
