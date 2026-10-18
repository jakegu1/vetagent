"""sim_probe.py -- W41 prototype: our own buy/sell simulation on UniswapV2-style routers.

Usage:
    python bench/sim_probe.py              # offline plan, no requests or writes
    python bench/sim_probe.py --refresh-controls --out <new-private-jsonl> --cache <new-dir>
    python bench/sim_probe.py --run --out <new-private-jsonl> --cache <new-dir>

Bench-only by design (docs/SELL_SIMULATION.md). It never imports the engine's fetch path, never
touches bench/cache, and nothing here is read by src/. Every rule it judges itself by was
committed in docs/SELL_SIMULATION.md (c66aba1) before this file existed; the thresholds below
are copied from that page and are not to be tuned against the output.

How it simulates: one `eth_simulateV1` request per token, pinned to one block, from a fresh
address given a native balance by state override. Buy through the router, read what arrived,
approve, sell back into the wrapped native token, read the proceeds. The expected amounts come
from `getAmountsOut` in the same block, so each tax is 1 - actual / expected with the LP fee and
price impact already inside both. A first request stops after the buy, to learn how many tokens
arrived; the second repeats it at the same block and sells exactly that many.

Controls are re-asked of honeypot.is on the day, and count only if today's answer still has the
shape they were chosen for.
"""

import argparse
import datetime
import glob
import hashlib
import io
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

from keccak import selector  # noqa: E402

CACHE = os.path.join(HERE, "cache_sim")
OUT_DIR = os.path.join(HERE, "sim_probe")
_ACTIVE_CACHE = None

RPC = {  # the engine's own hosts (src/risk.py _CHAIN_RPC)
    "ethereum": "https://rpc.mevblocker.io",
    "base": "https://mainnet.base.org",
    "bsc": "https://bsc-dataseed.bnbchain.org",
}
CHAIN_ID = {"ethereum": 1, "base": 8453, "bsc": 56}
# Routers as honeypot.is itself reports them in 265 / 104 / 45 answers (docs/SELL_SIMULATION.md).
ROUTER = {
    "ethereum": "0x7a250d5630b4cf539739df2c5dacb4c659f2488d",
    "base": "0x4752ba5dbc23f44d87826276bf6fd6b1c372ad24",
    "bsc": "0x10ed43c718714eb63d5aa57b78b54704e256024e",
}
WNATIVE = {
    "ethereum": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
    "base": "0x4200000000000000000000000000000000000006",
    "bsc": "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c",
}
AMOUNT_IN = {"ethereum": 2 * 10 ** 16, "base": 2 * 10 ** 16, "bsc": 10 ** 17}  # 0.02 / 0.02 / 0.1
SENDER = "0x5e11000000000000000000000000000000005e11"
DEADLINE = 2 ** 40
MAX = 2 ** 256 - 1

# Pre-registered in docs/SELL_SIMULATION.md. Do not edit to fit a result.
U_DEFINITE_BUILD, U_DEFINITE_STOP, U_N = 10, 7, 13
CLEAN_AGREE_SHARE, HONEYPOT_AGREE_SHARE, HONEYPOT_MIN_COUNTABLE = 0.90, 0.80, 5
TAX_TOLERANCE_POINTS = 5.0
ARCHIVE_CONTROLS_PER_CHAIN = 20

SEL = {name: selector(sig) for name, sig in {
    "getAmountsOut": "getAmountsOut(uint256,address[])",
    "buy": "swapExactETHForTokensSupportingFeeOnTransferTokens(uint256,address[],address,uint256)",
    "sell": "swapExactTokensForTokensSupportingFeeOnTransferTokens(uint256,uint256,address[],address,uint256)",
    "balanceOf": "balanceOf(address)",
    "approve": "approve(address,uint256)",
}.items()}


# ---------------------------------------------------------------- ABI, by hand

def _word(n):
    return "%064x" % n


