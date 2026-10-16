# Sequential Reciprocal Matching

This repository contains a participant policy for the Round 2 sequential reciprocal matching challenge. The policy operates through the official two-phase JSON interface: it first selects a bounded batch of clarification requests (`ASK`), then selects a valid set of non-overlapping introductions (`MATCH`) from the refreshed observable state.

The implementation keeps reciprocal hard constraints separate from soft compatibility. Only currently feasible pairs may be introduced. Among those pairs, the policy uses allocation-aware scoring and general-graph matching to coordinate introductions across competing endpoints.

The complete Round 2 technical report and matched baseline results are in [FINAL_REPORT.md](FINAL_REPORT.md). It records both favorable and unfavorable results and distinguishes the current default from experimental strategies.

## Problem Overview

On each decision day, the simulator invokes the policy twice:

1. **ASK:** select legal clarification requests within the remaining daily budget.
2. **MATCH:** after clarification results are applied, select a batch of legal introductions.

The policy may use only the supplied observable state and JSON-serializable memory. It must not use hidden simulator variables, future arrivals, unreleased outcomes, network access, or persistent files between invocations. The official runtime restarts the policy process for each phase.

The organizer contract, rather than this summary, is authoritative:

- [Policy interface](docs/POLICY_INTERFACE.md)
- [Submission instructions](docs/SUBMISSION.md)
- [Data contract](docs/DATA_CONTRACT.md)

## Implemented Policy

### Reciprocal Feasibility

`matching_core.py` evaluates hard eligibility in both directions. The checks cover the disclosed age and gender requirements, relationship structure, smoking and children constraints, geographic zones, schedule compatibility, participant availability, prior introductions, and outstanding introductions. Unknown or declined mandatory information prevents an edge from being treated as feasible.

Hard feasibility is a gate: a high soft score cannot override a failed or unresolved hard requirement. Before returning a `MATCH` action, the implementation validates the selected pairs again against the refreshed state.

### ASK Decision

`allocation_voi.py` implements bounded allocation-aware clarification:

1. identify legal hard-bundle and named soft-field questions;
2. generate and cheaply score potentially useful candidates;
3. shortlist candidates under fixed computation limits;
4. estimate each shortlisted question's effect on the current allocation under plausible answers, including decline or nondisclosure;
5. evaluate a bounded set of complementary two-question combinations;
6. select a diverse legal batch within the official clarification budget.

The submitted default `selective_joint_voi` limits its shortlist to four candidates, permits at most twelve allocation-solver calls during clarification, and applies a seven-second ASK time guard. It evaluates only hard-constraint questions and complementary pairs that can change the currently available allocation. A question batch must have positive counterfactual allocation value; it never falls back to asking merely because a member has missing fields. These controls bound the search; they do not make the value-of-information estimate exact.

The `joint_budget_voi` selector compares affordable subsets of shortlisted questions under one allocation-value objective. Individual gains are discounted when questions affect the same edges, and a complementary gain is credited only when both questions in its bundle are selected. The complementary gain is the comparator's incremental value after individual credit, rather than an assumed sum of the two individual values. Two evaluation-only ablations are also included: `single_only_voi` uses only positive individual-question values, while `joint_budget_no_redundancy` keeps the joint comparator and removes the overlap discount. A matched two-seed experiment found four more MSMI outcomes for the no-discount ablation across 12 episodes, at the cost of more clarification. That is a promising but small-sample result; it is not yet the default. See [the organizer-feedback experiment](results/comparisons/organizer_feedback_seed110-111.md).

`selective_joint_voi` is a newer experimental challenger. It retains bounded
single and complementary two-question evaluation but removes the count-based
zero-value fallback: it asks only when the counterfactual allocation estimate
is positive. On public seeds 114–115 it recorded 9 MSMI outcomes across 12
matched episodes, versus 5 for organizer greedy and 6 for random-feasible.
It had lower coverage and much longer inference time, so it remains
experimental. See [the matched comparison](results/comparisons/selective_joint_voi_seeds114-115.md).

The clarification batch is selected once per ASK invocation. The policy does not assume unsupported within-day, question-by-question adaptation.

