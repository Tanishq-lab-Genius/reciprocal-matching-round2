# Round 2 Technical Report: Sequential Reciprocal Matching

**Prepared:** 17 October 2026  
**Evaluation data:** organizer-supplied public synthetic simulator, release 1.0.0  
**Policies and results:** source files and raw episode JSON are included in this package.

## 1. Goal and hypothesis

The task is sequential: each day, the policy may ask people to clarify missing information and then make introductions from the updated observable state. A pair is allowed only if **both people satisfy the other's hard requirements**. The policy must also avoid giving one person multiple simultaneous introductions. The official primary metric is the equal-weight mean, across the six scenario families, of mutual second-meeting intention (MSMI) outcomes per 100 arrived members.

Our hypothesis was that bounded allocation-aware clarification can use the daily question budget better than asking in list order, while a global matcher can avoid wasting a good pair because one endpoint was already assigned elsewhere. An initial candidate did not beat the active baselines on seeds 112–113. A later stricter candidate, Selective Joint VOI, did beat all three organizer baselines on public seeds 114–115; the sample remains too small to establish hidden-world superiority.

## 2. What the policy does

### Ask

The submitted default `selective_joint_voi` policy examines a bounded shortlist of hard-constraint questions and estimates whether plausible answers could change the best whole-pool matching. It can evaluate complementary pairs of hard-field questions, then selects a non-overlapping question batch within the official daily question budget only when the counterfactual allocation gain is positive. It does not spend budget on a count-based zero-value fallback. Its search is deliberately bounded; it does not examine arbitrary question sets. It uses only the current observation and policy memory.

### Match

After answers are applied, the policy re-checks reciprocal hard eligibility using the refreshed state. Unknown or declined mandatory information does not count as a pass. It scores allowed pairs using disclosed soft preferences and chooses a non-overlapping set using general-graph matching. A soft score cannot override a hard-rule failure. If no pair is currently feasible, it returns no introductions.

`selective_joint_voi` is the submitted candidate. It retains the reciprocal hard gate and global matcher from the prior policy. `joint_budget_voi` and `joint_budget_no_redundancy` remain documented experimental alternatives. The separate `msmi_feedback_voi` challenger was tested earlier and remains experimental; it scored lower than the prior candidate on seeds 112–113 (5 versus 10 MSMI outcomes), as documented in `results/comparisons/msmi_feedback_voi_seed112-113.md`.

The current default is a transparent heuristic; it is **not a trained machine-learning model**. Optional online feedback strategies exist in the source tree but are not the selected default.

## 3. Observations, missing information and leakage controls

The policy reads only the evaluator's observable JSON state and its bounded JSON memory. It does not read hidden simulator outcomes, future arrivals, or unreleased feedback. A missing, declined, or unresolved hard answer blocks a pair when that answer is required to verify reciprocal eligibility. Feedback-based experimental strategies update only from released, mature feedback; their use and limits are documented separately.

The official interface offers ASK and MATCH, not a separate WAIT action. When no currently feasible edge exists, this policy returns an empty matching. That is non-service for that day, not a learned decision to wait. The report therefore measures unserved people and observed waits rather than claiming the policy optimizes waiting.

## 4. Evaluation design

We ran the current candidate and the three supplied baselines on the **same two simulator seeds (112, 113)** and all six official scenario families: development, sparse, cold start, delayed, shift and drift. That is 12 episodes per policy and 48 episodes for the four-way required comparison. We also ran the no-redundancy ablation on those same 12 episodes, for 60 episodes total. **All 60 episodes were valid.** The comparison is small and public; it does not establish performance on hidden seeds.

The primary score is computed by averaging each policy's MSMI-per-100-arrivals rate over the two seeds within each scenario, then taking the unweighted mean of the six scenario rates. The other summary metrics are arithmetic means across the 12 episodes. Waiting statistics use served members' first-introduction wait days; unserved members are reported separately. Runtime is the evaluator's total policy inference time per episode, not a single call's time limit.

