"""fetcher.py — HTTP fetcher with a disk cache that records who fetched each URL.

Two jobs:
1. Caching — the benchmark has to be reproducible and re-runnable, and it must not
   burn through upstream free tiers.
2. **Provenance accounting** — record which endpoints the "engine" and the "labeler"
   each hit. The benchmark is only valid if those two sets are disjoint, so make that
   an assertable fact rather than a promise in a doc that will go stale.
"""

import hashlib
import json
import os
import threading
import time
import urllib.error
import urllib.request

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
UA = "vetagent-benchmark/1.0 (+https://github.com/jakegu1/vetagent)"

# Who hit what. role is "engine" or "label".
_ACCESS_LOG = {"engine": set(), "label": set()}
_LOCK = threading.Lock()

# Minimum gap between requests per host (seconds), set conservatively from each free tier
_RATE = {
    "api.geckoterminal.com": 2.1,   # free tier is ~30 req/min
    "api.gopluslabs.io": 2.1,       # free tier is ~30 req/min
    "api.honeypot.is": 0.4,
    "api.dexscreener.com": 0.25,    # ~300 req/min
    "api.rugcheck.xyz": 0.5,
}
_last_hit = {}
_rate_lock = threading.Lock()


def endpoint_of(url):
    """Normalize a URL into an "endpoint" id: host plus path with variable parts removed.

    Used for provenance accounting: what we care about is which API was read, not
    which token.
    """
    from urllib.parse import urlparse
    u = urlparse(url)
    parts = []
    for seg in u.path.strip("/").split("/"):
        if not seg:
            continue
        # Address, hash, and all-digit segments are the variable ones — use a placeholder
        if seg.startswith("0x") or len(seg) > 25 or seg.isdigit():
            parts.append("{id}")
        else:
            parts.append(seg)
    return "%s/%s" % (u.netloc, "/".join(parts))


def _throttle(url):
    from urllib.parse import urlparse
    host = urlparse(url).netloc
    gap = _RATE.get(host, 0.3)
    with _rate_lock:
        last = _last_hit.get(host, 0.0)
        wait = gap - (time.time() - last)
        if wait > 0:
            time.sleep(wait)
        _last_hit[host] = time.time()


def fetch_json(url, role, retries=2, timeout=25, use_cache=True):
    """Fetch JSON. role must be "engine" or "label", for provenance accounting.

    Returns a dict/list on success, None on a failed fetch — the same contract as
    risk._fetch_json, so the engine behaves identically when it runs the benchmark.
    """
    assert role in ("engine", "label"), role
    with _LOCK:
        _ACCESS_LOG[role].add(endpoint_of(url))

    os.makedirs(CACHE_DIR, exist_ok=True)
    key = hashlib.sha256(url.encode()).hexdigest()[:40]
    path = os.path.join(CACHE_DIR, key + ".json")
    if use_cache and os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                blob = json.load(f)
            return blob.get("data")
        except (OSError, ValueError):
            pass

    data = None
    for attempt in range(retries + 1):
        try:
            _throttle(url)
            req = urllib.request.Request(url, headers={"Accept": "application/json",
                                                       "User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    body = resp.read().decode("utf-8", "replace")
                    if body:
                        data = json.loads(body)
                        break
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries:
                time.sleep(3.0 * (attempt + 1))
                continue
            if 400 <= e.code < 500 and e.code != 429:
                break  # retrying a 4xx gets you nothing
        except Exception:
            pass
        if attempt < retries:
            time.sleep(0.8 * (2 ** attempt))

    # Only cache successes: a cached failure turns one network blip into permanent "no data"
    if data is not None:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"url": url, "data": data}, f, ensure_ascii=False)
        except OSError:
            pass
    return data


ACCESS_LOG_PATH = os.path.join(CACHE_DIR, "..", "access_log.json")


def note_endpoint(role, endpoint):
    """Record an endpoint a sibling process sampled from, so the guard can see it."""
    assert role in ("engine", "label"), role
    with _LOCK:
        _ACCESS_LOG[role].add(endpoint)


def persist_access_log():
    """Write this process's endpoint log to disk.

    The labeling runs in build_dataset.py and the engine runs in run_benchmark.py --
    two separate processes. The in-memory log is per-process, so the benchmark saw an
    empty label set and its disjointness assertion passed vacuously: engine n {} is
    always {}. A check that cannot fail is not a check. Persisting the label side is
    what makes the assertion real.
    """
    with _LOCK:
        blob = {k: sorted(v) for k, v in _ACCESS_LOG.items()}
    try:
        os.makedirs(os.path.dirname(os.path.abspath(ACCESS_LOG_PATH)), exist_ok=True)
        # Replaces, never merges.
        #
        # It used to union each run into whatever was already on disk, which quietly
        # turned "endpoints this run touched" into "endpoints any run has ever touched".
        # That is wrong twice over: the benchmark prints the list under the heading
        # "endpoints actually hit on this run", and the disjointness assertion tests
        # against it. When DexScreener /search was dropped as a sampling source and
        # picked up by the engine for impersonation, the stale label-side entry was still
        # there, and the benchmark refused to run -- correctly objecting to an overlap
        # that no longer existed. A guard that fires on history rather than on the
        # present teaches people to work around it.
        with open(ACCESS_LOG_PATH, "w", encoding="utf-8") as fh:
            json.dump(blob, fh, ensure_ascii=False, indent=1)
    except (OSError, ValueError):
        pass


def load_persisted_access_log():
    """Merge the on-disk log into this process's view. Returns True if anything loaded."""
    try:
        with open(ACCESS_LOG_PATH, encoding="utf-8") as f:
            blob = json.load(f)
    except (OSError, ValueError):
        return False
    with _LOCK:
        for role in ("engine", "label"):
            _ACCESS_LOG[role].update(blob.get(role) or [])
    return True


def access_report():
    """Return (engine_endpoints, label_endpoints, overlap)."""
    with _LOCK:
        e = set(_ACCESS_LOG["engine"])
        l = set(_ACCESS_LOG["label"])
    return sorted(e), sorted(l), sorted(e & l)


def reset_access_log():
    with _LOCK:
        _ACCESS_LOG["engine"].clear()
        _ACCESS_LOG["label"].clear()