The evidence and trade-offs for choosing the current default are recorded in [the default-strategy comparison note](results/comparisons/default_strategy_decision.md). The directional-learner experiment and its earlier negative result are recorded in [the feedback-learning trial note](results/comparisons/feedback_voi_trial_seeds101-102.md). The organizer follow-up includes separate directional Brier scores and waiting/non-service rates by missing-hard-information group.

### MATCH Decision

For each feasible pair, the current default `joint_budget_voi` computes a bounded positive utility from disclosed agreement or disagreement on relationship goal, relationship pace, conversation preference, and lifestyle. Relationship goal receives additional weight because it is relevant to the downstream second-meeting stage. Missing values contribute no agreement signal, and observed mismatches reduce the utility. This score is a transparent allocation heuristic, not a trained probability estimate.

The policy then builds a general graph whose vertices are available participants and whose edges are feasible pairs. It solves bounded connected components exactly and uses a deterministic valid fallback for larger components or guarded failure cases. This coordinates endpoint competition more effectively than independently accepting edges in descending score order. The graph is not assumed to be bipartite.

The returned batch enforces:

- at most one introduction per participant;
- current reciprocal hard eligibility;
- current availability;
- no repeated pair;
- no participant already committed to an outstanding introduction.

If no valid edge remains, the policy returns an empty `pairs` list.

### Optional Directional Feedback Strategy

The `feedback_voi` strategy keeps the same hard-feasibility checks and ASK procedure. At each MATCH action it stores compact feature snapshots for both directions. Later, it updates a small regularized logistic model only from released, explicit `introduction_response` values of `yes` or `no`. Pending responses and `null`/no-response events are excluded. Repeated cumulative feedback is counted once.

Until the model has at least 40 explicit labels, including at least five yes and five no responses, matching uses the existing transparent score exactly. It also stays in fallback unless its prequential Brier score beats a smoothed historical-rate predictor by a small margin. Once both checks pass, the score adds a confidence-shrunk directional signal, with the smaller of the two acceptance estimates used as the reciprocal term. This protects matching when the learner has not shown useful predictive skill. The estimates are online ranking signals, not claimed calibrated probabilities. Date and second-meeting outcomes are not learned by this model.

### Experimental Scarcity-Aware MSMI Strategy

`msmi_feedback_voi` is an opt-in challenger built from the organizer's scarcity-aware hard-unlock suggestion. Its `hard_unlock_voi` ASK layer classifies available members as A (already has a feasible edge), B (has an actionable unresolved edge), or C (has no actionable edge). Hard questions are limited to bundles that can address an unresolved pair with no known failure; soft questions are considered only when they can reorder at least two currently feasible partners. A bounded scarcity multiplier is used only while valuing ASK options.

At MATCH time, this strategy uses released, mature feedback to build a factorised expected-MSMI ranking utility for feasible pairs. Beta smoothing stabilizes early rates, and the directional acceptance learner is confidence-gated. The factorisation is explicitly uncalibrated and assumes independent stages and second-meeting responses. The official reciprocal hard-eligibility gate and global matcher remain in place. In the first two-seed, six-scenario comparison, it produced 5 MSMI outcomes versus 10 for the unchanged default, so it remains experimental. See [the implementation and evaluation note](docs/implementation/HARD_UNLOCK_MSMI_FEEDBACK.md) and [the paired results](results/comparisons/msmi_feedback_voi_seed112-113.md).

## Strategy Configurations

The main entrypoint accepts `--strategy NAME`. The submitted default is `selective_joint_voi`. In a fresh matched comparison on seeds 114 and 115 across six public scenario families, it recorded 9 MSMI outcomes across 12 episodes, compared with 5 for organizer greedy and 6 for organizer random-feasible. It has lower coverage and higher runtime, so the result is promising public-simulator evidence rather than proof of hidden-world superiority.

