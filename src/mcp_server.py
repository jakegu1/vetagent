"""mcp_server.py — a minimal MCP streamable-http handler.

Hand-rolled rather than built on the official mcp SDK because:
- Cloudflare Python Workers (Pyodide) is a compatibility gamble with heavy SDKs
  (pydantic/uvicorn/httpx)
- we expose exactly 3 tools, so routing JSON-RPC by hand is smaller, faster and steadier
- streamable-http is really just one POST endpoint answering in JSON-RPC 2.0

Lifecycle:
- initialize                 -> protocol version + capabilities + serverInfo
- notifications/initialized  -> a notification: no id, no response
- tools/list                 -> tool list (name/description/inputSchema/outputSchema)
- tools/call                 -> run the tool, return content + structuredContent
- anything else              -> a top-level JSON-RPC error (not stuffed into result)
"""

import contextvars
import json

import risk  # reuse the pure-Python risk engine (risk.py)
import liquidity_comparison

PROTOCOL_VERSION = "2025-06-18"
SUPPORTED_PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")

# Standard JSON-RPC error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

_SIGNAL_SCHEMA = {
    "type": "object",
    "properties": {
        "severity": {"type": "string", "enum": ["ok", "info", "warn", "critical", "fatal"]},
        "name": {"type": "string"},
        "message": {"type": "string"},
        "category": {"type": "string"},
    },
}

_CHECKED_AT = {"type": "string", "description": "When this answer was made, ISO-8601 UTC."}

_COMPARISON_CONTEXT_SCHEMA = {
    "type": "array", "maxItems": 8,
    "description": "Optional client-carried observations, at most 8 and 8192 UTF-8 JSON bytes. "
                   "Pass a prior comparison_context unchanged, or [] to start. These are client "
                   "observations, not signed service records. An identified drained observation "
                   "has a numeric USD estimate of zero. No server history is stored.",
    "items": {
        "type": "object", "additionalProperties": False,
        "required": list(liquidity_comparison.OBSERVATION_FIELDS),
        "properties": {
            "status": {"type": "string", "enum": ["ok", "drained"]},
            "address": {"type": "string", "maxLength": 66},
            "best_pair_chain": {"type": "string", "enum": list(liquidity_comparison._CHAINS)},
            "best_pair_address": {"type": "string", "maxLength": 66},
            "source": {"type": "string", "enum": list(liquidity_comparison._SOURCES)},
            "checked_at": {"type": "string", "maxLength": 32},
            "liquidity_usd": {"type": "number", "minimum": 0},
        },
        "if": {"properties": {"status": {"const": "drained"}}},
        "then": {"properties": {"liquidity_usd": {"const": 0}}},
    },
}

_COMPARISON_SCHEMA = {
    "type": "object",
    "description": "Returned when comparison_context is supplied. Uses the latest strictly "
                   "earlier comparable client observation of this token, chain, complete pool ID "
                   "and provider. USD estimate change is not a reserve flow or executable depth. "
                   "Reply times can cover cached source data. A changed pool_transition and "
                   "baseline_is_latest_observation=false disclose a return to an older pool baseline.",
    "required": ["status", "baseline_origin"],
    "properties": {
        "status": {"type": "string", "enum": ["compared", "not_comparable"]},
        "reason": {"type": "string"},
        "baseline_origin": {"type": "string", "enum": ["client_observation"]},
        "before_checked_at": _CHECKED_AT, "after_checked_at": _CHECKED_AT,
        "before_usd": {"type": "number"}, "after_usd": {"type": "number"},
        "change_usd": {"type": "number"},
        "baseline_is_latest_observation": {"type": "boolean"},
        "context_evicted": {"type": "integer", "minimum": 1},
        "nonprior_observations": {"type": "integer", "minimum": 1,
            "description": "Client observations at or after the current reply time; excluded as baselines."},
        "pool_transition": {"type": "object", "properties": {
            "status": {"type": "string", "enum": ["changed", "unchanged", "ambiguous"]},
            "previous_pool_address": {"type": "string"}, "previous_checked_at": _CHECKED_AT,
        }},
    },
}

