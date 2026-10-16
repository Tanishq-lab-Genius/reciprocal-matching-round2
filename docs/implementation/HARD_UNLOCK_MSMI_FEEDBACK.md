# Scarcity-Aware Hard Unlocking and Expected-MSMI Matching

Status: implemented and locally evaluated as an opt-in challenger on 16 October
2026. The existing `joint_budget_voi` default is unchanged. The first paired
comparison found no primary-score improvement; see [the two-seed report](../../results/comparisons/msmi_feedback_voi_seed112-113.md).

## What the challenger changes

The strategy `msmi_feedback_voi` combines two choices:

- **ASK:** prioritize legal hard-constraint bundles that can make a currently
  unresolved pair actionable, then consider a narrow set of soft questions
  that can reorder already feasible partners.
- **MATCH:** rank feasible pairs with a factorised estimate of their chance of
  producing the official mutual second-meeting-intention outcome, then use the
  existing general-graph maximum-weight matcher.

The implementation layer inside `allocation_voi.py` is named
`hard_unlock_voi`. The strategy is available through
`msmi_feedback_voi_policy.py` and `--strategy msmi_feedback_voi`.

## A/B/C partner-pool classification

The classification is recomputed from the current public observation on each
ASK call:

- **A:** at least one currently feasible partner.
- **B:** no currently feasible partner, but at least one unresolved pair whose
  missing hard fields are all currently askable. Both endpoints count as B;
  only the endpoint(s) with missing fields can receive a hard question.
- **C:** no current feasible or actionable unresolved pair. A member in C does
  not receive a question just because some profile field is blank.

Pairs with a known hard failure, declined hard information, pending hard
information, a prior introduction, or a different pool are not treated as
actionable hard-unlock opportunities. The policy cannot waive those rules.

## Expected MSMI estimate

For a feasible pair A/B, the ranking utility is an estimate of:

```text
P(A responds yes) × P(B responds yes)
× P(a date happens within 30 days after mutual yes)
× P(A says yes to a second meeting within 3 days)
× P(B says yes to a second meeting within 3 days)
```

Each directional yes probability is split into a smoothed probability that a
response is recorded and a conditional yes estimate. Before the directional
learner has enough useful feedback, the conditional estimate starts from a
Beta(1,1)-smoothed global rate and a bounded adjustment from the transparent
soft-alignment score. When the existing directional learner is ready, its
predictions are confidence-shrunk toward that transparent baseline. Date and
second-meeting rates also use Beta(1,1) smoothing.

Only released feedback with `observed_day <= current day` is used. The
directional learner trains on explicit yes/no introduction responses. A
no-response event is a non-success in the response stage but is never turned
into a negative preference label. A date contributes only after its event is
released; a date outside the 30-day window cannot contribute second-meeting
success. A second-meeting response contributes only after a qualifying date,
and only an on-time yes is a success for this funnel estimate. Repeated
cumulative events are deduplicated.

This factorisation assumes independence between stages and between the two
second-meeting responses. The data are sparse and the estimate is not a
calibrated pair-level probability. It is an initial ranking utility that must
be checked against held-out evaluator outcomes.

## ASK value and scarcity

Hard questions are generated only for currently actionable unresolved edges.
The existing bounded counterfactual solver estimates how the feasible matching
value could change under a favorable, unfavorable/unresolved, or declined
answer. Complementary hard bundles are evaluated when both endpoints have
askable missing hard information. The joint comparison is bounded; it does not
search arbitrary multi-question sets.

For ASK evaluation only, each feasible edge receives a bounded scarcity
multiplier based on the smaller number of current feasible/actionable
alternatives at its endpoints:

```text
1 + min(0.25, 0.25 / max(1, min(endpoint alternative counts)))
```

This multiplier encourages asking about edges with fewer alternatives. It is
not used in final MATCH scoring. Soft-field questions are considered only when
the member has at least two currently feasible partners with different
disclosed values for that field. Even then, a soft question is selected only
when its counterfactual allocation value is positive.

The candidate shortlist is capped at six hard and six soft questions. The ASK
search uses no more than 40 allocation calls and has a seven-second internal
time guard. Hard bundles cost the official three budget units; soft questions
cost one. If the bounded search fails before scoring candidates, its fallback
contains only actionable hard candidates. It never falls back to blind counts
or soft questions.

The hard bundle counterfactual changes only hard fields that are currently
`not_asked`. It never rewrites declined or pending fields. Hypothetical answers
are used only to value questions; they are not passed into the real MATCH
observation. MATCH receives the refreshed official state, checks reciprocal
hard eligibility again, and uses the existing one-pair-per-person matcher.

## Evaluation plan

Compare the challenger and the current default on identical fresh seeds and
the same six scenario families. Preserve raw episode JSON and provenance
sidecars. Report the official primary metric (MSMI per 100 arrived members),
plus coverage, mutual acceptances, ASK cost, inference time, validity, and
waiting/non-service by initial hard-information group. A small-sample gain is
not enough to replace the default.

The following matched local evaluation was run on seeds 112 and 113 for all
six scenario families. The challenger and default results are stored as
separate raw outputs with provenance sidecars:

```text
python evaluate.py --policy msmi_feedback_voi_policy.py --seeds 112,113 --variants all --output results/evaluations/msmi_feedback_voi_seeds112-113_all.json
python evaluate.py --policy joint_budget_voi_policy.py --seeds 112,113 --variants all --output results/evaluations/joint_budget_voi_seeds112-113_all.json
python record_provenance.py --result results/evaluations/msmi_feedback_voi_seeds112-113_all.json --command "python evaluate.py --policy msmi_feedback_voi_policy.py --seeds 112,113 --variants all" --strategy msmi_feedback_voi --seeds 112,113 --variants all
python record_provenance.py --result results/evaluations/joint_budget_voi_seeds112-113_all.json --command "python evaluate.py --policy joint_budget_voi_policy.py --seeds 112,113 --variants all" --strategy joint_budget_voi --seeds 112,113 --variants all
```

The evaluator, public worlds, hard constraints, and official daily ASK budget
were held constant. The challenger changes are the ASK utility and matching
score described above. The run produced 5 MSMI outcomes for the challenger and
10 for the default across 12 paired episodes. Mean coverage was nearly tied;
mutual acceptances were higher and ASK cost lower for the challenger. Since
this sample is small and the primary score was worse, the default remains
unchanged. See the report for per-scenario results and limitations.

Experimental offline image:

```text
docker build -f Dockerfile.msmi_feedback_voi -t sequential-reciprocal-matching-msmi-feedback-voi .
python evaluate.py --image sequential-reciprocal-matching-msmi-feedback-voi --seeds 112 --variants cold_start --output results/evaluations/msmi_feedback_voi_container_seed112_cold_start.json
```

Both the default and challenger images were built with Docker Desktop 4.95.0
and evaluated on seed 112 across all six scenario families. Every episode was
valid; the challenger and default each produced action hashes identical to
their trusted local runs for all six variants. Both scored 0.3333 on this
single seed. These runs confirm the current containers execute consistently,
but do not establish a performance gain. Raw outputs and provenance sidecars
are `results/evaluations/joint_budget_voi_docker_seed112_all.json` and
`results/evaluations/msmi_feedback_voi_docker_seed112_all.json` and their
`.provenance.json` companions. Sidecars record the exact image IDs.
The scenario-by-scenario action-hash comparison is in
`results/comparisons/docker_seed112_parity.md` and `.json`.
