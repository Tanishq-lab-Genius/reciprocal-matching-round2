# Selective Joint VOI vs organizer baselines — seeds 114–115

This controlled public-simulator experiment evaluates the submitted default
`selective_joint_voi` policy on the same two public seeds and all six official
scenario families as the organizer baselines. Every one of the 48 episodes
was valid.

The submitted policy preserves the reciprocal hard-constraint gate, the
official daily question budget, and the global matcher. It asks a
hard-constraint bundle only when its bounded counterfactual matching
calculation finds positive value. It does not use a count-based zero-value
fallback.

| Policy | MSMI outcomes / 12 | Official primary score | Coverage | Mutual acceptances / 100 | ASK cost / episode | Inference seconds / episode |
|---|---:|---:|---:|---:|---:|---:|
| Selective Joint VOI | **9** | **0.3750** | 21.29% | 2.92 | 79.5 | 138.2 |
| Organizer greedy | 5 | 0.2083 | 30.38% | 4.17 | 193.8 | 14.4 |
| Organizer random-feasible | 6 | 0.2500 | 30.58% | 3.83 | 193.8 | 15.3 |
| Organizer no-questions | 1 | 0.0417 | 11.38% | 1.33 | 0.0 | 16.5 |

The submitted policy had a higher official primary metric than each organizer
baseline in this two-seed sample. It also spent about 114 fewer clarification
units per episode than greedy and random-feasible. The tradeoffs were lower
service coverage, fewer mutual acceptances, and much slower total inference
time. Its individual calls remained valid under the evaluator's ten-second
limit.

This is limited public-simulator evidence, not proof of general superiority:
only two public seeds were used and outcomes are synthetic. The runtime and
coverage tradeoffs remain important limitations.

Machine-readable paired comparisons:

- `selective_joint_voi_vs_greedy_seeds114-115.json`
- `selective_joint_voi_vs_random_seeds114-115.json`
- `selective_joint_voi_vs_no_asks_seeds114-115.json`
