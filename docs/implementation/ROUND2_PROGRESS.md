# Sequential Reciprocal Matching - Round 2 Progress

> **Current state:** dated sections are newest-first. The 16 October 2026
> status at the top and root `HANDOFF.md` supersede unchecked boxes in older
> phase snapshots below. Those older lists are retained as a historical
> record, not as today's task list.

## Final matched baseline and packaging check — 16 October 2026

- [x] Ran `joint_budget_voi`, greedy, no-asks and random-feasible on seeds 112
  and 113 across all six official scenarios; all 48 required episodes were
  valid.
- [x] Ran the no-redundancy challenger on the same 12 episodes; all were
  valid. It tied the default's primary score (10 MSMI outcomes each), with
  slightly lower coverage and slightly higher ASK cost. Keep the current
  default.
- [x] Added `FINAL_REPORT.md` and
  `results/comparisons/final_submission_results.json`, including scenario
  outcomes, service/waiting, clarification cost, missing feedback, runtime,
  seed variation, ablation interpretation and limitations.
- [x] Saved final test and data-verification logs under `results/logs/`.
- [x] Added provenance sidecars for every final matched result file.
- [x] Added a manifest-checked submission archiver and a checklist for the
  public upload and Final submission issue.
- [x] Refreshed the 241-file manifest and generated the verified local ZIP and
  its adjacent SHA-256 file: `../Reciprocal_Matching_Round2_Submission_2026-10-16.zip`.
- [ ] A team member must publish the immutable archive and open the official
  Final submission issue with public source, report and results URLs.

The matched two-seed scores were: greedy 0.5833, random-feasible 0.5417,
`joint_budget_voi` 0.4167, no-clarification 0.1250. These are exploratory
public-simulator values, not a claim of stable performance on unseen seeds.
The published repository instructions say 18 October, while the newer direct
organizer notice recorded by the team says 17 October 2026, 23:59 IST. Follow
the earlier deadline unless the organizer confirms otherwise.

## Scarcity-aware expected-MSMI challenger — 16 October 2026

- [x] Added the opt-in `msmi_feedback_voi` policy while preserving `joint_budget_voi` as the default.
- [x] Added observable A/B/C pool classification and hard questions only for actionable unresolved links with askable hard fields.
- [x] Added bounded scarcity adjustment to ASK utility only, complementary hard bundles, and soft questions only when they can reorder multiple feasible partners.
- [x] Added a smoothed expected-MSMI edge utility that uses released mature response/date/second-meeting feedback and retains transparent soft alignment before the directional learner is reliable.
- [x] Preserved the refreshed-state reciprocal eligibility check and one-pair-per-person matcher; hypothetical ASK values never become MATCH inputs.
- [x] Added challenger tests, a fixed adapter, a separate offline Dockerfile, provenance hashes, and a method/assumption/evaluation note.
- [x] Ran matched local evaluations against `joint_budget_voi` on seeds 112–113 and all six scenario families; all 12 paired episodes were valid.
- [x] Built both current Docker images and evaluated seed 112 on all six variants; all container episodes were valid and their action hashes matched trusted local runs.
- [x] Saved raw evaluator outputs, provenance sidecars, paired JSON and a written analysis. The challenger had 5 MSMI outcomes versus 10 for the default; the default remains selected.
- [ ] More fresh seeds and per-stage calibration remain needed before considering a strategy change.
- [ ] Do not promote the challenger or replace the default until fresh multi-seed, six-scenario results are reviewed.

## Organizer-feedback follow-up — 16 October 2026

- [x] Added a single-question-only control and a no-redundancy joint-VOI ablation under the same ASK budget, shortlist, solver-call cap, time guard, and MATCH policy.
- [x] Compared all six public variants on seed 110; repeated the discounted and no-discount joint selectors on seed 111.
- [x] The no-discount challenger recorded 14 MSMI outcomes versus 10 for the current joint selector across 12 matched episodes, while using more ASK budget. This is promising but small-sample evidence; it has not replaced the default.
- [x] Added missing-hard-information service/wait diagnostics and separate directional Brier scores to the study runner.
- [x] Recorded the full results, caveats, and next experiment in `results/comparisons/organizer_feedback_seed110-111.md`.

