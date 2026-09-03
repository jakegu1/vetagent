"""fetcher.py — 带磁盘缓存的 HTTP 取数器，并记录每个 URL 是谁取的。

两个职责：
1. 缓存 —— 基准要可复现、可重跑，也不能把上游免费额度打爆。
2. **来源记账** —— 记录「引擎」和「标注器」各自访问了哪些端点。
   基准的有效性完全建立在这两组端点不相交上，这里把它变成可断言的事实，
   而不是一句写在文档里、迟早会过期的承诺。
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

# 谁访问了什么。role 取值 "engine" / "label"。
_ACCESS_LOG = {"engine": set(), "label": set()}
_LOCK = threading.Lock()

# 每个 host 的最小请求间隔（秒），按各家免费额度保守取值
_RATE = {
    "api.geckoterminal.com": 2.1,   # 免费约 30 req/min
    "api.gopluslabs.io": 2.1,       # 免费约 30 req/min
    "api.honeypot.is": 0.4,
    "api.dexscreener.com": 0.25,    # 约 300 req/min
    "api.rugcheck.xyz": 0.5,
}
_last_hit = {}
_rate_lock = threading.Lock()


def endpoint_of(url):
    """把 URL 归一成「端点」标识：host + 去掉可变部分的路径。

    用于来源记账——我们关心的是「读了哪个接口」，不是「读了哪个代币」。
    """
    from urllib.parse import urlparse
    u = urlparse(url)
    parts = []
    for seg in u.path.strip("/").split("/"):
        if not seg:
            continue
        # 地址/哈希/纯数字这类可变段替换成占位符
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
    """取 JSON。role 必须是 "engine" 或 "label"，用于来源记账。

    返回 dict/list 表示成功，None 表示抓取失败——
    与 risk._fetch_json 的契约一致，这样引擎跑基准时行为不变。
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
                break  # 4xx 重试无意义
        except Exception:
            pass
        if attempt < retries:
            time.sleep(0.8 * (2 ** attempt))

    # 只缓存成功结果：失败缓存下来会把一次网络抖动变成永久的「无数据」
    if data is not None:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"url": url, "data": data}, f, ensure_ascii=False)
        except OSError:
            pass
    return data


def access_report():
    """返回 (engine_endpoints, label_endpoints, overlap)。"""
    with _LOCK:
        e = set(_ACCESS_LOG["engine"])
        l = set(_ACCESS_LOG["label"])
    return sorted(e), sorted(l), sorted(e & l)


def reset_access_log():
    with _LOCK:
        _ACCESS_LOG["engine"].clear()
        _ACCESS_LOG["label"].clear()
