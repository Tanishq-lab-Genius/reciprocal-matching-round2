# Sequential Reciprocal Matching — Round 2 Final Build

This repository contains the final submitted policy build for the Sequential Matching Problem. Its default strategy is **Selective Joint VOI** (`selective_joint_voi`). The policy follows the organizer's JSON interface and uses only the current public observation and JSON memory.

## What the policy does

The policy makes two decisions each day:

1. **ASK:** It considers a bounded set of questions about missing hard constraints. It estimates whether plausible answers could improve the overall pool allocation, including useful two-question combinations, and asks only when its estimated allocation value is positive.
2. **MATCH:** It rechecks both participants' hard requirements, then chooses a non-overlapping batch of eligible introductions using a global matching procedure.

Hard requirements are always enforced; a soft preference score cannot make an ineligible pair matchable. The soft score is a transparent ranking heuristic, not a trained model or calibrated probability. The search is bounded and may miss useful questions or combinations.

## Quick demo

From the project folder, run:

```sh
python3 demo.py
```

The demo uses the included public synthetic simulator and a small, reproducible example to show the available pool, ASK questions, refreshed information, and resulting MATCH action. It illustrates behavior; it is not benchmark evidence.

## Run the policy in Docker

The included `Dockerfile` builds the submitted default policy with Python 3.12.7. Docker is the recommended way to run the policy in an isolated environment.

```sh
docker build -t reciprocal-matching-round2-final .
printf '{"schema_version":"1.0.0","phase":"ask","state":{"schema_version":"1.0.0","synthetic":true,"day":0,"ask_budget_remaining":12,"members":[],"introductions":[],"feedback":[],"ask_log":[]},"memory":null}\n' | docker run --rm -i reciprocal-matching-round2-final
```

The policy reads one JSON request from standard input and writes one JSON response to standard output. For an empty pool, the ASK response contains no questions. The full interface is in [docs/POLICY_INTERFACE.md](docs/POLICY_INTERFACE.md).

## Final public evaluation

The submitted default was compared with the three organizer baselines on the same two public simulator seeds (114 and 115), across all six scenario families. All 48 episodes were valid.

| Policy | MSMI outcomes / 12 episodes | Primary score | Coverage | Mutual acceptances / 100 | ASK cost / episode | Inference seconds / episode |
|---|---:|---:|---:|---:|---:|---:|
| **Selective Joint VOI (submitted default)** | **9** | **0.3750** | 21.29% | 2.92 | 79.5 | 138.2 |
| Organizer greedy | 5 | 0.2083 | 30.38% | 4.17 | 193.8 | 14.4 |
| Organizer random-feasible | 6 | 0.2500 | 30.58% | 3.83 | 193.8 | 15.3 |
| Organizer no-clarification | 1 | 0.0417 | 11.38% | 1.33 | 0.0 | 16.5 |

Selective Joint VOI had the highest primary score in this small public-simulator comparison. It also had lower coverage and much longer total inference time than the active baselines. Two seeds are not enough to establish reliable performance on unseen scenarios.

The matched comparison and methods are in [the evaluation summary](results/comparisons/selective_joint_voi_seeds114-115.md). Raw episode results are in [results/evaluations](results/evaluations/).

## Verify the package

Run the included tests with:

```sh
python3 -m unittest -v test_kit test_matching_core test_matching_policy test_directional_learning test_msmi_feedback test_release test_runner
```

See [TESTING.md](TESTING.md) for the Docker check. Organizer interface and data details are in [docs/POLICY_INTERFACE.md](docs/POLICY_INTERFACE.md), [docs/DATA_CONTRACT.md](docs/DATA_CONTRACT.md), and [docs/SUBMISSION.md](docs/SUBMISSION.md). The complete technical report is in [FINAL_REPORT.md](FINAL_REPORT.md).

## Main files

- `reciprocal_matching_policy.py` — policy entrypoint; defaults to `selective_joint_voi`.
- `matching_core.py` and `allocation_voi.py` — reciprocal eligibility, allocation, ASK, and MATCH logic.
- `Dockerfile` — isolated container for the submitted policy.
- `demo.py` and `DEMO.md` — reproducible walkthrough.
- `evaluate.py` and `kit.py` — public local evaluator and simulator.
- `results/` — matched public evaluation outputs.
- `FINAL_REPORT.md` — technical report, including evaluation methods and limitations.

The simulator data is synthetic and does not establish real-world effectiveness or fairness. See [DATA_LICENSE.md](DATA_LICENSE.md) and [LICENSE](LICENSE) for licensing information.
