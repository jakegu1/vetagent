"""T-021: complete offline numeric-boundary acceptance and frozen characterizations.

Run: python tests/test_finite_market_measurements.py
"""
import ast
import asyncio
import copy
import json
import math
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import risk
import mcp_server

TOKEN = '0x1111111111111111111111111111111111111111'
USDC = '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48'
WETH = '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2'
INVALID = (None, '', ' ', 'garbage', True, False, {}, {'value': 5}, [], [5],
           -1, '-1', float('nan'), 'NaN', float('inf'), 'Infinity',
           float('-inf'), '-Infinity', '1e309', 10 ** 400)
PASSED = 0
FAILURES = []
EXECUTED = []


def check(name, condition, detail=''):
    global PASSED
    if condition:
        PASSED += 1
        print('  PASS ' + name)
    else:
        FAILURES.append((name, str(detail)))
        print('  FAIL %s: %s' % (name, detail))


def fixture(name):
    return json.loads((ROOT / 'tests/fixtures' / name).read_text(encoding='utf-8'))


def pair(depth=250000, price='1', volume=50000, sells=50, buys=100,
         chain='ethereum', identity='aa', amounts=False):
    got = {'chainId': chain, 'dexId': 'uniswap', 'pairAddress': '0x' + identity * 20,
           'baseToken': {'address': TOKEN, 'symbol': 'MKT'},
           'quoteToken': {'address': USDC, 'symbol': 'USDC'},
           'priceUsd': price, 'priceNative': '1', 'liquidity': {'usd': depth},
           'volume': {'h24': volume}, 'txns': {'h24': {'buys': buys, 'sells': sells}},
           'traders': {'h24': {'buyers': 30, 'sellers': 25}},
           'pairCreatedAt': 1589841515000}
    if amounts:
        got['liquidity'].update(base=125000, quote=125000)
    return got


def gt_pool(depth=250000, price='1', volume=50000, sells=50, buys=100):
    return {'id': 'eth_0x' + 'aa' * 20,
            'attributes': {'name': 'MKT / USDC', 'address': '0x' + 'aa' * 20,
                           'reserve_in_usd': depth, 'base_token_price_usd': price,
                           'base_token_price_quote_token': '1',
                           'quote_token_price_usd': '1', 'volume_usd': {'h24': volume},
                           'transactions': {'h24': {'sells': sells, 'buys': buys,
                                                    'sellers': 25, 'buyers': 30}},
                           'pool_created_at': '2020-05-19T00:00:00Z'},
            'relationships': {'base_token': {'data': {'id': 'eth_' + TOKEN}},
                              'quote_token': {'data': {'id': 'eth_' + USDC}}}}


@contextmanager
def offline(pairs, hp=None, address=TOKEN, gt=None, discovery=None, partial=False,
            seller_reading=25):
    """Every allowed request has an explicit local answer; an unmatched URL is red."""
    simulator = fixture('hp_matic.json') if hp is None else hp
    seen = []
    async def fetch(url, *args, **kwargs):
        seen.append(url)
        parsed = urlsplit(url)
        query = parse_qs(parsed.query)
        if parsed.netloc == 'api.dexscreener.com':
            if parsed.path == '/latest/dex/tokens/' + address and not query:
                return {'pairs': copy.deepcopy(pairs)}
            if parsed.path == '/latest/dex/search' and set(query) == {'q'}:
                allowed = {'MKT', 'USDC', 'WETH', 'WBNB', 'ETH'}
                allowed.update((p.get(side) or {}).get('symbol', '')
                               for p in pairs for side in ('baseToken', 'quoteToken'))
                if query['q'][0] in allowed:
                    return {'pairs': []}
            if parsed.path in ('/token-pairs/v1/ethereum/' + address,
                               '/token-pairs/v1/base/' + address,
                               '/token-pairs/v1/bsc/' + address) and not query:
                return []
        if parsed.netloc == 'api.honeypot.is' and parsed.path == '/v2/IsHoneypot':
            if query.get('address') == [address] and set(query) <= {'address', 'chainID', 'pair'}:
                return simulator
        if parsed.netloc == 'api.geckoterminal.com' and not query:
            for network in ('eth', 'base', 'bsc', 'polygon_pos'):
                prefix = '/api/v2/networks/' + network
                if parsed.path == prefix + '/tokens/' + address + '/pools':
                    return {'data': copy.deepcopy(gt or [])}
                if parsed.path == prefix + '/pools/' + '0x' + 'aa' * 20:
                    return {'data': {'attributes': {'transactions': {'h24': {
                        'sellers': seller_reading}}}}}
            if parsed.path == '/api/v2/networks/eth/new_pools':
                return {'data': copy.deepcopy(discovery or [])}
            if parsed.path == '/api/v2/networks/eth/trending_pools':
                return None if partial else {'data': []}
        raise AssertionError('Unmatched offline URL: ' + url)
    async def bytecode(rpc, asked):
        assert asked == address and rpc in risk._CHAIN_RPC.values()
        return '0x60006000', None
    with patch.object(risk, '_fetch_json', fetch), patch.object(risk, '_eth_get_code', bytecode):
        yield seen