_TRADE_ACTIVITY_SCHEMA = {
    "type": "object",
    "description": "Buys plus sells for this pool in the last hour and the five hours "
                   "before it, as of the listing observation. Omitted when the provider's "
                   "counts are missing or inconsistent.",
    "properties": {
        "trades_last_1h": {"type": "integer", "minimum": 0},
        "trades_prior_5h": {"type": "integer", "minimum": 0},
    },
    "required": ["trades_last_1h", "trades_prior_5h"],
}

_OWNER_POWERS_SCHEMA = {
    "type": "object",
    "description": "Optional, incomplete bytecode observations; not a current-permission audit.",
    "properties": {
        "evidence_basis": {
            "type": "string", "enum": ["bytecode_selector_match"],
            "description": "Matched selectors are code indicators, not verified callable actions "
                           "or evidence of present control.",
        },
        "matched_selectors": {
            "type": "object",
            "description": "Existing capability labels mapped to the unique lowercase "
                           "eight-hex selectors matched in the observed bytecode.",
            "additionalProperties": {
                "type": "array", "uniqueItems": True,
                "items": {"type": "string", "pattern": "^[0-9a-f]{8}$", "maxLength": 8},
            },
        },
        "current_authority": {
            "type": "string", "enum": ["not_checked"],
            "description": "Authority, activation and reachability were not observed.",
        },
        "powers": {
            "type": "array", "items": {"type": "string"},
            "description": "Legacy capability labels for code indicators, not verified "
                           "actions or current control.",
        },
        "found_none": {
            "type": "boolean",
            "description": "True means this incomplete scan found no mapped selector. "
                           "It does not prove absence of permissions.",
        },
        "scan_is_incomplete": {
            "type": "boolean", "description": "The bytecode scan does not cover every permission mechanism.",
        },
        "is_proxy": {
            "type": "boolean",
            "description": "Proxy-wrapper indicator; wrapper observations do not establish "
                           "implementation permissions.",
        },
        "selectors_dispatched": {
            "type": "integer", "minimum": 0,
            "description": "Number of dispatch selectors recognized by the incomplete scan.",
        },
        "bytecode_bytes": {"type": "integer", "minimum": 0, "description": "Size of the observed bytecode."},
        "unavailable": {
            "type": "string",
            "description": "Reason for a failed or unusable bytecode observation, not a completed no-match scan.",
        },
    },
}

_POOL_SCOPE_DETAILS_SCHEMA = {
    "type": "object",
    "description": "Verbose-only correspondence facts for the final displayed market and adopted "
                   "simulator response. The market and reported IDs are complete when available.",
    "properties": {
        "reason": {"type": ["string", "null"],
                   "enum": [None, "chain_conflict", "pool_conflict", "invalid_response", "no_market",
                            "no_simulation", "invalid_pool", "missing_pool", "missing_chain"],
                   "description": "Why correspondence is unknown; null for same or different."},
        "market_pool": {"type": ["string", "null"], "maxLength": 66,
                        "description": "Complete validated pool ID of the final displayed market."},
        "market_chain": {"type": ["string", "null"], "description": "Known chain of the final displayed market."},
        "adopted_response": {"type": "string", "enum": ["default", "retry", "none"],
                             "description": "Which simulator response the existing engine retained."},
        "policy_chain": {"type": ["string", "null"],
                         "description": "Existing engine validation/coverage context, not an observed chain."},
        "requested_chain": {"type": ["string", "null"],
                            "description": "Chain actually encoded in the simulator request, not a source observation."},
        "requested_pool": {"type": ["string", "null"],
                           "description": "Explicit pool request for the adopted response; never fills a missing report."},
        "reported_chain": {"type": ["string", "null"],
                           "description": "Known, consistent chain declared by the adopted response; null when unknown."},
        "reported_pool": {"type": ["string", "null"],
                          "description": "Valid, consistent 20-byte EVM venue declared by the adopted response."},
        "retry": {"type": "object", "description": "Only present when a pool-scoped retry occurred.",
                  "properties": {
                      "requested_pool": {"type": ["string", "null"]},
                      "reported_chain": {"type": ["string", "null"]},
                      "reported_pool": {"type": ["string", "null"]},
                      "accepted": {"type": "boolean", "description": "Whether the retry replaced the default response."},
                  }},
    },
}

