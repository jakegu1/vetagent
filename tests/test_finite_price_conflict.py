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


def _t068_pool(chain, price, native='1', quote=False, depth=250000, identity='aa'):
    pair = shared.pair(depth, price=price, chain=chain, identity=identity)
    pair['priceNative'] = native
    if quote:
        pair['baseToken'] = {'address': shared.WETH, 'symbol': 'WETH'}
        pair['quoteToken'] = {'address': shared.TOKEN, 'symbol': 'MKT'}
    return pair


def _t068_orders(label, pairs, expected, hint=None, selected_price=1.0, score=0,
                 verdict='unknown', selected_depth=300000):
    for index, order in enumerate((pairs, list(reversed(pairs)))):
        name = label + ' order ' + str(index)
        result = complete(name, order, hint)
        for kind in ('verbose', 'compact', 'mcp-verbose', 'mcp-compact'):
            answer = result[kind]
            evidence = answer.get('evidence') or {}
            observed = evidence.get('price_disagreement')
            signals = [s for s in answer.get('signals', [])
                       if s.get('category') == 'price_disagreement']
            gaps = [g for g in evidence.get('data_gaps', []) if g.get('dimension') == 'price']
            detail = {'observed': observed, 'signals': len(signals), 'gaps': len(gaps),
                      'score': answer.get('risk_score'), 'verdict': answer.get('risk_level')}
            if expected is None:
                check(name + ' ' + kind + ' has no invented target-price conflict',
                      observed is None and not signals and not gaps, detail)
            else:
                low, high = expected
                check(name + ' ' + kind + ' publishes truthful finite target conflict endpoints',
                      observed == {'low_usd': low, 'high_usd': high}
                      and all(math.isfinite(v) for v in (observed or {}).values()), detail)
                check(name + ' ' + kind + ' keeps the existing warning and about-token gap',
                      len(signals) == 1 and signals[0].get('severity') == 'warn'
                      and signals[0].get('name') == 'Pools disagree about the price'
                      and len(gaps) == 1
                      and gaps[0].get('reason', '').startswith(risk._ABOUT_TOKEN + ': ')
                      and 'pools on unranked chains disagree on the price' in gaps[0]['reason'], detail)
            check(name + ' ' + kind + ' keeps the existing score and coverage verdict',
                  answer.get('risk_score') == score and answer.get('risk_level') == verdict, detail)
            best = evidence.get('best_pair') or {}
            check(name + ' ' + kind + ' reports the selected target price and depth',
                  best.get('price_usd') == selected_price and best.get('liquidity_usd') == selected_depth,
                  {'price': best.get('price_usd'), 'depth': best.get('liquidity_usd')})
        for kind in ('liquidity', 'mcp-liquidity'):
            answer = result[kind]
            check(name + ' ' + kind + ' keeps actual selected target price and positive depth',
                  answer.get('status') == 'ok' and answer.get('price_usd') == selected_price
                  and answer.get('liquidity_usd') == selected_depth,
                  {k: answer.get(k) for k in ('status', 'price_usd', 'liquidity_usd')})
        yield name, result


def test_target_prices_define_quote_and_mixed_orientation_conflicts_in_complete_tools():
    cases = (
        ('mixed equal target prices', False, '1', '1', True, '2000', '2000', None, 0),
        ('quote equal target prices', True, '2', '2', True, '2000', '2000', None, 0),
        ('mixed different target prices', False, '1', '1', True, '1', '0.001', (1.0, 1000.0), 15),
        ('quote different target prices', True, '1', '1', True, '1', '0.001', (1.0, 1000.0), 15),
        ('base different target control', False, '1', '1', False, '1000', '1', (1.0, 1000.0), 15),
    )
    for label, first_quote, first_price, first_native, second_quote, second_price, second_native, expected, score in cases:
        pairs = [_t068_pool('unlisted-a', first_price, first_native, first_quote, 300000),
                 _t068_pool('unlisted-b', second_price, second_native, second_quote, identity='bb')]
        for name, result in _t068_orders(label, pairs, expected, score=score):
            check(name + ' request target remains the original token',
                  all(result[kind].get('address') == shared.TOKEN for kind in result))