def observe(name, call):
    try:
        return call()
    except Exception as exc:
        check(name + ' completes without raising', False, '%s: %s' % (type(exc).__name__, exc))
        return None


def strict(name, value):
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc:
        check(name + ' strict JSON', False, exc)
    else:
        check(name + ' strict JSON', value is not None, 'no returned object')


def tools(name, pairs, hp=None, address=TOKEN, hint='ethereum', gt=None, seller_reading=25):
    result = {}
    with offline(pairs, hp, address, gt, seller_reading=seller_reading):
        for label, call in (
                ('verbose', lambda: asyncio.run(risk.assess(address, hint, verbose=True))),
                ('compact', lambda: asyncio.run(risk.assess(address, hint, verbose=False))),
                ('liquidity', lambda: asyncio.run(risk.liquidity(address, hint)))):
            result[label] = observe(name + ' ' + label, call)
            strict(name + ' ' + label, result[label])
    return result


def names(answer):
    return {s['name'] for s in (answer or {}).get('signals', [])}


def no_depth_claim(name, result, verdict='unknown'):
    for label in ('verbose', 'compact'):
        answer = result[label] or {}
        evidence = answer.get('evidence') or {}
        check(name + ' ' + label + ' preserves expected verdict', answer.get('risk_level') == verdict,
              answer.get('risk_level'))
        check(name + ' ' + label + ' does not claim adequate or empty depth',
              not names(answer) & {'Liquidity is adequate', 'No liquidity left in any pool'}, names(answer))
        check(name + ' ' + label + ' has no fatal drained or empty count',
              not evidence.get('pools_all_empty') and not any(s['category'] == 'drained'
              or (s['severity'] == 'fatal' and s['category'] == 'liquidity')
              for s in answer.get('signals', [])), evidence)
        check(name + ' ' + label + ' has no invented best depth',
              (evidence.get('best_pair') or {}).get('liquidity_usd') is None, evidence.get('best_pair'))
    liq = result['liquidity'] or {}
    check(name + ' unpriced/null liquidity handoff',
          liq.get('status') == 'unpriced' and liq.get('liquidity_usd', 'missing') is None, liq)


def test_market_depth_rejects_invalid_scalars_without_inventing_zero():
    for index, raw in enumerate(INVALID):
        for leaf in ('usd', 'reserveInUsd', 'GT reserve'):
            name = '%s invalid[%d]=%r' % (leaf, index, raw)
            candidate = pair(raw)
            if leaf == 'reserveInUsd':
                candidate['liquidity'] = {}
                candidate['reserveInUsd'] = raw
            if leaf != 'GT reserve':
                depth = observe(name + ' credited depth', lambda: risk._reported_liquidity(candidate))
                stated = observe(name + ' stated depth', lambda: risk._stated_liquidity(candidate))
                check(name + ' credited and stated unavailable', depth is None and stated is None,
                      (depth, stated))
                result = tools(name, [candidate])
            else:
                result = tools(name, [], gt=[gt_pool(depth=raw)])
            no_depth_claim(name, result)
    # Exercise the measured complete fixture path, including side/chain selection.
    snapshot = fixture('ds_usdc.json')
    home = next(p for p in snapshot['pairs'] if p.get('chainId') == 'ethereum')
    for raw in ('NaN', 'Infinity'):
        candidate = copy.deepcopy(home)
        candidate['liquidity']['usd'] = raw
        result = tools('USDC fixture ' + raw, [candidate], address=USDC)
        no_depth_claim('USDC fixture ' + raw, result)