| Strategy | ASK procedure | MATCH procedure |
|---|---|---|
| `diversified_voi` | Diversified shortlist with bounded single- and joint-question allocation evaluation | Global component-wise matching |
| `selective_joint_voi` | Positive-value-only single and complementary joint VOI; submitted default | Global component-wise matching |
| `joint_budget_voi` | Integrated budget selection over the same single and complementary joint estimates; prior candidate | Global component-wise matching |
| `single_only_voi` | Integrated selection using positive individual-question values only; no joint bonus or count fallback | Global component-wise matching |
| `joint_budget_no_redundancy` | Joint-question bonus with overlap discount disabled; evaluation challenger | Global component-wise matching |
| `feedback_voi` | Same ASK procedure as `diversified_voi` | Adds a regularized, online directional-acceptance estimate after enough explicit feedback labels are available |
| `msmi_feedback_voi` | Scarcity-aware hard-unlock VOI, complementary hard bundles, then only ranking-relevant soft questions | Factorised expected-MSMI utility from mature released feedback; reciprocal global matching |
| `count_voi` | Count-based shortlist followed by bounded allocation evaluation | Global component-wise matching |
| `voi_only` | Immediate positive allocation-value questions without count-based diversification | Global component-wise matching |
| `count_based` | Deterministic feasibility-count clarification | Global component-wise matching |
| `foundation` | Foundation count-based clarification | Global component-wise matching |
| `foundation_fallback` | Foundation clarification | Deterministic fallback allocation |
| `no_asks_global` | No clarification requests | Global component-wise matching |

The adapter scripts `count_based_policy.py`, `voi_only_policy.py`, `count_voi_policy.py`, `diversified_voi_policy.py`, `joint_budget_voi_policy.py`, `selective_joint_voi_policy.py`, `single_only_voi_policy.py`, `joint_budget_no_redundancy_policy.py`, `feedback_voi_policy.py`, and `msmi_feedback_voi_policy.py` expose the corresponding configurations through the same JSON interface. The adapters provide evaluation paths without changing the default in `reciprocal_matching_policy.py`. The participant CLI accepts `--baseline NAME` only for compatibility with the evaluator invocation; strategy selection remains controlled by `--strategy NAME` or the chosen fixed-strategy adapter.

## Runtime Modules

| Path | Purpose |
|---|---|
| `reciprocal_matching_policy.py` | Submission entrypoint, request parsing, strategy selection, memory normalization, and JSON response emission |
| `matching_core.py` | Observable-state parsing, reciprocal feasibility, pair scoring, allocation, and final pair validation |
| `allocation_voi.py` | Bounded clarification candidate generation, counterfactual allocation evaluation, and batch selection |
| `directional_learning.py` | Optional action-time feature snapshots and online learning from explicit directional yes/no responses |
| `msmi_feedback.py` | Deduplicated mature outcome funnel rates and the factorised expected-MSMI edge utility |
| `record_provenance.py` | Sidecar metadata generator for future evaluator results |
| `organizer_study.py` | Matched ablation runner with missing-information wait and non-service diagnostics |
| `*_policy.py` adapters | Fixed-strategy entrypoints used by comparisons and ablations |
| `test_*.py` | Unit, interface, release, and regression checks |
| `evaluate.py` | Organizer-provided local evaluator |
| `kit.py` | Organizer-provided simulator and policy runner |
| `policy.py` | Organizer-provided reference policy; not this implementation's entrypoint |
| `verify_data.py` | Organizer-provided data validation utility |
| `Dockerfile` | Minimal runtime image for the policy and its participant modules |
| `Dockerfile.msmi_feedback_voi` | Separate offline image entrypoint for the experimental expected-MSMI strategy |

## Requirements

- Python 3.10 or later is recommended for local work. The current host's final test run used Python 3.9.6; earlier build checks used Python 3.12.2. The submission container uses Python 3.12.7 slim and was evaluated successfully.
- Docker image: Python 3.12.7 slim.
- No third-party Python package is required by the participant runtime. `requirements.txt` records the standard-library-only dependency policy.
- No model training is performed, so there is no training seed or training-compute requirement. The submitted `selective_joint_voi` policy is deterministic and uses no inference random seed. Evaluation seeds control the synthetic simulator, not policy randomness.
- The six-scenario matched final comparison uses simulator seeds 112 and 113. Exact reproduction commands are recorded below and in `FINAL_REPORT.md`.

## Open the Project in VS Code

Run the following commands in Windows PowerShell:

```powershell
Set-Location 'E:\Hackathon\round2\Reciprocal_Matching_Round2_Build'
code .
```

Use the VS Code integrated PowerShell terminal for the remaining commands.