_NETWORK_SELECTION_SCHEMA = {
    "type": "object",
    "description": "Requested network, observed market scope and outcome of the extra DexScreener lookup. "
                   "An empty listing differs from an unconfirmed lookup.",
    "required": ["requested_chain", "status", "lookup"],
    "properties": {
        "requested_chain": {"type": "string", "enum": list(liquidity_comparison._CHAINS)},
        "returned_chain": {"type": "string"},
        "status": {"type": "string", "enum": ["matched", "different", "unresolved"]},
        "lookup": {"type": "string", "enum": ["found", "empty", "unconfirmed", "incompatible_address"]},
    },
}

_ASSESS_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "address": {"type": "string"},
        "risk_level": {
            "type": "string",
            "enum": ["low", "medium", "high", "unknown"],
            "description": ("'unknown' means a critical check could not be completed. "
                            "It is NOT a low-risk result and must not justify a trade."),
        },
        "risk_score": {"type": "integer", "description": "0-100; higher is more dangerous"},
        "confidence": {
            "type": "string", "enum": ["low", "medium", "high"],
            "description": "How complete the input data was — not how safe the token is.",
        },
        "signals": {"type": "array", "items": _SIGNAL_SCHEMA},
        "recommendation": {"type": "string"},
        "network_selection": _NETWORK_SELECTION_SCHEMA,
        "evidence": {"type": "object", "properties": {
            "chain_searched": {"type": "string", "description": "Assessment search scope. "
                               "It can come from the request hint when no market was observed."},
            "best_pair": {"type": "object", "properties": {
                "pool_id": {"type": "string", "maxLength": 66,
                            "description": "Complete validated ID of the final displayed market, "
                                           "available in compact and verbose replies. EVM IDs are "
                                           "20 or 32 bytes; Solana IDs decode to 32 bytes and retain case."},
            }},
            "owner_powers": _OWNER_POWERS_SCHEMA,
            "pool_link": {"type": "string", "enum": ["same", "different", "unknown"],
                           "description": "Correspondence between the final displayed market and the "
                                          "source-reported venue of the adopted simulator response. "
                                          "same/different compare those identities; unknown means the comparison "
                                          "could not be established. The discovered or alerted pool is not compared. "
                                          "Even same does not establish simulation success, safety, or "
                                          "wallet/amount-specific executability."},
            "pool_link_details": _POOL_SCOPE_DETAILS_SCHEMA,
            "max_sell": {
                "type": "object",
                "description": "Optional per-sell cap reported by the adopted successful Honeypot.is simulation. "
                               "Amount is an exact nonnegative uint256 decimal string in smallest units of the "
                               "assessed token, not the paired asset. A displayed market is required. "
                               "Missing does not mean unlimited. "
                               "pool_link qualifies correspondence to the displayed market; different/unknown "
                               "does not establish its cap. This is not a wallet-specific execution guarantee.",
                "required": ["source", "scope", "amount", "unit", "pool_link"],
                "properties": {
                    "source": {"type": "string", "enum": ["honeypot.is"]},
                    "scope": {"type": "string", "enum": ["simulated_transaction"]},
                    "amount": {"type": "string", "maxLength": 78},
                    "unit": {"type": "string", "enum": ["token_smallest_unit"]},
                    "pool_link": {"type": "string", "enum": ["same", "different", "unknown"]},
                },
            },
        }},
        "driver": {"type": ["object", "null"],
                   "description": "The signal that decided the verdict: {name, category}. "
                                  "null when nothing above ok fired."},
        "checked_at": _CHECKED_AT,
        "evidence_max_age_seconds": {
            "type": "integer",
            "description": "Request-level upper bound on local cache residence observed when JSON is "
                           "returned from cache and usable cached bytecode is reused during the request. "
                           "JSON later rejected or replaced still "
                           "counts; this is not the precise age of only the finally adopted evidence. "
                           "Positive fractions round up to whole seconds; negative clock skew counts "
                           "as zero. Bytecode may use a longer cache TTL. "
                           "Zero means no positive local cache residence was recorded; it does not "
                           "prove that upstream observations are live or currently executable."},
        "unknown_kind": {"type": "string", "enum": ["infrastructure", "coverage", "mixed"],
                         "description": "Present only when risk_level is unknown."},
        "next_action": {"type": "string", "enum": ["retry", "abstain"]},
        "retry_after_seconds": {"type": "integer"},
    },
    "required": ["address", "risk_level", "risk_score", "confidence", "signals"],
}