## 5. Overall results

### Final submitted candidate: fresh matched public comparison

The submitted Selective Joint VOI candidate and the three organizer baselines were evaluated on the same fresh public seeds, 114 and 115, across all six scenario families. All 48 episodes were valid.

| Policy | MSMI outcomes / 12 episodes | Primary score | Coverage | Mutual acceptances / 100 | ASK cost / episode | Runtime seconds / episode |
|---|---:|---:|---:|---:|---:|---:|
| Submitted candidate: Selective Joint VOI | **9** | **0.3750** | 21.29% | 2.92 | 79.5 | 138.2 |
| Official greedy baseline | 5 | 0.2083 | 30.38% | 4.17 | 193.8 | 14.4 |
| Official random-feasible baseline | 6 | 0.2500 | 30.58% | 3.83 | 193.8 | 15.3 |
| Official no-clarification baseline | 1 | 0.0417 | 11.38% | 1.33 | 0.0 | 16.5 |

The submitted candidate had the highest public-simulator primary score in this matched two-seed comparison. It asked fewer questions than greedy and random-feasible, but served fewer people and required more total inference time. Every individual policy invocation remained within the evaluator's ten-second limit. This small public comparison is evidence for selecting the candidate, not a claim about private worlds. Raw results and machine-readable matched comparisons are in `results/evaluations/selective_joint_voi_seed114_all.json`, `results/evaluations/selective_joint_voi_seed115_all.json`, and `results/comparisons/selective_joint_voi_seeds114-115.md`.

### Earlier candidate comparison

| Policy | MSMI outcomes / 12 episodes | Primary score | Coverage | Mutual acceptances / 100 | ASK cost / episode | Mean first-intro wait (served) | Unserved / episode | Missing feedback / episode | Runtime seconds / episode | Valid episodes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Our submitted candidate: joint_budget_voi | 10 | 0.4167 | 35.9% | 4.29 | 204.8 | 10.1 | 128.2 | 36.8 | 61.2 | 12/12 |
| Official greedy baseline | 14 | 0.5833 | 36.1% | 4.92 | 194.5 | 6.5 | 127.8 | 31.4 | 9.5 | 12/12 |
| Official random-feasible baseline | 13 | 0.5417 | 36.0% | 5.62 | 194.5 | 6.2 | 127.9 | 33.5 | 10.0 | 12/12 |
| Official no-clarification baseline | 3 | 0.1250 | 14.2% | 1.12 | 0.0 | 3.0 | 171.7 | 9.2 | 11.6 | 12/12 |
| Experimental challenger: joint_budget_no_redundancy | 10 | 0.4167 | 35.7% | 4.46 | 211.8 | 9.7 | 128.7 | 35.9 | 60.7 | 12/12 |

On these seeds, greedy was highest on the primary score (14 MSMI outcomes), followed by random-feasible (13), our current policy (10), and no-clarification (3). The default improved substantially over no-clarification in both primary outcome and service coverage, but it did not beat the two active baselines in this sample. The gap was driven mainly by seed 113: greedy recorded 12 MSMI outcomes there, random-feasible 11, and our default 6. On seed 112 our default recorded 4 versus 2 for each of those baselines. This seed-to-seed variation is a reason to avoid strong claims from only two seeds.

The no-redundancy ablation tied the current default at 10 MSMI outcomes and a 0.4167 primary score on seeds 112–113. Its coverage was slightly lower (35.67% versus 35.92%) and its mean ASK cost slightly higher (211.75 versus 204.75). Thus this fresh matched test does **not** confirm the earlier apparent gain by removing the discount.

## 6. Scenario-level results and service

Each row below summarizes the two seeds for one scenario. `MSMI outcomes` is the total over those two 200-member episodes. `Mean wait` and `P90 wait` are among served members only. All rows are valid.

