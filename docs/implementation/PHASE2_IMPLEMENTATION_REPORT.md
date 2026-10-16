# Sequential Reciprocal Matching Phase 2 Reproduction Notes

## Implemented scope

`reciprocal_matching_policy.py` is a standard-library-only policy for interface version 1.0.0. It reads one JSON request from standard input and writes one JSON response to standard output. It accepts the evaluator's `--baseline` argument for command compatibility but always executes the Sequential Reciprocal Matching policy.

ASK behavior:

- considers only currently available observed members;
- asks only the legal `constraints` bundle;
- asks only when at least one missing hard field is marked `not_asked`;
- ranks candidates by how many currently unresolved, non-repeated pairs that member's answer may help resolve;
- uses member ID as the final deterministic tie-break;
- respects `ask_budget_remaining`, with each selected bundle costing three units;
- safely returns an empty ask list when no useful legal bundle fits.

MATCH behavior:

- rebuilds reciprocal hard feasibility from the refreshed observable state;
- excludes unavailable members and previously introduced pairs;
- admits only fully feasible pairs;
- scores visible soft-field agreement in both directions, plus small visible schedule-overlap and age-proximity terms;
- treats this value only as an uncalibrated heuristic, not a probability;
- sorts deterministically and greedily selects non-overlapping pairs;
- runs an internal final validity check and returns an empty pair list when no safe edge exists.

No trained probability model, global maximum-weight matching, allocation-aware VOI search, joint-question comparator, mature-feedback learning, or strategic waiting optimiser is implemented in Phase 2.

## Reproduction commands

Run from the repository root:

```text
python -m unittest -v
python -m unittest -v test_matching_policy.py
python verify_data.py
python evaluate.py --policy reciprocal_matching_policy.py --seeds 101 --variants development --output results/phase2_development_seed101.json
```

The evaluator appends `--baseline greedy` to the custom policy command. The custom entry point accepts that argument so it can run through the unmodified evaluator.

## Executed smoke-test result

The complete development/seed-101 episode finished validly through the official evaluator. It produced 102 assignments, 18 mutual acceptances, 14 completed dates, 2 MSMI outcomes, MSMI per 100 of 1.0, coverage of 0.46, 108 unserved members, clarification cost 351, and 19.50748830003431 total measured inference seconds across all policy invocations. The raw output is `results/phase2_development_seed101.json` and the cautious comparison is `results/phase2_comparison.md`.

This one-seed result is an integration smoke test, not evidence of superiority or statistical significance.

A second execution with the same seed and scenario produced the same action SHA-256 (`0e3f7f6626114f60458f5e656a5b65058842fa4d4548ff729125a64c768c1306`) and identical non-runtime metrics. Total wall-clock inference time varied between runs, so it is not treated as deterministic.

## Assumptions and limitations

- The implementation mirrors release 1.0.0 hard-constraint semantics.
- Missing hard information remains unresolved; a known hard failure dominates missingness.
- Declined-only missing hard fields are not repeatedly queried because the simulator keeps them unavailable.
- Soft-field missingness never becomes a hard exclusion.
- The heuristic score is deterministic and reciprocal but untrained and uncalibrated.
- Docker validation remains outstanding because Docker is unavailable in the current environment.
