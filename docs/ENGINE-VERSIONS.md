# Explicit historical source-fixture identity

`tools/engine_versions.py` verifies one fixed W40 source fixture and its actually loaded
code in the present Python interpreter. It does not qualify a historical study, migrate
an old plan, run a native collector, or change the sole production engine in `src/risk.py`.

## Commands

```
python tools/engine_versions.py verify-source w40-v1-e3ec46a git-lf
python tools/engine_versions.py verify-source w40-v1-e3ec46a observed-windows-crlf
```

The profile is mandatory. Default/help performs no verification. Missing/unknown contract
or profile refuses; host OS, checkout line endings and failures cannot select another
profile. `legacy-test`, collect, recover, report, study, pilot and scheduler are unsupported.
No arbitrary test/source path, executable, commit, old record or interpreter input exists.
Future historical-test dispatch is a separate task; existing workflow commands are unchanged.

## Source and execution checks

The reviewed registry pins a single commit/tree, role and ordered complete source closure.
The helper pins the registry's canonical SHA256, so changing a member, hash, mode, role,
profile or extra key requires another explicit reviewed source change. Duplicate JSON keys
and over-limit registry data refuse. The two profiles have independent complete raw-byte
hashes and sizes; canonical CRLF-to-LF equality alone grants no identity.

Read-only Git plumbing checks exact tree membership, blob mode/type/size, raw SHA256 and
Git object ID. Object replacement and lazy object fetching are disabled. Missing objects
refuse locally; no fetch, clone, ref update, shell or open-ended source acquisition occurs.
Fixed engineering limits are declared by `REGISTRY_CAP`, `MEMBER_CAP`, `FILE_CAP` and
`TOTAL_CAP`. Hitting a limit refuses, never truncates a source set.

A temporary external source view preserves the original relative layout. All members are
new regular files, not writable hardlinks; path aliases/reparse points and unexpected
members refuse. The fixed `.git` marker preserves the old raw-storage boundary and does
not make this a Git checkout. The complete selected raw/canonical identity is checked
before use and again on success or failure, then the private temporary view is removed.
No whole repository/dependency copy is created. Temporary storage follows the process's
external TEMP configuration and is refused inside a Git checkout.

A fresh child uses `-I -S -B`: no parent module state, PYTHONPATH, site packages or bytecode.
It checks the actual loaded original native/core/risk paths, original `code_manifest()`
and `engine_bindings()` (code filenames, compiled functions, defaults, closures and RPC
roots). Socket and descendant-process actions are refused in this verification child.
No engine assessment, acquisition or native test runner executes. Its interpreter hash,
version/cache tag, source manifest and predicate evidence are recorded as a digest.

The child also validates an original synthetic empty-source core plan without changing its
bytes, and observes original `source_drift` rejection for the opposite raw profile and an
unknown engine binding. Its `source_commit` remains a declaration, distinct from the
registry's verified `engine_source_commit`. Synthetic checks do not qualify an actual
historical record. The unchanged generic core has no global role/registry enforcement;
identical bytes alone do not make a production-role request eligible for this fixture.

## Receipt scope

Every verification/refusal receipt uses `engine-version-qualification-v1`. Invocation
status describes this request only. Contract/source identity, explicit requested/selected
profile, fixed command vector, actual wrapper exit and four separate result layers remain
visible. Unknown caller strings are not echoed: unrecognized profile/contract values use
null identity fields and a fixed refusal category. Receipt text contains hashes/fixed
categories, not private host paths or arbitrary exception prose.

| Result | What a pass proves | What remains unproved |
|---|---|---|
| `source_fixture` | Complete selected source bytes match the accepted fixture. | Any historical execution of those bytes. |
| `loaded_runtime` | This child loaded matching code in the present interpreter and passed original predicates. | The interpreter used by an old study, or successful V2 native interoperation. |
| `historical_record_tuple` | Not evaluated by these commands; no historical-record input is accepted. | Original study raw tuple/artifact qualification. |
| `historical_interpreter` | Not evaluated by these commands. | Historical interpreter/runtime provenance. |

Historical layers stay `not_evaluated` with fixed reasons and empty evidence. Missing source
objects/runtime may be `unavailable`; examined mismatches are `failed`, unexamined dimensions
are not fabricated failures. `historical_execution_qualified` is always false. Legacy tests
are `not_run`, and positive production-V2 compatibility with the historical native adapter
is `unsupported`. No fixture/runtime success promotes either historical layer.

## Test responsibilities and holds

This slice preserves the existing native commands and all old assertions. A later explicit
dispatch task must run the complete old native GET/RPC/cache/context and datetime contracts
in V1, retain the current dataset runner plus the entire historical dataset version, and
independently verify today's actual command/child execution. Those native tests are V1-only;
current production risk/MCP/HTTP/benchmark/numeric regressions retain their distinct duties.
Repaired V2 must still be rejected by the original native source predicates. Rejection is
a negative guarantee and not positive V2 native execution evidence.

An internal pure guard checks all four result layers before returning a verification and
again before emitting a CLI receipt. It rejects historical promotion, a passed runtime
without a passed fixture, copied fixture/runtime evidence, malformed hashes/reasons and
fabricated evidence on unexamined layers. Synthetic contract tests preserve known-absent
historical states as `unavailable` and inconclusive states as `unknown`; these tests do
not introduce a historical input or operation. Real commands still leave both historical
layers `not_evaluated`. Rejected result shapes produce a fixed sanitized refusal/nonzero,
with no positive historical qualification.

No T047/T049/T050 archive/seed/runtime/scheduler API or incomplete mandatory verdict is
adopted or replaced. Original research sources, windows, rules, labels, thresholds, originals,
failed/unknown states and closed conclusions remain unchanged. Prices and the old partial
T068 candidate are outside this source-identity slice. Any future operational adopter,
production repair or release needs its own assigned contract and actual acceptance.
