# Organized Build Verification

> **Current status (16 October 2026):** use the dated “16 October 2026
> extension” near the end of this document and the root `HANDOFF.md` as the
> current verification record. Sections below the heading “Historical Part 2
> snapshot” describe earlier checkpoints; their pending lists are not the
> current project status.

## Historical Part 2 snapshot

Status at that checkpoint: locally verified for Round 2 Part 2 on 13 October
2026. Its statements that the final ZIP had not been created and that
multi-seed/all-family evidence was pending refer to that earlier snapshot.

All commands below were executed from the organized build root after running the synchronization script.

## Combined tests

```text
python -m unittest -v
```

Observed result: 85 tests ran; 85 passed; zero failures; zero errors; zero skipped. This includes 22 supplied tests and 63 active custom tests, including 16 Part 2 ASK tests.

## Public data verification

```text
python verify_data.py
```

Observed result: verification succeeded for 71 files containing 2,000 members, 613 introductions, 1,270 feedback records and 1,129 conversations.

## Active-policy evaluator replay

```text
python evaluate.py --policy reciprocal_matching_policy.py --seeds 101 --variants development --output E:\Hackathon\round2\build_naming_recheck_seed101.json
```

Observed result: the complete 60-day decision horizon and 40-day follow-up finished validly. The episode produced 111 assignments, 18 mutual acceptances, 14 completed dates, 1 MSMI outcome, MSMI per 100 of 0.5, coverage 0.465, 93 served and 107 unserved members, and clarification cost 465. Local inference time was 117.7422 seconds.

The replay action SHA-256 was:

```text
8b01acd1797b4218dc353df4d7775a54c32c30bfd64c5d9bc7d9de7577c508a8
```

The replay exactly matched `results/implementation/part2_diversified_voi_seed101.json` for validity, assignments, acceptance outcomes, dates, MSMI, coverage, served/unserved counts, clarification cost and action hash. Wall-clock time is not treated as deterministic.

## Part 2 evidence included

- Four selectable ASK strategy adapters and the active diversified default.
- Raw seed-101 `development,sparse` evaluator JSON for all four strategies.
- Development runtime profiles with maximum invocation, solver-call, fallback and memory diagnostics.
- Exact evaluator/profile action-hash equality for all four development strategies.
- A preserved Part 1 result and machine-readable comparison output.
- Implementation reports, contract audit, build verification and professional naming verification under `docs/implementation/`.

## Pending at the historical Part 2 snapshot

Docker is unavailable in the current environment. The updated Dockerfile has not been built or evaluated. Container verification remains mandatory before final submission. Multi-seed and all-family evidence also remains pending. Part 3 has not started.

## 16 October 2026 extension — scarcity-aware expected-MSMI challenger

The preceding sections are historical verification notes for the earlier
Round 2 Part 2 snapshot. The current workspace now also contains the opt-in
`msmi_feedback_voi` challenger and its separate adapter/image definition.

### Current local checks

- `python3 -m unittest`: 132 tests passed.
- `python3 verify_data.py`: 71 public data files verified, containing 2,000 members, 613 introductions, 1,270 feedback records, and 1,129 conversations.
- `python3 -m py_compile` completed successfully for both policies, shared runtime modules, provenance utility, and the two build/evaluation helper scripts.
- The two-seed matched comparison covered all six variants for both strategies. All 12 paired episodes were valid. The challenger produced 5 MSMI outcomes versus 10 for the unchanged default. Mean coverage was 0.3588 versus 0.3592, mutual acceptances per 100 were 5.2917 versus 4.2917, mean ASK cost was 196.42 versus 204.75, and mean inference seconds per episode were 51.85 versus 61.16.
- Raw evaluator files and provenance sidecars are in `results/evaluations/`; the paired JSON and written interpretation are `results/comparisons/msmi_feedback_voi_seed112-113.json` and `.md`.

### Container status

Both current images built successfully with Docker Desktop 4.95.0. The
default and challenger were each evaluated on seed 112 across all six scenario
families; all 12 episodes were valid. Each container run matched the trusted
local run's action hash and MSMI outcome on all six variants. Both scored
0.3333 on seed 112. The current two-seed paired decision remains unchanged:
the challenger has 5 MSMI outcomes versus 10 for the default across seeds
112-113. Container outputs, provenance, and image IDs are saved in
`results/evaluations/`; the detailed parity report is
`results/comparisons/docker_seed112_parity.md` and `.json`.

### Remaining evidence gaps

The two-seed result is exploratory and does not establish general performance.
The challenger does not replace the default. More matched seeds and per-stage
calibration/fairness diagnostics remain future work before submission.

### Continuation handoff archive

A separate continuation archive has been created at
`../Sequential_Matching_Hackathon_Handoff_2026-10-16.zip`. It contains all
manifested current-build files, a root-level handoff guide, a package index,
and the earlier 13 October handoff archive with the original research/source
materials. The packaging utility verifies the current SHA-256 manifest and
checks every ZIP entry. This is a project-continuation handoff, not the final
competition submission package; `submission_ready` remains false.
