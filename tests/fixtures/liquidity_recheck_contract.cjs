// Replay the Worker-served script with responses from the actual MCP dispatcher.
const assert = require('node:assert/strict');
const vm = require('node:vm');
const {html, replies} = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const script = html.slice(html.lastIndexOf('<script>') + 8, html.lastIndexOf('</script>'));
const tick = () => new Promise(resolve => setImmediate(resolve));
const plain = value => JSON.parse(JSON.stringify(value));
const key = 'vetagent.liquidity.v1';

function boot(saved = new Map(), broken = false) {
  const nodes = {}, requests = [];
  for (const match of html.matchAll(/<(?:input|button|div|select)\b([^>]*)>/g)) {
    const attrs = Object.fromEntries([...match[1].matchAll(/([\w-]+)="([^"]*)"/g)].map(m => [m[1], m[2]]));
    if (!attrs.id) continue;
    const events = {};
    nodes[attrs.id] = {value: attrs.value || '', disabled: false, innerHTML: '', textContent: '',
      classList: {add() {}}, addEventListener(name, fn) { events[name] = fn; },
      fire(name, event = {}) { if (events[name]) events[name](event); }};
  }
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
    } nodes['liquidity-go'].fire('click'); return requests.at(-1); };
  return {nodes, requests, saved, click, text: () => nodes['liquidity-result'].innerHTML};
}

const cases = {
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
  async 'clearing returns to the first-use target and reopening never queries automatically'() {
    const row = plain(replies[0].result.structuredContent.comparison_context[0]);
    const saved = new Map([[key, JSON.stringify([row])]]), b = boot(saved);
    assert.equal(b.requests.length, 0); assert.equal(b.nodes.addr.value, row.address);
    b.nodes['liquidity-clear'].fire('click');
    const firstUse = boot(saved);
    assert.equal(firstUse.requests.length, 0);
    assert.equal(b.nodes.addr.value, firstUse.nodes.addr.value);
    assert.equal(b.nodes.chain.value, firstUse.nodes.chain.value);
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