def test_credible_depth_floor_and_anchor_caps_preserve_existing_measurements():
    for raw, expected in ((0, 0), ('0', 0), ('-0', 0), ('0e-400', 0),
                          (1e-7, None), ('0.0000001', None), (1e-6, 1e-6),
                          ('0.000001', 1e-6), ('0.25', .25), (250000, 250000)):
        check('credited USD floor %r' % raw, risk._reported_liquidity(pair(raw)) == expected)
    for reserve, expected in ((0, 0), ('0', 0), ('-0', 0), (1e-8, None),
                              (5e-7, 1e-6), (12500, 25000)):
        candidate = pair(amounts=True)
        candidate['liquidity']['quote'] = reserve
        check('computed cap floor %r' % reserve, risk._reported_liquidity(candidate) == expected,
              risk._reported_liquidity(candidate))
    for index, raw in enumerate(INVALID):
        for operand in ('quote', 'priceUsd', 'priceNative', 'anchored base'):
            if operand in ('quote', 'anchored base') and raw in (None, ''):
                continue  # Named absent-reserve residual, separately pinned below.
            candidate = pair(amounts=True)
            if operand == 'anchored base':
                candidate['baseToken']['address'] = WETH
                candidate['quoteToken']['address'] = TOKEN
                candidate['liquidity']['base'] = raw
            elif operand == 'quote':
                candidate['liquidity']['quote'] = raw
            else:
                candidate[operand] = raw
            label = 'required cap %s invalid[%d]' % (operand, index)
            got = observe(label, lambda: risk._reported_liquidity(candidate))
            check(label + ' cannot retain finite reassuring depth or cap zero', got is None, got)
            if operand == 'anchored base':
                result = tools(label, [candidate], address=WETH)
            else:
                result = tools(label, [candidate])
            no_depth_claim(label, result)
    unused = pair(amounts=True)
    unused['liquidity']['base'] = 'NaN'
    check('invalid unused non-anchored reserve does not disqualify the cap',
          risk._reported_liquidity(unused) == 250000)
    absent = pair(amounts=True)
    del absent['liquidity']['quote']
    check('missing reserve amount keeps the named uncheckable residual',
          risk._independent_depth_cap(absent) is risk._NOT_CHECKABLE
          and risk._reported_liquidity(absent) == 250000)
    unknown = pair(amounts=True, chain='unlisted-l2')
    unknown['liquidity']['quote'] = 'NaN'
    check('unknown chain keeps the named uncheckable residual',
          risk._independent_depth_cap(unknown) is risk._NOT_CHECKABLE
          and risk._reported_liquidity(unknown) == 250000)
    both = pair(amounts=True)
    both['baseToken']['address'] = WETH
    check('two admitted anchors retain the deliberate unbounded internal marker',
          math.isinf(risk._independent_depth_cap(both))
          and risk._reported_liquidity(both) == 250000)
    both['liquidity']['usd'] = 'Infinity'
    check('two-anchor marker cannot admit an upstream infinite USD figure',
          risk._reported_liquidity(both) is None)
    overflow = pair(amounts=True, price='1e308')
    overflow['liquidity']['quote'] = '1e308'
    no_depth_claim('positive cap product overflow', tools('positive cap product overflow', [overflow]))
    quotient = pair(amounts=True, price='1e308')
    quotient['priceNative'] = '1e-308'
    no_depth_claim('positive cap quotient overflow', tools('positive cap quotient overflow', [quotient]))


