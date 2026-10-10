# Research provenance and verification boundaries

Two distinct questions must be kept separate: whether the local archive is safe and internally consistent, and whether the historical execution circumstances can be independently authenticated. Passing the first does not resolve the second.

## Local release and numerical verification

- **PASS — local source and artifact checks:** static Python source inspection, release-manifest coverage, SHA-256 validation of frozen inputs and expected outputs, and generic privacy scanning of all files including the anonymity checker itself.
- **PASS — reference-lab frozen-core numerical reproduction:** `make reviewer-check` completed with 32/32 expected-output comparisons, original-instance LOO reconstruction matching 187 rows and 1,870 numeric cells, and `FINAL_REPRODUCTION_STATUS=PASS`.
- **OPEN — hosted repository:** the remote host's served files, Git metadata and account context require post-publication verification. Local anonymity scans do not establish this remotely.

The default reviewer reproduction uses archived inputs; no model/API request or physical intervention is required. The scientific inputs, numerical procedures and archived execution authorities are unchanged by the public documentation cleanup.

## Historical execution provenance

| Research question | Evidence status | Verified material and boundary |
|---|---|---|
| STEP3E checkpoint source equivalence | **PASS for source snapshots; PARTIAL for original runtime** | The original runner and published path-normalized runner have matching content after three source-root substitutions. The state-machine implementation is byte-identical. This source comparison alone does not reproduce historical provider responses or every checkpoint dependency. |
| Original-instance LOO operating-budget selection | **PASS for algorithm and frozen-output replay** | An archived upstream selection algorithm and the independent `scripts/rebuild_loo_from_d11.py` check agree on 187 rows and 1,870 numerical values. Training folds exclude the held-out instance, choose the smallest tied best quota and aggregate frozen Random replicates within original instance. The separate dated preanalysis freeze record is not independently authenticated. |
| Provider-effective generation settings | **PARTIAL** | The runner includes rejected-parameter fallback and the retained H2 record includes provider-rejection examples. Complete, independently authenticated server-side request/response records for every historical call are not distributed. |
| PRE-only graph fallback calibration | **PARTIAL/OPEN** | The graph source documents outcome-blind calibration of the coefficient 4/9. An independently verified, timestamped PRE-only cohort/disjointness ledger is unavailable in this public archive. |
| Anonymity of the remote Git mirror | **OPEN** | Requires inspection of hosted repository files, identities, commit metadata, and external links after uploading. |

## Checkpoint source comparison

The original checkpoint runner's hash in the private frozen authority snapshot is:

```text
14c2fe10379e107e407703514f8994e75e121d8ba82b8352f11b443c7e0aeb2a
```

The path-normalized published runner hash is:

```text
445275efd870bbb53fd6bdbbd7083c6382020030e8a7e1d41a4dfecd6beba72e
```

The matching original/published state-machine source hash is:

```text
7208cedc708c91fc0421e6bf23a47633b86ed25fec93695b59ee434233ca2ef1
```

For source-only equivalence, `scripts/verify_step3e_source_equivalence.py` accepts privately available original files as external input. It does not embed researcher-specific paths or ship private authorities.

## LOO reconstruction boundary

The frozen original-instance LOO procedure selects an operating budget using only the other original instances in its training fold, subject to the evaluated capacity, and selects the smallest tied best budget within numerical tolerance. Frozen Random replicate outcomes are combined at the original-instance/budget level. The 17 benchmark–comparator pairs and 11 capacities yield 187 rows. The portable replayer validates the source frozen D11 digest before comparing numerical outputs. This validates the selection computation **conditional on the frozen D11 input**; it does not validate the historical physical creation of D11 anew.

## Manuscript coverage

The included frozen-core analyses cover executed exact quotas, retrospective capacity, LOO, grid stability, identifiable zero-intervention outcomes and supporting statistical diagnostics. Four additional analyses reported in the manuscript are expressly classified as `NOT_INCLUDED` because their original per-case or per-step extension records are not packaged. Their coverage and source requirements are documented in `docs/PAPER_COVERAGE_MATRIX.tsv` and `docs/EXTENSION_EVIDENCE_REQUIREMENTS.md`. A numerical-reproduction PASS does not imply complete reproduction of those extensions.

**Integrity rule:** no missing primary experimental data, freeze ledger or provider responses are inferred or synthesized to close a provenance gap.
