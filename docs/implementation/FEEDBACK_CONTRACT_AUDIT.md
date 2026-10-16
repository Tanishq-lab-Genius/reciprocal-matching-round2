# Sequential Reciprocal Matching Phase 3A Feedback-Contract Audit

Status: verified against release 1.0.0 source and documentation.

## Observable interaction contract

The evaluator calls a policy as a fresh process twice per decision day: first
`ask`, then `match`. The `match` call receives the refreshed observation after
the simulator resolves that day's legal clarification batch. JSON `memory` is
the only policy-owned state that persists between processes.

An observation contains arrived members, currently observable profile fields,
field disclosure states, introduction records, released feedback, and the
remaining daily clarification budget. It contains no future arrivals, hidden
truth fields, unreleased events, simulator random state, or private outcomes.

Each introduction record has `introduction_id`, `user_a`, `user_b`,
`assigned_day`, and `response_deadline_day`. This provides an exact link from a
later feedback event to its historical action.

## Outcomes and maturity

`introduction_response` is directional. Each event carries both the
`introduction_id` and the responding `member_id`; therefore A-accepts-B and
B-accepts-A are separately identifiable. An explicit `yes` or `no` is a mature
directional label. Before an event is released, its outcome is pending. A
released `null` value with `missing_reason: no_response` is missing/censored and
is not a negative preference label.

`date_happened` is pair-level (`member_id` is null), Boolean, and emitted only
after two recorded positive introduction responses. It is a separate stage and
must not be inferred for pairs lacking mutual acceptance.

`second_meeting_intention` is directional, appears only after a completed date,
and may be `yes`, `no`, or `null`. A null response remains missing rather than a
negative label. The primary MSMI outcome additionally requires both positive
intentions within the specified three-day window. A later response can remain
in feedback while failing that outcome-window test.

`pause_after_mutual_interest` is a pair-level availability event and is not a
training label.

Only events with `observed_day <= current day` are released by the simulator.
The policy is called for 60 decision days. The subsequent 40 days advance
feedback but do not call the policy, so those newly released events cannot be
used by online training during that episode.

## Limits and implications

- Policy invocation time limit: 10 seconds.
- Request, response, and serialized memory limit: 1 MiB each.
- Assessed container limit: 2 CPU cores, 1 GiB RAM, offline execution.
- Actions and memory must be strict finite JSON.
- Clarification budget is 12 units per decision day.

Phase 3A may train a directional acceptance model because genuine directional
labels exist. It does not manufacture labels for pending or missing responses.
Date and second-intention events are tracked separately, but no reliable model
for those sparse downstream stages is claimed in Phase 3A. The model stores
action-time feature vectors before feedback and never reconstructs them from a
later, more complete profile.

## Sources inspected

- `docs/DATA_CONTRACT.md`
- `docs/POLICY_INTERFACE.md`
- `kit.py`
- `evaluate.py`
- `policy.py`
- `reciprocal_matching_policy.py`
- official and Sequential Reciprocal Matching tests