TOOLS = [
    {
        "name": "assess_token_risk",
        "title": "Assess Token Risk",
        "description": (
            "Safety check to run BEFORE buying, holding, or recommending a token. "
            "Returns an actionable verdict (low / medium / high / unknown), a 0-100 risk "
            "score, and the individual signals behind it.\n"
            "Covers on every chain: liquidity depth, trading-pair age, cross-chain "
            "presence, same-ticker impersonation.\n"
            "Covers on Ethereum, BSC and Base only: sell simulation (honeypot detection, "
            "buy/sell/transfer taxes), whether the contract is open source, and the "
            "aggregate verdicts of upstream security scanners.\n"
            "Covers on Solana: the mint/freeze authority, the RugCheck score, and the "
            "SPL Token-2022 extension block -- non-transferable, frozen-by-default, "
            "transfer fee (with its cap), permanent delegate, transfer hook, pausable, "
            "close authority, scaled balances and interest-bearing balances. Every "
            "other extension the report carries is named in the answer with the reason "
            "it is not scored, so silence about one means it was considered, not that "
            "it went unread.\n"
            "A compatible chain_hint is a network preference. If the initial market listing "
            "contains only other networks, VetAgent checks the preferred network first. "
            "When a different market is used, network_selection and the recommendation "
            "identify the scope of the rating. That rating does not cover the requested network.\n"
            "No sell simulation runs on Solana, nor on the four other EVM chains accepted "
            "as a chain_hint (polygon, arbitrum, optimism, avalanche): nothing there tests "
            "whether a holder can sell, so the answer comes back 'unknown' rather than "
            "'low'. "
            "On Solana, holder concentration is reported only when RugCheck supplies a holder list; missing lists remain a coverage gap. "
            "Identified liquidity-pool accounts are excluded when matching identities are available; "
            "otherwise the reported share may include pools. This check is unavailable on EVM.\n"
            "IMPORTANT: risk_level 'unknown' means a critical check could not be completed. "
            "It is NOT a low-risk result and must not be used to justify a trade; "
            "evidence.data_gaps lists exactly what was missing, and unknown_kind says whose "
            "gap it is: 'infrastructure' and 'mixed' mean an upstream of ours failed and come "
            "with next_action 'retry' and retry_after_seconds (in a 'mixed' answer the rest "
            "was worked out without that upstream, so the retry can change any of it); "
            "'coverage' comes with 'abstain'. "
            "'confidence' measures how "
            "complete the input data was, not how safe the token is.\n"
            "evidence.pool_link compares the final displayed market with the source-reported "
            "pool of the adopted simulator response. same/different describe those identities; "
            "unknown means the comparison could not be established. This does not compare a "
            "discovered or alerted pool, and same does not establish a successful simulation.\n"
            "Reports observable on-chain risk only. Not financial advice, does not size "
            "positions, and cannot see off-chain risk such as team behaviour, social "
            "engineering, or a rug executed through governance. Treat 'low' as 'no fatal "
            "signal found in the checks that ran', never as 'safe to buy'."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "address": {"type": "string",
                            "description": "Token contract address: ERC-20 (0x + 40 hex) or Solana (base58)"},
                "chain_hint": {"type": "string",
                               "description": "Optional chain name (ethereum / bsc / base / polygon / "
                                              "arbitrum / solana). Strongly recommended: Ethereum forks "
                                              "such as PulseChain inherit contract addresses, so the same "
                                              "address exists on several chains at wildly different prices. "
                                              "Without it, an answer covers one chain -- the one holding "
                                              "the most depth -- and names it."},
                "verbose": {"type": "boolean", "default": False,
                            "description": "Return full upstream evidence. Off by default to save tokens."},
            },
            "required": ["address"],
        },
        "outputSchema": _ASSESS_OUTPUT_SCHEMA,
        "annotations": {"readOnlyHint": True, "openWorldHint": True,
                        "destructiveHint": False, "idempotentHint": True},
    },
    {
        "name": "get_token_liquidity",
        "title": "Get Token Liquidity",
        "description": (
            "Liquidity snapshot for a token's primary trading pair: price, 24h volume, "
            "pair count and the chains it trades on. Optional trade_activity reports buys plus sells "
            "in the last hour and the preceding five hours from that selected pool's raw integer counts. "
            "Missing counts are omitted; observed zeros remain zero.\n"
            "chain_hint is a network preference. If only other networks appear in the initial "
            "listing, VetAgent checks the requested network before returning another market. "
            "When present, network_selection explains the requested lookup and returned scope. "
            "A market from another network is reported separately from any requested-network change.\n"
            "For native change estimates, pass the previous comparison_context unchanged "
            "(or [] to start). The server selects the latest comparable client observation with "
            "the same token, chain, complete pool ID and provider, and separately discloses "
            "a change from the most recent selected pool. It never subtracts different pools or "
            "providers, and refuses stale fallback. Context is bounded client observation, not "
            "signed service history. No server history is stored. Legacy calls remain snapshots. "
            "The local examples/liquidity_compare.py CLI remains available for saved replies. "
            "checked_at is reply time; source data may be cached.\n"
            "Check 'status' before using the numbers. 'ok' means usable upstream data, "
            "not independently verified reserves or executable sell depth. "
            "The optional liquidity_reserve_check marker says 'not_checkable' when a "
            "positive selected estimate has no computable reserve cap. A missing marker "
            "never asserts that reserves, prices or an exit trade were independently verified. "
            "'unavailable' means the upstream request failed, which does NOT mean the "
            "token has no liquidity. 'not_found' means no trading pair exists for this "
            "address at all. 'unpriced' means pairs exist but no source has costed them, "
            "so liquidity_usd is null and the depth is unknown -- this is NOT a report of "
            "zero liquidity. 'drained' means the USD liquidity estimates for the returned market "
            "scope are zero, including estimates capped by reserve evidence. A drained result "
            "with a complete pool ID, chain and provider can participate in a same-pool recheck. "
            "This identity is included only for a single pool whose provider reported zero."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "address": {"type": "string", "description": "Token contract address"},
                "chain_hint": {"type": "string",
                               "description": "Optional network preference; inspect network_selection if returned."},
                "comparison_context": _COMPARISON_CONTEXT_SCHEMA,
            },
            "required": ["address"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "address": {"type": "string"},
                "status": {"type": "string",
                           "enum": ["ok", "not_found", "unpriced", "drained",
                                    "unavailable"]},
                "price_usd": {"type": ["number", "null"]},
                "source": {"type": "string", "description": "Liquidity data provider, not the trading venue."},
                "best_pair_chain": {"type": "string"},
                "best_pair_dex": {"type": "string", "description": "Selected market's trading venue."},
                "network_selection": _NETWORK_SELECTION_SCHEMA,
                "best_pair_address": {
                    "type": "string",
                    "description": "Optional complete validated selected-pool ID on ok results: "
                                   "20-byte/32-byte EVM hex or 32-byte Solana base58, preserving case. "
                                   "Also included on an identified single-pool drained result. "
                                   "Omitted for invalid or conflicting identity. Old truncated display IDs "
                                   "cannot establish exact cross-response identity. No sell simulation runs."},
                "trade_activity": _TRADE_ACTIVITY_SCHEMA,
                "comparison_context": _COMPARISON_CONTEXT_SCHEMA,
                "comparison": _COMPARISON_SCHEMA,
                "liquidity_usd": {"type": ["number", "null"]},
                "liquidity_reserve_check": {
                    "type": "string", "enum": ["not_checkable"],
                    "description": "The positive upstream estimate was retained, but its "
                                   "reserve amounts could not be checked. Absence of this "
                                   "marker makes no verification claim."},
                "volume_24h_usd": {"type": ["number", "null"]},
                "pairs_total": {"type": "integer"},
                "checked_at": {"type": "string",
                               "description": "Reply time in ISO-8601 UTC, not the source observation time. "
                                              "Source data may be cached."},
                "served_stale": {
                    "type": "array",
                    "description": "Present only when an upstream was unreachable and "
                                   "this answer used cached data. Each entry names the "
                                   "source and how many seconds old it was.",
                    "items": {"type": "object"}},
                "chains": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["address", "status"],
        },
        "annotations": {"readOnlyHint": True, "openWorldHint": True,
                        "destructiveHint": False, "idempotentHint": True},
    },
    {
        "name": "find_new_hot_pools",
        "title": "Find New Hot Pools",
        "description": (
            "Scan a chain for the newest and most active trading pools, returning name, "
            "token_address, price, liquidity, 24h volume and pool age.\n"
            "For active-pool queries, use listing=trending to select only the original trending "
            "listing before the limit. The default mixed view puts new pools first. Inspect "
            "pool_age_days, current liquidity and volume; trending, age and one liquidity "
            "observation do not establish sustained funding, exit availability or safety.\n"
            "Discovery only. New pools carry inherently high risk and appearing here is NOT "
            "a safety endorsement. Pass assessment_args unchanged to assess_token_risk when "
            "present; when absent, do not guess an address or chain. This preserves a chain "
            "preference, not a strict chain lock: the engine may report another observed chain. "
            "Before using the result for this target, require evidence.chain_searched to match "
            "assessment_args.chain_hint. Assessment may select a different primary pool. It does not certify "
            "the exact discovered pool or authorize a trade. evidence.pool_link compares the final "
            "displayed market with the source-reported pool of the adopted simulator response, "
            "not the discovered or alerted pool. same does not prove that the discovered pool "
            "was simulated or that any simulation succeeded."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "chain": {"type": "string", "default": "solana",
                          "description": "Chain name, e.g. solana / ethereum / base / bsc"},
                "limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50},
                "listing": {"type": "string", "enum": ["mixed", "trending"], "default": "mixed",
                            "description": "mixed scans new then trending; trending scans only that listing."},
            },
        },
        "annotations": {"readOnlyHint": True, "openWorldHint": True,
                        "destructiveHint": False, "idempotentHint": False},
        "outputSchema": {
            "type": "object",
            "description":
                "Discovery only, never an endorsement. Use assessment_args when present to "
                "preserve the discovered chain preference; do not guess when it is absent. "
                "Require returned evidence.chain_searched to match its chain_hint before using the result.",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["ok", "partial"],
                    "description":
                        "Completeness only, in the default mixed view: ok means both listings were observed; "
                        "partial means only one usable listing was observed. This is "
                        "not a token risk verdict or a safety endorsement. With listing=trending, "
                        "ok means the selected listing was observed, including an empty list; new is not requested.",
                },
                "listing": {"type": "string", "enum": ["trending"],
                            "description": "Present only for the explicitly selected trending scope; absent for mixed."},
                "chain": {"type": "string"},
                "network": {"type": "string",
                            "description": "The upstream's own name for the chain, "
                                           "which differs from `chain` (eth vs ethereum)."},
                "count": {
                    "type": "integer",
                    "description":
                        "How many pools are in `pools`. NOT how many were examined -- "
                        "that is `scanned`. This field reported the fetched total beside "
                        "a shorter list until 2026-09-08, so a caller reading it believed "
                        "it had seen twenty pools when it had three.",
                },
                "scanned": {
                    "type": "integer",
                    "description":
                        "How many distinct pools were examined before the limit was "
                        "applied. Always >= count.",
                },
                "sources_ok": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["new", "trending"]},
                    "description":
                        "Which of the two upstream listings answered. Both means a full "
                        "mixed scan. In trending mode only the selected trending listing is requested.",
                },
                "sources_failed": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["new", "trending"]},
                    "description":
                        "Which requested listings did NOT answer. Unrequested listings are not failures. "
                        "A non-empty array means this is a "
                        "PARTIAL scan: a smaller `scanned` here is a coverage gap, not a "
                        "quiet market. Treat it as missing information, not as absence.",
                },
                "checked_at": _CHECKED_AT,
                "served_stale": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description":
                        "Present only when an upstream was unreachable and cached data "
                        "was used. Each entry names the source and its age in seconds.",
                },
                "pools": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "pool_id": {
                                "type": "string",
                                "description": "Valid 20-byte/32-byte EVM or Solana base58 pool IDs remain "
                                               "complete, preserving case and any matching network prefix. "
                                               "Other values retain escaped display text capped at 64 input "
                                               "characters plus an ellipsis; they are not complete identities. "
                                               "This identifies the discovered pool, not the assessment's "
                                               "selected market or simulator venue.",
                            },
                            "name": {"type": "string"},
                            "token_address": {
                                "type": "string",
                                "description":
                                    "The base token. Use assessment_args for the chain preference, then "
                                    "verify the returned chain; pool_id is not a token address.",
                            },
                            "assessment_args": {
                                "type": "object",
                                "description": "Arguments preserving the selected chain preference, not a strict lock. "
                                               "Omitted for invalid or wrong-family addresses or unsupported networks. "
                                               "Check returned evidence.chain_searched against chain_hint before use.",
                                "properties": {"address": {"type": "string"}, "chain_hint": {"type": "string"}},
                                "required": ["address", "chain_hint"],
                                "additionalProperties": False,
                            },
                            "kind": {"type": "string", "enum": ["new", "trending"]},
                            "price_usd": {"type": ["number", "null"]},
                            "liquidity_usd": {"type": ["number", "null"]},
                            "volume_24h_usd": {"type": ["number", "null"]},
                            "trade_activity": _TRADE_ACTIVITY_SCHEMA,
                            "pool_age_days": {"type": ["integer", "null"]},
                        },
                        "required": ["pool_id", "name", "token_address", "kind"],
                    },
                },
            },
            "required": ["status", "chain", "network", "count", "scanned",
                         "sources_ok", "sources_failed", "pools"],
        },
    },
]


