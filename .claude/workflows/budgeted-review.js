export const meta = {
  name: 'budgeted-review',
  description: 'Multi-dimension adversarial review with a hard agent ceiling',
  whenToUse:
    'Any fan-out review, audit or design critique in this repo. Use this INSTEAD of ' +
    'writing a fresh fan-out script: it caps the agent count before the run instead of ' +
    'letting model output decide it.',
  phases: [
    { title: 'Review', detail: 'one agent per dimension, findings capped at the schema' },
    { title: 'Verify', detail: 'top findings only, verifier count scaled by severity' },
    { title: 'Synthesize', detail: 'one memo, on reserved budget' },
  ],
}

// ---------------------------------------------------------------------------------
// WHY THIS FILE EXISTS
//
// On 2026-09-07 a hand-written review workflow spawned 233 agents, burned 5.2M output
// tokens, exhausted the account's session limit, and killed 190 of its own agents --
// including the synthesizer, whose memo was the only thing actually wanted. 43 agents
// finished. Roughly 80% of the spend bought nothing.
//
// The cause was one line: `parallel(findings.map(...))` with three verifiers each, where
// `findings` was whatever the models chose to return. The schema had no `maxItems`, so
// seven finders returned 75 findings and the verify stage became 225 agents.
//
// THE RULE THIS FILE ENCODES: **the agent count must be a constant known before the run,
// never a function of model output.** Everything below follows from that.
//
//   1. Cap findings at the schema (maxItems), so N finders -> at most N x K findings.
//   2. Dedup and rank in plain code. Triage costs zero tokens; verification does not.
//   3. Scale verifiers by severity, not uniformly. Last time a `low` cosmetic note got
//      the same three adversarial verifiers as a critical data-loss finding.
//   4. Reserve budget for synthesis and check it, so the one output that matters is not
//      last in a queue that may not reach it.
//   5. Tier effort. A verifier checking whether a line number is real does not need the
//      session default.
//   6. Never cap silently. A dropped finding is logged, or the report reads as complete
//      when it is not.
//
// Budget with these caps: 7 finders + <=~29 verifiers + 1 synthesizer = under 40 agents,
// against 233. The twelve findings that survived verification last time all came from
// exactly the top slice this keeps.
// ---------------------------------------------------------------------------------

const A = args || {}
const REPO = A.repo || '.'
const CONTEXT = A.context || ''
const DIMENSIONS = A.dimensions || []

// Hard ceilings. These are the point of the file; do not raise them casually.
const MAX_AGENTS = A.maxAgents || 40
const FINDINGS_PER_DIMENSION = A.findingsPerDimension || 6
const MAX_VERIFIED = A.maxVerified || 15
const SYNTH_RESERVE_TOKENS = A.synthReserve || 150000

// How many independent refuters a finding earns. A finding nobody verified is reported
// as unverified rather than quietly presented as confirmed.
const VERIFIERS = { critical: 3, high: 2, medium: 1, low: 0 }
const RANK = { critical: 0, high: 1, medium: 2, low: 3 }

let spawned = 0
const budgetLeft = () => (budget.total ? budget.remaining() : Infinity)
function canSpawn(n, reserve) {
  return spawned + n <= MAX_AGENTS && budgetLeft() - (reserve || 0) > 0
}

const FINDING_SCHEMA = {
  type: 'object',
  properties: {
    findings: {
      type: 'array',
      maxItems: FINDINGS_PER_DIMENSION,
      description:
        'At most ' + FINDINGS_PER_DIMENSION + ' findings, YOUR BEST ONES. This is a ' +
        'hard cap, not a target: three real defects beat six padded with observations. ' +
        'Anything you cannot evidence from the actual files should not be here at all.',
      items: {
        type: 'object',
        properties: {
          title: { type: 'string' },
          severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
          evidence: { type: 'string', description: 'file:line plus the concrete observation' },
          why_it_matters: { type: 'string' },
          proposed_change: { type: 'string' },
          reversible: {
            type: 'boolean',
            description: 'false if delay destroys something that cannot be recovered later',
          },
        },
        required: ['title', 'severity', 'evidence', 'why_it_matters', 'proposed_change',
                   'reversible'],
      },
    },
  },
  required: ['findings'],
}