Governing deadline: **17 October 2026, 11:59 PM IST**. This is the newer organiser announcement and overrides the 18 October date embedded in release 1.0.0.

## Phase 1 - Starter-kit verification

- [x] Extracted the supplied release into `The-Sequential-Matching-Problem-main/`.
- [x] Inspected the problem statement, data contract, policy interface, evaluator, baselines, tests, Dockerfile, submission guide, report guide, manifest, FAQ and changelog.
- [x] Confirmed Python 3.12.2; the starter requires only the standard library.
- [x] Ran `python -m unittest -v`: 22/22 tests passed.
- [x] Ran `python verify_data.py`: 71 files verified; 2,000 members across ten pools.
- [x] Ran the official greedy baseline for seed 101, development variant.
- [x] Confirmed valid execution, MSMI count 1, score 0.5, and an action SHA-256 identical to the checked reference run.
- [ ] Docker/container verification: blocked because Docker is not installed or not available on PATH.

## Verified official contract

- Two calls per decision day: ASK, then MATCH using refreshed state.
- ASK returns exactly `asks` and `memory`; MATCH returns exactly `pairs` and `memory`.
- Clarification budget: 12 units/day; hard bundle costs 3, named soft field costs 1.
- Feasibility is reciprocal and exact; missing hard data blocks introduction.
- Complete batches are atomic; empty ask and match lists are valid.
- 60 decision days followed by 40 feedback-only days.
- Primary metric: equal-weight mean of MSMI per 100 arrived members across six scenario families.
- Required official comparisons: greedy, no-clarification and random-feasible on matched seeds and variants.
- Assessed inference: 10 seconds per call, 2 CPU cores, 1 GiB RAM, 1 MiB request/response/memory, offline container.

## Missing Sequential Reciprocal Matching deliverables

- [x] Phase 2 custom validity-first policy implementation.
- [x] Exact-feasibility final guard and deterministic legal no-match behavior.
- [x] Separate ASK/MATCH handling with refreshed-state use.
- [x] Deterministic reciprocal heuristic and greedy non-overlapping matching.
- [x] Twenty-two focused Sequential Reciprocal Matching tests; combined suite is 44/44 passing.
- [x] Valid full development/seed-101 official evaluator episode.
- [x] Repeat run confirmed identical action SHA-256 and non-runtime metrics.
- [x] Saved raw Phase 2 result, comparison and reproduction notes.
- [x] Bounded component-wise general-graph matching and deterministic fallback (Part 1).
- [x] Directional probability and mature-feedback feature pipeline (Phase 3A).
- [x] Allocation-aware single-question selector with four selectable ASK strategies.
- [ ] Bounded two-question comparator and redundancy-penalty ablation.
- [ ] Matched-seed baseline/ablation experiments across all six variants.
- [ ] Calibration, waiting/non-service and missingness-level diagnostics.
- [ ] Reproducible Docker build and container evaluation.
- [ ] Final README, machine-readable results, figures, technical report and immutable submission package.

## Phase 2 acceptance checklist

- [x] Executable Sequential Reciprocal Matching source exists and accepts the evaluator command.
- [x] ASK and MATCH outputs follow the exact JSON contract.
- [x] Reciprocal hard constraints and unresolved information are handled explicitly.
- [x] Matching output contains no duplicate endpoint and excludes repeated pairs.
- [x] Official supplied tests pass.
- [x] Sequential Reciprocal Matching tests pass.
- [x] One complete development/seed-101 episode is valid.
- [x] Raw results and baseline comparison are saved.
- [x] Reproduction commands and implementation limitations are documented.
- [x] Progress checklist updated.
- [ ] Docker/container validation remains outstanding for pre-submission work.

## Organized build