def _addr(a):
    return _word(int(a, 16))


def _encode(sel, head_args, path=None, path_index=None):
    """Static args plus at most one dynamic address[] at position path_index."""
    n_head = len(head_args) + (1 if path is not None else 0)
    head, tail = [], ""
    args = list(head_args)
    if path is not None:
        args.insert(path_index, None)
    for a in args:
        if a is None:
            head.append(_word(32 * n_head))
            tail = _word(len(path)) + "".join(_addr(p) for p in path)
        elif isinstance(a, str):
            head.append(_addr(a))
        else:
            head.append(_word(a))
    return "0x" + sel + "".join(head) + tail


def _uint_array_last(ret):
    if not isinstance(ret, str) or not ret.startswith("0x"):
        return None
    data = ret[2:]
    if any(c not in "0123456789abcdefABCDEF" for c in data):
        return None
    try:
        n = int(data[64:128], 16)
        if int(data[:64], 16) != 32 or n not in (2, 3) or len(data) != 128 + 64 * n:
            return None
        return int(data[-64:], 16)
    except (ValueError, TypeError):
        return None


def _uint(ret):
    if not isinstance(ret, str) or not ret.startswith("0x") or len(ret) != 66:
        return None
    if any(c not in "0123456789abcdefABCDEF" for c in ret[2:]):
        return None
    try:
        return int(ret[2:], 16)
    except ValueError:
        return None


# ---------------------------------------------------------------- transport, cached

def _source_envelope(out, payload):
    """Minimum observed source contract, shared by fresh replies and cache reads."""
    if not isinstance(out, dict) or not out or "error" in out or "transport_error" in out:
        return False
    if payload is None:
        result = out.get("honeypotResult")
        return isinstance(result, dict) and type(result.get("isHoneypot")) is bool
    if not isinstance(payload, dict):
        return False
    result = out.get("result")
    if payload.get("method") == "eth_blockNumber":
        return (isinstance(result, str) and result.startswith("0x") and len(result) > 2
                and all(c in "0123456789abcdefABCDEF" for c in result[2:]))
    if payload.get("method") != "eth_simulateV1":
        return False
    if not isinstance(result, list) or len(result) != 1 or not isinstance(result[0], dict):
        return False
    calls = result[0].get("calls")
    return (isinstance(calls, list) and bool(calls)
            and all(isinstance(call, dict) and call.get("status") in ("0x0", "0x1")
                    for call in calls))


