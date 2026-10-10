# DECOUPLE — Anonymous Reproducibility Repository

This repository accompanies the **DECOUPLE** frozen closed-loop verification study. It is a reviewer-facing archive of the shared frozen benchmark authority; subsequent manuscript extension experiments are explicitly scoped separately. It contains the retained first-party method/baseline/execution source, final manuscript-analysis code, and the frozen scientific artifacts needed to reproduce the reported paper statistics without new API calls or physical intervention execution.

## Quick start (reviewer-facing zero-API)

The validated environment is CPython **3.10.12**, NumPy **2.2.6**, and Matplotlib **3.10.9**. The direct dependencies in `requirements.txt` are pinned to the tested package versions. Create the venv next to the release tree, not within it:

```bash
python3.10 -m venv ../decouple-review-venv
../decouple-review-venv/bin/python -m pip install -r requirements.txt
PATH="$(cd ../decouple-review-venv/bin && pwd):$PATH" bash scripts/reproduce_all.sh
```

See [`docs/ENVIRONMENT.md`](docs/ENVIRONMENT.md) for the original-lab profile, Conda alternative, reproducibility limits, and an existing-env workflow. The full model-facing environment is **not** dependency-locked here.

A successful run ends with:

```text
FINAL_REPRODUCTION_STATUS=PASS
```

Tier A makes **no API calls, no model calls, and no new physical intervention executions**. It verifies the frozen inputs, reconstructs the paper-level numerical outputs from included authorities, checks them against frozen expected results, validates manuscript claims, and runs the anonymity gate.

## Repository layout

```text
pipeline/
  method/            Decision-time DECOUPLE implementation
  baselines/         Step-PRM, PRM@BoK, specialized ToolPRM source
  data_generation/   Base-trajectory / K=8 proposal construction source
  execution/         Refinement, checkpoint replay, execution-ledger, post-outcome source
  vendor/            Small first-party compatibility helper retained with the pipeline

analysis/final/       Final manuscript-analysis scripts
artifacts/frozen_inputs/
                      Minimal frozen decision-time / executed-outcome authorities
artifacts/expected/   Frozen manuscript-level outputs used for numerical comparison
protocol/             Compact frozen protocol summary
scripts/              Portable reproduction, validation, figure, and public integrity entrypoints
docs/                 Paper-to-code map, execution semantics, scope, dependencies, anonymization
reproduced/           Generated outputs; safe to delete and rebuild
```

The files under `pipeline/` are publication copies of actual first-party research code. They are included for methodological inspection and full-pipeline provenance; the default reviewer path intentionally does not reissue expensive or externally dependent model calls.

## What Tier A reconstructs

`bash scripts/reproduce_all.sh` rebuilds or validates the manuscript surface used for the final submission: exact forced-quota terminal-utility curves; the retrospective positive-capacity envelope and 15 core A+ contrasts; the 10P/5 point-tie/0N headline pattern; non-envelope exact-curve area and 5/10/20% low-quota summaries with paired inference; 24/24 grid/weight stability; 6P/5T/4N leave-one-instance-out cross-fit sensitivity; BFCL/Math-Shepherd zero anchors; Math-Shepherd 0%→5% harm accounting; allocation-active effects; realized displacement regret and score–gain association; exact-vs-envelope saturation/flattening; specialized ToolPRM-GRPO contrasts; K=4 retrospective subsampling from the frozen K=8 semantic classes; earliest-step physical-coverage accounting; and the component-level compute/provenance claim gate.

The earliest-step reconstruction recovers the manuscript coverage fact that 172 of 1,100 required selected sets lack a matching frozen physical outcome; incomplete quotas are omitted rather than imputed.

## Exact execution semantics

The frozen model-facing code records requested sampling controls separately from what the provider actually accepted. In particular, the K=8 continuation pipeline records requested temperature `0.7` / top-p `0.95`, while the retained provider path records provider-default sampling; the scientific 256-token local window was applied locally. The intervention refiner requested temperature `0.2`; retained source and sampled H2 records document a rejected-temperature retry that omits this parameter. This does not establish exhaustive provider-side confirmation for every historical request. See [`docs/EXECUTION_SEMANTICS.md`](docs/EXECUTION_SEMANTICS.md) for the exact retained semantics.

## Optional full inferential reruns

The CPU-heavier frozen procedures are kept separate from the default reviewer path:

```bash
bash scripts/reproduce_full_vef_bootstrap.sh
bash scripts/reproduce_full_permutation.sh
bash scripts/reproduce_full_zero_anchor.sh
```

These rerun the 10,000-cluster-bootstrap VEF/A+ analysis, the final 100,000-permutation Holm-5 analysis, and the zero-anchor bootstrap/permutation analysis. They remain zero-API.

## Figures

After Tier A:

```bash
make figures
```

This renders the main exact-quota/envelope figure and the supplementary earliest-step overlay from reconstructed data. Figure rendering is kept separate from the numerical PASS/FAIL gate so that plotting-library/font differences cannot block statistical reproduction.

## Full model-facing execution

