// Replay the Worker-served script with responses from the actual MCP dispatcher.
const assert = require('node:assert/strict');
const vm = require('node:vm');
const {html, replies, precision_replies: precisionReplies, limited_reply: limitedReply,
  curve_replies: curveReplies, balancer_replies: balancerReplies,
  balancer_unpriced_replies: balancerUnpricedReplies} =
  JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const script = html.slice(html.lastIndexOf('<script>') + 8, html.lastIndexOf('</script>'));
const tick = () => new Promise(resolve => setImmediate(resolve));
const plain = value => JSON.parse(JSON.stringify(value));
const key = 'vetagent.liquidity.v1';
const balanceOption = 'include-known-address-balances';

function boot(saved = new Map(), broken = false) {
  const nodes = {}, requests = [];
  for (const match of html.matchAll(/<(?:input|button|div|select)\b([^>]*)>/g)) {
    const attrs = Object.fromEntries([...match[1].matchAll(/([\w-]+)="([^"]*)"/g)].map(m => [m[1], m[2]]));
    if (!attrs.id) continue;
    const events = {};
    nodes[attrs.id] = {value: attrs.value || '', checked: 'checked' in attrs, disabled: false, innerHTML: '', textContent: '',
      classList: {add() {}}, addEventListener(name, fn) { events[name] = fn; },
      fire(name, event = {}) { if (events[name]) events[name](event); }};
  }
  const chosen = html.match(/<option\b(?=[^>]*\bselected\b)[^>]*value="([^"]*)"/);
  if (chosen && nodes.chain) nodes.chain.value = chosen[1];
  const forbidden = () => { throw Error('unexpected browser side effect'); };
  const storage = {getItem(k) { if (broken) throw Error('blocked'); return saved.get(k) || null; },
    setItem(k, v) { if (broken) throw Error('blocked'); assert.equal(k, key); saved.set(k, v); },
    removeItem(k) { if (broken) throw Error('blocked'); assert.equal(k, key); saved.delete(k); }};
  const sandbox = {document: {getElementById: id => nodes[id], querySelectorAll: () => []},
    localStorage: storage, sessionStorage: {getItem: forbidden, setItem: forbidden},
    console: {log: forbidden, warn: forbidden, error: forbidden},
    history: {pushState: forbidden, replaceState: forbidden},
    location: new Proxy({}, {set: forbidden}),
    fetch(url, options) { return new Promise((resolve, reject) => requests.push({url, options,
      body: JSON.parse(options.body), resolve: body => resolve({json: () => Promise.resolve(body)}), reject})); }};
  sandbox.window = sandbox;
  vm.runInNewContext(script, sandbox, {timeout: 1000});
  assert.ok(nodes['liquidity-go'], 'one-click liquidity recheck is missing');
  assert.ok(nodes['liquidity-clear'], 'clear browser history control is missing');
  const click = (fill = true) => { if (fill) {
    nodes.addr.value = replies[0].result.structuredContent.address; nodes.chain.value = 'base';
    nodes.chain.fire('change');
    } nodes['liquidity-go'].fire('click'); return requests.at(-1); };
  return {nodes, requests, saved, click, text: () => nodes['liquidity-result'].innerHTML};
}

function knownAddressesReply() {
  const reply = plain(replies[0]), result = reply.result.structuredContent;
  result.known_address_balances = {status: 'ok', address: result.address, chain: 'base',
    source: 'public_rpc', pool_id: result.best_pair_address, block_number: '262', block_hash: '0x' + 'ab'.repeat(32),
    total_supply_raw: '40000000000000000', balances: {
      pool: {status: 'ok', address: result.best_pair_address, balance_raw: '10000000000000000', supply_percent: '25.000000'},
      zero: {status: 'ok', address: '0x' + '0'.repeat(40), balance_raw: '0', supply_percent: '0.000000'},
      dead: {status: 'ok', address: '0x' + '0'.repeat(36) + 'dead', balance_raw: '1', supply_percent: '<0.000001'}
    }};
  return reply;
}

