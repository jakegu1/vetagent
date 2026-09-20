"""Every upstream JSON path src/risk.py actually reads, derived from src/risk.py.

Why this is generated and not written down
------------------------------------------
`tests/test_upstream_contract.py` used to carry a hand-typed list of the fields the
engine depends on. On 2026-09-20 that list held ten assertions for honeypot.is and four
for RugCheck, and the four were "reachable", "has a score field", "risks is an array" --
so `topHolders`, `totalHolders` and the whole `token_extensions` block, which is where
E25 and E26 lived, were watched by nothing. The list did not lag because anyone was
careless. It lagged because it was a second copy of a fact whose first copy is the code,
and the second copy of a fact is always the stale one.

So: no list. Every `rc.get("...")` in the engine is a dependency on RugCheck, every
`hp.get("...")` on honeypot.is, and this module finds them by reading the engine.

How the attribution is made, without anyone declaring it
--------------------------------------------------------
The seed is not "the parameter `rc` means RugCheck" -- that would be the same hand-typed
fact one level up. The seed is the URL:

    _fetch_json("https://api.rugcheck.xyz/v1/tokens/%s/report" % address)

`_note_failure` already maps hosts to source names, so that map is read out of the engine
too. From each fetch site the value is followed: through `await`, through assignment,
through `or {}`, through `for ... in`, into other functions by argument position, and
through list elements. Every `.get("literal")`, `["literal"]` and `"literal" in x` on a
followed value is recorded as a path.

Where it stops, and where it over-reaches -- both on purpose
------------------------------------------------------------
It stops at a constructed value. `_gt_to_pair` reads a GeckoTerminal pool and returns a
new dict; those reads are recorded against GeckoTerminal, and the dict it builds is ours,
so the trace ends there. Fetch sites whose URL cannot be resolved to a host are not
guessed at -- `--report` lists them under `untraced`, because a fetch nobody can
attribute is exactly the blind spot this file exists to remove. That list is empty today
and a non-empty one is a finding.

It over-reaches on the pair shape, and this is the deliberate direction. `_gt_to_pair`
normalises GeckoTerminal pools *into* the DexScreener pair shape, so one body of code
reads both and every read on it is attributed to DexScreener -- including `pool_id`,
`traders` and `reserveInUsd`, which are the normaliser's own additions and never arrive
from DexScreener. The engine really does call `.get("pool_id")` on a DexScreener pair; it
really is always absent; the fallback is what runs. A measured baseline records that as
0% present rather than asserting it must exist, which is the honest way to hold a fact
nobody should act on. Under-reaching is the dangerous direction here: a path this misses
is a dependency nothing is watching, which is how E25 and E26 shipped.

Usage:
    python tools/upstream_fields.py            # human-readable table
    python tools/upstream_fields.py --json     # machine-readable, for the contract test
    python tools/upstream_fields.py --report   # plus untraced fetch sites and call sites
"""
import ast
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.path.join(ROOT, "src", "risk.py")

# CoinGecko's onchain API is the GeckoTerminal API behind a key -- `_onchain_sources`
# returns the two as interchangeable for one path shape, and the engine reads one set of
# fields out of whichever answers. They are one contract, and the keyless one is the one
# a test without a key can probe.
_SHAPE_ALIAS = {"coingecko": "geckoterminal"}

# Element-of marker inside a path tuple.
ELEM = "[]"