| Scenario | Policy | MSMI outcomes / 2 episodes | MSMI / 100 arrivals | Coverage | Mean wait (served, days) | P90 wait (days) | Unserved / episode | ASK cost / episode | Missing feedback / episode | Runtime seconds / episode | Valid |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| development | Our submitted candidate: joint_budget_voi | 3 | 0.75 | 39.5% | 9.3 | 27.0 | 121.0 | 200.0 | 42.5 | 57.7 | true |
| development | Official greedy baseline | 3 | 0.75 | 39.8% | 6.1 | 16.0 | 120.5 | 183.0 | 33.0 | 9.5 | true |
| development | Official random-feasible baseline | 3 | 0.75 | 39.8% | 5.8 | 13.2 | 120.5 | 183.0 | 37.5 | 9.8 | true |
| development | Official no-clarification baseline | 1 | 0.25 | 17.8% | 2.8 | 9.0 | 164.5 | 0.0 | 11.5 | 10.9 | true |
| development | Experimental challenger: joint_budget_no_redundancy | 3 | 0.75 | 39.2% | 8.9 | 25.4 | 121.5 | 206.0 | 43.0 | 55.6 | true |
| sparse | Our submitted candidate: joint_budget_voi | 0 | 0.00 | 19.5% | 9.6 | 26.3 | 161.0 | 194.5 | 11.0 | 69.4 | true |
| sparse | Official greedy baseline | 0 | 0.00 | 19.5% | 6.2 | 15.0 | 161.0 | 196.5 | 14.0 | 9.7 | true |
| sparse | Official random-feasible baseline | 0 | 0.00 | 19.5% | 6.0 | 14.3 | 161.0 | 196.5 | 15.5 | 10.4 | true |
| sparse | Official no-clarification baseline | 0 | 0.00 | 6.0% | 3.6 | 11.4 | 188.0 | 0.0 | 2.5 | 11.7 | true |
| sparse | Experimental challenger: joint_budget_no_redundancy | 1 | 0.25 | 19.5% | 9.4 | 26.0 | 161.0 | 199.5 | 11.5 | 66.9 | true |
| cold_start | Our submitted candidate: joint_budget_voi | 1 | 0.25 | 37.2% | 13.0 | 33.0 | 125.5 | 236.5 | 40.5 | 67.4 | true |
| cold_start | Official greedy baseline | 4 | 1.00 | 38.0% | 8.3 | 18.9 | 124.0 | 238.5 | 36.0 | 8.9 | true |
| cold_start | Official random-feasible baseline | 3 | 0.75 | 37.8% | 8.2 | 19.0 | 124.5 | 238.5 | 35.0 | 9.5 | true |
| cold_start | Official no-clarification baseline | 0 | 0.00 | 8.0% | 4.6 | 10.9 | 184.0 | 0.0 | 5.5 | 14.3 | true |
| cold_start | Experimental challenger: joint_budget_no_redundancy | 1 | 0.25 | 37.2% | 13.0 | 33.0 | 125.5 | 242.0 | 40.5 | 67.3 | true |
| delayed | Our submitted candidate: joint_budget_voi | 0 | 0.00 | 40.0% | 9.6 | 27.0 | 120.0 | 197.5 | 44.5 | 58.2 | true |
| delayed | Official greedy baseline | 1 | 0.25 | 39.8% | 6.1 | 16.0 | 120.5 | 183.0 | 40.0 | 9.6 | true |
| delayed | Official random-feasible baseline | 1 | 0.25 | 40.0% | 5.9 | 14.0 | 120.0 | 183.0 | 39.0 | 11.2 | true |
| delayed | Official no-clarification baseline | 0 | 0.00 | 17.8% | 2.8 | 9.0 | 164.5 | 0.0 | 12.0 | 11.5 | true |
| delayed | Experimental challenger: joint_budget_no_redundancy | 0 | 0.00 | 39.2% | 9.0 | 26.0 | 121.5 | 207.0 | 40.0 | 54.5 | true |
| shift | Our submitted candidate: joint_budget_voi | 3 | 0.75 | 39.8% | 9.5 | 27.0 | 120.5 | 199.5 | 39.5 | 55.6 | true |
| shift | Official greedy baseline | 3 | 0.75 | 39.8% | 6.4 | 16.0 | 120.5 | 183.0 | 32.5 | 9.4 | true |
| shift | Official random-feasible baseline | 3 | 0.75 | 39.5% | 5.7 | 13.3 | 121.0 | 183.0 | 36.5 | 10.1 | true |
| shift | Official no-clarification baseline | 1 | 0.25 | 17.8% | 2.8 | 9.0 | 164.5 | 0.0 | 12.0 | 10.4 | true |
| shift | Experimental challenger: joint_budget_no_redundancy | 2 | 0.50 | 39.5% | 9.1 | 26.0 | 121.0 | 209.0 | 38.0 | 59.2 | true |
| drift | Our submitted candidate: joint_budget_voi | 3 | 0.75 | 39.5% | 9.3 | 27.0 | 121.0 | 200.5 | 42.5 | 58.8 | true |
| drift | Official greedy baseline | 3 | 0.75 | 39.8% | 6.1 | 16.0 | 120.5 | 183.0 | 33.0 | 9.8 | true |
| drift | Official random-feasible baseline | 3 | 0.75 | 39.8% | 5.8 | 13.2 | 120.5 | 183.0 | 37.5 | 9.0 | true |
| drift | Official no-clarification baseline | 1 | 0.25 | 17.8% | 2.8 | 9.0 | 164.5 | 0.0 | 11.5 | 10.7 | true |
| drift | Experimental challenger: joint_budget_no_redundancy | 3 | 0.75 | 39.2% | 8.9 | 25.4 | 121.5 | 207.0 | 42.5 | 60.6 | true |

