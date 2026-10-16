# Round 2 Submission Checklist

Prepared 17 October 2026. This checklist separates local work from the public
submission action, which must be completed by a team member with access to the
team's GitHub account.

## Local package

- [x] Policy source, official interface, data contract and Dockerfile included.
- [x] README contains setup, Python/dependency and evaluation details.
- [x] Three official baselines and the current policy evaluated on the same
  seeds 112 and 113 across all six scenarios; all 48 required episodes valid.
- [x] Additional no-redundancy ablation evaluated on the same 12 episodes; all
  valid. The current default remains selected because the fresh primary scores
  tied and the default had slightly better coverage and lower question cost.
- [x] Selective Joint VOI evaluated against all three official baselines on
  fresh seeds 114 and 115 across all six scenarios; all 48 episodes valid.
  It recorded 9 MSMI outcomes, compared with 5 for greedy, 6 for
  random-feasible and 1 for no-clarification. It is the submitted default.
- [x] Raw episode JSON and provenance records included.
- [x] Technical report includes scenario results, service/wait measures,
  clarification cost, missing feedback, runtime, ablation and limitations.
- [x] Current default Docker image checked on seed 112 and all six scenarios;
  container actions matched trusted-local actions.
- [x] Public synthetic data and project licence files included; no private
  participant data or credentials are intended for this package.
- [x] Archive manifest and checksum generated and ZIP integrity checked.

## Before the official issue is submitted

1. Upload the versioned ZIP to a **public, immutable** release/archive location.
2. Copy the public URLs for the source archive, `FINAL_REPORT.md`, and
   `results/comparisons/final_submission_results.json`.
3. Confirm the uploaded ZIP's SHA-256 exactly matches the accompanying
   `.sha256` file.
4. Open the repository's Final submission issue and include the three public
   URLs plus the full SHA-256. Pin the exact archive version; do not use a
   mutable “latest” download link.
5. Re-open the public issue and verify its links before the deadline.

## Deadline note

The repository's published submission instructions currently state 18 October
2026, 23:59 IST. A newer direct organiser notice recorded in the project says
17 October 2026, 23:59 IST. Follow the newer direct notice and aim to submit by
17 October unless the organiser confirms otherwise.

The local archive is prepared, but it cannot satisfy the public-URL and final
issue requirements until a team member uploads it and opens that issue.