## JSON Policy Interface

The policy reads one UTF-8 JSON request from standard input and writes exactly one JSON response to standard output. Diagnostic output, if any, must go to standard error. A successful invocation exits with status code `0`.

An ASK response has the form `{"asks": [...], "memory": ...}`. A MATCH response has the form `{"pairs": [...], "memory": ...}`. Field-level request and action schemas are defined in [docs/POLICY_INTERFACE.md](docs/POLICY_INTERFACE.md).

### Manual ASK Check

The following uses the valid empty-state request published in the official interface documentation:

```powershell
$request = '{"schema_version":"1.0.0","phase":"ask","state":{"schema_version":"1.0.0","synthetic":true,"day":0,"ask_budget_remaining":12,"members":[],"introductions":[],"feedback":[],"ask_log":[]},"memory":null}'
$request | python .\reciprocal_matching_policy.py | ConvertFrom-Json | ConvertTo-Json -Depth 20
```

### Manual MATCH Check

```powershell
$request = '{"schema_version":"1.0.0","phase":"match","state":{"schema_version":"1.0.0","synthetic":true,"day":0,"ask_budget_remaining":12,"members":[],"introductions":[],"feedback":[],"ask_log":[]},"memory":null}'
$request | python .\reciprocal_matching_policy.py | ConvertFrom-Json | ConvertTo-Json -Depth 20
```

For an empty state, ASK should return no clarification requests and MATCH should return no pairs. These commands verify parsing and response shape; they are not an episode evaluation.

To exercise a specific strategy, add its name after the entrypoint:

```powershell
$request | python .\reciprocal_matching_policy.py --strategy count_voi | ConvertFrom-Json | ConvertTo-Json -Depth 20
```

For experimental selectors, use `--strategy joint_budget_voi`, `--strategy single_only_voi`, `--strategy joint_budget_no_redundancy`, or `--strategy msmi_feedback_voi`, or invoke their fixed adapter scripts. Normal execution uses the `selective_joint_voi` default; no source constant needs to be edited.

## Regression Tests and Validation

Run the local regression suite:

```powershell
python -m unittest -v
```

Validate the supplied challenge data:

```powershell
python .\verify_data.py
```

The test suite covers matching-core invariants, allocation-value calculations, strategy behavior, official runner behavior, release checks, the bounded joint-question comparator, integrated joint-budget selection, redundancy-discount ablations, mature outcome feedback, hard-unlock classification, and provenance hashing. These commands are intentionally separate from full multi-day evaluations.

## Evaluation

`evaluate.py` supports participant policies through `--policy` and official baselines through `--baseline`. It also accepts explicit seeds, scenario variants, and an output path.

A one-seed development smoke evaluation can be launched with:

```powershell
python .\evaluate.py --policy .\reciprocal_matching_policy.py --seeds 101 --variants development --output .\results\implementation\recheck_seed101.json
```

For matched comparisons, use the same seeds and variants for every method. The final public-simulator comparison uses seeds 112 and 113 across all six scenario families. These commands reproduce its raw machine-readable episode files:

```powershell
python .\evaluate.py --policy .\reciprocal_matching_policy.py --seeds 112 --variants all --output .\results\evaluations\joint_budget_voi_seed112_all.json
python .\evaluate.py --policy .\reciprocal_matching_policy.py --seeds 113 --variants all --output .\results\evaluations\joint_budget_voi_seed113_all.json
python .\evaluate.py --baseline greedy --seeds 112,113 --variants all --output .\results\evaluations\final_greedy_seeds112-113_all.json
python .\evaluate.py --baseline no_asks --seeds 112,113 --variants all --output .\results\evaluations\final_no_asks_seeds112-113_all.json
python .\evaluate.py --baseline random --seeds 112,113 --variants all --output .\results\evaluations\final_random_seeds112-113_all.json
```

The primary score, scenario-level table, coverage, waiting, clarification, missing-feedback and runtime summaries are in `results/comparisons/final_submission_results.json` and `FINAL_REPORT.md`. All raw episode files are included in `results/evaluations/`. The four-way comparison is a small two-seed sample and is not evidence of reliable performance on unseen private seeds.

### Build the pinned submission archive

After any edit, refresh the file-hash inventory and create the ZIP with its external SHA-256 file:

```powershell
python .\scripts\refresh_build_manifest.py
python .\scripts\package_submission.py
```

The ZIP is written one folder above this project as `Reciprocal_Matching_Round2_Submission_2026-10-16.zip`. Upload that exact file to a public, immutable release/archive location, then use its URL and the checksum in the repository's Final submission issue. Also provide public report and results URLs. A local ZIP alone does not complete the organizer's submission process; see [SUBMISSION_CHECKLIST.md](SUBMISSION_CHECKLIST.md).

Use multiple disclosed seeds and all required scenario families for final evidence. Do not infer superiority from a smoke run or from unmatched configurations.

The new expected-MSMI challenger has been compared with the unchanged default on two matched seeds and all six variants. The result favors keeping the existing default; broader evaluation and stage calibration are still needed. See [the paired results](results/comparisons/msmi_feedback_voi_seed112-113.md).

### Organizer Feedback Study

The current reproducible study compares the single-only control, the discounted joint selector, and the no-discount challenger on seed 110, then repeats the two joint selectors on seed 111. It also records initial-missingness wait groups and separate directional feedback scores:

```powershell
python .\organizer_study.py --policy .\single_only_voi_policy.py --seeds 110 --variants all --output .\results\organizer_single_only_seed110_all.json
python .\organizer_study.py --policy .\joint_budget_voi_policy.py --seeds 110 --variants all --output .\results\organizer_joint_budget_seed110_all.json
python .\organizer_study.py --policy .\joint_budget_no_redundancy_policy.py --seeds 110 --variants all --output .\results\organizer_joint_no_redundancy_seed110_all.json
python .\evaluate.py --policy .\joint_budget_voi_policy.py --seeds 111 --variants all --output .\results\organizer_joint_budget_seed111_all.json
python .\evaluate.py --policy .\joint_budget_no_redundancy_policy.py --seeds 111 --variants all --output .\results\organizer_joint_no_redundancy_seed111_all.json
python .\organizer_study.py --policy .\feedback_voi_policy.py --seeds 110 --variants development,sparse,cold_start --output .\results\organizer_directional_feedback_seed110_core_scenarios.json
```

Full results and interpretation are in [the experiment note](results/comparisons/organizer_feedback_seed110-111.md). These commands use public synthetic data; two seeds are not enough to guarantee the challenger will generalize.

### Controlled Joint-Budget Comparison

The following matched commands keep the evaluator, development seeds, scoring logic, ASK budget, shortlist, and solver limits fixed. They use separate output files and do not replace existing results:

```powershell
$defaultCommand = "python .\evaluate.py --policy .\diversified_voi_policy.py --seeds 101,102,103,104,105,106 --variants development --output .\results\implementation\diversified_voi_seeds101-106_repeat.json"
$experimentalCommand = "python .\evaluate.py --policy .\joint_budget_voi_policy.py --seeds 101,102,103,104,105,106 --variants development --output .\results\implementation\joint_budget_voi_seeds101-106.json"
Invoke-Expression $defaultCommand
Invoke-Expression $experimentalCommand
```

MSMI per 100 arrived members is the primary comparison. Also inspect coverage, mutual acceptances, ASK cost, inference time, validity, and any available non-service diagnostics. The installed evaluator supports `development`, `sparse`, `cold_start`, `delayed`, `shift`, and `drift`. For broader validation, predeclare an unused seed set before running either policy, then run both policies on the identical seeds and variants. Do not promote the experimental strategy based only on the development seeds above.

## Docker Execution

`Dockerfile` builds the current default policy image. `Dockerfile.msmi_feedback_voi` builds a separate image whose entrypoint is the experimental `msmi_feedback_voi` adapter. Both use Python 3.12.7 slim and run as an unprivileged numeric user.

```powershell
docker build -t sequential-reciprocal-matching-round2 .
$request | docker run --rm -i sequential-reciprocal-matching-round2
```

The current default image and experimental challenger image were built and
checked on seed 112 across all six scenario variants. Every episode was valid.
For both strategies, the container action hashes exactly matched the trusted
local evaluator's action hashes on all six variants. The default and challenger
both scored 0.3333 on this one seed. This confirms container reproducibility;
it does not change the two-seed result above or establish a challenger gain.
The current container outputs and provenance sidecars are saved under
`results/evaluations/`. Older seed-101 container records refer to prior source
snapshots and are historical only.