def _post(url, payload, key):
    if _ACTIVE_CACHE is None:
        return {"transport_error": "run_not_reserved"}
    path = os.path.join(_ACTIVE_CACHE, hashlib.sha256(key.encode()).hexdigest()[:40] + ".json")
    if os.path.exists(path):
        try:
            with io.open(path, encoding="utf-8") as cached:
                out = json.load(cached)
        except (OSError, ValueError):
            return {"transport_error": "cache_unreadable"}
        return out if _source_envelope(out, payload) else {"transport_error": "cache_malformed"}
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=body, headers={
        "content-type": "application/json", "user-agent": "vetagent-research/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            out = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        out = {"transport_error": "http_failed", "http_status": e.code}
    except Exception:
        out = {"transport_error": "request_failed"}
    time.sleep(0.6)
    if not _source_envelope(out, payload):
        return {"transport_error": "response_malformed"}
    if "transport_error" not in out:
        with io.open(path, "x", encoding="utf-8") as cached:
            json.dump(out, cached)
    return out


def rpc(chain, method, params, key):
    return _post(RPC[chain], {"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                 "%s|%s|%s" % (chain, method, key))


def honeypot_today(chain, token, day):
    url = "https://api.honeypot.is/v2/IsHoneypot?address=%s&chainID=%d" % (token, CHAIN_ID[chain])
    return _post(url, None, "hp|%s|%s" % (day, url))


def hp_shape(hp):
    if not isinstance(hp, dict) or "transport_error" in hp or not hp.get("honeypotResult"):
        return "none", None, None
    sim = hp.get("simulationResult") or {}
    is_hp = (hp.get("honeypotResult") or {}).get("isHoneypot")
    ok = hp.get("simulationSuccess") is True
    sell, buy = sim.get("sellTax"), sim.get("buyTax")
    if is_hp is False and ok:
        return "clean", buy, sell
    if is_hp is True and (not ok or (sell or 0) >= 50):
        return "proven", buy, sell
    return "other", buy, sell


def _number(value):
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def control_eligibility(hp, group, observed_day, run_day):
    """Separate a same-day source observation from the simulator's agreement."""
    result = {"eligibility": "unobserved", "reason": "control_unavailable"}
    try:
        valid_day = (datetime.date.fromisoformat(run_day).isoformat() == run_day
                     and observed_day == run_day)
    except (ValueError, TypeError):
        valid_day = False
    if not valid_day:
        return dict(result, reason="not_same_day")
    if not _source_envelope(hp, None):
        return result
    try:
        shape, _, _ = hp_shape(hp)
    except (TypeError, ValueError, AttributeError):
        return dict(result, reason="control_malformed")
    if shape != ("clean" if group == "C-clean" else "proven"):
        return {"eligibility": "excluded", "reason": "shape_changed"}
    if group == "C-honeypot":
        pair = hp.get("pair")
        amount = _number(pair.get("liquidity")) if isinstance(pair, dict) else None
        if amount is None:
            return dict(result, reason="liquidity_unobserved")
        if amount < 1000:
            return {"eligibility": "excluded", "reason": "below_floor"}
    return {"eligibility": "eligible", "reason": "same_day_control"}


# ---------------------------------------------------------------- the simulation

def simulate(chain, token, quote, block):
    w = WNATIVE[chain]
    token, quote = token.lower(), (quote or w).lower()
    path = [w, token] if quote == w else [w, quote, token]
    rev = list(reversed(path))
    router = ROUTER[chain]
    amt = AMOUNT_IN[chain]

    def calls(arrived=None):
        c = [
            {"from": SENDER, "to": router, "data": _encode(SEL["getAmountsOut"], [amt], path, 1)},
            {"from": SENDER, "to": router, "value": hex(amt),
             "data": _encode(SEL["buy"], [0, SENDER, DEADLINE], path, 1)},
            {"from": SENDER, "to": token, "data": _encode(SEL["balanceOf"], [SENDER])},
        ]
        if arrived is not None:
            c += [
                {"from": SENDER, "to": token, "data": _encode(SEL["approve"], [router, MAX])},
                {"from": SENDER, "to": router,
                 "data": _encode(SEL["getAmountsOut"], [arrived], rev, 1)},
                {"from": SENDER, "to": router,
                 "data": _encode(SEL["sell"], [arrived, 0, SENDER, DEADLINE], rev, 2)},
                {"from": SENDER, "to": w, "data": _encode(SEL["balanceOf"], [SENDER])},
            ]
        return c

    def run(c, tag):
        params = [{"blockStateCalls": [{"stateOverrides": {SENDER: {"balance": hex(10 ** 19)}},
                                        "calls": c}],
                   "validation": False}, block]
        try:
            out = rpc(chain, "eth_simulateV1", params, "%s|%s|%s|%s" % (tag, token, quote, block))
        except Exception:
            return None, "rpc_unobserved"
        if not isinstance(out, dict) or "transport_error" in out or "error" in out:
            return None, "rpc_unobserved"
        result = out.get("result")
        if not isinstance(result, list) or len(result) != 1 or not isinstance(result[0], dict):
            return None, "rpc_malformed"
        observed = result[0].get("calls")
        if not isinstance(observed, list) or len(observed) != len(c):
            return None, "rpc_malformed"
        return observed, None

    def succeeded(call):
        return isinstance(call, dict) and call.get("status") == "0x1"

    def setup(observed):
        if not all(succeeded(x) for x in observed[:3]):
            return None, None
        expected = _uint_array_last(observed[0].get("returnData"))
        balance = _uint(observed[2].get("returnData"))
        return expected, balance

    rec = {"chain": chain, "token": token, "path": path, "block": block}
    first, err = run(calls(), "buy")
    if first is None:
        rec.update(result="rpc_error", detail=err)
        return rec
    for index, result in ((0, "no_path"), (1, "buy_reverted"), (2, "setup_failed")):
        if isinstance(first[index], dict) and first[index].get("status") == "0x0":
            rec.update(result=result, detail="buy_setup_failed")
            return rec
    expected_buy, arrived = setup(first)
    if not expected_buy or not arrived:
        rec.update(result="setup_unobserved", detail="buy_or_balance_unobserved")
        return rec
    rec["buy_tax"] = round(100.0 * (1 - arrived / expected_buy), 2) if expected_buy else None

    second, err = run(calls(arrived), "sell")
    if second is None:
        rec.update(result="rpc_error", detail=err)
        return rec
    repeated_quote, repeated_balance = setup(second)
    if repeated_quote != expected_buy or repeated_balance != arrived:
        failed = any(isinstance(x, dict) and x.get("status") == "0x0" for x in second[:3])
        rec.update(result="setup_failed" if failed else "setup_unobserved",
                   detail="second_buy_or_balance_unobserved")
        return rec
    approval = second[3]
    if (not succeeded(approval)
            or (approval.get("returnData") != "0x" and _uint(approval.get("returnData")) != 1)):
        failed = (isinstance(approval, dict) and (
            approval.get("status") == "0x0" or _uint(approval.get("returnData")) == 0))
        rec.update(result="setup_failed" if failed else "setup_unobserved",
                   detail="approval_unobserved")
        return rec
    expected_sell = (_uint_array_last(second[4].get("returnData"))
                     if succeeded(second[4]) else None)
    if not expected_sell:
        rec.update(result="setup_unobserved", detail="sell_quote_unobserved")
        return rec
    sell = second[5]
    if isinstance(sell, dict) and sell.get("status") == "0x0":
        rec.update(result="sell_reverted", detail="executed_sell_reverted")
        return rec
    if not succeeded(sell) or not succeeded(second[6]):
        rec.update(result="setup_unobserved", detail="sell_or_proceeds_unobserved")
        return rec
    proceeds = _uint(second[6].get("returnData"))
    if proceeds is None:
        rec.update(result="setup_unobserved", detail="proceeds_unobserved")
        return rec
    rec["sell_tax"] = (round(100.0 * (1 - proceeds / expected_sell), 2)
                       if expected_sell else None)
    rec.update(result="sold" if proceeds > 0 else "sell_no_proceeds")
    return rec


# ---------------------------------------------------------------- the sets

def archive_controls():
    """Distinct tokens from the sellability archive: clean Uniswap V2 on eth/base, proven
    honeypots on eth. Each token's latest answer supplies its pool's other side."""
    latest = {}
    for f in sorted(glob.glob(os.path.join(HERE, "snapshots", "sellability-*.ndjson"))):
        for line_number, line in enumerate(io.open(f, encoding="utf-8"), 1):
            try:
                x = json.loads(line)
            except ValueError:
                if not line.strip():
                    continue
                raise ValueError("archive_unreadable") from None
            if x.get("outcome") != "ok":
                continue
            pair = (x.get("pair") or {}).get("pair") or {}
            if pair.get("type") != "UniswapV2":
                continue
            latest[(x["chain"], x["token"].lower())] = (x, pair, f, line_number)
    clean = {"ethereum": [], "base": []}
    honeypots = []
    for (chain, token), (x, pair, source, line_number) in sorted(latest.items(), key=lambda kv: kv[0][1]):
        chain = {"eth": "ethereum"}.get(chain, chain)
        other = [a for a in (pair.get("token0"), pair.get("token1"))
                 if a and a.lower() != token]
        quote = other[0].lower() if other else None
        item = {"chain": chain, "token": token, "quote": quote,
                "archive_seen_at": x.get("seen_at"),
                "archive_source": os.path.relpath(source, ROOT).replace(os.sep, "/"),
                "archive_line": line_number,
                "archived_liquidity": (x.get("pair") or {}).get("liquidity")}
        proven = x.get("isHoneypot") and (not x.get("simulationSuccess")
                                          or (x.get("sellTax") or 0) >= 50)
        if chain == "ethereum" and proven:
            honeypots.append(item)
        elif chain in clean and x.get("isHoneypot") is False and x.get("simulationSuccess"):
            if len(clean[chain]) < ARCHIVE_CONTROLS_PER_CHAIN:
                clean[chain].append(item)
    return clean["ethereum"] + clean["base"], honeypots


def make_plan():
    """Keep the base cohort algorithm; bind every source byte before any request."""
    target_path = os.path.join(OUT_DIR, "targets-2026-09-15.json")
    with io.open(target_path, encoding="utf-8") as source:
        targets = json.load(source)
    u = [{"chain": "bsc", "token": t["address"], "quote": t["quote"], "symbol": t["symbol"]}
         for t in targets["unknown"]]
    bsc_clean = [{"chain": "bsc", "token": t["address"], "quote": t["quote"], "symbol": t["symbol"]}
                 for t in targets["controls"]
                 if t["address"].lower() != WNATIVE["bsc"]]
    arch_clean, arch_hp = archive_controls()
    if len(u) != U_N:
        raise ValueError("invalid_target_population")
    inputs = []
    paths = [target_path] + sorted(glob.glob(os.path.join(HERE, "snapshots", "sellability-*.ndjson")))
    for path in paths:
        with io.open(path, "rb") as source:
            digest = hashlib.sha256(source.read()).hexdigest()
        inputs.append({"source": os.path.relpath(path, ROOT).replace(os.sep, "/"), "sha256": digest})
    candidates = sorted((t for t in arch_hp
                         if (_number(t.get("archived_liquidity")) is not None
                             and _number(t.get("archived_liquidity")) >= 1000)),
                        key=lambda t: (t["chain"], t["token"]))
    return {"sets": {"U": u, "C-clean": bsc_clean + arch_clean, "C-honeypot": arch_hp},
            "refresh_candidates": candidates[:6], "inputs": inputs,
            "input_digest": hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest(),
            "selection": "base latest-answer cohorts; historical-floor sorted first six for refresh only"}


def _day():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def _event(stream, record):
    # Invalid source numbers remain visibly invalid, while the artifact stays valid JSONL.
    def safe(value):
        if isinstance(value, float) and not math.isfinite(value):
            return str(value)
        if isinstance(value, dict):
            return {k: safe(v) for k, v in value.items()}
        if isinstance(value, list):
            return [safe(v) for v in value]
        return value
    stream.write(json.dumps(safe(record), allow_nan=False) + "\n")
    stream.flush()


def _refresh(plan, day, stream):
    population = len(plan["sets"]["C-honeypot"])
    chosen = plan["refresh_candidates"]
    if len(chosen) > 6:
        raise ValueError("refresh_population_invalid")
    counts = {"eligible": 0, "excluded": 0, "unobserved": 0, "not_asked": population}
    for index, token in enumerate(chosen):
        if counts["eligible"] + len(chosen) - index < HONEYPOT_MIN_COUNTABLE:
            break
        try:
            hp = honeypot_today(token["chain"], token["token"], day)
        except Exception:
            hp = {"transport_error": "request_failed"}
        eligibility = control_eligibility(hp, "C-honeypot", _day(), day)
        counts[eligibility["eligibility"]] += 1
        counts["not_asked"] -= 1
        _event(stream, {"type": "control", "candidate": token, "source_response": hp,
                        "observed_day": _day(), **eligibility})
    counts["screen_status"] = ("eligible" if counts["eligible"] >= HONEYPOT_MIN_COUNTABLE
                               else "not_measurable")
    return counts


def _decision(records, plan):
    definite = sum(r["result"] in ("sold", "sell_reverted") for r in records["U"])
    cc = [r for r in records["C-clean"] if r["countable"]]
    hc = [r for r in records["C-honeypot"] if r["countable"]]
    clean_share = sum(r["agrees"] for r in cc) / len(cc) if cc else None
    hp_share = sum(r["agrees"] for r in hc) / len(hc) if hc else None
    not_asked = sum(len(plan["sets"][g]) - len(records[g]) for g in records)
    if not_asked or len(records["U"]) != U_N:
        decision = "INCONCLUSIVE"
    elif definite < U_DEFINITE_STOP:
        decision = "STOP"
    elif (definite >= U_DEFINITE_BUILD and clean_share is not None
          and clean_share >= CLEAN_AGREE_SHARE and len(hc) >= HONEYPOT_MIN_COUNTABLE
          and hp_share >= HONEYPOT_AGREE_SHARE):
        decision = "BUILD V3 NEXT"
    elif (definite >= U_DEFINITE_BUILD and clean_share is not None
          and clean_share >= CLEAN_AGREE_SHARE and len(hc) < HONEYPOT_MIN_COUNTABLE):
        decision = "WAIT: positive control not measurable"
    else:
        decision = "INCONCLUSIVE"
    return {"u_definite": definite, "u_population": len(plan["sets"]["U"]),
            "clean_countable": len(cc), "clean_agree": sum(r["agrees"] for r in cc),
            "positive_countable": len(hc), "positive_agree": sum(r["agrees"] for r in hc),
            "excluded": sum(r.get("eligibility") == "excluded"
                            for g in ("C-clean", "C-honeypot") for r in records[g]),
            "unobserved": sum(r.get("eligibility") == "unobserved"
                              for g in ("C-clean", "C-honeypot") for r in records[g]),
            "not_asked": not_asked, "decision": decision}


def _run(plan, day, stream):
    records = {group: [] for group in plan["sets"]}
    blocks = {}
    for chain in RPC:
        out = rpc(chain, "eth_blockNumber", [], "block|%s" % day)
        block = out.get("result") if isinstance(out, dict) else None
        if not isinstance(block, str) or not block.startswith("0x"):
            _event(stream, {"type": "block", "chain": chain, "observation": "unobserved",
                            "reason": "block_unavailable"})
            return _decision(records, plan)
        try:
            int(block[2:], 16)
        except ValueError:
            _event(stream, {"type": "block", "chain": chain, "observation": "unobserved",
                            "reason": "block_malformed"})
            return _decision(records, plan)
        blocks[chain] = block
        _event(stream, {"type": "block", "chain": chain, "block": block})
    for token in plan["sets"]["U"]:
        rec = simulate(token["chain"], token["token"], token["quote"], blocks[token["chain"]])
        records["U"].append(rec)
        _event(stream, {"type": "simulation", "group": "U", "candidate": token, "observation": rec})
    for group in ("C-clean", "C-honeypot"):
        items = plan["sets"][group]
        for t in items:
            hp = honeypot_today(t["chain"], t["token"], day)
            eligibility = control_eligibility(hp, group, _day(), day)
            try:
                shape, hp_buy, hp_sell = hp_shape(hp)
            except (AttributeError, TypeError, ValueError):
                shape, hp_buy, hp_sell = "none", None, None
            _event(stream, {"type": "control_source", "group": group, "candidate": t,
                            "source_response": hp, "observed_day": _day(), **eligibility})
            rec = simulate(t["chain"], t["token"], t["quote"], blocks[t["chain"]])
            rec.update(symbol=t.get("symbol") or "", hp_today=shape, hp_buy_tax=hp_buy,
                       hp_sell_tax=hp_sell)
            rec.update(eligibility)
            rec["countable"] = rec["eligibility"] == "eligible"
            if group == "C-clean":
                rec["agrees"] = bool(rec["countable"] and rec["result"] == "sold"
                                     and rec.get("buy_tax") is not None
                                     and rec.get("sell_tax") is not None
                                     and abs(rec["buy_tax"] - (hp_buy or 0)) <= TAX_TOLERANCE_POINTS
                                     and abs(rec["sell_tax"] - (hp_sell or 0)) <= TAX_TOLERANCE_POINTS)
            else:
                rec["agrees"] = bool(rec["countable"] and (
                    rec["result"] == "sell_reverted"
                    or (rec["result"] == "sold" and (rec.get("sell_tax") or 0) >= 50)))
            records[group].append(rec)
            _event(stream, {"type": "control", "group": group, "candidate": t,
                            "source_response": hp, "observed_day": _day(), "observation": rec})
    return _decision(records, plan)


def _private_new_paths(output, cache):
    if not output or not cache or not os.path.isabs(output) or not os.path.isabs(cache):
        return False
    paths = [os.path.normcase(os.path.realpath(output)), os.path.normcase(os.path.realpath(cache))]
    for path in paths:
        if os.path.lexists(path) or not os.path.isdir(os.path.dirname(path)):
            return False
        parent = os.path.dirname(path)
        while True:
            if (parent == os.path.normcase(os.path.realpath(ROOT))
                    or os.path.isfile(os.path.join(parent, "bench", "sim_probe.py"))):
                return False
            above = os.path.dirname(parent)
            if above == parent:
                break
            parent = above
    try:
        return os.path.commonpath(paths) not in paths
    except ValueError:
        return True  # Distinct volumes cannot contain each other.


def main(argv=None):
    class Parser(argparse.ArgumentParser):
        def error(self, message):
            raise ValueError("invalid_arguments")
    parser = Parser(prog="sim_probe.py")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--refresh-controls", action="store_true")
    mode.add_argument("--run", action="store_true")
    parser.add_argument("--out")
    parser.add_argument("--cache")
    global _ACTIVE_CACHE
    previous_cache = _ACTIVE_CACHE
    try:
        args = parser.parse_args(argv)
        live = args.refresh_controls or args.run
        if live and not _private_new_paths(args.out, args.cache):
            print("Refused: live modes require new isolated output and cache paths.")
            return 2
        plan = make_plan()
        if not live:
            print(json.dumps({"mode": "plan", "populations": {
                g: len(items) for g, items in plan["sets"].items()},
                "refresh_max_requests": min(6, len(plan["refresh_candidates"])),
                "input_digest": plan["input_digest"]}))
            return 0
        with io.open(args.out, "x", encoding="utf-8") as stream:
            os.mkdir(args.cache, mode=0o700)
            _ACTIVE_CACHE = os.path.realpath(args.cache)
            day = _day()
            _event(stream, {"type": "manifest", "run_day": day, "mode":
                            "refresh-controls" if args.refresh_controls else "run", "plan": plan})
            try:
                summary = (_refresh(plan, day, stream) if args.refresh_controls
                           else _run(plan, day, stream))
            except (Exception, KeyboardInterrupt):
                _event(stream, {"type": "interrupted", "reason": "run_incomplete"})
                print("Incomplete: prior observations were preserved.")
                return 1
            _event(stream, {"type": "summary", "summary": summary})
        print(json.dumps(summary))
        return 0
    except (Exception, KeyboardInterrupt):
        print("Refused: invalid arguments, paths or unreadable plan inputs.")
        return 2
    finally:
        _ACTIVE_CACHE = previous_cache


if __name__ == "__main__":
    sys.exit(main())