const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    refuted: { type: 'boolean' },
    reasoning: { type: 'string' },
    corrected_claim: { type: 'string' },
  },
  required: ['refuted', 'reasoning'],
}

// ---------------------------------------------------------------------------- review
phase('Review')
log(`${DIMENSIONS.length} dimensions, <=${FINDINGS_PER_DIMENSION} findings each, ` +
    `ceiling ${MAX_AGENTS} agents`)

spawned += DIMENSIONS.length
const reviews = await parallel(DIMENSIONS.map(d => () =>
  agent(`${CONTEXT}\n\nYOUR LENS: ${d.prompt}\n\n` +
        `Read the real files at ${REPO}. Report only what you can evidence with a file ` +
        `reference or a measurement you actually ran. At most ` +
        `${FINDINGS_PER_DIMENSION} findings, and fewer is better than padded.`,
    { label: `review:${d.key}`, phase: 'Review', schema: FINDING_SCHEMA })))

const raw = reviews.filter(Boolean).flatMap((r, i) =>
  (r.findings || []).map(f => ({ ...f, dimension: (DIMENSIONS[i] || {}).key || '?' })))

// ------------------------------------------------------------------ triage, in code
// Free. This is the stage the failed run did not have.
const seen = new Set()
const deduped = raw.filter(f => {
  const k = (f.title || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim().slice(0, 60)
  if (seen.has(k)) return false
  seen.add(k)
  return true
})
deduped.sort((a, b) =>
  (RANK[a.severity] ?? 9) - (RANK[b.severity] ?? 9) ||
  (a.reversible === b.reversible ? 0 : a.reversible ? 1 : -1))

const shortlist = deduped.slice(0, MAX_VERIFIED)
const dropped = deduped.slice(MAX_VERIFIED)
log(`${raw.length} raised -> ${deduped.length} after dedup -> ${shortlist.length} verified`)
if (dropped.length) {
  log(`NOT VERIFIED (reported as unverified, not as absent): ` +
      dropped.map(f => `[${f.severity}] ${f.title}`).join(' | '))
}

// ---------------------------------------------------------------------------- verify
phase('Verify')
const LENSES = [
  'CORRECTNESS: is the factual claim true? Check every line reference and number against the real files.',
  'MATERIALITY: even if true, does it change any decision? Or is it cosmetic?',
  'COST: is the fix actually cheap and safe? What does it break?',
]

const verified = await pipeline(
  shortlist,
  f => {
    const want = VERIFIERS[f.severity] ?? 1
    const n = canSpawn(want, SYNTH_RESERVE_TOKENS) ? want : 0
    if (!n) {
      if (want) log(`ceiling reached: "${f.title}" reported UNVERIFIED`)
      return Promise.resolve({ ...f, verifiers: 0, survived: null, votes: [] })
    }
    spawned += n
    return parallel(LENSES.slice(0, n).map((lens, li) => () =>
      agent(`${CONTEXT}\n\nA reviewer of the ${f.dimension} dimension claims:\n\n` +
            `  TITLE: ${f.title}\n  SEVERITY: ${f.severity}\n  EVIDENCE: ${f.evidence}\n` +
            `  MATTERS: ${f.why_it_matters}\n  CHANGE: ${f.proposed_change}\n\n` +
            `REFUTE IT, through this lens:\n${lens}\n\n` +
            `Read the real files at ${REPO}. Verify every line reference and number ` +
            `yourself. Default to refuted=true if you cannot confirm it. If it is ` +
            `partly right, set refuted=false and give the narrower surviving version.`,
        { label: `verify:${f.dimension}:${li}`, phase: 'Verify', schema: VERDICT_SCHEMA,
          effort: 'low' })))
      .then(votes => {
        const v = votes.filter(Boolean)
        return {
          ...f,
          verifiers: v.length,
          survived: v.length ? v.filter(x => !x.refuted).length > v.length / 2 : null,
          votes: v.map(x => ({ refuted: x.refuted, corrected: x.corrected_claim || '' })),
        }
      })
  },
)

const results = verified.filter(Boolean)
const confirmed = results.filter(r => r.survived === true)
const unjudged = results.filter(r => r.survived === null)
const refuted = results.filter(r => r.survived === false)

// ------------------------------------------------------------------------- synthesize
phase('Synthesize')

// Always produce a memo, even if the synthesizer cannot run. The failed run returned
// memo:null because its one synthesizer was last in a queue that never reached it.
const fallback = [
  `# Review (fallback memo -- the synthesizer did not run)`,
  ``,
  `CONFIRMED (${confirmed.length}):`,
  ...confirmed.map(f => `- [${f.severity}${f.reversible ? '' : ', IRREVERSIBLE'}] ${f.title}\n  ${f.proposed_change}`),
  ``,
  `UNVERIFIED (${unjudged.length}) -- raised, never judged:`,
  ...unjudged.map(f => `- [${f.severity}] ${f.title}`),
  ``,
  `REFUTED (${refuted.length}):`,
  ...refuted.map(f => `- ${f.title}`),
  ``,
  `NOT REACHED (${dropped.length}):`,
  ...dropped.map(f => `- [${f.severity}] ${f.title}`),
].join('\n')

let memo = fallback
if (canSpawn(1, 0)) {
  spawned += 1
  const brief = confirmed.map(f =>
    `[${f.severity}${f.reversible ? '' : ', IRREVERSIBLE'}] (${f.dimension}) ${f.title}\n` +
    `  evidence: ${f.evidence}\n  matters: ${f.why_it_matters}\n` +
    `  change: ${f.proposed_change}\n` +
    `  verifier corrections: ${f.votes.map(v => v.corrected).filter(Boolean).join(' | ') || 'none'}`
  ).join('\n\n')

  const out = await agent(
    `${CONTEXT}\n\n${confirmed.length} findings survived adversarial verification ` +
    `(each attacked by up to three refuters; a finding survives on a majority):\n\n` +
    `${brief || '(none)'}\n\n` +
    `RAISED BUT NEVER JUDGED (the run hit its ceiling -- treat as open questions, ` +
    `not as findings):\n${unjudged.map(f => `- [${f.severity}] ${f.title}`).join('\n') || '(none)'}\n\n` +
    `REFUTED, do not resurrect without new evidence:\n` +
    `${refuted.map(f => `- ${f.title}`).join('\n') || '(none)'}\n\n` +
    `NOT REACHED AT ALL:\n${dropped.map(f => `- [${f.severity}] ${f.title}`).join('\n') || '(none)'}\n\n` +
    `Write a decision memo:\n` +
    `1. VERDICT in one paragraph.\n` +
    `2. DO NOW, ranked -- only changes where delay costs something irreversible. Be ruthless.\n` +
    `3. DO LATER, each with the trigger that un-parks it.\n` +
    `4. DO NOT DO, with why.\n` +
    `5. WHAT NOBODY CHECKED -- including the unjudged and not-reached lists above.\n\n` +
    `Concrete and specific to this repository. Resolve conflicts between findings ` +
    `rather than listing both. Name any assumption a finding rests on.`,
    { label: 'synthesize', phase: 'Synthesize' })
  if (out) memo = out
}

log(`${spawned} agents used of a ${MAX_AGENTS} ceiling`)

return {
  agents: spawned,
  raised: raw.length,
  confirmed: confirmed.length,
  unjudged: unjudged.length,
  refuted: refuted.length,
  not_reached: dropped.length,
  memo,
  findings: confirmed,
  open_questions: unjudged.concat(dropped),
}
