# V7 provenance and publication boundaries

This is an explicit **two-gate** report. Passing release hygiene does not establish that all historical research provenance is independently verified. No model calls, API requests, or physical branches were run to produce V7.

## Gate A — local release safety

- **PASS, local archive staging:** generic privacy and credential scan includes `scripts/check_anonymity.py` itself, with no publication of project-specific identity denylist strings.
- **PASS, local archive staging:** complete static Python syntax, frozen scientific-input SHA-256, frozen expected-output SHA-256, and release manifest (after final packaging).
- **PASS, local numeric replay:** original cross-fit upstream quota selection is independently re-derived from frozen D11, and default paper reconstruction remains zero-API.
- **OPEN, public mirror:** the actual online anonymous mirror has not been authenticated from this execution environment. A ZIP hash or local audit cannot substitute for checking the remote directory, exposed metadata, and exact download bytes after publishing.

## Gate B — original execution provenance

| Research question | V4 status | Precisely supported evidence / outstanding requirement |
|---|---|---|
| STEP3E source equivalence | **PASS for source snapshot; PARTIAL historically** | The accessible private-authority bundle contains the original runner and state machine. The runner differs from the publication copy only through three occurrences of the source-root string. Full text is identical after root-prefix normalization. The state machine is byte-identical. A fresh read-only comparison against the live, historically frozen lab files and checkpoint/runtime dependency versions is still recommended. |
| LOO fold-selection code | **PASS for upstream algorithm and output replay** | `analysis/provenance/run_vef_v1_audit_archived.py` preserves the original upstream algorithm with only a path-label change. `scripts/rebuild_loo_from_d11.py` independently reconstructs the 187-row cross-fit authority: 1,870/1,870 numeric cells equal at frozen output precision; every 11-cap held-out fold chooses the smallest tied best training-fold budget. This does not make the diagnostic prospective or external validation. The separate dated preanalysis freeze record was not independently authenticated in the earlier read-only source audit. |
| Provider-effective settings | **PARTIAL** | Frozen runner implements rejected-temperature fallback; sampled retained H2 report shows provider-rejection examples. Requested and provider-accepted settings are distinguished. Exhaustive provider-original authenticated request/response evidence for every call is not bundled. |
| PRE-only alpha = 4/9 | **PARTIAL/OPEN** | Graph source documents development-only, outcome-blind calibration and the frozen formula. A separately authenticated timestamped PRE-only cohort membership/freeze ledger demonstrating chronological disjointness is not bundled. Do not infer one from the equation alone. |
| External anonymous mirror | **OPEN** | Local ZIP only; review downloaded mirror and account/commit metadata after upload. |

## STEP3E source comparison against provided authority snapshot

The original runner's source SHA-256 in the private authority snapshot is
`14c2fe10379e107e407703514f8994e75e121d8ba82b8352f11b443c7e0aeb2a`.
Its release path-normalized version is
`445275efd870bbb53fd6bdbbd7083c6382020030e8a7e1d41a4dfecd6beba72e`.
The source and release state-machine SHA-256 is
`7208cedc708c91fc0421e6bf23a47633b86ed25fec93695b59ee434233ca2ef1`.
The script `scripts/verify_step3e_source_equivalence.py` performs these comparisons using privately supplied file paths; no personal paths are embedded in the archive.

## LOO source and numerical controls

Historical `choose_budget` enumerates the frozen grid at caps no greater than the currently evaluated cap, averages training-instance exact outcomes, and resolves equal best means with **minimum budget** (`min(best_budgets)` within 1e-12). Each held-out fold excludes that instance before choosing either method's quota. Frozen Random replicates are collapsed within instance and budget. The 187-row comparison covers 17 benchmark-comparator pairs × 11 caps, including 15 core and 2 specialized pairs. The portable replayer is fully deterministic and validates the SHA-256 of the 16,907-row frozen D11 input. Its result comparison is not a test of how that D11 input was physically generated.

## Paper-version coverage

The V7 package reproduces the scientific analyses carried forward from the earlier frozen benchmark authority, including exact-quota/VEF, LOO, grid stability, zero anchors and associated historical sensitivities. A later TMLR revision may include additional no-critique regeneration controls, simulator-rerun experiments, position-controlled association, and tie-frequency diagnostics. Their historical extension input artifacts have not been supplied in this V4 authority snapshot, so this ZIP **does not assert full replay of those additional manuscript-specific experiments**. Those are distinct from whether the V7 archive is anonymously publishable.

## Hard scientific restrictions

No historical data or outcomes were rewritten. No original STEP3E source, model requests, frozen branch, protocol claim, or selection result was changed. Absence of an external ledger is an explicit evidence gap, never a warrant to synthesize it.

## V7 TMLR v5 evidence-coverage gate

The scientific core inherited from V6 remains untouched. For manuscript-wide review, see `docs/TMLR_V5_COVERAGE_MATRIX.tsv` and `docs/EXTENSION_EVIDENCE_REQUIREMENTS.md`. Four later TMLR-only analyses have explicit `NOT_INCLUDED` status pending original frozen inputs; do not interpret the Tier A PASS as a complete replay of all v5 extensions. V6 lab `make audit` evidence does not automatically authenticate a new V7 full `make reproduce` run.