```powershell
python .\evaluate.py --image sequential-reciprocal-matching-round2 --seeds 112 --variants all --output .\results\evaluations\joint_budget_voi_docker_seed112_all.json
```

Build and evaluate the challenger with:

```powershell
docker build -f .\Dockerfile.msmi_feedback_voi -t sequential-reciprocal-matching-msmi-feedback-voi .
python .\evaluate.py --image sequential-reciprocal-matching-msmi-feedback-voi --seeds 112 --variants all --output .\results\evaluations\msmi_feedback_voi_docker_seed112_all.json
```

## Reproducibility

- The participant policy is deterministic and does not use a random-number generator; no inference seed is required inside the policy.
- `feedback_voi` updates its model deterministically from released feedback stored in JSON memory; no model file or external training dataset is loaded.
- `msmi_feedback_voi` updates its smoothed outcome rates and directional acceptance learner only from currently released feedback stored in JSON memory; its estimated MSMI utility is uncalibrated.
- Evaluator seeds still control synthetic scenarios and must be recorded with every result file.
- `BUILD_MANIFEST.json` records hashes for the organized build. After changing files or results, refresh it with `python .\scripts\refresh_build_manifest.py` before creating an archive.
- `record_provenance.py` writes a separate JSON sidecar containing the result filename and SHA-256 hash, exact command, policy strategy, Python version, seeds, variants, evaluator settings present in the result, runtime-module hashes, and a UTC timestamp. It does not alter the evaluator result.

After the two controlled evaluations above finish, create their provenance sidecars:

```powershell
python .\record_provenance.py --result .\results\implementation\diversified_voi_seeds101-106_repeat.json --command "$defaultCommand" --strategy diversified_voi --seeds 101,102,103,104,105,106 --variants development
python .\record_provenance.py --result .\results\implementation\joint_budget_voi_seeds101-106.json --command "$experimentalCommand" --strategy joint_budget_voi --seeds 101,102,103,104,105,106 --variants development
```

The default sidecar names are `diversified_voi_seeds101-106_repeat.provenance.json` and `joint_budget_voi_seeds101-106.provenance.json`. Generate sidecars immediately after their corresponding evaluations. The helper does not infer or fabricate provenance for historical result files.

## Participant and Organizer Assets

Participant implementation files include `reciprocal_matching_policy.py`, `matching_core.py`, `allocation_voi.py`, the fixed-strategy adapter scripts, participant-focused tests, and implementation result artifacts.

Organizer-provided assets include the simulator and runner (`kit.py`), evaluator (`evaluate.py`), reference policy (`policy.py`), validation utility (`verify_data.py`), challenge data, examples, official documentation, and organizer tests. Retaining these files supports local verification; it does not make them part of the participant policy runtime.

## Known Limitations

- The pair score is a transparent heuristic, not a calibrated estimate of completed meetings or mutual second-meeting intention.
- Clarification search is deliberately bounded. The shortlist, computation cap, and pairwise joint comparator can miss useful questions or higher-order complementarities.
- The experimental joint-budget selector considers only the already evaluated three-question shortlist and complementary two-hard-question bundles. It is not an arbitrary joint-question search, and its overlap adjustment is a deterministic approximation.
- Exact allocation is limited to bounded graph components; larger components use a deterministic valid fallback.
- `feedback_voi` learns only from explicit directional acceptance responses; it has no trained date or second-meeting outcome model and does not estimate future arrivals or calibrated strategic waiting.
- Scenario-family weights are not learned from benchmark evidence.
- Multi-seed, all-family evidence remains limited to the results recorded below; it is not a guarantee of private-world performance.

## Runtime Limits

The official interface currently specifies a ten-second limit per invocation, two CPU cores, 1 GiB RAM, a 64-process limit, no network access, a read-only image, 64 MiB temporary storage, and 1 MiB limits for requests, responses, memory, and diagnostics. Consult [docs/POLICY_INTERFACE.md](docs/POLICY_INTERFACE.md) for the complete authoritative contract before packaging or evaluation.
