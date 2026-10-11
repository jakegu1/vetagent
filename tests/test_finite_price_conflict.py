"""T-021 (c2): finite admitted prices preserve the strict unranked conflict rule.

Run: python tests/test_finite_price_conflict.py
"""
import ast
import asyncio
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_finite_market_measurements as shared

risk, mcp_server = shared.risk, shared.mcp_server
PASSED, FAILURES, EXECUTED = 0, [], []


def check(name, condition, detail=''):
    global PASSED
    if condition:
        PASSED += 1
        print('  PASS ' + name)
    else:
        FAILURES.append((name, str(detail)))
        print('  FAIL %s: %s' % (name, detail))


def strict(name, value):
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc:
        check(name + ' strict JSON', False, exc)
    else:
        check(name + ' strict JSON', isinstance(value, dict), value)


def rpc(name, arguments):
    response = asyncio.run(mcp_server.handle_mcp_request({
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
        'params': {'name': name, 'arguments': arguments}}))
    strict(name + ' MCP envelope', response)
    result = (response or {}).get('result') or {}
    payload = result.get('structuredContent')
    check(name + ' MCP executes the real tool', 'error' not in (response or {})
          and not result.get('isError') and isinstance(payload, dict), response)
    text = (result.get('content') or [{}])[0].get('text', '{}')
    check(name + ' MCP text agrees with structured output', json.loads(text) == payload, response)
    schema = next(tool['outputSchema'] for tool in mcp_server.TOOLS if tool['name'] == name)
    check(name + ' actual MCP output matches declared schema',
          isinstance(payload, dict) and shared.accepts(schema, payload), payload)
    strict(name + ' MCP structured output', payload)
    return payload or {}


def complete(label, pairs, hint=None):
    results = {}
    with shared.offline(pairs):
        results['verbose'] = asyncio.run(risk.assess(shared.TOKEN, hint, True))
        results['compact'] = asyncio.run(risk.assess(shared.TOKEN, hint, False))
        results['liquidity'] = asyncio.run(risk.liquidity(shared.TOKEN, hint))
        for verbose in (True, False):
            kind = 'mcp-verbose' if verbose else 'mcp-compact'
            args = dict(address=shared.TOKEN, verbose=verbose)
            if hint is not None:
                args['chain_hint'] = hint
            results[kind] = rpc('assess_token_risk', args)
        args = dict(address=shared.TOKEN)
        if hint is not None:
            args['chain_hint'] = hint
        results['mcp-liquidity'] = rpc('get_token_liquidity', args)
    for kind, result in results.items():
        strict(label + ' ' + kind, result)
    return results


def candidates(low, high, low_depth=250000, high_depth=250000, same_chain=False):
    return [shared.pair(low_depth, price=low, chain='unlisted-a', identity='aa'),
            shared.pair(high_depth, price=high, chain='unlisted-a' if same_chain else 'unlisted-b', identity='bb')]


def conflict(label, result, expected):
    for kind in ('verbose', 'compact', 'mcp-verbose', 'mcp-compact'):
        answer = result[kind]
        evidence = answer.get('evidence') or {}
        observed = evidence.get('price_disagreement')
        signals = [s for s in answer.get('signals', []) if s.get('category') == 'price_disagreement']
        gaps = [gap for gap in evidence.get('data_gaps', []) if gap.get('dimension') == 'price']
        if expected is None:
            check(label + ' ' + kind + ' preserves no-conflict admission control',
                  observed is None and not signals and not gaps, answer)
        else:
            low, high = expected
            check(label + ' ' + kind + ' retains finite low/high conflict evidence',
                  observed == {'low_usd': low, 'high_usd': high}
                  and set(observed or {}) == {'low_usd', 'high_usd'}
                  and all(math.isfinite(value) for value in (observed or {}).values()), evidence)
            check(label + ' ' + kind + ' retains the existing disagreement signal',
                  len(signals) == 1 and signals[0].get('name') == 'Pools disagree about the price', signals)
            check(label + ' ' + kind + ' retains qualified about-token price gap',
                  len(gaps) == 1 and gaps[0].get('reason', '').startswith(risk._ABOUT_TOKEN + ': ')
                  and 'pools on unranked chains disagree on the price' in gaps[0]['reason'], gaps)


def both_orders(label, pairs, expected, hint=None):
    for index, order in enumerate((pairs, list(reversed(pairs)))):
        name = label + ' order ' + str(index)
        result = complete(name, order, hint)
        conflict(name, result, expected)
        yield name, result