def test_underivable_quote_conversion_cannot_vote_in_actual_price_conflict():
    invalid = [(raw, '2000') for raw in shared.INVALID + (0, '0', '-0', '1e-400', '-1e-400')]
    invalid += [('1e-308', '1e308'), ('1e308', '1e-300')]
    for native, price in invalid:
        label = 'unusable quote conversion ' + ascii(native) + ' base ' + ascii(price)
        pairs = [_t068_pool('unlisted-a', '1', depth=300000),
                 _t068_pool('unlisted-b', price, native, True, identity='bb')]
        check(label + ' target conversion is genuinely unavailable',
              risk._price_of_target(pairs[1], shared.TOKEN) is None)
        for name, result in _t068_orders(label, pairs, None):
            check(name + ' unavailable peer does not alter the home-chain uncertainty',
                  result['verbose'].get('risk_level') == 'unknown')


def test_oriented_target_conflict_keeps_scope_depth_quorum_and_strict_boundary():
    for high, expected, score in ((100, None, 0), (101, (1.0, 101.0), 15)):
        pairs = [_t068_pool('unlisted-a', '1', depth=300000),
                 _t068_pool('unlisted-b', str(high * 2), '2', True, identity='bb')]
        for name, result in _t068_orders('target strict boundary ' + str(high), pairs, expected, score=score):
            check(name + ' two target prices remain on unranked chains',
                  set(result['liquidity'].get('chains', [])) == {'unlisted-a', 'unlisted-b'})
    for label, first_chain, second_chain, hint, verdict in (
            ('ranked control', 'ethereum', 'unlisted-b', None, 'low'),
            ('single unranked chain control', 'unlisted-a', 'unlisted-a', None, 'unknown'),
            ('explicit unranked chain scope', 'unlisted-a', 'unlisted-b', 'unlisted-a', 'unknown')):
        pairs = [_t068_pool(first_chain, '1', depth=300000),
                 _t068_pool(second_chain, '1', '0.001', True, identity='bb')]
        for name, result in _t068_orders(label, pairs, None, hint=hint, verdict=verdict):
            check(name + ' selected chain remains unchanged',
                  result['liquidity'].get('best_pair_chain') == first_chain)
    for depth in (None, 0, '0', 'garbage', 'NaN', '1e-400'):
        pairs = [_t068_pool('unlisted-a', '1', depth=300000),
                 _t068_pool('unlisted-b', '1', '0.001', True, depth, 'bb')]
        for name, result in _t068_orders('unavailable or zero peer depth ' + ascii(depth), pairs, None):
            check(name + ' nonvoting peer cannot displace observed depth',
                  result['liquidity'].get('liquidity_usd') == 300000)


def test_unranked_helper_without_a_target_retains_legacy_base_price_behavior():
    pairs = [_t068_pool('unlisted-a', '1', depth=300000),
             _t068_pool('unlisted-b', '2000', '2000', True, identity='bb')]
    for index, order in enumerate((pairs, list(reversed(pairs)))):
        check('no-target helper legacy base prices order ' + str(index),
              risk._unranked_price_conflict(order) == (1.0, 2000.0))


def _t068_consensus(label, prices, expected_kept, expected_selected):
    identities = ('aa', 'bb', 'cc', 'dd', 'ee')
    pairs = [_t068_pool('ethereum', price, depth=1000000 if index == 0 else 250001 - index,
                       identity=identities[index]) for index, price in enumerate(prices)]
    for index, order in enumerate((pairs, list(reversed(pairs)))):
        name = label + ' order ' + str(index)
        kept = risk._drop_price_outliers(order, shared.TOKEN)
        observed = [i for i, pair in enumerate(pairs) if any(pair is p for p in kept)]
        check(name + ' keeps exactly the expected original candidates',
              observed == list(expected_kept), observed)
        picked = risk._pick_best(order, 'ethereum', shared.TOKEN)
        check(name + ' depth selects the expected surviving candidate',
              picked is pairs[expected_selected], risk._price_of_target(picked, shared.TOKEN))
    return pairs


