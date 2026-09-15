"""sim_probe.py -- W41 prototype: our own buy/sell simulation on UniswapV2-style routers.

Usage:
    python bench/sim_probe.py              # run, print, write bench/sim_probe/v2-<date>.json

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

import datetime
import glob
import hashlib
import io
import json
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
    data = (ret or "0x")[2:]
    if len(data) < 128:
        return None
    n = int(data[64:128], 16)
    if n == 0:
        return None
    return int(data[64 + 64 * n:128 + 64 * n], 16)


def _uint(ret):
    data = (ret or "0x")[2:]
    return int(data[:64], 16) if len(data) >= 64 else None


# ---------------------------------------------------------------- transport, cached

def _post(url, payload, key):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, hashlib.sha256(key.encode()).hexdigest()[:40] + ".json")
    if os.path.exists(path):
        return json.load(io.open(path, encoding="utf-8"))
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=body, headers={
        "content-type": "application/json", "user-agent": "vetagent-research/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            out = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        out = {"transport_error": "HTTP %d" % e.code}
    except Exception as e:  # noqa: BLE001
        out = {"transport_error": str(e)[:160]}
    time.sleep(0.6)
    if "transport_error" not in out:       # an unanswered call is never cached as an answer
        json.dump(out, io.open(path, "w", encoding="utf-8"))
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
        out = rpc(chain, "eth_simulateV1", params, "%s|%s|%s|%s" % (tag, token, quote, block))
        if "transport_error" in out or "error" in out:
            return None, (out.get("transport_error") or json.dumps(out.get("error"))[:160])
        return (out.get("result") or [{}])[0].get("calls") or [], None

    def failed(call):
        return call.get("status") != "0x1"

    def why(call):
        err = call.get("error") or {}
        return str(err.get("message") or err.get("data") or "reverted")[:120]

    rec = {"chain": chain, "token": token, "path": path, "block": block}
    first, err = run(calls(), "buy")
    if first is None:
        rec.update(result="rpc_error", detail=err)
        return rec
    if len(first) < 3 or failed(first[0]):
        rec.update(result="no_path", detail=why(first[0]) if first else "no calls")
        return rec
    expected_buy = _uint_array_last(first[0].get("returnData"))
    if failed(first[1]):
        rec.update(result="buy_reverted", detail=why(first[1]))
        return rec
    arrived = _uint(first[2].get("returnData"))
    if not arrived:
        rec.update(result="buy_no_tokens")
        return rec
    rec["buy_tax"] = round(100.0 * (1 - arrived / expected_buy), 2) if expected_buy else None

    second, err = run(calls(arrived), "sell")
    if second is None or len(second) < 7:
        rec.update(result="rpc_error", detail=err or "short response")
        return rec
    if failed(second[3]):
        rec.update(result="sell_reverted", detail="approve: " + why(second[3]))
        return rec
    expected_sell = _uint_array_last(second[4].get("returnData")) if not failed(second[4]) else None
    if failed(second[5]):
        rec.update(result="sell_reverted", detail=why(second[5]))
        return rec
    proceeds = _uint(second[6].get("returnData")) or 0
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
        for line in io.open(f, encoding="utf-8"):
            try:
                x = json.loads(line)
            except ValueError:
                continue
            if x.get("outcome") != "ok":
                continue
            pair = (x.get("pair") or {}).get("pair") or {}
            if pair.get("type") != "UniswapV2":
                continue
            latest[(x["chain"], x["token"].lower())] = (x, pair)
    clean = {"ethereum": [], "base": []}
    honeypots = []
    for (chain, token), (x, pair) in sorted(latest.items(), key=lambda kv: kv[0][1]):
        chain = {"eth": "ethereum"}.get(chain, chain)
        other = [a for a in (pair.get("token0"), pair.get("token1"))
                 if a and a.lower() != token]
        quote = other[0].lower() if other else None
        proven = x.get("isHoneypot") and (not x.get("simulationSuccess")
                                          or (x.get("sellTax") or 0) >= 50)
        if chain == "ethereum" and proven:
            honeypots.append({"chain": chain, "token": token, "quote": quote})
        elif chain in clean and x.get("isHoneypot") is False and x.get("simulationSuccess"):
            if len(clean[chain]) < ARCHIVE_CONTROLS_PER_CHAIN:
                clean[chain].append({"chain": chain, "token": token, "quote": quote})
    return clean["ethereum"] + clean["base"], honeypots


def main():
    day = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    targets = json.load(io.open(os.path.join(OUT_DIR, "targets-2026-09-15.json"), encoding="utf-8"))
    blocks = {}
    for chain in RPC:
        out = rpc(chain, "eth_blockNumber", [], "block|%s" % day)
        blocks[chain] = out.get("result")
        if not blocks[chain]:
            print("no block number from %s: %s" % (chain, out))
            return 1

    u = [{"chain": "bsc", "token": t["address"], "quote": t["quote"], "symbol": t["symbol"]}
         for t in targets["unknown"]]
    bsc_clean = [{"chain": "bsc", "token": t["address"], "quote": t["quote"], "symbol": t["symbol"]}
                 for t in targets["controls"]
                 if t["address"].lower() != WNATIVE["bsc"]]
    arch_clean, arch_hp = archive_controls()
    records = {"U": [], "C-clean": [], "C-honeypot": []}

    for t in u:
        rec = simulate("bsc", t["token"], t["quote"], blocks["bsc"])
        rec["symbol"] = t["symbol"]
        records["U"].append(rec)
        print("U  %-12s %-16s %s" % (t["symbol"][:12], rec["result"], rec.get("detail", "")[:60]))

    for group, items in (("C-clean", bsc_clean + arch_clean), ("C-honeypot", arch_hp)):
        for t in items:
            hp = honeypot_today(t["chain"], t["token"], day)
            shape, hp_buy, hp_sell = hp_shape(hp)
            rec = simulate(t["chain"], t["token"], t["quote"], blocks[t["chain"]])
            rec.update(symbol=t.get("symbol") or "", hp_today=shape, hp_buy_tax=hp_buy,
                       hp_sell_tax=hp_sell)
            want = "clean" if group == "C-clean" else "proven"
            rec["countable"] = shape == want
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
            print("%-10s %-8s %-44s hp=%-6s %-16s buy=%s sell=%s agrees=%s %s" % (
                group, t["chain"][:8], t["token"], shape, rec["result"], rec.get("buy_tax"),
                rec.get("sell_tax"), rec["agrees"], rec.get("detail", "")[:50]))

    definite = sum(1 for r in records["U"] if r["result"] in ("sold", "sell_reverted"))
    cc = [r for r in records["C-clean"] if r["countable"]]
    hc = [r for r in records["C-honeypot"] if r["countable"]]
    clean_share = (sum(r["agrees"] for r in cc) / len(cc)) if cc else None
    hp_share = (sum(r["agrees"] for r in hc) / len(hc)) if hc else None
    if definite < U_DEFINITE_STOP:
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
    summary = {
        "run_day": day, "blocks": blocks, "rule": "docs/SELL_SIMULATION.md (c66aba1)",
        "u_definite": "%d of %d" % (definite, len(records["U"])),
        "clean_controls": "%d agree of %d countable (%d asked)" % (
            sum(r["agrees"] for r in cc), len(cc), len(records["C-clean"])),
        "honeypot_controls": "%d agree of %d countable (%d asked)" % (
            sum(r["agrees"] for r in hc), len(hc), len(records["C-honeypot"])),
        "decision": decision,
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "v2-%s.json" % day)
    json.dump({"summary": summary, "records": records}, io.open(path, "w", encoding="utf-8"),
              indent=1)
    print("\n" + json.dumps(summary, indent=1))
    print("wrote %s" % path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
