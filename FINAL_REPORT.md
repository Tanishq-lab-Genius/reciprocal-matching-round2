# Round 2 Final Build: Technical Report

**Prepared:** 17 October 2026  
**Evaluation:** Organizer-supplied public synthetic simulator, interface 1.0.0
**Submitted default:** Selective Joint VOI (`selective_joint_voi`)

## 1. Objective

The policy operates in two phases each day. It may ask participants to clarify missing information, then recommends introductions using the refreshed public state. An introduction is allowed only when both participants satisfy the other's hard requirements. The policy also prevents a participant from receiving multiple introductions in one batch.

The official primary metric is the equal-weight mean, over six scenario families, of mutual second-meeting intention (MSMI) outcomes per 100 arrived members.

## 2. Submitted policy

### ASK

The submitted `selective_joint_voi` strategy evaluates a bounded shortlist of questions about missing hard constraints. It estimates whether plausible answers could improve the best whole-pool allocation and includes bounded evaluation of complementary two-question combinations. It asks only when estimated counterfactual allocation value is positive. It does not use a count-based fallback to spend the question budget when estimated value is zero.

The search is deliberately bounded. It does not evaluate arbitrary question sets, and its estimated value is not an exact guarantee of future improvement. The policy selects a legal batch within the organizer's daily question budget.

### MATCH

After ASK responses are applied, the policy rechecks reciprocal hard eligibility against the refreshed state. Missing, declined, or unresolved mandatory information does not count as satisfying a hard requirement. Among eligible pairs, it uses disclosed soft preferences as a transparent ranking heuristic and selects a non-overlapping batch with global matching. A soft score cannot override a hard-rule failure. If no pair is currently feasible, the policy returns no introductions.

The soft score is not a trained model or a calibrated probability of mutual acceptance or second-meeting intention.

## 3. Information and runtime boundaries

The policy reads the current public JSON observation and JSON-serializable memory. It does not use hidden simulator state, future arrivals, unreleased outcomes, network access, or persistent files between invocations. The runtime is restarted for each phase. The submitted Docker image uses Python 3.12.7 slim and the policy's standard-library runtime dependencies.

The official interface provides ASK and MATCH, not a separate WAIT action. An empty MATCH action means that no introduction is made that day; it is not a learned waiting strategy.

## 4. Final public evaluation

The submitted default and the three organizer baselines were evaluated on the same public simulator seeds, 114 and 115, across all six scenario families: development, sparse, cold start, delayed, shift, and drift. This produced 12 episodes per policy and 48 episodes overall. All 48 episodes were valid.

| Policy | MSMI outcomes / 12 episodes | Primary score | Coverage | Mutual acceptances / 100 | ASK cost / episode | Inference seconds / episode |
|---|---:|---:|---:|---:|---:|---:|
| **Submitted default: Selective Joint VOI** | **9** | **0.3750** | 21.29% | 2.92 | 79.5 | 138.2 |
| Organizer greedy | 5 | 0.2083 | 30.38% | 4.17 | 193.8 | 14.4 |
| Organizer random-feasible | 6 | 0.2500 | 30.58% | 3.83 | 193.8 | 15.3 |
| Organizer no-clarification | 1 | 0.0417 | 11.38% | 1.33 | 0.0 | 16.5 |

Selective Joint VOI had the highest primary score in this two-seed public comparison. It used fewer clarification units than greedy and random-feasible, while achieving lower coverage and fewer mutual acceptances. Its total inference time per episode was also much higher. These results support the submitted strategy on the tested seeds; they do not establish performance on hidden seeds or real-world participants.

The [matched comparison note](results/comparisons/selective_joint_voi_seeds114-115.md) gives the methods and interpretation. The raw episode outputs and machine-readable comparisons are in `results/evaluations/` and `results/comparisons/`.

## 5. Limitations

1. The evaluation uses only two public seeds, so results may vary on other seeds.
2. ASK search is bounded and may miss useful questions or higher-order combinations.
3. The policy does not make an explicit waiting decision and does not resolve the high non-service rate seen in some scenarios.
4. Soft compatibility is a hand-designed ranking heuristic, not a calibrated outcome probability.
5. Synthetic simulator outcomes do not establish real-world effectiveness or fairness.

## 6. Reproduction and verification

From the project root, run the included verification suite:

```sh
python3 -m unittest -v test_kit test_matching_core test_matching_policy test_directional_learning test_msmi_feedback test_release test_runner
```

To reproduce the submitted policy's public evaluation, run:

```sh
python3 evaluate.py --policy reciprocal_matching_policy.py --seeds 114,115 --variants all --output results/evaluations/reproduced_selective_joint_voi_seeds114-115.json
```

The three baselines can be evaluated on the same seeds and variants with `--baseline greedy`, `--baseline random`, and `--baseline no_asks`. Each policy must use the same seed set and scenario variants for a matched comparison. See [TESTING.md](TESTING.md) for the Docker build and invocation check, and [docs/POLICY_INTERFACE.md](docs/POLICY_INTERFACE.md) for the authoritative JSON contract.

## 7. Included implementation files

- `reciprocal_matching_policy.py` — JSON entrypoint; defaults to `selective_joint_voi`.
- `matching_core.py` and `allocation_voi.py` — reciprocal feasibility, allocation, ASK, and MATCH logic.
- `Dockerfile` — container definition for the submitted policy.
- `evaluate.py` and `kit.py` — public evaluator and simulator.
- `results/` — final matched public evaluation outputs.
- `demo.py` and `DEMO.md` — reproducible demonstration.

The code and synthetic data are licensed as described in [LICENSE](LICENSE) and [DATA_LICENSE.md](DATA_LICENSE.md). AI assistance was used for brainstorming, implementation support, and report drafting; the team reviewed the implementation and results.
