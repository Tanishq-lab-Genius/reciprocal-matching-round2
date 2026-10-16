# Sequential Reciprocal Matching Round 2 Actual Build — Part 2 Completion Report

Date: 13 October 2026  
Status: ready for independent technical review; not submission-ready  
Scope: allocation-aware single-question ASK engine and controlled comparison only

## A. Project Location

- Active project: `E:\Hackathon\round2\The-Sequential-Matching-Problem-main`
- Organized build: `E:\Hackathon\round2\Reciprocal_Matching_Round2_Build`
- Preserved Part 1 checkpoint: external verified backup under `E:\Hackathon\project_backups\sequential_reciprocal_matching_pre_rename_2026-10-13`

All Part 2 work was saved inside the existing Round 2 project and its established organized-build workflow. No final submission ZIP was created.

## B. Work Completed

### Implemented and tested

1. **Four selectable ASK strategies.** `count_based`, `voi_only`, `count_voi`, and `diversified_voi` share one policy controller and the unchanged Part 1 MATCH path. Four thin executable adapters allow fair use of the official evaluator without duplicating logic. The active default is `diversified_voi`.
2. **Observable-only candidate metadata.** Every legal question is annotated with affected pairs, resolving-pair count, final-missing count, best visible pair score, current feasible-degree scarcity, endpoint competition and count priority. No simulator object, latent field, future arrival or unreleased outcome is read.
3. **Allocation-aware approximate VOI.** For a legal question `q`, the implementation calculates `max(0, sum_a w_a V(O after a) - V(O)) / cost(q)`. `V` is the value of a matching on currently feasible, observable weighted edges. This is an approximation, not a learned answer model or an exact sequential optimum.
4. **Hard and soft hypothetical scenarios.** Hard-bundle scenarios are compatible-with-anchor, incompatible-or-unresolved, and declined. Soft scenarios use up to two documented schema values, ordered by frequency among visible affected partners, plus declined. Hypotheses are applied to a deep copy and never enter real policy memory or the subsequent MATCH request.
5. **Diversified shortlisting.** The selector round-robins five deterministic rankings: count priority, high visible edge score, scarcity, final missing requirement and competition. This can retain a low-count but potentially high-impact candidate.
6. **Cost-aware multi-question batching.** Questions are ordered by VOI per official clarification unit. Pair overlap discounts the marginal score of later questions, so two questions affecting the same edges do not receive independent full allocation credit. The official 12-unit daily budget is validated atomically.
7. **Bounded computation and fallback.** At most 12 candidates are materialized for consideration, six are shortlisted, three scenarios are evaluated per question, and 19 matching solves are permitted per ASK phase. Counterfactual exact matching is limited to components of at most 12 vertices; larger components use the existing deterministic bounded fallback. A 7-second emergency guard falls back to Count-Based ASK, and final validation falls closed to an empty legal batch if needed.
8. **Diagnostics and profiling.** JSON memory records aggregate ASK calls, solve calls, evaluated questions, scenarios and fallbacks. A separate diagnostic runner measures phase totals, maximum invocation and final memory size using the official request and simulator contract.
9. **Checkpoint, evidence and build synchronization.** The verified Part 1 files were preserved before editing. Raw evaluator JSON, diagnostic JSON, comparison files, diffs and the full test log are saved and included in the organized build.

### Prepared but not implemented

The strategy registry reserves `joint_question_voi`, `feedback_adjusted` and `optional_waiting` as explicit future modes that raise `NotImplementedError`. No joint-question search, outcome learning, calibration, strategic waiting or Part 3 code was added.

## C. Files Changed

### Created

- `allocation_voi.py`: candidate metadata, scenario generation, counterfactual observations, approximate VOI, diversified shortlisting, overlap-aware selection and safe fallback.
- `count_based_policy.py`, `voi_only_policy.py`, `count_voi_policy.py`, `diversified_voi_policy.py`: evaluator adapters.
- `test_allocation_voi.py`: 16 Part 2 tests.
- `part2_profile.py`: official-contract runtime and memory diagnostic runner.
- `PART2_IMPLEMENTATION_REPORT.md`: this report.
- `results/part2_comparison.md` and `results/part2_comparison.json`.
- Four `results/part2_*_seed101.json` evaluator files and four `results/part2_profile_*_seed101_development.json` diagnostic files.
- `results/part2_test_log.txt`: current complete regression-test log.
- Historical diffs, checkpoints, and provenance-sensitive evidence are retained in the verified external backup rather than the active workspace.

