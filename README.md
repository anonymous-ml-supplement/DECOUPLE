# DECOUPLE

**Anonymous code and frozen-result reproducibility for the TMLR manuscript.**

This repository provides the DECOUPLE selection method, baseline implementations, checkpoint-intervention source code, archived frozen inputs, and offline scripts for regenerating the shared-core analyses reported in the paper. The default workflow makes **no model/API requests and executes no new physical branches**.

## Quick start

From the repository root, with Python 3.10 and NumPy/Matplotlib available:

```bash
make reviewer-check
```

The command runs source and integrity audits, local anonymity scanning, a paper-to-code coverage audit, and zero-API numerical reproduction. The numerical launcher automatically resolves a compatible existing Python interpreter when possible; a manual override is available:

```bash
DECOUPLE_PYTHON=/path/to/bin/python3 make reviewer-check
```

See [environment setup](docs/ENVIRONMENT.md) if dependencies are missing. The tested reference environment is Python 3.10.12, NumPy 2.2.6, and Matplotlib 3.10.9. For full verification, the terminal output should include `FINAL_OUTPUT_COMPARISON_STATUS=PASS`, `FINAL_CLAIM_VALIDATION_STATUS=PASS`, and `FINAL_REPRODUCTION_STATUS=PASS`.

### Verified reference result

A completed run in the research lab using the tested environment produced:

```text
FINAL_SOURCE_TREE_STATUS=PASS
FINAL_RELEASE_MANIFEST_STATUS=PASS
FINAL_FROZEN_HASH_STATUS=PASS
FINAL_EXPECTED_HASH_STATUS=PASS
COVERAGE_INVENTORY_STATUS=PASS
FINAL_LOO_UPSTREAM_REPLAY_STATUS=PASS
FINAL_OUTPUT_COMPARISON_STATUS=PASS
PASS_COUNT=32
FAIL_COUNT=0
FINAL_CLAIM_VALIDATION_STATUS=PASS
FINAL_ANONYMITY_STATUS=PASS
FINAL_REPRODUCTION_STATUS=PASS
```

This evidence supports **frozen-core numerical reproduction**. Documentation updates and release-manifest regeneration do not change the verified scientific computations. The command also works on the published checkout subject to environment availability; see [release audit](RELEASE_AUDIT.md) for scope and what remains unverified.

## Repository layout

| Directory | Contents |
|---|---|
| `pipeline/method/` | Semantic uncertainty, dependency graphs, scoring and allocation |
| `pipeline/baselines/` | Matched-baseline source and model-related interfaces |
| `pipeline/execution/` | Frozen checkpoint replay implementation and execution semantics |
| `pipeline/data_generation/` | Historical frozen trajectory and candidate construction |
| `analysis/final/` | Terminal-outcome and statistical analyses |
| `artifacts/frozen_inputs/` | Frozen decision-time and executed-outcome authorities |
| `artifacts/expected/` | Expected analysis outputs with published digests |
| `scripts/` | Zero-API reproduction, audits and figure rebuilding |
| `docs/` | Method/protocol details, paper-to-code mapping and evidence boundaries |

`pipeline/` contains historical model-facing source for inspection, but the default reviewer workflow **does not execute model-facing experiments**. Third-party benchmark and model dependencies required for that historical process are not included.

## Paper-to-code coverage

Use the [manuscript-to-code map](docs/PAPER_TO_CODE.md) and [coverage matrix](docs/PAPER_COVERAGE_MATRIX.tsv) to locate evidence. Its 18 items are classified as:

- **10 CORE_REPLAY:** an included frozen numerical reproduction or output comparison.
- **4 SOURCE_INSPECTION:** source is available, but full historical external execution is not asserted.
- **4 NOT_INCLUDED:** existing reported extensions cannot be independently regenerated from the supplied per-case/per-step raw records.

The four disclosed coverage gaps are the no-critique continuation control, ToolAlpaca simulator-noise extension, position-controlled score–gain analysis, and hash tie-frequency diagnostic. These were **not invented or rerun**; the archive does not contain the complete original frozen inputs needed to rederive them. See [extension evidence requirements](docs/EXTENSION_EVIDENCE_REQUIREMENTS.md).

Core reproduction covers exact-quota utility, retrospective capacity envelopes, non-envelope contrasts, grid and Holm analyses, original-instance leave-one-out budget selection (187 rows and 1,870 numeric cells), identifiable zero-intervention outcomes, Math-Shepherd 13/20 harm accounting, realized singleton-regret analysis, allocation-active summaries, retrospective K=4 sensitivity and Earliest-step coverage.

## Additional commands

```bash
make audit          # source, manifest, hash and local anonymity checks
make coverage       # evidence coverage classification
make reproduce      # frozen-core numerical reproduction, zero API calls
make figures        # rebuild figures after reproduction
make full-inference # optional compute-intensive offline inference
make env-check      # exact reference-environment check
make clean          # remove generated reviewer outputs only
```

The `Makefile` is retained as a standard reviewer entry point. It is not a history of release packages.

## Scientific interpretation and limits

- Exact forced intervention quotas, retrospective positive-capacity envelopes and no-intervention activation are distinct evaluation objects. The capacity envelope is outcome-selected, **not** an executable policy.
- Leave-one-instance-out budget selection is an internal frozen-panel diagnostic, not prospective deployment validation.
- Physical execution branches are **not** statistically independent original trajectories. Point ties are not evidence of equivalence.
- Matched intervention counts do not imply matched total computational costs, and provider-effective historical settings are only partially authenticated.
- The local generic anonymity scan includes its own source but does not authenticate the identity or contents of a separately hosted remote Git checkout.

For protocol details, consult [execution semantics](docs/EXECUTION_SEMANTICS.md), [reproducibility scope](docs/REPRODUCIBILITY_SCOPE.md), [provenance boundaries](docs/PROVENANCE_GATES.md), and [release audit](RELEASE_AUDIT.md).