On the current default, average coverage was 35.92%; about 128 of 200 people per episode were unserved. Among those served, mean wait to a first introduction was 10.1 days and the 90th percentile was 27.9 days. The average missing-feedback count was 36.75 per episode. These are simulator outcomes, not evidence about real-world participants. The separate organizer-feedback study also found that people with more initially missing hard fields were served less often, but its subgroup sample was small; see `results/comparisons/organizer_feedback_seed110-111.md`.

### Scores by seed

| Seed | Policy | MSMI outcomes / 6 episodes | Primary score | All valid |
|---:|---|---:|---:|:---:|
| 112 | Our submitted candidate: joint_budget_voi | 4 | 0.3333 | true |
| 112 | Official greedy baseline | 2 | 0.1667 | true |
| 112 | Official random-feasible baseline | 2 | 0.1667 | true |
| 112 | Official no-clarification baseline | 0 | 0.0000 | true |
| 112 | Experimental challenger: joint_budget_no_redundancy | 6 | 0.5000 | true |
| 113 | Our submitted candidate: joint_budget_voi | 6 | 0.5000 | true |
| 113 | Official greedy baseline | 12 | 1.0000 | true |
| 113 | Official random-feasible baseline | 11 | 0.9167 | true |
| 113 | Official no-clarification baseline | 3 | 0.2500 | true |
| 113 | Experimental challenger: joint_budget_no_redundancy | 4 | 0.3333 | true |

## 7. Hypothesis-driven ablation: redundancy discount

The organizer asked whether a redundancy penalty could make the single-question policy miss useful joint information. The controlled ablation held the matcher and main ASK bounds fixed and compared the current joint selector with the same joint selector without the overlap discount.