def test_positive_underflow_is_unavailable_and_true_zero_stays_observed():
    raw_usd = pair('1e-400')
    product = pair(100000, price='1e-300', amounts=True)
    product['liquidity'].update(base=1, quote='1e-300')
    quotient = pair(100000, price='1e-300', amounts=True)
    quotient['liquidity'].update(base=1, quote='1e-20')
    quotient['priceNative'] = '1e300'
    for label, candidate in (('raw positive USD string underflow', raw_usd),
                              ('strictly positive cap product underflow', product),
                              ('strictly positive cap quotient underflow', quotient)):
        got = observe(label, lambda: risk._reported_liquidity(candidate))
        check(label + ' credited depth is unavailable rather than zero', got is None, got)
        no_depth_claim(label, tools(label, [candidate]))
        result = tools(label + ' finite sells plus NO_DATA', [candidate], hp=risk.NO_DATA)
        no_depth_claim(label + ' finite sells plus NO_DATA', result)
        check(label + ' reuses the T-012 reason', any(g.get('reason') == risk._TRADED_DEPTH_REASON
              for g in (result['verbose'] or {}).get('evidence', {}).get('data_gaps', [])))
    for raw in (0, '0', '-0', '0e-400'):
        candidate = pair(100000, amounts=True)
        candidate['liquidity']['quote'] = raw
        result = tools('genuine anchored zero %r' % raw, [candidate])
        check('genuine anchored zero %r remains drained/high' % raw,
              (result['liquidity'] or {}).get('status') == 'drained'
              and (result['liquidity'] or {}).get('liquidity_usd') == 0
              and (result['verbose'] or {}).get('risk_level') == 'high'
              and 'No liquidity left in any pool' in names(result['verbose']))


def test_invalid_best_pair_cannot_outvote_a_valid_alternative():
    valid = pair(80000, identity='bb')
    for raw in INVALID:
        invalid = pair(raw, identity='aa')
        off_chain = pair(100000000, chain='pulsechain', identity='cc')
        for index, order in enumerate(([invalid, valid, off_chain], [valid, invalid, off_chain])):
            result = tools('valid alternative %r order %d' % (raw, index), order)
            best = ((result['verbose'] or {}).get('evidence') or {}).get('best_pair') or {}
            check('valid alternative %r order %d wins on the unchanged home chain' % (raw, index),
                  best.get('pair_address') == valid['pairAddress']
                  and best.get('liquidity_usd') == 80000 and best.get('chain') == 'ethereum', best)
    for raw in INVALID:
        if raw in (None, ''):
            continue  # Missing price legitimately qualifies, pinned as a characterization.
        bad = pair(9000000, price=raw)
        for index, order in enumerate(([bad, valid], [valid, bad])):
            result = tools('invalid primary price %r order %d' % (raw, index), order)
            check('invalid primary price %r order %d cannot qualify a candidate' % (raw, index),
                  ((result['verbose'] or {}).get('evidence', {}).get('best_pair') or {})
                  .get('pair_address') == valid['pairAddress'])


def test_complete_assessment_preserves_t012_traded_and_absence_controls():
    for raw in ('NaN', 'Infinity', None, '1e-400'):
        traded = pair(raw, sells='0.5', buys=90000)
        result = tools('finite weak sells invalid depth %r' % raw, [traded], hp=risk.NO_DATA)
        no_depth_claim('finite weak sells invalid depth %r' % raw, result)
        answer = result['verbose'] or {}
        check('weak positive sells %r retain T-012 integrated reason/exclusion' % raw,
              any(g.get('reason') == risk._TRADED_DEPTH_REASON
                  for g in answer.get('evidence', {}).get('data_gaps', []))
              and 'Nothing about this token can be verified' not in names(answer))
    variants = [('no pair', []), ('untraded', [pair(None, sells=0, buys=0)]),
                ('buys only', [pair(None, sells=0, buys=900)]),
                ('off-chain only sells', [pair(None, sells=0),
                                        pair(None, chain='pulsechain', sells=900)])]
    variants += [('invalid sells %r' % raw, [pair(None, sells=raw)]) for raw in INVALID]
    for label, scope in variants:
        result = tools(label, scope, hp=risk.NO_DATA)
        check(label + ' keeps high no-trace escalation',
              (result['verbose'] or {}).get('risk_level') == 'high'
              and 'Nothing about this token can be verified' in names(result['verbose']))
    flagged = fixture('hp_matic.json')
    flagged['honeypotResult'] = {'isHoneypot': True}
    flagged['holderAnalysis'] = {'holders': '3689', 'successful': '3599', 'failed': '90',
                                 'siphoned': '0', 'averageTax': 0, 'highestTax': 0}
    flagged['summary'] = {'risk': 'honeypot', 'riskLevel': 100,
                          'flags': [{'flag': 'medium_fail_rate', 'severity': 'high',
                                     'description': 'A high amount of users cannot sell their tokens.',
                                     'severityIndex': 16}]}
    result = tools('real fatal holder flag beside invalid depth', [pair('NaN')], hp=flagged)
    check('real fatal HP finding remains high without depth',
          (result['verbose'] or {}).get('risk_level') == 'high'
          and (result['verbose'] or {}).get('driver', {}).get('category') == 'honeypot')