def test_finite_even_consensus_survives_midpoint_overflow_in_complete_tools():
    pairs = _t068_consensus('four finite consensus prices', ['1', '1e308', '1e308', '1e308'],
                           (1, 2, 3), 1)
    # A peer can quote the request token too; the converted target prices are identical.
    pairs[2]['baseToken'] = {'address': shared.WETH, 'symbol': 'WETH'}
    pairs[2]['quoteToken'] = {'address': shared.TOKEN, 'symbol': 'MKT'}
    pairs[2]['priceUsd'], pairs[2]['priceNative'] = '1', '1e-308'
    # Distinct peer depth avoids an unrelated tied-winner ordering assertion.
    pairs[1]['liquidity']['usd'] = 300000
    for name, result in _t068_orders('finite even target consensus', pairs, None, hint='ethereum',
                                      selected_price=1e308, verdict='low'):
        check(name + ' selected chain remains Ethereum',
              result['liquidity'].get('best_pair_chain') == 'ethereum')


def test_consensus_fallback_preserves_largest_finite_neighbors_and_odd_samples():
    largest = sys.float_info.max
    previous = math.nextafter(largest, 0.0)
    check('largest finite neighbors are distinct finite positive prices',
          0 < previous < largest and math.isfinite(largest))
    _t068_consensus('largest finite midpoint', [1.0, previous, largest, largest], (1, 2, 3), 1)
    _t068_consensus('odd finite midpoint control', [1.0, 1e308, 1e308], (1, 2), 1)
    _t068_consensus('duplicate ordinary control', [1.0, 2.0, 2.0, 200.0], (0, 1, 2, 3), 0)
    _t068_consensus('two prices do not form a quorum', [1.0, 1e308], (0, 1), 0)
    pairs = _t068_consensus('unpriced candidate remains eligible', [None, 1.0, 1e308, 1e308, 1e308],
                           (0, 2, 3, 4), 0)
    for name, result in _t068_orders('unpriced consensus survivor', pairs, None, hint='ethereum',
                                      selected_price=None, verdict='low', selected_depth=1000000):
        check(name + ' missing optional price does not invent a number',
              result['liquidity'].get('price_usd', 'missing') is None)


def test_finite_median_ordinary_rounding_subnormals_and_100x_edges_stay_exact():
    # A global rewrite to a + (b-a)/2 moves this ordinary median down one ULP.
    # The existing exactly-100x candidate would become 100.00000000000001x and disappear.
    a, b = 0.8100068323241498, 8.931232234496916
    candidate = 487.0619533410533
    import statistics
    ordinary = statistics.median([0.1, a, b, candidate])
    check('ordinary witness pins the existing median and exact strict edge',
          ordinary == 4.870619533410533 and candidate / ordinary == 100.0
          and candidate / (a + (b - a) / 2) > 100.0)
    _t068_consensus('ordinary median exact 100x edge', [candidate, 0.1, a, b], (0, 1, 2, 3), 0)
    tiny = float.fromhex('0x0.0000000000001p-1022')
    check('subnormal witness pins ordinary median rounding',
          statistics.median([tiny, tiny, 2 * tiny, 200 * tiny]) == 2 * tiny)
    _t068_consensus('subnormal ordinary midpoint control', [200 * tiny, tiny, tiny, 2 * tiny],
                    (0, 1, 2, 3), 0)
    for price, expected, selected in ((100, (0, 1, 2), 0), (101, (1, 2), 1)):
        _t068_consensus('strict deviation ' + str(price), [price, 1, 1], expected, selected)


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