Full historical re-execution requires external benchmark assets, model repositories/checkpoints, benchmark-specific runtime environments, and model/API access. First-party BFCL compatibility helpers used by the retained code are bundled here; third-party repositories are not. See [`docs/EXTERNAL_DEPENDENCIES.md`](docs/EXTERNAL_DEPENDENCIES.md) and [`docs/REPRODUCIBILITY_SCOPE.md`](docs/REPRODUCIBILITY_SCOPE.md).

`requirements-full.txt` lists the directly imported model-facing Python packages retained in this repository. It does not substitute for those external benchmark/model repositories.

## Original-fold LOO and provenance boundaries

The release includes the original historical upstream LOO source (source-only, root-path anonymized) plus a portable **zero-API** replayer which reconstructs all 187 cross-fit curve rows from the frozen D11 logical results, matching all 1,870 numerical fields at their archived output precision. Run `python3 scripts/rebuild_loo_from_d11.py` separately or as part of Tier A.

An independently available STEP3E runner snapshot is identical to the publication code after only root-path normalization; the state-machine source is byte-identical. This is a source-diff result, not a claim of exhaustive runtime or checkpoint equivalence. Provider-effective settings, PRE-only alpha freeze chronology, and the remote mirror have separate provenance gates; see [`docs/PROVENANCE_GATES.md`](docs/PROVENANCE_GATES.md).

## Public integrity and privacy checks

```bash
make audit
```

The audit checks Python syntax and required first-party helpers, frozen-input hashes, expected-output hashes, and **generic** privacy/credential/filename/Git checks, including the entire published scanner itself. The three redundant shell wrappers from V4 have been removed; the underlying Python checks are intentionally retained for reviewers. The author-specific private red-team rules are not distributed. Release-only metadata normalization is documented in [`docs/ANONYMIZATION_NOTES.md`](docs/ANONYMIZATION_NOTES.md); for normalized frozen artifacts, `artifacts/AUTHORITY_HASH_MAP.tsv` preserves the private-authority SHA-256 and public release SHA-256 mapping.

## Paper-to-code map

See [`docs/PAPER_TO_CODE.md`](docs/PAPER_TO_CODE.md) for a section/table/figure-level map from the manuscript to the corresponding scripts and frozen authorities.

## Convenience targets

```bash
make reproduce       # Tier A zero-API paper reproduction
make figures         # regenerate main/supplement figures after reproduction
make audit           # optional public checks: syntax + hashes + privacy
make full-inference  # optional CPU-heavier inference reruns
make clean           # remove generated reviewer outputs
make env-check       # optional strict tested-lab environment check
```

## Scientific scope

The positive-budget capacity envelope is retrospective and outcome-accessed; it is not a deployable budget-selection policy. Exact forced-quota results remain visible because consuming interventions and merely having intervention capacity answer different questions. Zero intervention is a separate adverse claim-boundary sensitivity. Point-estimate ties are not equivalence claims, cross-fitting is a within-dataset selector-transfer diagnostic rather than external validation, and heterogeneous CPU/GPU/API accounting is not collapsed into an unsupported unified end-to-end compute metric.

## Release status

This is the **V7 TMLR v5 documentation-and-coverage revision** of the frozen-core repository. The original V4 zero-API reproduction completed successfully on the lab machine. V7 does not change frozen outcome data, the scientific selector, scoring logic, or the archived expected paper results. Separate Gate B provenance limitations still apply: complete historical runtime and checkpoints, provider-effective request audit, independent PRE-only graph-alpha freeze chronology, and the uploaded remote mirror are not all independently authenticated. Later TMLR-only extension analyses are not asserted to have full Tier A artifacts in this frozen-core release. See `docs/PROVENANCE_GATES.md` and `RELEASE_AUDIT.md`.


## TMLR v5 manuscript-specific coverage (V7)

**Start with [`docs/PAPER_TO_CODE.md`](docs/PAPER_TO_CODE.md)** for the actual TMLR v5 §3–§7 and Appendices A–M mapping, not older NAACL numbering. The checked [`docs/TMLR_V5_COVERAGE_MATRIX.tsv`](docs/TMLR_V5_COVERAGE_MATRIX.tsv) classifies every listed result as `CORE_REPLAY`, `SOURCE_INSPECTION`, or `NOT_INCLUDED`. Run `make coverage` to verify referenced release paths and make the remaining extension gaps explicit.

Tier A reconstructs the frozen shared-core numerical analyses. Later TMLR v5 no-critique, simulator-noise, position-controlled correlation and tie-frequency extensions **do not** have complete original per-case / per-step input and original replayer data in this archive. The paper reports them, but this package does not claim end-to-end regeneration of those four extensions; see [`docs/EXTENSION_EVIDENCE_REQUIREMENTS.md`](docs/EXTENSION_EVIDENCE_REQUIREMENTS.md). Do not substitute published aggregates for their raw evidence.

For lab validation, `make reviewer-check` performs local audit, coverage check, and full zero-API `make reproduce` sequentially in the foreground. It can take longer than a quick `make audit`; keep the exact tested Python environment and the final PASS/FAIL log. The release is a candidate until its **own** complete run succeeds.