def _as_bool(v):
    """JSON-RPC clients send booleans as booleans, strings, and 0/1. Read all three.

    bool("false") is True, so a client that sent the string "false" -- which several
    MCP clients do, because the schema type gets lost on the way through -- turned
    verbose on and got the full evidence payload it had explicitly declined.
    """
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on")
    return bool(v)


def _error(req_id, code, message):
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _ok(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


# What the client called itself on initialize, for this request only. A contextvar
# rather than a global: a Worker isolate serves many requests and a module-level
# variable would leak one caller's identity into another's telemetry.
_LAST_CLIENT_INFO = contextvars.ContextVar("vetagent_client_info", default="")


def declared_client():
    """The client's own declared name/version, or "" if it never said."""
    try:
        return _LAST_CLIENT_INFO.get()
    except LookupError:
        return ""


async def handle_mcp_request(body):
    """Handle a single MCP JSON-RPC message.

    Returns the full JSON-RPC response dict; None means this was a notification and
    must not get a response body.
    Errors always go in the **top-level error**, never stuffed into result.
    """
    if not isinstance(body, dict):
        return _error(None, INVALID_REQUEST, "Request must be a JSON object")

    method = body.get("method")
    req_id = body.get("id")

    # A notification has no "id" key. id=0 is a legal request id, so test for the
    # key itself, not for truthiness.
    if "id" not in body:
        return None

    # JSON-RPC restricts id to String, Number or Null; a dict or list was being echoed
    # back verbatim. bool is excluded explicitly because in Python it is a subclass of
    # int, and a JSON boolean is not a Number.
    if not (req_id is None or isinstance(req_id, str)
            or (isinstance(req_id, (int, float)) and not isinstance(req_id, bool))):
        return _error(None, INVALID_REQUEST,
                      "id must be a string, number or null")

    # `params` was read as `body.get("params") or {}`, and a list is truthy, so an Array
    # survived unchanged and `_call_tool` then called `.get` on it -- AttributeError,
    # uncaught, on a message JSON-RPC 2.0 explicitly permits. Every method here takes its
    # arguments by name, so an Array is a refusal rather than a crash: INVALID_PARAMS is
    # a normal thing for a protocol to say. Tested against `is None` rather than
    # truthiness so that `"params": 0` is refused too and does not fall through as {}.
    params = body.get("params")
    if params is None:
        params = {}
    elif not isinstance(params, dict):
        return _error(req_id, INVALID_PARAMS, "params must be an object")

    if not method:
        return _error(req_id, INVALID_REQUEST, "Missing method")

    if method == "initialize":
        # The client declares its own name and version here, and the MCP spec requires
        # it. That is application self-description, not personal data, and it de-mushes
        # the 11% of traffic currently arriving as "mozilla", "node", "undici" and
        # "unknown" -- buckets that are User-Agent artefacts rather than callers.
        info = params.get("clientInfo")
        if isinstance(info, dict):
            _LAST_CLIENT_INFO.set("%s %s" % (str(info.get("name") or "?")[:32],
                                             str(info.get("version") or "?")[:16]))
        asked = params.get("protocolVersion")
        version = asked if asked in SUPPORTED_PROTOCOLS else PROTOCOL_VERSION
        return _ok(req_id, {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "vetagent", "version": "0.2.0"},
            # The second sentence is a product decision, not a nicety.
            #
            # A decision gate asks whether anyone outside this project uses this server,
            # and fourteen days of telemetry could not answer it. The traffic is 96%
            # handshakes from directory crawlers; the one candidate that looks like real
            # use arrives as "mozilla", which is a User-Agent prefix shared by every
            # browser and every bot that spoofs one. No amount of log forensics resolves
            # that, and the fields that would -- addresses, identities, tokens -- are ones
            # this project has deliberately refused to record.
            #
            # So: ask. An operator who has wired this into something can say so in one
            # line, and that is worth more than any inference from 42 requests. It costs
            # a sentence and it is the only path here that produces a name attached to a
            # human intention.
            "instructions": (
                "Call assess_token_risk before an agent buys, holds, or recommends a "
                "token. risk_level 'unknown' means a critical check could not run — it is "
                "not a low-risk result and must not be used to justify a trade.\n\n"
                "Building on this? The maintainer would like to know it is being used, "
                "and will tell you before anything changes under you: "
                "hello@vetagent.dev, or github.com/jakegu1/vetagent/issues. Free, no "
                "signup, no tracking — "
                "this server records no addresses, no token queries and no identities, "
                "which is also why it cannot tell who you are unless you say."
            ),
        })

    if method == "ping":
        return _ok(req_id, {})

    if method == "tools/list":
        return _ok(req_id, {"tools": TOOLS})

    if method == "tools/call":
        return await _call_tool(req_id, params)

    return _error(req_id, METHOD_NOT_FOUND, "Method not found: %s" % method)


