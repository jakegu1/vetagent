"""T-021 (c1): decimal Unicode strings retain zero/absence across real tools.

Run: python tests/test_unicode_market_underflow.py
"""
import ast
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_finite_market_measurements as shared

risk, mcp_server = shared.risk, shared.mcp_server
FAMILIES = (
    ('fullwidth', '\uff10\uff11\uff12\uff13\uff14\uff15\uff16\uff17\uff18\uff19'),
    ('arabic-indic', '\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669'),
    ('devanagari', '\u0966\u0967\u0968\u0969\u096a\u096b\u096c\u096d\u096e\u096f'),
)
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


def decimal(digits, value, exponent=True):
    if exponent:
        return value.translate(str.maketrans('0123456789', digits))
    mantissa, power = value.split('e')
    return mantissa.translate(str.maketrans('0123456789', digits)) + 'e' + power


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
    check(name + ' MCP text agrees with structured content', json.loads(text) == payload, response)
    schema = next(tool['outputSchema'] for tool in mcp_server.TOOLS if tool['name'] == name)
    check(name + ' actual MCP output matches declared schema',
          isinstance(payload, dict) and shared.accepts(schema, payload), payload)
    strict(name + ' MCP structured output', payload)
    return payload or {}


def complete(label, pairs, hp=None, address=shared.TOKEN, gt=None):
    results = {}
    with shared.offline(pairs, hp=hp, address=address, gt=gt):
        results['verbose'] = asyncio.run(risk.assess(address, 'ethereum', True))
        results['compact'] = asyncio.run(risk.assess(address, 'ethereum', False))
        results['liquidity'] = asyncio.run(risk.liquidity(address, 'ethereum'))
        for verbose in (True, False):
            kind = 'mcp-verbose' if verbose else 'mcp-compact'
            results[kind] = rpc('assess_token_risk', dict(address=address, chain_hint='ethereum', verbose=verbose))
        results['mcp-liquidity'] = rpc('get_token_liquidity', dict(address=address, chain_hint='ethereum'))
    for kind, result in results.items():
        strict(label + ' ' + kind, result)
    return results


def unavailable(label, results):
    for kind in ('verbose', 'compact', 'mcp-verbose', 'mcp-compact'):
        result = results[kind]
        evidence = result.get('evidence') or {}
        signals = result.get('signals', [])
        check(label + ' ' + kind + ' unavailable depth is unknown',
              result.get('risk_level') == 'unknown', result)
        check(label + ' ' + kind + ' has no false-empty or adequate claim',
              not evidence.get('pools_all_empty')
              and not shared.names(result) & {'No liquidity left in any pool', 'Liquidity is adequate'}
              and not any(s.get('category') == 'drained'
                          or (s.get('severity') == 'fatal' and s.get('category') == 'liquidity')
                          for s in signals), result)
        check(label + ' ' + kind + ' does not publish invented best depth',
              (evidence.get('best_pair') or {}).get('liquidity_usd') is None, evidence)
    for kind in ('liquidity', 'mcp-liquidity'):
        check(label + ' ' + kind + ' is unpriced with null depth',
              results[kind].get('status') == 'unpriced'
              and results[kind].get('liquidity_usd', 'missing') is None, results[kind])


def observed_zero(label, results, count=1):
    for kind in ('verbose', 'compact', 'mcp-verbose', 'mcp-compact'):
        result = results[kind]
        check(label + ' ' + kind + ' genuine zero remains high/all-empty',
              result.get('risk_level') == 'high'
              and (result.get('evidence') or {}).get('pools_all_empty') == count
              and 'No liquidity left in any pool' in shared.names(result), result)
    for kind in ('liquidity', 'mcp-liquidity'):
        check(label + ' ' + kind + ' genuine zero remains drained/zero',
              results[kind].get('status') == 'drained' and results[kind].get('liquidity_usd') == 0,
              results[kind])


def test_unicode_nonzero_underflow_is_unavailable_in_complete_tools():
    unavailable('ASCII underflow control', complete('ASCII underflow control', [shared.pair('1e-400')]))
    for family, digits in FAMILIES:
        for value, unicode_exponent in (('1e-400', False), ('1e-400', True),
                                        ('+1.5e-400', True), ('.1E-399', True), ('-1e-400', True)):
            raw = decimal(digits, value, unicode_exponent)
            label = family + ' nonzero underflow ' + ascii(raw)
            check(label + ' is accepted by float but becomes zero', float(raw) == 0, ascii(raw))
            check(label + ' is unavailable as a signed/nonnegative scalar',
                  risk._market_number(raw) is None and risk._market_number(raw, signed=True) is None,
                  risk._market_number(raw))
            unavailable(label, complete(label, [shared.pair(raw)]))


def test_unicode_genuine_zero_and_finite_values_remain_measurements():
    for family, digits in FAMILIES:
        for value in ('0e-400', '-0e-400', '+0.0e-400', '0.0e400'):
            raw = decimal(digits, value)
            label = family + ' genuine zero ' + ascii(raw)
            observed_zero(label, complete(label, [shared.pair(raw), shared.pair(raw, identity='bb')]), 2)
        for value in ('1e-6', '250000', '1.5'):
            raw = decimal(digits, value)
            label = family + ' finite depth ' + ascii(raw)
            result = complete(label, [shared.pair(raw)])
            for kind in ('liquidity', 'mcp-liquidity'):
                check(label + ' ' + kind + ' finite depth survives',
                      result[kind].get('status') == 'ok' and result[kind].get('liquidity_usd') == float(raw),
                      result[kind])
        tiny = decimal(digits, '1e-22')
        signed = decimal(digits, '-12.5')
        candidate = shared.pair(price=tiny)
        candidate['priceChange'] = {'h24': signed}
        result = complete(family + ' representable tiny price', [candidate])
        for kind in ('liquidity', 'mcp-liquidity'):
            check(family + ' ' + kind + ' tiny price has no new floor', result[kind].get('price_usd') == 1e-22,
                  result[kind])
        check(family + ' signed finite change keeps its value', risk._market_number(signed, signed=True) == -12.5)
        for kind in ('verbose', 'compact', 'mcp-verbose', 'mcp-compact'):
            check(family + ' ' + kind + ' signed finite change retains ordinary rounding',
                  (result[kind].get('evidence') or {}).get('price_change_24h_pct') == -12,
                  result[kind])


