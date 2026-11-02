# ADR-0003: Separate historical W40 validation from current production

Status: accepted design and exact implementation scope, 2026-11-02. Implementation,
runtime and release acceptance remain separate. The Owner confirms this specific
source/test-context transition after two independent design-review rounds.

## Context

The existing native adapter intentionally fixes entire canonical source files,
including the production engine. A production price repair changes that identity
and correctly triggers source_drift. Updating the frozen hash or silently changing
an old test cannot reconcile historical provenance with an evolving production
engine. A source fixture also does not prove a historical execution.

## Decision

Keep src/risk.py as the sole production engine. Introduce a bounded, explicit
historical verification domain with an exact accepted source commit/tree, closed
member paths/modes/blobs/raw profiles and the original canonical source pins.
Only fixed existing Git objects may supply it; missing objects refuse, never fetch.
Both git-lf and observed-windows-crlf are explicit, complete byte identities. No
host-OS default, latest-source selection or failed-verification fallback is allowed.

The identity slice provides source verification and the existing predicates on
actually loaded current-runtime code in an isolated source view. It introduces no
operational study, collection, acquisition, recovery or scheduler API. Source
fixture, this actual loaded runtime, historical record tuple and historical
interpreter have independent states and evidence. The first two cannot establish
the latter two; historical_execution_qualified remains false in this slice.

A later independently qualified dispatch slice may run both complete original
native runners in that exact V1 domain, including all assertions, descendants,
workflow checks and datetime tests. Every fixed historical command explicitly
selects git-lf. The complete current dataset test remains, with an additional
complete historical dataset run. Current-workflow checks must prove today's real
dispatch and exits; the original workflow assertion then proves history only.

Accept that a repaired production V2 has no positive compatibility with this
historical native adapter. Current production regressions validate current service
behavior; the unmodified native predicates still reject actual repaired V2 source.
Negative source rejection is not a successful V2 native run. Preserve the explicit
V1-only/current responsibility map and add a separately named test requirement if
a current production obligation lacks a contemporary check.

The generic evidence core remains unchanged: local raw bindings are not a global
role/version registry. Future operational callers need their own accepted adoption
of the outer identity boundary; a version label alone grants no qualification.

## Consequences and limits

This explicitly changes historical test-context ownership, not old original bytes,
plans, labels, thresholds, windows, failure states or scientific conclusions. Full
source/runtime checks, meaningful tests-first evidence, independent functional and
applicable adversarial review, actual configured gates and normal release evidence
remain mandatory for each slice. Current interpreter provenance cannot fill an
unknown historical interpreter.

T047/T049/T050 remain held. This decision neither repeats nor replaces their
incomplete mandatory security verdict and activates none of their APIs. The old
partial T068 candidate stays unpublished. Its two price defects can resume only
after the source identity and dispatch implementations themselves qualify, followed
by separate unchanged-witness repairs and current production acceptance.

Rollback is by normal commits with evidence retained. After production repairs,
restore the accepted production parent before removing historical dispatch; do not
rewrite history or make the original source guard accept arbitrary versions.
