// Built-ins only. Execute the real Worker-served inline script with controlled replies.
const assert = require('node:assert/strict');
const vm = require('node:vm');
const {html, recorded, controls} = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const script = html.slice(html.lastIndexOf('<script>') + 8, html.lastIndexOf('</script>'));
const chains = ['arbitrum', 'avalanche', 'base', 'bsc', 'ethereum', 'optimism', 'polygon', 'solana'];
const attrs = s => Object.fromEntries([...s.matchAll(/([\w-]+)="([^"]*)"/g)].map(m => [m[1], m[2]]));
const tick = () => new Promise(resolve => setImmediate(resolve));
const verdict = (chain = 'base') => ({risk_level: 'unknown', risk_score: 0, confidence: 0.2,
  recommendation: 'Critical checks missing: do not treat this as low risk.',
  signals: [{severity: 'warn', name: 'Missing check', message: 'Upstream unavailable'}],
  evidence: chain === null ? {} : {chain_searched: chain}});
const response = v => ({result: {structuredContent: v}});
const clone = value => JSON.parse(JSON.stringify(value));
const front = page => page.split('<details')[0];
async function render(value) {
  const b = boot(), saved = JSON.stringify(value);
  b.enter(value.address || '0x' + 'ab'.repeat(20));
  b.requests[0].resolve(response(value)); await tick();
  assert.equal(JSON.stringify(value), saved, 'rendering must not mutate the machine result');
  assert.equal(b.requests.length, 1, 'rendering must not trigger extra queries');
  return b;
}

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
  const chosen = html.match(/<option\b(?=[^>]*\bselected\b)[^>]*value="([^"]*)"/);
  if (chosen && nodes.chain) nodes.chain.value = chosen[1];
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
    select(value) { assert.ok(nodes.chain, 'native network selector is missing');
      nodes.chain.value = value; nodes.chain.fire('change'); },
    text() { return nodes.verdict.innerHTML; }};
}