On seeds 110–111, the earlier study recorded 14 MSMI outcomes without the discount versus 10 with it across 12 episodes, with a modest increase in question cost and slightly lower mutual acceptance. On the fresh matched seeds 112–113, both versions recorded 10 MSMI outcomes; the discounted default had slightly higher coverage and slightly lower ASK cost. The combined evidence is mixed: removing the discount helped in the first two seeds but not the next two. We therefore kept the existing default and do not claim that the ablation is an improvement. Full methods and diagnostics are in `results/comparisons/organizer_feedback_seed110-111.md`; the fresh raw JSON is `results/evaluations/final_joint_budget_no_redundancy_seeds112-113_all.json`.

## 8. Runtime, data and provenance

- The participant runtime uses Python's standard library only; `requirements.txt` lists no third-party runtime packages. The container uses Python 3.12.7 slim. The final host-side test and data-verification commands used Python 3.9.6; earlier project checks used Python 3.12.2. The recommended local version is Python 3.10 or later.
- No model training or external dataset was used. There is no training seed or training-compute requirement. The submitted default is deterministic and uses no inference random seed; the evaluation seeds control the synthetic simulator. The official random baseline uses its supplied deterministic day-based seed.
- The source licence is `LICENSE`; the public synthetic dataset is covered by `DATA_LICENSE.md`. No real-person records are included. Code and data provenance details are in `BUILD_MANIFEST.json`, `data_manifest.json`, `data_checksums.json`, and the `.provenance.json` sidecars beside evaluation files.
- The current default Docker image was built and evaluated on seed 112 across all six scenarios; all six episodes were valid and action hashes matched the trusted-local run exactly. See `results/comparisons/docker_seed112_parity.md`. The optional expected-MSMI image was also checked there.
- The final local suite ran 132 tests successfully, and `verify_data.py` verified 71 public data files. The outputs are preserved in `results/logs/final_unit_tests.txt` and `results/logs/final_data_verification.json`. These checks do not prove a hidden-world score.

## 9. Limitations and next steps

1. Two matched seeds are too few to establish stable policy superiority; the public scores vary sharply by seed.
2. The main policy uses bounded two-question search, not arbitrary question combinations. Its allocation-value estimate is approximate.
3. The policy has no explicit wait action and does not solve the high non-service rate observed in sparse scenarios.
4. The default soft-alignment score is a hand-designed ranking rule, not a calibrated probability of mutual second-meeting intention.
5. Optional feedback models have limited mature labels and remain experimental; do not rely on them as calibrated probabilities.
6. Simulator outcomes are synthetic and cannot establish product effectiveness or fairness for real people.
7. Before real-world use, an authorized data adapter, privacy review, consent process, safety/fairness evaluation and validation on representative real outcomes would be required.

## 10. Reproduction files and commands

The full machine-readable summary is `results/comparisons/final_submission_results.json`. It links to the raw episode files. Example commands from the project root:

```text
python3 -m unittest -v
python3 verify_data.py
python3 evaluate.py --policy reciprocal_matching_policy.py --seeds 112 --variants all --output results/evaluations/joint_budget_voi_seed112_all.json
python3 evaluate.py --policy reciprocal_matching_policy.py --seeds 113 --variants all --output results/evaluations/joint_budget_voi_seed113_all.json
python3 evaluate.py --baseline greedy --seeds 112,113 --variants all --output results/evaluations/final_greedy_seeds112-113_all.json
python3 evaluate.py --baseline no_asks --seeds 112,113 --variants all --output results/evaluations/final_no_asks_seeds112-113_all.json
python3 evaluate.py --baseline random --seeds 112,113 --variants all --output results/evaluations/final_random_seeds112-113_all.json
python3 evaluate.py --policy joint_budget_no_redundancy_policy.py --seeds 112,113 --variants all --output results/evaluations/final_joint_budget_no_redundancy_seeds112-113_all.json
```

## 11. Tool assistance disclosure

AI assistance was used for brainstorming, implementation support and report drafting. I reviewed and revised the approach and checked the implementation through the tests and evaluations reported here.