def test_mixed_zero_and_unavailable_depth_is_not_all_empty():
    for raw in (None, 'NaN', 'Infinity', 'garbage', 1e-9, '1e-400'):
        scope = [pair(0), pair(raw, identity='bb')]
        result = tools('mixed zero/unavailable %r clean' % raw, scope)
        no_depth_claim('mixed zero/unavailable %r clean' % raw, result)
        gaps = (result['verbose'] or {}).get('evidence', {}).get('data_gaps', [])
        reason = next((g['reason'] for g in gaps if g['dimension'] == 'liquidity'), '')
        check('mixed %r uses qualified existing about-token no-depth wording' % raw,
              reason.startswith(risk._ABOUT_TOKEN + ': ')
              and 'no source reported pool depth' in reason and 'some' in reason
              and reason != risk._TRADED_DEPTH_REASON, reason)
        result = tools('mixed zero/unavailable %r NO_DATA' % raw, scope, hp=risk.NO_DATA)
        no_depth_claim('mixed zero/unavailable %r NO_DATA' % raw, result, verdict='high')
        check('mixed %r preserves finalizer escalation without drained finding' % raw,
              'Nothing about this token can be verified' in names(result['verbose']))
    for raw in (0, '0', '-0'):
        result = tools('all genuine zero %r' % raw, [pair(raw), pair(raw, identity='bb')])
        check('all genuine zero %r stays drained/high with two observations' % raw,
              (result['verbose'] or {}).get('risk_level') == 'high'
              and (result['verbose'] or {}).get('evidence', {}).get('pools_all_empty') == 2
              and (result['liquidity'] or {}).get('status') == 'drained')


def test_optional_market_prices_and_volumes_preserve_unavailable_values():
    for raw in INVALID:
        base = pair(volume=raw)
        result = tools('unavailable volume %r' % raw, [base])
        best = (result['verbose'] or {}).get('evidence', {}).get('best_pair') or {}
        check('unavailable volume %r is null in both tools' % raw,
              best.get('volume_24h_usd', 'missing') is None
              and (result['liquidity'] or {}).get('volume_24h_usd', 'missing') is None, best)
        quote = pair()
        quote['baseToken']['address'], quote['quoteToken']['address'] = WETH, TOKEN
        quote['priceNative'] = raw
        result = tools('underivable quote price %r' % raw, [quote])
        check('underivable quote price %r is null in both tools' % raw,
              ((result['verbose'] or {}).get('evidence', {}).get('best_pair') or {})
              .get('price_usd', 'missing') is None
              and (result['liquidity'] or {}).get('price_usd', 'missing') is None)
    for raw in (0, '0', '-0', 12345.6789, '12345.6789'):
        result = tools('finite volume %r' % raw, [pair(volume=raw)])
        check('finite volume %r keeps ordinary rounding and observed zero' % raw,
              (result['liquidity'] or {}).get('volume_24h_usd') == risk._sig_round(raw))
    for price in ('1e-22', '5e-24', '1e-300', 1e-300):
        result = tools('legitimate tiny price %r' % price, [pair(price=price)])
        check('tiny price %r has no USD-depth floor' % price,
              (result['liquidity'] or {}).get('price_usd') == risk._sig_round(price)
              and (result['liquidity'] or {}).get('status') == 'ok')
    for native in ('1e-308', '1e308'):
        quote = pair(price='1e308' if native == '1e-308' else '1e-300')
        quote['baseToken']['address'], quote['quoteToken']['address'] = WETH, TOKEN
        quote['priceNative'] = native
        result = tools('target inversion overflow/underflow ' + native, [quote])
        check('target inversion arithmetic ' + native + ' cannot manufacture a price',
              (result['liquidity'] or {}).get('price_usd', 'missing') is None)
    for bq, qu in (('1e308', '1e308'), ('1e-300', '1e-300'), ('NaN', '1'), ('1', 'Infinity')):
        pool = gt_pool(price=None)
        pool['attributes'].update(base_token_price_quote_token=bq, quote_token_price_usd=qu)
        derived = observe('GT derived arithmetic', lambda: risk._gt_base_price(pool['attributes']))
        check('GT multiplication %r x %r is unavailable' % (bq, qu), derived is None, derived)
        result = tools('GT derived %r x %r' % (bq, qu), [], gt=[pool])
        check('GT computed invalid price stays null publicly',
              (result['liquidity'] or {}).get('price_usd', 'missing') is None)
    pool = gt_pool(price=None)
    pool['attributes'].update(base_token_price_quote_token='2', quote_token_price_usd='3')
    result = tools('GT ordinary multiplication', [], gt=[pool])
    check('GT normal derived price remains six dollars',
          (result['liquidity'] or {}).get('price_usd') == 6)