- [x] Created `Reciprocal_Matching_Round2_Build/` without moving or renaming the development repository.
- [x] Preserved the active root-level policy/evaluator layout required by the official commands.
- [x] Separated active Sequential Reciprocal Matching source, official baseline/reference files, raw results and comparisons.
- [x] Added a standard-library synchronization script with an explicit allowlist and safe staging replacement.
- [x] Added a SHA-256 build manifest identifying the active policy and every packaged file.
- [x] Ran 65/65 tests from the organized Phase 3A build.
- [x] Verified all 71 public data files from the organized build.
- [x] Completed a valid Phase 3A official evaluator replay from the organized build.
- [x] Confirmed the replay action SHA-256 and all non-runtime metrics match the saved Phase 3A result.
- [ ] Docker build and isolated evaluator check remain pending.
- [ ] Final technical report, full experiments and submission audit remain pending.
- [ ] `Reciprocal_Matching_Round2_Submission.zip` is reserved but has not been created.

## Phase 3A acceptance checklist

- [x] Audited and documented the release 1.0.0 feedback contract.
- [x] Confirmed directional introduction responses are identifiable by member and introduction ID.
- [x] Captured deterministic directional features at action time without later backfilling.
- [x] Excluded pending and null/no-response outcomes from negative labels.
- [x] Added bounded JSON-memory tracking with duplicate-event protection.
- [x] Added a deterministic regularized online directional acceptance model.
- [x] Preserved Phase 2 unchanged as a comparator and fallback source.
- [x] Added 21 Phase 3A tests; combined suite is 65/65 passing.
- [x] Completed a valid development/seed-101 official evaluator episode.
- [x] Saved raw evaluation, learning diagnostics and three-policy comparison.
- [x] Verified 71 public data files after implementation.
- [ ] Docker/container verification remains outstanding.
- [ ] Multi-seed, all-family evidence remains outstanding.

## Round 2 actual build - Part 1

- [x] Preserved the previous working implementation in a recoverable archive outside the active import path.
- [x] Replaced the active Sequential Reciprocal Matching entry point with a clean foundation controller.
- [x] Added separate observation, feasibility, scoring, ASK, matching and validation components.
- [x] Implemented exact reciprocal feasibility with explicit unresolved requirements.
- [x] Implemented deterministic transparent observable-only scoring.
- [x] Implemented count-per-cost hard-constraint ASK shortlisting.
- [x] Implemented exact matching on components up to 18 vertices and bounded fallback on larger components.
- [x] Added strict final ASK and MATCH validation with legal fallbacks.
- [x] Added explicit implemented and future strategy modes.
- [x] Added 47 active custom tests; combined suite is 69/69 passing.
- [x] Recorded deterministic graph quality and runtime benchmarks.
- [x] Completed a valid development/seed-101 full evaluator smoke test.
- [x] Saved raw Part 1 results and comparison against preserved policies.
- [x] Organized build resynchronized; 69 tests, data verification and full replay passed.
- [ ] Docker/container verification remains outstanding.

## Historical next step — superseded 16 October 2026

At that checkpoint, Part 2 was complete and joint-question complementarity had not begun. After the organizer's Round 2 feedback and the user's go-ahead, bounded two-question experiments and directional diagnostics were added; see the follow-up at the top of this file.

## Round 2 actual build - Part 2

- [x] Preserved a recoverable Part 1 checkpoint before editing.
- [x] Implemented selectable Count-Based, VOI-Only, Count+VOI and Diversified+VOI ASK strategies.
- [x] Added observable-only hard/soft hypothetical scenarios and isolated counterfactual observations.
- [x] Added approximate allocation delta per official clarification cost.
- [x] Added diversified shortlisting and overlap-aware budgeted multi-question selection.
- [x] Bounded counterfactual work to 12 candidates, six shortlisted questions, three scenarios each, 19 solves and small exact components.
- [x] Added legal Count-Based and empty-batch fallback paths.
- [x] Added 16 Part 2 tests; combined source suite is 85/85 passing.
- [x] Completed matched seed-101 official evaluations for development and sparse across all four strategies.
- [x] Profiled maximum request time, solver calls, fallbacks and final memory for all strategies.
- [x] Confirmed official/profile action-hash equality for all four development runs.
- [x] Saved raw JSON, comparison, diffs, test log and the A-K completion report.
- [x] Resynchronized and locally verified the organized build.
- [ ] Docker/container verification remains blocked because Docker is unavailable.
- [ ] All-family and multi-seed experiments remain incomplete and are not claimed.
- [ ] Part 3 has not started; independent review is required first.