def test_unicode_required_anchor_operands_preserve_zero_absence():
    for family, digits in FAMILIES:
        raw = decimal(digits, '1e-400')
        fallback = shared.gt_pool(depth=raw)
        unavailable(family + ' fallback reserve underflow',
                    complete(family + ' fallback reserve underflow', [], gt=[fallback]))
        quote = shared.pair(amounts=True)
        quote['liquidity']['quote'] = raw
        unavailable(family + ' required quote reserve', complete(family + ' required quote reserve', [quote]))
        base = shared.pair(amounts=True)
        base['baseToken'] = {'address': shared.WETH, 'symbol': 'WETH'}
        base['quoteToken'] = {'address': shared.TOKEN, 'symbol': 'MKT'}
        base['liquidity']['base'] = raw
        unavailable(family + ' required base reserve',
                    complete(family + ' required base reserve', [base], address=shared.WETH))
        for key in ('priceUsd', 'priceNative'):
            candidate = shared.pair(amounts=True)
            candidate[key] = raw
            unavailable(family + ' required ' + key, complete(family + ' required ' + key, [candidate]))
        quote['liquidity']['quote'] = decimal(digits, '-0e-400')
        observed_zero(family + ' actual anchored zero', complete(family + ' actual anchored zero', [quote]))


def test_unicode_optional_fields_discovery_and_fatal_controls():
    flagged = shared.fixture('hp_matic.json')
    flagged['honeypotResult'] = {'isHoneypot': True}
    flagged['holderAnalysis'] = {'holders': '3689', 'successful': '3599', 'failed': '90',
                                 'siphoned': '0', 'averageTax': 0, 'highestTax': 0}
    flagged['summary'] = {'risk': 'honeypot', 'riskLevel': 100,
                          'flags': [{'flag': 'medium_fail_rate', 'severity': 'high',
                                     'description': 'A high amount of users cannot sell their tokens.',
                                     'severityIndex': 16}]}
    for family, digits in FAMILIES:
        raw = decimal(digits, '1e-400')
        candidate = shared.pair(volume=raw)
        candidate['priceChange'] = {'h24': decimal(digits, '-1e-400')}
        result = complete(family + ' optional volume underflow', [candidate])
        for kind in ('liquidity', 'mcp-liquidity'):
            check(family + ' ' + kind + ' unknown volume remains null',
                  result[kind].get('volume_24h_usd', 'missing') is None, result[kind])
        for kind in ('verbose', 'compact', 'mcp-verbose', 'mcp-compact'):
            check(family + ' ' + kind + ' signed change underflow remains null',
                  (result[kind].get('evidence') or {}).get('price_change_24h_pct', 'missing') is None,
                  result[kind])
            check(family + ' ' + kind + ' unavailable volume cannot claim market quiet',
                  not shared.names(result[kind]) & {'Looks abandoned', 'Very little trading'}, result[kind])
        unavailable(family + ' optional price underflow', complete(family + ' optional price underflow',
                    [shared.pair(price=raw)]))
        for value, expected in (('1e-400', None), ('-0e-400', 0), ('1e-22', 1e-22), ('12.5', 12.5)):
            reading = decimal(digits, value)
            entry = shared.gt_pool(depth=reading, price=reading, volume=reading)
            with shared.offline([], discovery=[entry]):
                direct = asyncio.run(risk.new_pools('ethereum', 1))
                mcp = rpc('find_new_hot_pools', {'chain': 'ethereum', 'limit': 1})
            for kind, answer in (('discovery', direct), ('MCP discovery', mcp)):
                strict(family + ' ' + kind + ' ' + ascii(reading), answer)
                pool = (answer.get('pools') or [{}])[0]
                for key in ('price_usd', 'liquidity_usd', 'volume_24h_usd'):
                    check(family + ' ' + kind + ' ' + key + ' preserves unavailable/zero/finite',
                          pool.get(key, 'missing') == expected, pool)
        fatal = complete(family + ' actual fatal HP control', [shared.pair(raw)], hp=flagged)
        for kind in ('verbose', 'compact', 'mcp-verbose', 'mcp-compact'):
            check(family + ' ' + kind + ' actual fatal HP remains high',
                  fatal[kind].get('risk_level') == 'high'
                  and fatal[kind].get('driver', {}).get('category') == 'honeypot', fatal[kind])


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
    check('every Unicode test function ran exactly once', declared == set(EXECUTED)
          and len(EXECUTED) == len(declared))
    check('offline workflow registers the Unicode guard',
          'run: python tests/test_unicode_market_underflow.py' in
          (shared.ROOT / '.github/workflows/test.yml').read_text(encoding='utf-8'))
    print('\n%d passed; %d failed; %d test functions executed' % (PASSED, len(FAILURES), len(EXECUTED)))
    return 1 if FAILURES else 0


if __name__ == '__main__':
    raise SystemExit(main())