const cases = {
  async 'eight unrelated estimates leave room for the latest unpriced market and reload target'() {
    const old = replies[0].result.structuredContent.comparison_context[0];
    const filled = Array.from({length: 8}, (_, i) => ({...old,
      address: '0x' + String(i + 1).padStart(40, '0'),
      checked_at: '2026-11-01T00:00:0' + i + 'Z'}));
    const b = boot(new Map([[key, JSON.stringify(filled)]]));
    const [a1, next, a2] = balancerUnpricedReplies;
    const target = a1.result.structuredContent.address;
    b.nodes.addr.value = target;
    b.nodes.chain.value = 'ethereum'; b.nodes.chain.fire('change');
    b.click(false).resolve(a1); await tick();
    const reopened = boot(b.saved);
    assert.equal(reopened.nodes.addr.value, target);
    assert.equal(reopened.nodes.chain.value, 'ethereum');
    assert.equal(JSON.parse(b.saved.get(key)).length, 8);
    const nextRequest = reopened.click(false);
    assert.deepEqual(nextRequest.body.params.arguments.comparison_context, a1.result.structuredContent.comparison_context);
    nextRequest.resolve(next); await tick();
    assert.match(reopened.text(), /Selected market changed/);
    assert.doesNotMatch(reopened.text(), /Estimated change/);
    const back = reopened.click(false);
    assert.deepEqual(back.body.params.arguments.comparison_context, next.result.structuredContent.comparison_context);
    back.resolve(a2); await tick();
    assert.match(reopened.text(), /Selected market changed/);
    assert.doesNotMatch(reopened.text(), /Estimated change/);
    assert.equal(JSON.parse(b.saved.get(key)).length, 8);
  },
  async 'unpriced Balancer markets keep their IDs and an earlier dollar baseline across reloads'() {
    const b = boot(), [a, next, unpricedA, back] = balancerReplies;
    const first = a.result.structuredContent, second = next.result.structuredContent;
    b.nodes.addr.value = first.address;
    b.nodes.chain.value = 'ethereum'; b.nodes.chain.fire('change');
    b.click(false).resolve(a); await tick();
    b.click(false).resolve(next); await tick();
    assert.match(b.text(), /Selected market changed/);
    assert.match(b.text(), /No USD liquidity estimate/);
    assert.ok(b.text().includes(second.best_pair_market_id));
    assert.doesNotMatch(b.text(), /Estimated change/);
    b.click(false).resolve(unpricedA); await tick();
    const reopened = boot(b.saved), request = reopened.click(false);
    const saved = request.body.params.arguments.comparison_context;
    assert.ok(saved.some(row => row.best_pair_market_id === first.best_pair_market_id && row.liquidity_usd === 19952));
    assert.ok(saved.some(row => row.status === 'unpriced' && row.liquidity_usd === null));
    request.resolve(back); await tick();
    assert.match(reopened.text(), /Estimated change: \+\$3,313/);
  },
  async 'Curve market ID is shown in full and carried unchanged by a browser recheck'() {
    const b = boot();
    const first = curveReplies[0].result.structuredContent;
    const id = first.best_pair_market_id;
    b.nodes.addr.value = first.address;
    b.nodes.chain.value = 'ethereum'; b.nodes.chain.fire('change');
    b.click(false).resolve(curveReplies[0]); await tick();
    assert.match(b.text(), /DexScreener market ID/);
    assert.ok(b.text().includes(id));
    const saved = JSON.parse(b.saved.get(key));
    assert.equal(saved[0].best_pair_market_id, id);
    assert.equal('best_pair_address' in saved[0], false);
    const reopened = boot(b.saved), next = reopened.click(false);
    assert.deepEqual(next.body.params.arguments.comparison_context, saved);
    next.resolve(curveReplies[1]); await tick();
    assert.match(reopened.text(), /Estimated change: \$0/);
    assert.ok(reopened.text().includes(id));
  },
  async 'a verified Curve market zero is displayed as an observed estimate and can compare to zero'() {
    const b = boot();
    const firstZero = curveReplies[2].result.structuredContent;
    b.nodes.addr.value = firstZero.address;
    b.nodes.chain.value = 'ethereum'; b.nodes.chain.fire('change');
    b.click(false).resolve(curveReplies[2]); await tick();
    b.click(false).resolve(curveReplies[3]); await tick();
    assert.match(b.text(), /Current estimate: \$0/);
    assert.match(b.text(), /The provider reported zero liquidity for this market/);
    assert.match(b.text(), /Estimated change: \$0/);
    assert.doesNotMatch(b.text(), /No pool-specific zero was available/);
  },
  async 'a rate-limited optional read keeps liquidity and offers a manual recheck'() {
    const b = boot();
    b.nodes.addr.value = limitedReply.result.structuredContent.address;
    b.nodes.chain.value = 'base'; b.nodes.chain.fire('change');
    b.nodes[balanceOption].checked = true;
    b.click(false).resolve(limitedReply); await tick();
    assert.match(b.text(), /Current estimate: \$80,000/);
    assert.match(b.text(), /public node.*rate limit/i);
    assert.match(b.text(), /recheck.*manually/i);
    assert.equal(b.requests.length, 1);
  },
  async 'fixed-block balances are explicit, scoped and excluded from saved market history'() {
    const b = boot();
    assert.match(html, /<input\b(?=[^>]*\bid="include-known-address-balances")(?=[^>]*\btype="checkbox")(?![^>]*\schecked\b)[^>]*>/);
    assert.equal(b.nodes[balanceOption].checked, false);
    const normal = b.click();
    assert.equal('include_known_address_balances' in normal.body.params.arguments, false);
    normal.resolve(replies[0]); await tick();
    b.nodes[balanceOption].checked = true; b.nodes[balanceOption].fire('change');
    assert.equal(b.requests.length, 1);
    const query = b.click();
    assert.equal(query.body.params.arguments.include_known_address_balances, true);
    const reply = knownAddressesReply();
    query.resolve(reply); await tick();
    assert.match(b.text(), /Known address balances/i);
    assert.match(b.text(), /Block[^\n]+262/i);
    assert.match(b.text(), /25\.000000%/);
    assert.match(b.text(), /0\.000000%/);
    assert.match(b.text(), /&lt;0\.000001%/);
    assert.doesNotMatch(b.saved.get(key), /known_address_balances|total_supply_raw|40000000000000000/);
    b.nodes[balanceOption].checked = false; b.nodes[balanceOption].fire('change');
    assert.doesNotMatch(b.text(), /Known address balances|25\.000000%/i);
  },
  async 'changed forms and conflicting response identity suppress the opt-in observation'() {
    for (const changed of ['address', 'network', 'response token', 'response chain', 'response pool']) {
      const b = boot(), reply = knownAddressesReply();
      b.nodes[balanceOption].checked = true; b.nodes[balanceOption].fire('change');
      const request = b.click();
      const reading = reply.result.structuredContent.known_address_balances;
      if (changed === 'address') {
        b.nodes.addr.value = '0x' + 'ef'.repeat(20); b.nodes.addr.fire('input');
      } else if (changed === 'network') {
        b.nodes.chain.value = 'bsc'; b.nodes.chain.fire('change');
      } else if (changed === 'response token') reading.address = '0x' + 'ef'.repeat(20);
      else if (changed === 'response chain') reading.chain = 'bsc';
      else reading.pool_id = '0x' + 'ef'.repeat(20);
      request.resolve(reply); await tick();
      assert.doesNotMatch(b.text(), /25\.000000%/);
      assert.equal(b.nodes['liquidity-go'].disabled, false);
    }
  },
  async 'a balance cannot be rendered as a pool without an addressable selected pool'() {
    for (const invalid of [null, '0x' + 'cd'.repeat(32)]) {
      const b = boot(), reply = knownAddressesReply(), value = reply.result.structuredContent;
      const reading = value.known_address_balances;
      reading.pool_id = invalid;
      if (invalid === null) {
        delete value.best_pair_address;
        delete reading.balances.pool.address;
      } else {
        value.best_pair_address = invalid;
        reading.balances.pool.address = invalid;
      }
      b.nodes[balanceOption].checked = true;
      b.click().resolve(reply); await tick();
      assert.doesNotMatch(b.text(), /25\.000000%/);
      assert.match(b.text(), /0\.000000%/);
    }
  },
  async 'three actual MCP replies survive reopening and source alternation'() {
    const saved = new Map(); let expected = [];
    for (let i = 0; i < replies.length; i++) {
      const b = boot(saved); assert.equal(b.requests.length, 0);
      if (i > 0) {
        assert.equal(b.nodes.addr.value, replies[0].result.structuredContent.address);
        assert.equal(b.nodes.chain.value, 'base');
      }
      const q = b.click(i === 0);
      assert.equal(q.body.params.name, 'get_token_liquidity');
      assert.equal(q.url, 'https://vetagent.dev/mcp');
      assert.equal(q.options.headers['X-MCP-Client'], 'vetagent-landing-demo');
      assert.equal(q.body.params.arguments.chain_hint, 'base');
      assert.deepEqual(q.body.params.arguments.comparison_context, expected);
      q.resolve(replies[i]); await tick();
      expected = replies[i].result.structuredContent.comparison_context;
      assert.ok(Array.isArray(expected)); assert.ok(expected.length <= 8);
      assert.deepEqual(JSON.parse(saved.get(key)), expected);
      assert.equal(b.nodes['liquidity-go'].disabled, false);
      if (i === 0) assert.match(b.text(), /baseline/i);
      if (i === 1) assert.match(b.text(), /source|provider/i);
      if (i === 2) {
        assert.match(b.text(), /366,?200/); assert.match(b.text(), /-/);
        assert.match(b.text(), /2026-11-19T16:09:07Z/);
        assert.match(b.text(), /2026-11-19T16:54:56Z/);
      }
    }
    assert.match(html, /in this browser/i); assert.match(html, /No.*server.side history/i);
  },
  async 'same-pool rechecks preserve cents, small change direction and real zero'() {
    const saved = new Map();
    const shown = [];
    for (const reply of precisionReplies) {
      const b = boot(saved);
      const query = b.click();
      assert.deepEqual(query.body.params.arguments.comparison_context, JSON.parse(saved.get(key) || '[]'));
      query.resolve(reply); await tick();
      shown.push(b.text());
      assert.deepEqual(JSON.parse(b.saved.get(key)), reply.result.structuredContent.comparison_context);
    }
    assert.match(shown[0], /Current estimate: \$0\.10<\/div>/);
    assert.match(shown[1], /Last comparable dexscreener estimate: \$0\.10 at /);
    assert.match(shown[1], /Estimated change: increase of less than \$0\.01<\/div>/);
    assert.match(shown[2], /Estimated change: -\$0\.10<\/div>/);
    assert.match(shown[3], /Last comparable dexscreener estimate: less than \$0\.01 at /);
    assert.match(shown[3], /After: less than \$0\.01 at /);
    assert.match(shown[3], /Current estimate: less than \$0\.01<\/div>/);
    assert.match(shown[3], /Estimated change: decrease of less than \$0\.01<\/div>/);
    assert.match(shown[4], /Estimated change: \$0<\/div>/);
    assert.match(shown[5], /Current estimate: \$0<\/div>/);
    assert.match(shown[5], /reported zero liquidity for this pool/i);
    assert.match(shown[5], /Estimated change: decrease of less than \$0\.01/);
    assert.match(shown[6], /Current estimate: Unavailable<\/div>/);
    assert.doesNotMatch(shown[6], /Estimated change:/);
    assert.match(shown[7], /Estimated change: \$0<\/div>/);
    assert.match(shown[8], /Estimated change: increase of less than \$0\.01/);
    assert.match(shown[9], /No trading pair was found/i);
    assert.doesNotMatch(shown[9], /Current estimate: \$0|Estimated change:/);
    assert.match(shown[10], /No pool-specific zero/i);
    assert.doesNotMatch(shown[10], /Current estimate: \$0|Estimated change:/);
  },
  async 'another network is clearly labelled and its comparison is never rendered for the selected network'() {
    for (const [lookup, message] of [['empty', /returned no pools for base/i],
                                     ['unconfirmed', /could not confirm pools on base/i]]) {
      const b = boot(), reply = plain(replies[2]);
      const result = reply.result.structuredContent;
      result.network_selection = {requested_chain: 'base', returned_chain: 'ethereum',
        status: 'different', lookup};
      result.best_pair_chain = 'ethereum';
      b.click().resolve(reply); await tick();
      assert.match(b.text(), /Market data below is for ethereum/i);
      assert.match(b.text(), message);
      assert.match(b.text(), /Estimate on ethereum: \$85,946,000/i);
      assert.doesNotMatch(b.text(), /Estimated change:|Last comparable|366,200/);
    }
  },
  async 'reopening keeps the chosen BSC baseline after a fallback Ethereum snapshot'() {
    const row = {...plain(replies[0].result.structuredContent.comparison_context[0]), best_pair_chain: 'bsc'};
    const saved = new Map([[key, JSON.stringify([row])]]), b = boot(saved);
    const query = b.click(false);
    assert.equal(query.body.params.arguments.chain_hint, 'bsc');
    assert.deepEqual(query.body.params.arguments.comparison_context, [row]);
    const reply = plain(replies[0]), result = reply.result.structuredContent;
    result.network_selection = {requested_chain: 'bsc', returned_chain: 'ethereum',
      status: 'different', lookup: 'empty'};
    result.best_pair_chain = 'ethereum';
    result.comparison = {status: 'not_comparable', reason: 'different_network'};
    result.comparison_context = [row];
    query.resolve(reply); await tick();
    assert.match(b.text(), /Market data below is for ethereum/i);
    assert.deepEqual(JSON.parse(saved.get(key)), [row]);
    const reopened = boot(saved);
    assert.equal(reopened.nodes.chain.value, 'bsc');
    assert.equal(reopened.requests.length, 0);
  },
  async 'clearing returns to the first-use target and reopening never queries automatically'() {
    const row = plain(replies[0].result.structuredContent.comparison_context[0]);
    const saved = new Map([[key, JSON.stringify([row])]]), b = boot(saved);
    assert.equal(b.requests.length, 0); assert.equal(b.nodes.addr.value, row.address);
    b.nodes['liquidity-clear'].fire('click');
    const firstUse = boot(saved);
    assert.equal(firstUse.requests.length, 0);
    assert.equal(b.nodes.addr.value, firstUse.nodes.addr.value);
    assert.equal(b.nodes.chain.value, firstUse.nodes.chain.value);
    assert.equal(firstUse.nodes.chain.value, 'ethereum');
    b.nodes.addr.value = row.address; b.nodes.addr.fire('input');
    assert.equal(b.nodes.chain.value, '');
    assert.notEqual(firstUse.nodes.addr.value, row.address);
  },
  async 'clear invalidates an in-flight reply and leaves the risk demo usable'() {
    const b = boot(); const q = b.click();
    b.nodes['liquidity-clear'].fire('click');
    const cleared = b.text(); q.resolve(replies[0]); await tick();
    assert.equal(b.text(), cleared); assert.equal(b.saved.size, 0);
    assert.equal(b.nodes['liquidity-go'].disabled, false);
    b.nodes.go.fire('click');
    assert.equal(b.requests.at(-1).body.params.name, 'assess_token_risk');
    assert.equal(b.nodes.verdict.innerHTML.includes('Running live checks'), true);
  },
  async 'only the current token leaves browser storage with chain-aware address case'() {
    const row = plain(replies[0].result.structuredContent.comparison_context[0]);
    const other = {...row, address: '0x' + 'ab'.repeat(20)};
    const sol = {...row, best_pair_chain: 'solana', address: 'So11111111111111111111111111111111111111112',
      best_pair_address: 'So11111111111111111111111111111111111111112'};
    const b = boot(new Map([[key, JSON.stringify([row, other, sol])]]));
    b.nodes.addr.value = other.address.toUpperCase().replace('0X', '0x'); b.nodes.chain.value = 'base';
    b.nodes['liquidity-go'].fire('click');
    assert.deepEqual(b.requests[0].body.params.arguments.comparison_context, [other]);
    const reply = plain(replies[0]); reply.result.structuredContent.comparison_context = [other];
    b.requests[0].resolve(reply); await tick();
    assert.equal(JSON.parse(b.saved.get(key)).length, 3, 'other local token baselines must survive merging');
    b.nodes.addr.value = sol.address.toLowerCase(); b.nodes.chain.value = 'solana';
    b.nodes['liquidity-go'].fire('click');
    assert.deepEqual(b.requests[1].body.params.arguments.comparison_context, []);
    b.nodes.addr.value = sol.address; b.nodes['liquidity-go'].fire('click');
    assert.deepEqual(b.requests[2].body.params.arguments.comparison_context, [sol]);
  },
  async 'older liquidity replies and failures cannot overwrite newer output or storage'() {
    for (const failure of [false, true]) {
      const b = boot(); const old = b.click(), latest = b.click();
      latest.resolve(replies[2]); await tick();
      const text = b.text(), saved = b.saved.get(key);
      if (failure) old.reject(Error('old failure')); else old.resolve(replies[0]);
      await tick(); assert.equal(b.text(), text); assert.equal(b.saved.get(key), saved);
    }
  },
  async 'merging a ninth token keeps eight local observations and discloses eviction'() {
    const row = plain(replies[0].result.structuredContent.comparison_context[0]);
    const older = Array.from({length: 8}, (_, i) => ({...row,
      address: '0x' + (i + 1).toString(16).padStart(40, '0'), checked_at: '2026-11-18T00:00:0' + i + 'Z'}));
    const b = boot(new Map([[key, JSON.stringify(older)]]));
    const q = b.click(); assert.deepEqual(q.body.params.arguments.comparison_context, []);
    q.resolve(replies[0]); await tick();
    const saved = JSON.parse(b.saved.get(key));
    assert.equal(saved.length, 8); assert.ok(saved.some(r => r.address === row.address));
    assert.ok(!saved.some(r => r.address === older[0].address));
    assert.match(b.text(), /dropped/i);
  },
  async 'corrupt and unavailable storage are visible and do not stop a recheck'() {
    for (const raw of ['bad JSON', '{}', JSON.stringify(Array(9).fill({})), 'x'.repeat(9000)]) {
      const b = boot(new Map([[key, raw]])); const q = b.click();
      assert.deepEqual(q.body.params.arguments.comparison_context, []);
      q.resolve(replies[0]); await tick(); assert.match(b.text(), /reset|invalid|discard/i);
    }
    const b = boot(new Map(), true); b.click().resolve(replies[0]); await tick();
    assert.match(b.text(), /storage.*unavailable|page closes/i);
    b.nodes['liquidity-clear'].fire('click'); assert.match(b.text(), /could not clear/i);
  },
  async 'pool changes disclose both facts and upstream text is escaped'() {
    const b = boot(), reply = plain(replies[2]);
    reply.result.structuredContent.comparison.pool_transition = {status: 'changed',
      previous_pool_address: '<img src=x>', previous_checked_at: '2026-11-19T16:54:34Z'};
    reply.result.structuredContent.comparison.baseline_is_latest_observation = false;
    b.click().resolve(reply); await tick();
    assert.match(b.text(), /pool changed/i); assert.match(b.text(), /older.*baseline|older.*observation/i);
    assert.match(b.text(), /&lt;img/); assert.doesNotMatch(b.text(), /<img/);
  }
};
(async () => {
  let failed = 0;
  for (const [name, test] of Object.entries(cases)) {
    try { await test(); console.log('PASS ' + name); }
    catch (e) { failed++; console.log('FAIL ' + name + ': ' + e.message); }
  }
  console.log(`${Object.keys(cases).length - failed} passed, ${failed} failed`);
  process.exitCode = failed ? 1 : 0;
})();