def test_incomplete_volume_cannot_describe_the_whole_market_as_quiet():
    for raw in INVALID:
        deep = pair(1000000, volume=1000)
        other = pair(200000, volume=raw, identity='bb')
        result = tools('whole-market volume gap %r' % raw, [deep, other])
        evidence = (result['verbose'] or {}).get('evidence') or {}
        check('unknown venue volume %r does not become observed quiet market' % raw,
              evidence.get('turnover_24h', 'missing') is None
              and not names(result['verbose']) & {'Looks abandoned', 'Very little trading'}, evidence)
        check('known best-pool turnover %r remains separate' % raw,
              evidence.get('turnover_24h_best_pool') == .001)
        result = tools('best-volume gap %r' % raw, [pair(1000000, volume=raw)])
        evidence = (result['verbose'] or {}).get('evidence') or {}
        check('unknown best-volume %r makes both turnovers unavailable' % raw,
              evidence.get('turnover_24h', 'missing') is None
              and evidence.get('turnover_24h_best_pool', 'missing') is None)
    result = tools('ordinary whole-market turnover',
                   [pair(1000000, volume=1000), pair(200000, volume=100000, identity='bb'),
                    pair(9999999, volume=0, chain='pulsechain', identity='cc')])
    check('finite venues retain scope, aggregation, rounding and thresholds',
          (result['verbose'] or {}).get('evidence', {}).get('turnover_24h')
          == risk._sig_round(101000 / 1200000, 4)
          and not names(result['verbose']) & {'Looks abandoned', 'Very little trading'})
    result = tools('all valid zero volume', [pair(volume=0), pair(80000, volume='0', identity='bb')])
    check('whole-market observed zero still supports existing quiet signal',
          (result['verbose'] or {}).get('evidence', {}).get('turnover_24h') == 0
          and 'Looks abandoned' in names(result['verbose']))
    for dimension in ('volume', 'depth'):
        candidates = [pair(1e308, volume=1e308, identity='aa'),
                      pair(1e308, volume=1e308, identity='bb')]
        if dimension == 'volume':
            for p in candidates:
                p['liquidity']['usd'] = 250000
        else:
            for p in candidates:
                p['volume']['h24'] = 1
        result = tools(dimension + ' aggregate overflow', candidates)
        check(dimension + ' non-finite aggregate cannot manufacture turnover',
              (result['verbose'] or {}).get('evidence', {}).get('turnover_24h', 'missing') is None)