const cases = {
  async 'first use is Ethereum WETH without an automatic request'() {
    const b = boot();
    assert.equal(b.requests.length, 0);
    assert.equal(b.nodes.addr.value, recorded[0].args.address);
    assert.equal(b.nodes.chain.value, 'ethereum');
    b.nodes.go.fire('click');
    assert.deepEqual(b.requests[0].args, {address: recorded[0].args.address, chain_hint: 'ethereum'});
  },
  async 'pasting a new target releases the default chain for assessment and recheck'() {
    for (const button of ['go', 'liquidity-go']) {
      for (const address of ['0x4200000000000000000000000000000000000006',
        '0x' + 'ab'.repeat(20), 'So11111111111111111111111111111111111111112']) {
        const b = boot(); b.nodes.addr.value = address; b.nodes.addr.fire('input');
        assert.equal(b.nodes.chain.value, '');
        b.nodes[button].fire('click');
        assert.equal(b.requests[0].args.address, address);
        assert.equal(Object.hasOwn(b.requests[0].args, 'chain_hint'), false);
      }
    }
    const same = boot(); same.nodes.addr.value = recorded[0].args.address.toLowerCase();
    same.nodes.addr.fire('input'); assert.equal(same.nodes.chain.value, 'ethereum');
  },
  async 'explicit network choice survives manual replacement and examples keep their own network'() {
    for (const button of ['go', 'liquidity-go']) {
      const b = boot(); b.select('base');
      b.nodes.addr.value = '0x4200000000000000000000000000000000000006'; b.nodes.addr.fire('input');
      b.nodes[button].fire('click'); assert.equal(b.requests[0].args.chain_hint, 'base');
      b.samples[1].fire('click'); assert.equal(b.requests.at(-1).args.chain_hint, 'ethereum');
    }
  },
  async 'native confirmation of the current network is explicit but Tab focus is not'() {
    for (const button of ['go', 'liquidity-go']) {
      const confirmed = boot();
      confirmed.nodes.chain.fire('keydown', {key: 'ArrowDown', altKey: true, isTrusted: true});
      confirmed.nodes.chain.fire('click', {isTrusted: true, detail: 0});
      confirmed.nodes.addr.value = '0x4200000000000000000000000000000000000006';
      confirmed.nodes.addr.fire('input'); confirmed.nodes[button].fire('click');
      assert.equal(confirmed.requests[0].args.chain_hint, 'ethereum');
      const mouse = boot(); mouse.nodes.chain.fire('pointerdown', {isTrusted: true});
      mouse.nodes.chain.fire('click', {isTrusted: true, detail: 1});
      mouse.nodes.chain.fire('click', {isTrusted: true, detail: 0});
      mouse.nodes.addr.value = '0x4200000000000000000000000000000000000006';
      mouse.nodes.addr.fire('input'); mouse.nodes[button].fire('click');
      assert.equal(mouse.requests[0].args.chain_hint, 'ethereum');
      for (const opener of ['mouse', 'keyboard']) {
        const escaped = boot();
        if (opener === 'mouse') {
          escaped.nodes.chain.fire('pointerdown', {isTrusted: true});
          escaped.nodes.chain.fire('click', {isTrusted: true, detail: 1});
        } else escaped.nodes.chain.fire('keydown', {key: 'ArrowDown', altKey: true, isTrusted: true});
        escaped.nodes.chain.fire('keydown', {key: 'Escape', isTrusted: true});
        escaped.nodes.addr.value = '0x4200000000000000000000000000000000000006';
        escaped.nodes.addr.fire('input'); escaped.nodes[button].fire('click');
        assert.equal(Object.hasOwn(escaped.requests[0].args, 'chain_hint'), false);
      }
      const tabbed = boot(); tabbed.nodes.chain.fire('focus', {isTrusted: true});
      tabbed.nodes.addr.value = 'So11111111111111111111111111111111111111112';
      tabbed.nodes.addr.fire('input'); tabbed.nodes[button].fire('click');
      assert.equal(Object.hasOwn(tabbed.requests[0].args, 'chain_hint'), false);
    }
  },
  async 'three recorded responses keep their real verdicts and explain BUY_FAILED before details'() {
    for (const [index, row] of recorded.entries()) {
      const b = boot(); b.samples[index].fire('click');
      assert.equal(b.requests.length, 1);
      assert.equal(b.requests[0].args.address.toLowerCase(), row.args.address.toLowerCase());
      assert.equal(b.requests[0].args.chain_hint, 'ethereum');
      const saved = JSON.stringify(row.result);
      b.requests[0].resolve(response(row.result)); await tick();
      assert.equal(JSON.stringify(row.result), saved);
      assert.match(b.text(), new RegExp('>' + row.result.risk_level + '<'));
      if (row.result.risk_level === 'unknown') {
        assert.doesNotMatch(front(b.text()), /score [0-9]+\/100/);
      } else {
        assert.match(front(b.text()), new RegExp('score ' + row.result.risk_score + '/100'));
      }
      assert.match(b.text(), /<details[\s>]/); assert.match(b.text(), /Detailed report/i);
      const report = b.text().match(/<pre>([\s\S]*?)<\/pre>/)[1]
        .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');
      assert.deepEqual(JSON.parse(report), row.result, 'detailed report must preserve the complete original machine reply');
      if (row.result.risk_level === 'unknown' && row.result.evidence.honeypot.simulation_success === true) {
        assert.match(front(b.text()), /provider reports simulation completion/i);
        assert.doesNotMatch(front(b.text()), /provider reports a completed buy and sell simulation/i);
      } else {
        assert.doesNotMatch(front(b.text()), /provider reports simulation completion/i);
      }
      if (row.result.risk_level === 'unknown') {
        const shown = front(b.text());
        assert.match(shown, /buy step failed/i);
        assert.match(shown, /did not reach a sell test|selling was not tested/i);
        assert.match(shown, /existing holder.*unverified/i);
        assert.match(shown, /automated.*paused/i);
        assert.match(shown, /2,499\.99/); assert.match(shown, /578 seconds/);
        assert.match(shown, /different pool/i); assert.match(shown, /Proxy/i);
        assert.doesNotMatch(shown, /See evidence\.data_gaps|Not assessed\./);
      }
    }
  },
  async 'scoped recommendation precedes signals without repeating the simulation context'() {
    const example = clone(recorded.find(row => row.case === 'weth-eth').result);
    example.recommendation = 'Low risk. Honeypot.is reports a completed simulation in another pool. ' +
      'The displayed pool was not verified.';
    const shown = front((await render(example)).text());
    const recommendation = shown.indexOf('class="rec"');
    const firstSignal = shown.indexOf('class="sig"');
    assert.ok(recommendation >= 0 && firstSignal > recommendation, 'show scoped guidance above the signal list');
    assert.match(shown, /Honeypot\.is reports a completed simulation in another pool/);
    assert.match(shown, /The displayed pool was not verified/);
    assert.doesNotMatch(shown, /simulation provider reported a different pool|provider reports simulation completion/i);
    assert.match(shown, /selected pool liquidity estimate/i);
  },
  async 'no record and unsupported chain name the actual missing sell check'() {
    const absent = front((await render(clone(controls.no_record))).text());
    assert.match(absent, /sell.*no record|no record.*sell/i);
    assert.match(absent, /honeypot\.is/); assert.match(absent, /unverified|not verified/i);
    const unsupported = front((await render(clone(controls.unsupported))).text());
    assert.match(unsupported, /does not cover polygon/i);
    assert.match(unsupported, /coverage/i); assert.match(unsupported, /automated.*paused/i);
  },
  async 'retry timing comes from the result and mixed gaps do not promise recovery'() {
    for (const name of ['outage', 'mixed']) {
      const value = clone(controls[name]); value.retry_after_seconds = 17;
      const shown = front((await render(value)).text());
      assert.match(shown, /17 seconds/); assert.match(shown, /retry|check again/i);
      assert.match(shown, /then retry once/i);
      assert.match(shown, /provider request failed|provider.*could not|upstream.*failed/i);
      assert.doesNotMatch(shown, /about a minute|retry in 60/i);
      if (name === 'mixed') {
        assert.match(shown, /no record/i);
        assert.match(shown, /other checks may still be missing|gaps may remain/i);
        assert.doesNotMatch(shown, /will still be unknown|cannot become low/i);
      }
    }
    for (const invalid of [null, true, -1, '17']) {
      const value = clone(controls.outage); value.retry_after_seconds = invalid;
      const shown = front((await render(value)).text());
      assert.match(shown, /no valid.*wait time|wait time.*not.*provided/i);
      assert.doesNotMatch(shown, /Wait (null|true|-1|17|60) seconds/i);
    }
  },
  async 'non-sell gaps do not invent a sell failure or missing market observations'() {
    const value = clone(controls.non_sell);
    const shown = front((await render(value)).text());
    assert.match(shown, /liquidity estimate/i); assert.match(shown, /quote_prices/);
    assert.match(shown, /automated.*paused/i);
    assert.doesNotMatch(shown, /buy step failed|selling was not tested|cached|different pool|liquidity estimate: \$0/i);
    assert.doesNotMatch(shown, /provider reports simulation completion/i);
  },
  async 'missing facts stay unknown and all returned detail is escaped'() {
    const missing = front((await render({risk_level: 'unknown', risk_score: 0,
      signals: [], evidence: {}, recommendation: 'See evidence.data_gaps.'})).text());
    assert.match(missing, /did not name.*check|check.*not reported/i);
    assert.doesNotMatch(missing, /score 0\/100/);
    assert.match(missing, /automated.*paused/i); assert.doesNotMatch(missing, /different pool|cached|\$0/);
    const value = clone(controls.non_sell);
    value.evidence.data_gaps[0].reason = 'about the token: <img src=x onerror=alert(1)>';
    value.evidence.data_gaps[0].source = '<svg onload=alert(2)>';
    const text = (await render(value)).text();
    assert.match(text, /&lt;img/); assert.match(text, /&lt;svg/); assert.doesNotMatch(text, /<img|<svg/);
  },
  async 'accessible Auto and eight existing networks'() {
    const select = html.match(/<select\b[^>]*id="chain"[^>]*>([\s\S]*?)<\/select>/);
    assert.ok(select, 'native network selector is missing');
    assert.match(html, /<label\b[^>]*for="chain"[^>]*>\s*Network\s*<\/label>/);
    const values = [...select[1].matchAll(/<option\b[^>]*value="([^"]*)"/g)].map(m => m[1]);
    assert.deepEqual(values, ['', ...values.slice(1)]);
    assert.deepEqual(values.slice(1).sort(), chains);
    assert.match(select[1], /value=""[^>]*>Auto</);
    assert.equal(boot().nodes.chain.value, 'ethereum');
  },
  async 'explicit submission only and Auto preserves the self client'() {
    const b = boot();
    assert.equal(b.requests.length, 0);
    b.select('');
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
