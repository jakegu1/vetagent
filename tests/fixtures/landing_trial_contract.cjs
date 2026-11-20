// Built-ins only. Execute the real Worker-served inline script with controlled replies.
const assert = require('node:assert/strict');
const vm = require('node:vm');
const html = require('node:fs').readFileSync(0, 'utf8');
const script = html.slice(html.lastIndexOf('<script>') + 8, html.lastIndexOf('</script>'));
const chains = ['arbitrum', 'avalanche', 'base', 'bsc', 'ethereum', 'optimism', 'polygon', 'solana'];
const attrs = s => Object.fromEntries([...s.matchAll(/([\w-]+)="([^"]*)"/g)].map(m => [m[1], m[2]]));
const tick = () => new Promise(resolve => setImmediate(resolve));
const verdict = (chain = 'base') => ({risk_level: 'unknown', risk_score: 0, confidence: 0.2,
  recommendation: 'Critical checks missing: do not treat this as low risk.',
  signals: [{severity: 'warn', name: 'Missing check', message: 'Upstream unavailable'}],
  evidence: chain === null ? {} : {chain_searched: chain}});
const response = v => ({result: {structuredContent: v}});

function boot() {
  function element(a = {}) {
    const listeners = {};
    return {value: a.value || '', disabled: false, innerHTML: '',
      dataset: {a: a['data-a'], c: a['data-c']}, classList: {add() {}},
      addEventListener(type, fn) { listeners[type] = fn; },
      fire(type, event = {}) { if (listeners[type]) listeners[type](event); }};
  }
  const nodes = {};
  for (const m of html.matchAll(/<(input|button|div|select)\b([^>]*)>/g)) {
    const a = attrs(m[2]);
    if (a.id) nodes[a.id] = element(a);
  }
  const samples = [...html.matchAll(/<button\b([^>]*data-a="[^"]*"[^>]*)>/g)]
    .map(m => element(attrs(m[1])));
  const requests = [];
  const forbidden = () => { throw Error('input must not enter storage, URLs or logs'); };
  const storage = {getItem(key) { assert.equal(key, 'vetagent.liquidity.v1'); return null; },
    removeItem(key) { assert.equal(key, 'vetagent.liquidity.v1'); }, setItem: forbidden};
  const sandbox = {document: {getElementById: id => nodes[id] || null,
      querySelectorAll: selector => selector === '.samples button' ? samples : []},
    fetch(url, options) {
      return new Promise((resolve, reject) => requests.push({url, options,
        args: JSON.parse(options.body).params.arguments,
        resolve: data => resolve({json: () => Promise.resolve(data)}), reject}));
    }, localStorage: storage, sessionStorage: storage,
    history: {pushState: forbidden, replaceState: forbidden},
    location: new Proxy({}, {set: forbidden}),
    console: {log: forbidden, warn: forbidden, error: forbidden}};
  sandbox.window = sandbox;
  vm.runInNewContext(script, sandbox, {timeout: 1000});
  return {nodes, samples, requests,
    enter(address) { nodes.addr.value = address; nodes.addr.fire('keydown', {key: 'Enter', preventDefault() {}}); },
    select(value) { assert.ok(nodes.chain, 'native network selector is missing'); nodes.chain.value = value; },
    text() { return nodes.verdict.innerHTML; }};
}

const cases = {
  async 'accessible Auto and eight existing networks'() {
    const select = html.match(/<select\b[^>]*id="chain"[^>]*>([\s\S]*?)<\/select>/);
    assert.ok(select, 'native network selector is missing');
    assert.match(html, /<label\b[^>]*for="chain"[^>]*>\s*Network\s*<\/label>/);
    const values = [...select[1].matchAll(/<option\b[^>]*value="([^"]*)"/g)].map(m => m[1]);
    assert.deepEqual(values, ['', ...values.slice(1)]);
    assert.deepEqual(values.slice(1).sort(), chains);
    assert.match(select[1], /value=""[^>]*>Auto</);
    assert.equal(boot().nodes.chain.value, '');
  },
  async 'explicit submission only and Auto preserves the self client'() {
    const b = boot();
    assert.equal(b.requests.length, 0);
    b.nodes.addr.value = '0xmanual';
    b.nodes.addr.fire('input'); b.nodes.addr.fire('keydown', {key: 'a'});
    if (b.nodes.chain) b.nodes.chain.fire('change');
    assert.equal(b.requests.length, 0);
    b.nodes.go.fire('click');
    const q = b.requests[0];
    assert.deepEqual(q.args, {address: '0xmanual'});
    assert.equal(q.url, 'https://vetagent.dev/mcp');
    assert.equal(q.options.method, 'POST');
    assert.equal(q.options.headers['X-MCP-Client'], 'vetagent-landing-demo');
    q.resolve(response(verdict())); await tick();
    const before = b.text(); b.enter('   ');
    assert.equal(b.requests.length, 1); assert.equal(b.text(), before);
  },
  async 'click and Enter send every selected network'() {
    for (const chain of chains) {
      const b = boot(); b.select(chain); b.nodes.addr.value = '  0xclick  ';
      b.nodes.go.fire('click');
      assert.deepEqual(b.requests[0].args, {address: '0xclick', chain_hint: chain});
      b.enter('0xenter');
      assert.deepEqual(b.requests[1].args, {address: '0xenter', chain_hint: chain});
    }
  },
  async 'examples keep their address and chain in the visible selector'() {
    const b = boot();
    for (const sample of b.samples) {
      sample.fire('click');
      assert.deepEqual(b.requests.at(-1).args, {address: sample.dataset.a, chain_hint: sample.dataset.c});
      assert.equal(b.nodes.chain && b.nodes.chain.value, sample.dataset.c);
      assert.equal(b.nodes.addr.value, sample.dataset.a);
    }
    b.select(''); b.enter('0xauto');
    assert.deepEqual(b.requests.at(-1).args, {address: '0xauto'});
  },
  async 'result uses submitted asset, chosen and returned scopes'() {
    const b = boot(); b.select('ethereum'); b.enter('0xsubmitted');
    b.nodes.addr.value = '0xedited'; b.select('solana');
    b.requests[0].resolve(response(verdict('base'))); await tick();
    assert.match(b.text(), /0xsubmitted/); assert.doesNotMatch(b.text(), /0xedited|solana/);
    assert.match(b.text(), /Selected network:[\s\S]*ethereum/i);
    assert.match(b.text(), /Assessment network:[\s\S]*base/i);
    assert.match(b.text(), /unknown/); assert.match(b.text(), /Critical checks missing/);
    assert.match(b.text(), /Upstream unavailable/);
  },
  async 'missing engine scope is not inferred from the selection or best pair'() {
    const b = boot(); b.select('ethereum'); b.enter('0xmissing');
    const v = verdict(null); v.evidence.best_pair = {chain: 'ethereum'};
    b.requests[0].resolve(response(v)); await tick();
    assert.match(b.text(), /Assessment network:\s*(?:<[^>]+>)*Not reported/i);
    assert.match(b.text(), /0xmissing/);
  },
  async 'older success cannot change pending latest output or button'() {
    const b = boot(); b.enter('0xolder'); b.enter('0xlatest');
    const pending = b.text();
    b.requests[0].resolve(response(verdict())); await tick();
    assert.equal(b.text(), pending); assert.equal(b.nodes.go.disabled, true);
    b.requests[1].resolve(response(verdict())); await tick();
    assert.match(b.text(), /0xlatest/); assert.equal(b.nodes.go.disabled, false);
  },
  async 'older failure cannot change pending latest output or button'() {
    const b = boot(); b.enter('0xolder'); b.enter('0xlatest');
    const pending = b.text();
    b.requests[0].reject(Error('stale failure')); await tick();
    assert.equal(b.text(), pending); assert.equal(b.nodes.go.disabled, true);
    b.requests[1].reject(Error('current failure')); await tick();
    assert.match(b.text(), /0xlatest/); assert.match(b.text(), /current failure/);
    assert.equal(b.nodes.go.disabled, false);
  },
  async 'older replies cannot replace a completed latest result'() {
    for (const old of ['success', 'failure', 'malformed', 'rpc', 'tool']) {
      const b = boot(); b.enter('0xolder'); b.samples[0].fire('click');
      b.requests[1].resolve(response(verdict('ethereum'))); await tick();
      const latest = b.text();
      if (old === 'failure') b.requests[0].reject(Error('stale'));
      else b.requests[0].resolve(old === 'success' ? response(verdict()) :
        old === 'rpc' ? {error: {message: 'stale rpc'}} :
        old === 'tool' ? {result: {isError: true, content: [{text: 'stale tool'}]}} : {});
      await tick(); assert.equal(b.text(), latest); assert.equal(b.nodes.go.disabled, false);
    }
  },
  async 'latest RPC, tool and parse failures remain scoped and release the button'() {
    for (const reply of [{error: {message: 'rpc failure'}},
      {result: {isError: true, content: [{text: 'tool failure'}]}}, {}]) {
      const b = boot(); b.enter('0xfailed'); b.requests[0].resolve(reply); await tick();
      assert.match(b.text(), /0xfailed/); assert.equal(b.nodes.go.disabled, false);
    }
  },
  async 'address and returned network remain escaped text'() {
    const b = boot(); b.enter('<img src=x onerror=alert(1)>');
    b.requests[0].resolve(response(verdict('<script>alert(2)</script>'))); await tick();
    assert.match(b.text(), /&lt;img/); assert.match(b.text(), /&lt;script/);
    assert.doesNotMatch(b.text(), /<img|<script/);
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