def test_market_counts_and_signed_change_are_finite_without_global_num_drift():
    for raw in INVALID:
        for leaf in ('sells', 'buys', 'sellers'):
            candidate = pair()
            if leaf == 'sellers':
                candidate['traders']['h24']['sellers'] = raw
            else:
                candidate['txns']['h24'][leaf] = raw
            result = tools('DS invalid %s %r' % (leaf, raw), [candidate], hp=risk.NO_DATA)
            bp = (result['verbose'] or {}).get('evidence', {}).get('best_pair') or {}
            check('DS invalid %s %r is an optional null' % (leaf, raw),
                  bp.get(leaf + '_24h', 'missing') is None, bp)
            if leaf != 'sellers':
                check('DS invalid %s %r cannot support demonstrated exits' % (leaf, raw),
                      not (result['verbose'] or {}).get('evidence', {}).get('sellability_from_chain'))
            gt = gt_pool()
            gt['attributes']['transactions']['h24'][leaf] = raw
            result = tools('GT invalid %s %r' % (leaf, raw), [], gt=[gt], hp=risk.NO_DATA)
            bp = (result['verbose'] or {}).get('evidence', {}).get('best_pair') or {}
            check('GT invalid %s %r is null before numeric provenance is lost' % (leaf, raw),
                  bp.get(leaf + '_24h', 'missing') is None, bp)
        evidence = {'best_pair': {'liquidity_usd': 250000, 'sells_24h': raw, 'buys_24h': 100}}
        demonstrated = observe('raw invalid sells predicate', lambda: risk._sells_demonstrated(evidence))
        check('raw invalid sells %r cannot demonstrate an exit' % raw,
              demonstrated is not None and demonstrated[0] is False, demonstrated)
    flagged = fixture('hp_matic.json')
    flagged['honeypotResult'] = {'isHoneypot': True}
    for leaf in ('sells', 'buys', 'sellers'):
        for raw in ('Infinity', float('nan'), True, -1, 10 ** 400):
            candidate = pair()
            if leaf == 'sellers':
                candidate['traders']['h24']['sellers'] = raw
            else:
                candidate['txns']['h24'][leaf] = raw
            result = tools('invalid market count cannot adjudicate simulator %s %r' % (leaf, raw),
                           [candidate], hp=flagged, seller_reading=raw)
            evidence = (result['verbose'] or {}).get('evidence') or {}
            check('invalid %s %r cannot overrule the simulator' % (leaf, raw),
                  not evidence.get('honeypot', {}).get('contradicted_by_chain'), evidence.get('honeypot'))
    for raw in INVALID:
        if isinstance(raw, (int, float, str)) and not isinstance(raw, bool):
            try:
                if math.isfinite(float(raw)) and float(raw) < 0:
                    continue  # Signed finite changes are valid, unlike nonnegative leaves.
            except (TypeError, ValueError, OverflowError):
                pass
        candidate = pair()
        candidate['priceChange'] = {'h24': raw}
        result = tools('invalid signed change %r' % raw, [candidate])
        check('invalid optional signed change %r is null or absent' % raw,
              (result['verbose'] or {}).get('evidence', {}).get('price_change_24h_pct') is None)
    for raw in (-51.25, '-51.25', 0, '0', '-0', '12.5'):
        candidate = pair()
        candidate['priceChange'] = {'h24': raw}
        result = tools('valid signed change %r' % raw, [candidate])
        check('signed finite change %r retains rounding' % raw,
              (result['verbose'] or {}).get('evidence', {}).get('price_change_24h_pct')
              == risk._sig_round(raw, 2))
    valid = {'best_pair': {'liquidity_usd': 5000, 'sells_24h': '20', 'buys_24h': '100'}}
    check('strong exit thresholds remain 5000/20/15 percent', risk._sells_demonstrated(valid) == (True, 20, 100))
    valid['best_pair']['sells_24h'] = '0.5'
    check('T-012 finite positive sells remain weaker than demonstrated-exit thresholds',
          risk._sells_demonstrated(valid)[0] is False)


def accepts(schema, value):
    types = schema.get('type', [])
    types = [types] if isinstance(types, str) else types
    kind = ('null' if value is None else 'boolean' if isinstance(value, bool)
            else 'number' if isinstance(value, (int, float)) else 'string' if isinstance(value, str)
            else 'object' if isinstance(value, dict) else 'array' if isinstance(value, list) else '')
    if types and kind not in types and not (kind == 'number' and 'integer' in types and type(value) is int):
        return False
    if 'enum' in schema and value not in schema['enum']:
        return False
    if isinstance(value, dict):
        if any(key not in value for key in schema.get('required', [])):
            return False
        return all(accepts(rule, value[key]) for key, rule in schema.get('properties', {}).items() if key in value)
    return True