### Modified

- `matching_core.py`: extended `StrategyConfig`; added Part 2 strategy registry entries; added `build_ask_decision`; retained `build_ask_action` compatibility wrapper.
- `reciprocal_matching_policy.py`: active default changed to `diversified_voi`; strategy-aware CLI and deterministic diagnostic memory added; MATCH continues to call the Part 1 `build_match_action` with the real refreshed state.
- `test_matching_policy.py`: active-default expectation updated.
- `E:\Hackathon\round2\sync_round2_build.py`: Part 2 source, tests, report and current evidence added to the explicit allowlist; manifest status advanced to local Part 2 verification.
- `E:\Hackathon\round2\packaging\Dockerfile` and `.dockerignore`: `allocation_voi.py` included in the future container context.
- `E:\Hackathon\round2\ROUND2_PROGRESS.md` and `packaging\BUILD_VERIFICATION.md`: Part 2 status and local evidence updated.

No official starter-kit source, baseline or public data file was modified. Historical line-level diffs are preserved in the verified external backup; newly created active modules are identified above.

Important interfaces are `build_ask_decision`, `select_voi_asks`, `build_question_metadata`, `plausible_scenarios`, `hypothetical_observation`, `allocation_value`, `evaluate_question`, `select_cost_aware`, `decide` and `run_cli`.

## D. Algorithm Details

### Candidate generation and Count-Based ranking

`enumerate_legal_questions` first removes known, declined, already asked/pending and otherwise illegal requests. `build_question_metadata` intersects those requests with non-infeasible observable pair states. A hard-bundle question receives count value equal to the number of unresolved pairs for which that member's constraints are missing; a soft question receives `0.25` per affected pair. Count priority divides that value by the official cost: three for `constraints`, one for a named soft field. Deterministic secondary keys use visible pair score, final-missing count, member ID and field.

### Baseline allocation and scenarios

`allocation_value` builds only exact-feasible edges through the Part 1 reciprocal gate and transparent observable pair score. For VOI re-solves, exact dynamic programming is used only on components of at most 12 vertices; larger components use the deterministic bounded matching fallback. The final real MATCH keeps the Part 1 component limit of 18 and is otherwise unchanged.

For hard questions, a visible high-scoring affected partner supplies a conservative compatible anchor. The unfavorable scenario changes one missing constraint to conflict where possible, otherwise leaves it declined/unresolved. The third scenario declines every missing hard item. For soft questions, the two documented values most common among visible affected partners are used, followed by decline. Available scenarios receive equal weight. These weights are an explicit uncalibrated approximation and are not represented as empirically estimated answer probabilities.

The raw decision value is:

`delta(q) = max(0, sum_a weight(a) * V(O after answer a) - V(O))`

The priority is `delta(q) / official_cost(q)`. Negative expected deltas are clipped to zero. `voi_only` skips zero-delta questions. The two hybrid modes permit a small deterministic count-based marginal score for zero-delta questions so that immediately neutral questions can still unlock later matching opportunities.

### Diversification, overlap and budget

`diversified_shortlist` selects round-robin from five complete deterministic orderings: count, visible edge value, scarcity, final missing requirement and endpoint competition. The shortlist cap is six. During batch construction, the marginal score is multiplied by one minus the fraction of the candidate's affected pairs already covered by selected questions. The selector checks official unit cost against remaining daily budget and final `safe_ask_batch` validation rechecks shape, duplication, history and the atomic 12-unit budget.

### Limits and fallbacks

- Maximum generated candidates considered downstream: 12.
- Shortlist: 6.
- Scenarios per question: 3.
- Matching solves per ASK: 19, including the current allocation.
- Exact component size inside VOI: 12.
- Emergency ASK wall-clock cap: 7.0 seconds, below the official 10-second process limit.
- Fallback chain: advanced selector to Count-Based ASK; final validator to a legal empty batch.
- Real MATCH: refreshed official observation only; hypothetical objects are local deep copies and discarded.

## E. Test Results

Commands actually executed:

```text
python verify_data.py
python -m unittest -v test_allocation_voi.py
python -m unittest -v
```

Final source-tree result: **85 passed, 0 failed, 0 errors, 0 skipped** in the final full run. This consists of 22 supplied tests and 63 active custom tests, including 16 Part 2 tests. The previously passing official and Part 1 tests still pass.

