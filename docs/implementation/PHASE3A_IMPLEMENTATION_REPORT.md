# Sequential Reciprocal Matching Phase 3A Implementation

Status: locally verified on release 1.0.0. This is not a final submission build.

## Scope

Phase 3A adds a leakage-safe directional acceptance learner while preserving
`reciprocal_matching_policy.py` as the Phase 2 comparator. The active Phase 3A entry point is
`phase3a_policy.py`; reusable learning logic is in
`directional_learning.py`.

This phase deliberately does not implement global maximum-weight matching,
allocation-aware value of information, or joint-question search. Matching
remains deterministic greedy selection over exactly feasible edges.

## Action-time features

For every submitted introduction, the policy stores two feature vectors: A to B
and B to A. The vectors contain a bias term, signed and absolute age difference,
directional age-preference margins, same-zone status, schedule overlap, seven
visible soft-field agreements, directional soft-field missing indicators, and
directional declined-field ratios.

Features are captured during the MATCH action before feedback exists. The
snapshot is linked to the simulator-created introduction ID on the next policy
call. Later clarifications never backfill an older snapshot.

## Feedback tracking

Only released events are considered. Explicit directional `yes` and `no`
responses are mature acceptance labels. Pending responses and null/no-response
events do not train the model. A deterministic event fingerprint prevents
duplicate updates when cumulative feedback is sent again.

The memory stores a maximum of 256 action/interaction records and 2,048 event
fingerprints. It contains only synthetic identifiers, compact feature vectors,
model state, and aggregate diagnostics. On the verified episode, serialized
memory at the final policy call was 84,652 bytes, below the 1 MiB limit.

## Directional learner

A single shared directional logistic model is applied twice per candidate pair:
once to A-to-B features and once to B-to-A features. Sharing parameters is a
data-efficient choice for sparse online feedback; the two predictions are
nevertheless distinct because the feature vectors are directional. Cold-start
predictions are 0.5.

The model uses deterministic online gradient updates, mild L2 shrinkage,
decaying step size, bounded weights, and a clipped logit. Outputs are finite and
within [0, 1]. Before eight mature labels, the Phase 2 score alone is used. After
that threshold, the ranking score adds six times the smaller of the two
directional estimates. This minimum is a conservative reciprocal ranking term,
not a joint probability and not an independence assumption.

These estimates are not described as calibrated. The saved Brier and bin
statistics are prequential diagnostics: each label is evaluated using the
prediction immediately before its update.

## Outcome stages

Acceptance, date completion, and second-meeting intention are tracked as
separate stages. Phase 3A trains only the directional acceptance model. Date and
second-intention sample counts are recorded, but their sparse, selectively
observed labels are not used to claim reliable stage-specific prediction.

At the final policy call in development seed 101, the memory contained:

- 154 mature directional acceptance labels, including 79 positive labels.
- 47 censored/missing directional responses excluded from training.
- 1 pending directional response.
- 16 mature date events, including 12 completed dates visible by then.
- 20 mature second-intention labels, including 14 positive labels.
- 4 missing second-intention responses.

The 40 feedback-only days occur after the final policy call. One additional
explicit directional label matured during that period and was correctly absent
from online training.

## Verification

Executed from the development repository:

```text
The historical Phase 3A source, focused tests, and provenance-sensitive
diagnostics are preserved in the external verified backup. The active project
retains the measured result and this implementation report, but does not expose
those superseded modules as active entry points.
```

Results:

- Focused Phase 3A tests: 21/21 passed.
- Combined official and Sequential Reciprocal Matching tests: 65/65 passed.
- Public data verification: 71 files, 2,000 members, verified.
- Full episode: valid; 101 assignments, 18 mutual acceptances, 13 dates,
  2 MSMI, 1.0 MSMI per 100 arrived members, 0.465 coverage, 351 ask cost.
- Action SHA-256: `4e66a00e9cc9190e5c431bfee5b9984e4527e1046594c90bada3c9c3171299a6`.

This is one synthetic development seed. It does not establish superiority or
generalisation. Docker verification and multi-seed, all-family evaluation remain
pending.