def test_discovery_and_mcp_schema_accept_optional_nulls_and_strict_json():
    schema = next(t['outputSchema'] for t in mcp_server.TOOLS if t['name'] == 'get_token_liquidity')
    for raw in INVALID + (0, '0', '-0', 12.3456789, '12.3456789', '1e-22'):
        entry = gt_pool(depth=raw, price=raw, volume=raw)
        with offline([], discovery=[entry], partial=True):
            answer = observe('complete discovery %r' % raw,
                             lambda: asyncio.run(risk.new_pools('ethereum', 3)))
        strict('complete discovery %r' % raw, answer)
        pool = ((answer or {}).get('pools') or [{}])[0]
        expected = None if any(raw is invalid for invalid in INVALID) else risk._sig_round(raw)
        for key in ('price_usd', 'liquidity_usd', 'volume_24h_usd'):
            check('discovery %r %s preserves unavailable/finite zero/value' % (raw, key),
                  pool.get(key, 'missing') == expected, pool.get(key))
        check('discovery %r keeps handoff and partial scan shape' % raw,
              pool.get('token_address') == TOKEN and (answer or {}).get('count') == 1
              and (answer or {}).get('scanned') == 1 and (answer or {}).get('sources_ok') == ['new']
              and (answer or {}).get('sources_failed') == ['trending'])
    null_pair = pair(price=None, volume=None)
    results = [tools('MCP actual optional null price/volume', [null_pair])['liquidity'],
               tools('MCP actual null depth', [pair(None)])['liquidity'],
               tools('MCP actual normal numbers', [pair()])['liquidity']]
    for index, answer in enumerate(results):
        check('declared MCP schema accepts actual liquidity response %d' % index,
              answer is not None and accepts(schema, answer), answer)
    check('MCP nullable leaves and required-field contract',
          all(set(schema['properties'][key]['type']) == {'number', 'null'}
              for key in ('price_usd', 'volume_24h_usd', 'liquidity_usd'))
          and schema['required'] == ['address', 'status'])


def test_nonmarket_helpers_ordinary_rounding_and_missing_price_selection_stay_unchanged():
    check('global _num still has its default missing/boolean/non-finite behavior',
          risk._num(None) == 0 and risk._num(True) == 1 and math.isnan(risk._num('NaN')))
    check('default _sig_round still converts None to zero for non-market consumers',
          risk._sig_round(None) == 0 and risk._sig_round('12345.6789') == 12345.7
          and risk._sig_round('-51.25', 2) == -51)
    missing = pair(price=None)
    result = tools('legitimate missing-price selection', [missing])
    check('a genuinely missing price still permits valid-depth selection',
          (result['liquidity'] or {}).get('status') == 'ok'
          and (result['liquidity'] or {}).get('liquidity_usd') == 250000
          and (result['liquidity'] or {}).get('price_usd', 'missing') is None)
    snapshot = fixture('ds_weth.json')
    result = tools('ordinary recorded WETH output', snapshot['pairs'], address=WETH)
    check('ordinary recorded WETH assessment remains low',
          (result['verbose'] or {}).get('risk_level') == 'low', result['verbose'])
    expected = risk._pick_best(snapshot['pairs'], 'ethereum', WETH)
    check('ordinary recorded output preserves rounding',
          (result['liquidity'] or {}).get('price_usd') == risk._sig_round(risk._price_of_target(expected, WETH))
          and (result['liquidity'] or {}).get('liquidity_usd') == risk._sig_round(risk._reported_liquidity(expected)))
    best = (result['verbose'] or {}).get('evidence', {}).get('best_pair') or {}
    check('existing verbose best_pair optional-key shape stays intact', set(best) == {
        'dex', 'chain', 'liquidity_usd', 'price_usd', 'pair_address', 'sellers_24h',
        'volume_24h_usd', 'pair_created_at', 'buys_24h', 'sells_24h'})


def main():
    tests = sorted((name, function) for name, function in globals().items()
                   if name.startswith('test_') and callable(function))
    for name, function in tests:
        print('\n[' + name + ']')
        EXECUTED.append(name)
        try:
            function()
        except Exception as exc:
            check(name + ' runner completed its test body', False, '%s: %s' % (type(exc).__name__, exc))
    declared = {n.name for n in ast.parse(Path(__file__).read_text(encoding='utf-8')).body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith('test_')}
    check('every declared test function ran exactly once', declared == set(EXECUTED) and len(EXECUTED) == len(declared))
    workflow = (ROOT / '.github/workflows/test.yml').read_text(encoding='utf-8')
    check('offline workflow registers this acceptance runner',
          'run: python tests/test_finite_market_measurements.py' in workflow)
    print('\n%d passed; %d failed; %d test functions executed' % (PASSED, len(FAILURES), len(EXECUTED)))
    return 1 if FAILURES else 0


if __name__ == '__main__':
    raise SystemExit(main())