def test_extreme_finite_prices_keep_conflict_in_complete_tools():
    check('extreme inputs are finite positive while their quotient overflows',
          math.isfinite(1e-307) and math.isfinite(1e308) and math.isinf(1e308 / 1e-307))
    for label, result in both_orders('finite ratio overflow', candidates(1e-307, 1e308), (1e-307, 1e308)):
        for kind in ('verbose', 'compact', 'mcp-verbose', 'mcp-compact'):
            check(label + ' ' + kind + ' retains existing unknown coverage result',
                  result[kind].get('risk_level') == 'unknown', result[kind])
        for kind in ('liquidity', 'mcp-liquidity'):
            check(label + ' ' + kind + ' returns admitted finite price/depth without ratio field',
                  result[kind].get('status') == 'ok' and result[kind].get('liquidity_usd') == 250000
                  and result[kind].get('price_usd') in (1e-307, 1e308)
                  and 'ratio' not in result[kind], result[kind])


def test_strict_100_boundary_and_101_conflict_are_unchanged():
    for high, expected in ((100, None), (101, (1.0, 101.0))):
        for label, result in both_orders('strict boundary ' + str(high), candidates(1, high), expected):
            for kind in ('liquidity', 'mcp-liquidity'):
                check(label + ' ' + kind + ' ordinary finite numbers and schema stay intact',
                      result[kind].get('status') == 'ok' and result[kind].get('price_usd') in (1, high),
                      result[kind])


def test_rank_and_single_unranked_chain_keep_existing_scope():
    ranked = candidates(1e-307, 1e308)
    ranked[0]['chainId'] = 'ethereum'
    for label, result in both_orders('supported-chain rank control', ranked, None):
        for kind in ('liquidity', 'mcp-liquidity'):
            check(label + ' ' + kind + ' rank keeps Ethereum finite price',
                  result[kind].get('best_pair_chain') == 'ethereum' and result[kind].get('price_usd') == 1e-307,
                  result[kind])
    for label, result in both_orders('single unranked chain control',
                                      candidates(1e-307, 1e308, same_chain=True), None):
        check(label + ' one unranked chain remains available', result['liquidity'].get('status') == 'ok')


def test_invalid_price_and_zero_unavailable_depth_cannot_create_conflict():
    for raw in shared.INVALID + (0, '0', '-0'):
        for label, result in both_orders('invalid, absent or nonpositive price ' + ascii(raw), candidates(raw, 1e308), None):
            absent = raw is None or (isinstance(raw, str) and raw == '')
            expected_price = None if absent and label.endswith('order 0') else 1e308
            for kind in ('liquidity', 'mcp-liquidity'):
                check(label + ' ' + kind + ' preserves missing-price selection or finite alternative',
                      result[kind].get('status') == 'ok' and result[kind].get('price_usd') == expected_price,
                      result[kind])
    for depth in (None, 0, '0', 'garbage', 'NaN', '1e-400'):
        for label, result in both_orders('one absent or zero depth ' + ascii(depth),
                                          candidates(1e-307, 1e308, low_depth=depth), None):
            check(label + ' genuine admitted depth remains', result['liquidity'].get('liquidity_usd') == 250000)
    for depth, status in ((None, 'unpriced'), (0, 'drained')):
        for label, result in both_orders('all absent or all genuine zero ' + ascii(depth),
                                          candidates(1e-307, 1e308, depth, depth), None):
            for kind in ('liquidity', 'mcp-liquidity'):
                check(label + ' ' + kind + ' preserves unavailable/observed-zero status',
                      result[kind].get('status') == status
                      and result[kind].get('liquidity_usd') == (None if depth is None else 0), result[kind])


def main():
    tests = sorted((name, function) for name, function in globals().items()
                   if name.startswith('test_') and callable(function))
    for name, function in tests:
        print('\n[' + name + ']')
        EXECUTED.append(name)
        try:
            function()
        except Exception as exc:
            check(name + ' test body completed', False, '%s: %s' % (type(exc).__name__, exc))
    declared = {node.name for node in ast.parse(Path(__file__).read_text(encoding='utf-8')).body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test_')}
    check('every finite-conflict test function ran exactly once', declared == set(EXECUTED)
          and len(EXECUTED) == len(declared))
    check('offline workflow registers the finite-conflict guard',
          'run: python tests/test_finite_price_conflict.py' in
          (shared.ROOT / '.github/workflows/test.yml').read_text(encoding='utf-8'))
    print('\n%d passed; %d failed; %d test functions executed' % (PASSED, len(FAILURES), len(EXECUTED)))
    return 1 if FAILURES else 0


if __name__ == '__main__':
    raise SystemExit(main())
