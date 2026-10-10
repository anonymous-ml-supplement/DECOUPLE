# Reproducibility and release audit

## Frozen-core reference verification

A completed reference-lab `make reviewer-check` run with Python 3.10.12, NumPy 2.2.6 and Matplotlib 3.10.9 reported the following verified results:

| Check | Evidence |
|---|---|
| Source syntax and first-party dependencies | `FINAL_SOURCE_TREE_STATUS=PASS` |
| Local package manifest | `FINAL_RELEASE_MANIFEST_STATUS=PASS` |
| Frozen inputs | `FINAL_FROZEN_HASH_STATUS=PASS` (17 authorities) |
| Expected outputs | `FINAL_EXPECTED_HASH_STATUS=PASS` (48 authorities) |
| Local static anonymity scan | `FINAL_ANONYMITY_STATUS=PASS`; scanner self-included |
| Original-instance LOO reconstruction | `FINAL_LOO_UPSTREAM_REPLAY_STATUS=PASS`; 187 rows, 1,870 numeric cells |
| Frozen numerical comparisons | `FINAL_OUTPUT_COMPARISON_STATUS=PASS`; 32 matches, 0 failures |
| Paper headline consistency | `FINAL_CLAIM_VALIDATION_STATUS=PASS` |
| Full frozen-core numerical workflow | `FINAL_REPRODUCTION_STATUS=PASS` |

The scientific methods, protected analyses and archived frozen authorities in this checkout have the same bytes as the tested source. Reader-facing documentation, evidence-mapping utilities and archive integrity listings were updated without changing scientific inputs or numerical methods. The current checkout's static audit is tested separately. Do not interpret a reference-lab result as a newly executed complete numerical run on every future Git commit.

## Coverage boundaries

The above PASS is for the included **frozen shared core**. Four reported extension analyses lack complete original per-instance/per-step raw evidence in this package. The [coverage matrix](docs/PAPER_COVERAGE_MATRIX.tsv) labels those analyses `NOT_INCLUDED` and does not claim their output reconstruction.

- Historical provider-accepted decoding settings are partially documented; exhaustive original server-side records are not bundled.
- The chronology and exact disjointness of the PRE-only graph calibration require additional original dated evidence.
- Source equivalence for the checkpoint executor and output equivalence for the LOO reconstruction are not new physical execution of the historical model.
- The actual remotely hosted Git files, commit and account metadata, and anonymous mirror status must be checked independently after upload; **remote anonymity is not certified by the local scan**.

## Integrity and use

`make audit` checks first-party source syntax, the release manifest, local anonymity and the frozen-input/expected-output hashes. `make reviewer-check` additionally executes the deterministic offline reconstruction. Results are written only under `reproduced/`, leaving the distributed authorities untouched. If reader-facing files change, regenerate `RELEASE_MANIFEST.tsv` before publishing; this does not alter science.

The root `Makefile` intentionally remains the one-command reviewer interface. Historical internal experiment directory names are retained to preserve executable file-path provenance; they should not be interpreted as separate software releases.
