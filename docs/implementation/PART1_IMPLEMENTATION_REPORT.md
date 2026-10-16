# Sequential Reciprocal Matching Round 2 Part 1 Implementation

Status: locally verified against official release 1.0.0. This is a clean
foundation build, not a final submission package.

## Active architecture

The authoritative custom entry point is `reciprocal_matching_policy.py`. It imports only
`matching_core.py`, which separates:

1. observation parsing and bounded memory validation;
2. reciprocal feasibility with feasible, infeasible and unresolved states;
3. deterministic transparent pair scoring;
4. count-based hard-constraint ASK shortlisting;
5. bounded general-graph weighted matching;
6. ASK and MATCH action validation with fail-closed fallbacks; and
7. explicit strategy configuration.

The previously verified Phase 2 and Phase 3A code is preserved in an external
verified backup under `E:\Hackathon\project_backups`. Historical checkpoints
are excluded from active imports and the organized build.

## Official contract findings

- The policy is a fresh process that reads one JSON request and emits one JSON
  response. `memory` is the only policy-owned persistent state.
- The engine calls ASK and then MATCH on each decision day. ASK answers are
  immediate in release 1.0.0, and MATCH receives the refreshed observation.
- There is no distinct WAIT action. An empty MATCH list waits one day.
- Legal questions are `constraints` at cost 3 or one named soft field at cost 1.
  The daily budget is 12.
- A complete MATCH batch is atomic. Every endpoint must be available, each pair
  must be new and from one pool, every hard condition must be known and
  reciprocally satisfied, and each endpoint can appear only once.
- No official maximum batch size is defined beyond disjointness and current
  availability.
- Feedback is released only when `observed_day <= day`; missing feedback remains
  explicit. The policy never sees hidden truth, future arrivals, or unreleased
  outcomes.
- Each invocation has a 10-second limit. Request, response, diagnostics and
  memory are each limited to 1 MiB. Assessed execution is offline with 2 CPU
  cores and 1 GiB RAM.

The implementation follows the executable official files where these details
are more specific than earlier design notes.

## Reciprocal feasibility

The engine enforces identity, pool, availability, prior-introduction history,
age bounds, accepted genders, geography, smoking, present children,
relationship structure, children plans and schedule overlap. Known conflicts
take precedence over missingness. An unresolved result records every blocking
`(member_id, field)` requirement and never enters MATCH.

## Transparent scoring

The edge score uses only observable values:

- exact agreement for the seven named soft fields, with documented fixed
  weights;
- observable schedule overlap; and
- bounded age closeness.

Missing soft values contribute zero. Scores are finite, deterministic heuristic
weights and are not presented as probabilities.

## Count-based ASK baseline

All currently legal official question shapes are enumerable. The active Part 1
baseline selects only constraint bundles that can remove a recorded hard
eligibility blocker. Candidates are ordered by affected unresolved-pair count
per cost, then affected-pair score, then stable identifiers. Declined, known,
previously asked or pending-equivalent entries are excluded. The selected batch
is revalidated against the current daily budget.

Named soft questions remain represented for later VOI modes but are not selected
by this feasibility-count baseline because they cannot make an unresolved edge
legally matchable.

## General-graph matching

Feasible positive-weight edges are divided into connected components. Components
with at most 18 vertices use exact dynamic-programming maximum-weight matching.
Larger components use deterministic greedy selection followed by at most two
strictly improving one-edge local-replacement passes. The large-component result
is explicitly approximate, not mathematically optimal. Every selected batch is
rechecked; an invalid proposal falls back to deterministic greedy matching and
then to an empty legal batch.

The saved synthetic graph benchmark records exact-versus-fallback solution
quality and host-local timing. It is not assessed inference latency.

## Strategy configuration

Implemented modes:

- `foundation`: count-based ASK, transparent scoring, bounded global matching.
- `foundation_fallback`: same ASK and score with forced fallback matching.
- `no_asks_global`: no clarification with bounded global matching.

Reserved VOI, joint-question, feedback-adjusted and waiting modes raise clear
development errors rather than silently selecting another strategy. The
unchanged official `policy.py` remains the executable source for official greedy,
no-clarification and random baselines.

## Verification commands

```text
python -m unittest -v test_matching_core.py test_matching_policy.py
python -m unittest -v
python verify_data.py
python benchmark_part1_matching.py --output results/part1_matching_benchmark.json
python evaluate.py --policy reciprocal_matching_policy.py --seeds 101 --variants development --output results/part1_development_seed101.json
```

Observed results:

- New Part 1 tests: 47/47 passed.
- Combined official and custom tests: 69/69 passed.
- Public data: 71 files verified.
- Full development/seed-101 episode: valid, 105 assignments, 14 mutual
  acceptances, 12 dates, 1 MSMI, 0.5 MSMI per 100, 0.455 coverage, 351
  clarification cost and 25.7193 local inference seconds.
- Action SHA-256:
  `59fc8a707263d131fbe1413995528c6a618aff288fe514ac4bd44a7c577bd9eb`.

The smoke run underperforms the preserved Phase 2 and Phase 3A runs on this one
seed. This is recorded rather than hidden. The changed matching allocation is a
plausible mechanism, but causal attribution requires controlled ablations and
multiple matched seeds.

## Part 1 boundaries

Allocation-aware VOI, diversified shortlisting, joint-question evaluation,
feedback-adjusted scoring and optional waiting are not implemented here. Docker
verification and multi-seed/all-family evaluation also remain pending. No final
submission ZIP has been created.
