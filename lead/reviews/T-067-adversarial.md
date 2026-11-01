# T-067 focused adversarial review, round 2

Head: `44174ea7718aa323b746b552db4461107efdfd55`.
Previous rejected head: `0e4bcda9b8e58ec1033bcf256dcd602982c76c18`.
Original base: `dffdbc20b6609a4949f62ed23ca997f0cc0fcb17`.

RED-TEAM: none

R1's M1 is closed on the revised head. Real offline fetch/probe/write/readiness
and both actual main modes retain a valid/null/valid sequence as
`[ok,invalid_payload,ok]`, count the middle received failure once, preserve the
existing completion clock and every valid neighbor/prefix, and return failure.
Four passes use exactly three physical requests and counts `[1,2,3,3]`.

Timeout/HTTP429/invalid-JSON/empty-body followed by null preserve the original
retry behavior and terminal diagnostic reset. HTTP404, HTTP403, terminal failures
and legacy None retain their original categories, row bytes and allowance.
Invalid clocks do not manufacture availability. Unicode/finite/null legacy
controls, strict writer neighbors, honest I/O failures and false readiness flags
hold. Fetcher and readiness sources are unchanged from the original base.

Forty-three explicit focused checks pass. Three memory-only mutants are caught.
All eleven sealed R1 artifacts remain exact. No material findings or minor notes
remain in this second bounded round.

No product source was edited and no production request was made. This clears the
focused adversarial gate; complete gates and publication require their separate
evidence. The original R1 finding remains bound to its original rejected head.