async def _call_tool(req_id, params):
    name = params.get("name")
    args = params.get("arguments") or {}
    if not isinstance(args, dict):
        return _error(req_id, INVALID_PARAMS, "arguments must be an object")

    try:
        if name == "assess_token_risk":
            result = await risk.assess(args.get("address", ""),
                                       args.get("chain_hint"),
                                       _as_bool(args.get("verbose", False)))
        elif name == "get_token_liquidity":
            context = liquidity_comparison.validate_context(args.get("comparison_context", []))
            result = await risk.liquidity(args.get("address", ""), args.get("chain_hint"))
            result = liquidity_comparison.with_context(result, context, requested="comparison_context" in args)
        elif name == "find_new_hot_pools":
            if "listing" in args:
                result = await risk.new_pools(args.get("chain", "solana"), args.get("limit", 10), args["listing"])
            else:
                result = await risk.new_pools(args.get("chain", "solana"), args.get("limit", 10))
        else:
            return _error(req_id, INVALID_PARAMS, "Unknown tool: %s" % name)
    except ValueError as e:
        # Bad input: return it as a tool error so the calling model sees it and self-corrects
        return _ok(req_id, {"isError": True,
                            "content": [{"type": "text", "text": str(e)}]})
    except Exception as e:  # noqa: BLE001
        return _ok(req_id, {"isError": True,
                            "content": [{"type": "text",
                                         "text": "Tool execution failed: %s" % e}]})

    payload = {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}
    # structuredContent must be an object, so wrap array results in one
    payload["structuredContent"] = result if isinstance(result, dict) else {"items": result}
    return _ok(req_id, payload)