The Part 2 tests cover count-versus-allocation ranking, zero allocation improvement, unfavorable hard answers, multiple missing requirements, soft answers changing edge value, official costs, daily budget, known/pending/duplicate exclusion, diversified retention, solver-cap fallback, determinism, refreshed real-state MATCH, hidden-state non-interference, overlap credit, all four CLI adapters, and the VOI exact-component cap.

Saved log: `results/part2_test_log.txt`. The log is refreshed again during final source/build verification so its reported count matches the final 85-test suite.

Public data verification: 71 files verified, containing 2,000 members, 613 introductions, 1,270 feedback records and 1,129 conversations.

## F. Official Simulation Results

All strategies used public seed 101 and the official full 60-decision-day plus 40-follow-up-day simulator. `development` and the challenging `sparse` family were evaluated for every strategy. All eight episodes were valid; invalid action count was zero.

| ASK strategy | Two-family MSMI / 100 | Mean coverage | Mean mutual accepts / 100 | Mean ask cost | Mean inference s |
|---|---:|---:|---:|---:|---:|
| Count-Based | 0.25 | 31.50% | 4.25 | 361.5 | 31.511 |
| VOI-Only | 0.25 | 19.25% | 4.00 | 78.0 | 182.180 |
| Count shortlist + VOI | 0.25 | 31.50% | 4.25 | 419.5 | 160.643 |
| Diversified shortlist + VOI | 0.25 | 32.00% | 5.00 | 458.5 | 148.819 |

| Strategy | Family | MSMI | MSMI / 100 | Coverage | Ask cost | Assignments | Mutual accepts | Dates | Served / unserved |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Count-Based | development | 1 | 0.5 | 45.5% | 351 | 105 | 14 | 12 | 91 / 109 |
| Count-Based | sparse | 0 | 0.0 | 17.5% | 372 | 23 | 3 | 3 | 35 / 165 |
| VOI-Only | development | 1 | 0.5 | 29.0% | 99 | 61 | 14 | 11 | 58 / 142 |
| VOI-Only | sparse | 0 | 0.0 | 9.5% | 57 | 13 | 2 | 2 | 19 / 181 |
| Count + VOI | development | 1 | 0.5 | 45.5% | 411 | 100 | 15 | 13 | 91 / 109 |
| Count + VOI | sparse | 0 | 0.0 | 17.5% | 428 | 23 | 2 | 2 | 35 / 165 |
| Diversified + VOI | development | 1 | 0.5 | 46.5% | 465 | 111 | 18 | 14 | 93 / 107 |
| Diversified + VOI | sparse | 0 | 0.0 | 17.5% | 452 | 24 | 2 | 2 | 35 / 165 |

The primary metric is tied in this small slice. Diversified VOI shows the highest mean coverage and mutual-acceptance rate, but also the highest clarification cost. Count-Based is much faster. VOI-Only uses the fewest clarification units but leaves substantially more members unserved. None of these observations establishes general superiority.

Not completed: multi-seed evaluation; `cold_start`, `delayed`, `shift` and `drift`; uncertainty intervals; hidden evaluation; official baseline reruns in Part 2. The preserved Count-Based comparator reproduces the Part 1 action hash exactly.

## G. Runtime and Reliability

Development/seed-101 diagnostic results:

| Strategy | Maximum invocation s | Profile inference s | ASK solves | Fallbacks | Final memory bytes |
|---|---:|---:|---:|---:|---:|
| Count-Based | 0.243 | 22.383 | 0 | 0 | 334 |
| VOI-Only | 4.087 | 188.493 | 1,140 | 0 | 365 |
| Count + VOI | 2.591 | 128.491 | 1,140 | 0 | 367 |
| Diversified + VOI | 2.243 | 122.806 | 1,140 | 0 | 379 |

No final profile request exceeded 10 seconds. No final controlled episode timed out or produced an invalid action. All response memories are far below the 1 MiB limit. Evaluator and profiler action hashes match for all four strategies, demonstrating repeatability on the measured episode.

During development, profiling exposed an unbounded exact counterfactual component and then timing-dependent normal fallback. Both defects were fixed before final evidence was accepted: VOI exact components are now capped at 12, deterministic work is capped at 19 solves, and the 7-second clock is only an emergency guard. Provisional result files were overwritten by final reruns.

## H. Evidence and Reproducibility

Primary source paths are listed in Section C. Historical diffs and immutable pre-refactor evidence are preserved in the external backup. Test log: `results/part2_test_log.txt`. Evaluations:

- `results/part2_count_based_seed101.json`
- `results/part2_voi_only_seed101.json`
- `results/part2_count_voi_seed101.json`
- `results/part2_diversified_voi_seed101.json`

Profiles use the same strategy names under `results/part2_profile_<strategy>_seed101_development.json`. Consolidated evidence is in `results/part2_comparison.md` and `.json`.

Reproduction commands from the active project root:

```text
python verify_data.py
python -m unittest -v
python evaluate.py --policy count_based_policy.py --seeds 101 --variants development,sparse --output results\part2_count_based_seed101.json
python evaluate.py --policy voi_only_policy.py --seeds 101 --variants development,sparse --output results\part2_voi_only_seed101.json
python evaluate.py --policy count_voi_policy.py --seeds 101 --variants development,sparse --output results\part2_count_voi_seed101.json
python evaluate.py --policy diversified_voi_policy.py --seeds 101 --variants development,sparse --output results\part2_diversified_voi_seed101.json
python part2_profile.py --policy diversified_voi_policy.py --seed 101 --variant development --output results\part2_profile_diversified_voi_seed101_development.json
python E:\Hackathon\round2\sync_round2_build.py
```

Configuration: 12 candidate cap, 6-question shortlist, 3 scenarios/question, 19 solves/ASK, VOI exact-component limit 12, 7-second emergency cap, official 12-unit daily budget. The organized-build tests, data check, manifest and active-policy replay are recorded in `E:\Hackathon\round2\packaging\BUILD_VERIFICATION.md` after synchronization.

## I. Problems, Limitations, and Regressions

- Failed/skipped final tests: none.
- Incomplete features: joint-question complementarity, learned directional outcome model, mature-feedback learning, calibration, waiting/non-service policy and drift adaptation.
- Unverified assumption: equal scenario weights are conservative engineering assumptions, not calibrated response probabilities. A single-question immediate allocation proxy can miss complementary question pairs.
- Runtime risk: advanced ASK is 4.7–5.8 times slower in evaluator mean inference than Count-Based on the two-family slice, although measured individual requests remain below 10 seconds.
- Performance regressions: VOI-Only sharply reduces coverage (19.25% mean versus 31.50% for Count-Based) and does not improve the measured primary metric. Count+VOI and Diversified use more clarification units than Count-Based.
- Statistical limitation: one seed and two families are insufficient for general performance claims; rare MSMI outcomes make these comparisons noisy.
- Container limitation: Docker is unavailable, so the updated container has not been built or evaluated.
- Unresolved known code bugs after final runs: none observed. Independent review is still required.
- Deviation from the broadest requested evaluation: only the required minimum development plus one challenging family was completed; broader all-family/multi-seed evaluation was deferred and is explicitly not claimed.

## J. Phase Completion Checklist

- Part 1 checkpoint preserved — **Completed and tested**.
- Allocation-aware single-question VOI — **Completed and tested**.
- Independently selectable Count-Based ASK — **Completed and tested**.
- VOI-Only ASK — **Completed and tested**.
- Count shortlist + VOI — **Completed and tested**.
- Diversified shortlist + VOI — **Completed and tested**.
- Official clarification costs and budget — **Completed and tested**.
- Observable-only hypothetical scenarios — **Completed and tested**.
- Real refreshed observation for MATCH — **Completed and tested**.
- Bounded counterfactual computation — **Completed and tested**.
- Safe fallback behavior — **Completed and tested**.
- Official and custom suite — **Completed and tested**.
- Controlled official comparisons — **Completed and tested** for seed 101 on development and sparse.
- Per-invocation runtime measurement — **Completed and tested** locally.
- Organized-build synchronization and local verification — **Completed and tested**.
- Docker/container verification — **Blocked** because Docker is unavailable in the environment.
- All-family/multi-seed experiment — **Incomplete**; not required for the minimum Part 2 gate and not claimed.
- Final submission ZIP — **Incomplete by design**; explicitly prohibited at this phase.
- Part 3 — **Incomplete by design**; not started.

## K. Readiness for the Next Phase

Part 2 is ready for independent technical review. It is not yet approved for Part 3 and is not submission-ready.

Part 3 would require a bounded joint-question complementarity comparator under the same compute and information budget, mature-feedback learning with temporal label handling, and broader evaluation/optimization. Those tasks have not begun. Work stops at this review gate.