def _host_map(tree):
    """The host -> source-name map, read out of `_note_failure` rather than retyped."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict) and node.keys:
            keys = [k.value for k in node.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)]
            if any(k.startswith("api.") for k in keys) and len(keys) == len(node.keys):
                vals = [v.value for v in node.values if isinstance(v, ast.Constant)]
                if len(vals) == len(keys):
                    return dict(zip(keys, vals))
    return {}


class Fields(object):
    def __init__(self, path=ENGINE):
        self.src = open(path, encoding="utf-8").read()
        self.tree = ast.parse(self.src)
        self.hosts = _host_map(self.tree)
        self.funcs = {}
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.funcs[node.name] = node
        # source -> path tuple -> sorted line numbers
        self.reads = {}
        # function name -> param name -> set of (source, path)
        self.bindings = {}
        self.untraced = []
        self.crossings = []
        self._pending = []
        # function name -> return slot -> set of (source, path). Slot None is the whole
        # return value; an integer is a position in a returned tuple, which is how
        # `pairs, source = await _load_pairs(...)` hands DexScreener's pair list to the
        # whole engine. Without this the trace stopped at _load_pairs and every read of
        # priceUsd, liquidity, volume and pairCreatedAt was invisible.
        self.returns = {}

    # ---------------------------------------------------------------- resolution

    def _source_of_url(self, node, env):
        """Host attribution for a _fetch_json url argument, or None."""
        texts = []

        def literals(n):
            if isinstance(n, ast.Constant) and isinstance(n.value, str):
                texts.append(n.value)
            elif isinstance(n, ast.BinOp):
                literals(n.left)
                literals(n.right)
            elif isinstance(n, ast.JoinedStr):
                for v in n.values:
                    literals(v)
            elif isinstance(n, ast.Tuple):
                # `"%s&pair=%s" % (hp_url, hp_pair)` -- the host lives in an operand,
                # not in the format string. Missing this unbound `hp` at the retry and
                # cost honeypot.is two thirds of its paths.
                for v in n.elts:
                    literals(v)
            elif isinstance(n, ast.Name):
                for t in env.get("__str__" + n.id, ()):
                    texts.append(t)

        literals(node)
        for t in texts:
            for host, name in self.hosts.items():
                if host in t:
                    return _SHAPE_ALIAS.get(name, name)
        return None

    def _record(self, source, path, lineno):
        by_path = self.reads.setdefault(source, {})
        by_path.setdefault(path, set()).add(lineno)

    def resolve(self, node, env, record=True):
        """(source, path) for an expression that holds upstream data, else None."""
        if isinstance(node, ast.Await):
            return self.resolve(node.value, env, record)

        if isinstance(node, ast.Name):
            return env.get(node.id)

        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
            # The `(x.get("k") or {})` idiom: the value is the left operand's shape.
            for v in node.values:
                got = self.resolve(v, env, record)
                if got:
                    return got
            return None

        if isinstance(node, ast.IfExp):
            return (self.resolve(node.body, env, record)
                    or self.resolve(node.orelse, env, record))

        # `[p for p in pairs if _valid(p)]` -- a filter keeps the collection's shape. The
        # element expression has to be the loop variable itself; anything else builds a
        # new object and the trace correctly stops there.
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
            gens = node.generators
            if (len(gens) == 1 and isinstance(gens[0].target, ast.Name)
                    and isinstance(node.elt, ast.Name)
                    and node.elt.id == gens[0].target.id):
                return self.resolve(gens[0].iter, env, record)
            return None

        if isinstance(node, ast.Subscript):
            base = self.resolve(node.value, env, record)
            if not base:
                return None
            s, p = base
            sl = node.slice
            if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
                p2 = p + (sl.value,)
                if record:
                    self._record(s, p2, node.lineno)
                return (s, p2)
            if isinstance(sl, ast.Constant) and isinstance(sl.value, int):
                return (s, p + (ELEM,))
            if isinstance(sl, ast.Slice):
                return (s, p)
            return None

        if isinstance(node, ast.Call):
            f = node.func
            # x.get("key") / x.get("key", default)
            if (isinstance(f, ast.Attribute) and f.attr == "get" and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                base = self.resolve(f.value, env, record)
                if base:
                    s, p = base
                    p2 = p + (node.args[0].value,)
                    if record:
                        self._record(s, p2, node.lineno)
                    return (s, p2)
                return None
            # Collection wrappers that keep the shape. `dict(hp, simulationError=...)` is
            # still the honeypot.is body with one field overridden -- missing that unbound
            # `hp` for the rest of _honeypot_signals and lost contractCode and
            # token.totalHolders, two fields the old hand-written test did assert.
            if isinstance(f, ast.Name) and f.id in ("sorted", "list", "reversed",
                                                    "tuple", "dict"):
                return self.resolve(node.args[0], env, record) if node.args else None
            # `max(pool, key=_pair_liquidity)` picks one pair out of the list: this is how
            # `best` reaches _liquidity_signals, and with it pairCreatedAt and volume.h24.
            if isinstance(f, ast.Name) and f.id in ("max", "min") and len(node.args) == 1:
                got = self.resolve(node.args[0], env, record)
                return (got[0], got[1] + (ELEM,)) if got else None
            # The fetch itself: this is the seed.
            if isinstance(f, ast.Name) and f.id == "_fetch_json":
                src = self._source_of_url(node.args[0], env) if node.args else None
                if src:
                    return (src, ())
                self.untraced.append({"line": node.lineno,
                                      "code": ast.get_source_segment(self.src, node)})
                return None
            # A local function whose return is unambiguously one upstream shape. Checked
            # after _fetch_json, which is itself a local function -- putting this first
            # swallowed every seed and the table came out empty.
            if isinstance(f, ast.Name) and f.id in self.funcs:
                slot = (self.returns.get(f.id) or {}).get(None) or set()
                return next(iter(slot)) if len(slot) == 1 else None
            return None

        return None

    # ---------------------------------------------------------------- statements

    def _bind_call_args(self, node, env):
        """A tracked value passed into another function binds that function's parameter."""
        f = node.func
        name = f.id if isinstance(f, ast.Name) else None
        if name not in self.funcs:
            return
        target = self.funcs[name]
        params = [a.arg for a in target.args.args]
        pairs = list(zip(params, node.args))
        for kw in node.keywords:
            if kw.arg:
                pairs.append((kw.arg, kw.value))
        for pname, arg in pairs:
            got = self.resolve(arg, env)
            if not got:
                continue
            slot = self.bindings.setdefault(name, {}).setdefault(pname, set())
            if got not in slot:
                slot.add(got)
                self._pending.append(name)
                self.crossings.append({"into": name, "param": pname,
                                       "source": got[0],
                                       "path": ".".join(got[1]) or "<root>",
                                       "line": node.lineno})

    def _walk(self, body, env, fname=None):
        for stmt in body:
            self._stmt(stmt, env, fname)

    def _note_return(self, fname, stmt, env):
        if stmt.value is None:
            return
        slots = {}
        if isinstance(stmt.value, ast.Tuple):
            for i, el in enumerate(stmt.value.elts):
                got = self.resolve(el, env)
                if got:
                    slots[i] = got
        else:
            got = self.resolve(stmt.value, env)
            if got:
                slots[None] = got
        for slot, got in slots.items():
            self.returns.setdefault(fname, {}).setdefault(slot, set()).add(got)

    def _stmt(self, stmt, env, fname=None):
        if isinstance(stmt, ast.Return):
            if fname:
                self._note_return(fname, stmt, env)
            self._expressions(stmt, env)
            return

        # `pairs, source = await _load_pairs(...)`: bind each name from its return slot.
        if (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], (ast.Tuple, ast.List))):
            # The right-hand side first, always. Rebinding the targets before the call's
            # arguments were read deleted `pairs` on the way into
            # `_complete_home_chain(pairs, ...)`, so that function never learned its
            # parameter, never recorded a return, and the fixpoint sat deadlocked at a
            # table missing every DexScreener pair field.
            self._expressions(stmt.value, env)
            call = stmt.value.value if isinstance(stmt.value, ast.Await) else stmt.value
            slots = {}
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name):
                slots = self.returns.get(call.func.id) or {}
            for i, el in enumerate(stmt.targets[0].elts):
                if not isinstance(el, ast.Name):
                    continue
                cand = slots.get(i) or set()
                if len(cand) == 1:
                    env[el.id] = next(iter(cand))
                elif el.id in env:
                    del env[el.id]

        # Record reads anywhere in the statement, and note string constants assigned to
        # names so a url built in two steps still resolves to its host.
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
            tgt = stmt.targets[0]
            val = stmt.value
            if isinstance(tgt, ast.Name):
                # Remember plain string values, for `hp_url = "https://..."`.
                texts = []
                if isinstance(val, ast.Constant) and isinstance(val.value, str):
                    texts = [val.value]
                elif isinstance(val, ast.BinOp):
                    seg = ast.get_source_segment(self.src, val) or ""
                    texts = [seg]
                if texts:
                    env["__str__" + tgt.id] = tuple(texts)
                got = self.resolve(val, env)
                if got:
                    env[tgt.id] = got
                elif tgt.id in env:
                    del env[tgt.id]
        elif isinstance(stmt, ast.AugAssign) and isinstance(stmt.target, ast.Name):
            prev = env.get("__str__" + stmt.target.id, ())
            seg = ast.get_source_segment(self.src, stmt.value) or ""
            env["__str__" + stmt.target.id] = tuple(prev) + (seg,)

        if isinstance(stmt, (ast.For, ast.AsyncFor)):
            got = self.resolve(stmt.iter, env)
            if got and isinstance(stmt.target, ast.Name):
                env[stmt.target.id] = (got[0], got[1] + (ELEM,))
            # `for url, headers, name in _onchain_sources(...)`: the URLs are built from
            # literals inside that helper, so the names it yields carry those hosts.
            # Attribution by evidence -- the literals really are in that function -- and
            # it is how the two GeckoTerminal-shaped fetches stop being untraced.
            if (isinstance(stmt.iter, ast.Call) and isinstance(stmt.iter.func, ast.Name)
                    and stmt.iter.func.id in self.funcs
                    and isinstance(stmt.target, ast.Tuple)):
                texts = tuple(n.value for n in ast.walk(self.funcs[stmt.iter.func.id])
                              if isinstance(n, ast.Constant)
                              and isinstance(n.value, str))
                for el in stmt.target.elts:
                    if isinstance(el, ast.Name):
                        env["__str__" + el.id] = texts
            self._expressions(stmt.iter, env)
            self._walk(stmt.body, env, fname)
            self._walk(stmt.orelse, env, fname)
            return
        if isinstance(stmt, (ast.If, ast.While)):
            self._expressions(stmt.test, env)
            # Branch bodies get a copy, and only names the branch *introduced* merge back.
            # Walking them in the live env let a branch-local rebinding
            # (`hp = dict(hp, ...)` inside `if _sim_never_ran(hp):`) unbind `hp` for
            # everything after the branch, which is how holderAnalysis went unwatched.
            for body in (stmt.body, stmt.orelse):
                inner = dict(env)
                self._walk(body, inner, fname)
                for k, v in inner.items():
                    if k not in env:
                        env[k] = v
            return
        if isinstance(stmt, ast.Try):
            self._walk(stmt.body, env, fname)
            for h in stmt.handlers:
                self._walk(h.body, env, fname)
            self._walk(stmt.orelse, env, fname)
            self._walk(stmt.finalbody, env, fname)
            return
        if isinstance(stmt, (ast.With, ast.AsyncWith)):
            self._walk(stmt.body, env, fname)
            return
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # A closure sees the enclosing names; analyse it with the same env.
            self._walk(stmt.body, dict(env), stmt.name)
            return

        for node in ast.walk(stmt):
            self._expressions(node, env, shallow=True)

    def _expressions(self, node, env, shallow=False):
        """Resolve every sub-expression so reads get recorded."""
        stack = [node] if shallow else list(ast.walk(node))
        for n in stack:
            if isinstance(n, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
                inner = dict(env)
                for gen in n.generators:
                    got = self.resolve(gen.iter, inner)
                    if got and isinstance(gen.target, ast.Name):
                        inner[gen.target.id] = (got[0], got[1] + (ELEM,))
                    for cond in gen.ifs:
                        self._expressions(cond, inner)
                for part in ((n.key, n.value) if isinstance(n, ast.DictComp) else (n.elt,)):
                    self._expressions(part, inner)
                continue
            if isinstance(n, ast.Compare) and any(isinstance(o, ast.In) for o in n.ops):
                if isinstance(n.left, ast.Constant) and isinstance(n.left.value, str):
                    base = self.resolve(n.comparators[0], env)
                    if base:
                        self._record(base[0], base[1] + (n.left.value,), n.lineno)
            if isinstance(n, ast.Call):
                self.resolve(n, env)
                self._bind_call_args(n, env)
            elif isinstance(n, ast.Subscript):
                self.resolve(n, env)

    # ---------------------------------------------------------------- driver

    def _facts(self):
        return (sum(len(v) for v in self.reads.values()),
                sum(len(s) for p in self.bindings.values() for s in p.values()),
                sum(len(s) for r in self.returns.values() for s in r.values()))

    def run(self, max_rounds=12):
        """Analyse every function until nothing new is learned.

        Facts only ever accumulate -- a read, a parameter binding, a return slot -- so
        the count is monotonic and the loop terminates. Whole rounds rather than a
        worklist because a fact can travel backwards here: `_load_pairs` teaches `assess`
        what its return holds, and `assess` then teaches `_pick_best` and
        `_liquidity_signals`, which were defined long before either.
        """
        self.rounds = 0
        for _ in range(max_rounds):
            before = self._facts()
            self.rounds += 1
            for name, fn in self.funcs.items():
                combos = [{}]
                bound = self.bindings.get(name) or {}
                if bound:
                    combos = [{pname: v} for pname, vals in bound.items() for v in vals]
                for env in combos:
                    self._walk(fn.body, dict(env), name)
            if self._facts() == before:
                return self
        # Not reached in practice; if it ever is, the table is incomplete and saying so
        # is the whole point of this file.
        self.incomplete = True
        return self

    def urls(self):
        """Every upstream URL template the engine builds, source -> sorted templates.

        The field table answers "what do we read"; this answers "from where". A new
        endpoint added to the engine and probed by nothing is the same blind spot one
        level up, so the contract test compares this against the endpoints it knows how
        to probe, in both directions.
        """
        out = {}
        for node in ast.walk(self.tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            v = node.value
            if not v.startswith("http"):
                continue
            host = v.split("/")[2] if v.count("/") >= 2 else ""
            name = self.hosts.get(host)
            if name:
                out.setdefault(_SHAPE_ALIAS.get(name, name), set()).add(v)
        return {k: sorted(v) for k, v in out.items()}

    def table(self):
        out = {}
        for source in sorted(self.reads):
            paths = self.reads[source]
            out[source] = {".".join(p): sorted(paths[p]) for p in sorted(paths)}
        return out


def build():
    return Fields().run()


def main(argv):
    f = build()
    table = f.table()
    if "--json" in argv:
        print(json.dumps(table, indent=1, sort_keys=True))
        return 0
    total = sum(len(v) for v in table.values())
    print("upstream JSON paths src/risk.py reads: %d across %d sources"
          % (total, len(table)))
    for source in sorted(table):
        print("\n%s  (%d paths)" % (source, len(table[source])))
        for path in sorted(table[source]):
            lines = table[source][path]
            shown = ",".join(str(n) for n in lines[:4])
            if len(lines) > 4:
                shown += ",+%d" % (len(lines) - 4)
            print("   %-58s risk.py:%s" % (path, shown))
    if "--report" in argv:
        print("\nuntraced fetch sites: %d" % len(f.untraced))
        for u in f.untraced:
            print("   risk.py:%s  %s" % (u["line"], (u["code"] or "")[:90]))
        print("\nvalue crossings into other functions: %d" % len(f.crossings))
        for c in sorted(f.crossings, key=lambda c: c["line"]):
            print("   risk.py:%-5s %s -> %s(%s)"
                  % (c["line"], c["source"] + ":" + c["path"], c["into"], c["param"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
