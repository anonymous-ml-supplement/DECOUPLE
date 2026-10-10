# Release changes

## V6 (packaging and environment specification; no frozen scientific changes)

- Pinned Tier A/B **direct** dependencies to the exact successfully tested lab versions (NumPy 2.2.6, Matplotlib 3.10.9) and recorded CPython 3.10.12 in `.python-version`.
- Added optional `environment.yml`, `docs/ENVIRONMENT.md`, and a generic standard-library-only environment preflight with optional strict-version enforcement.
- Removed redundant `check_anonymity.sh`, `verify_frozen_hashes.sh`, and `verify_expected_hashes.sh`. The **actual** privacy and integrity verification programs remain Python scripts; `Makefile` and `reproduce_all.sh` call them directly.
- Updated README with a venv created outside the release tree and explicitly separated Tier A/B requirements from **unlocked** Tier C model/API dependencies.
- Kept the frozen scientific artifacts, retained source analysis, primary numeric semantics, and historical-provenance caveats unchanged.
- Regenerated distribution manifest and SHA-256 after final clean-copy validation.

## V4 (scientific authority baseline)

- V4 lab completed full end-to-end zero-API test with 32/32 regenerated output comparisons and claim validator PASS, original LOO 187/187 and 1,870/1,870 reconstructed fields.
- Original STEP3E source-diff comparison supported normalized-root code identity, but historical runtime and checkpoint equivalence remain PARTIAL.
- PRE-only alpha chronology, exhaustive provider-side decoding verification, and live anonymous mirror are not fully closed.

The jump from V4 to V6 is a naming choice; no undocumented V5 empirical results are implied.


## V7 (TMLR v5 coverage and reviewer usability)

- Replaced obsolete NAACL/V4 `PAPER_TO_CODE.md` section links with validated TMLR v5 locations (main §§3–7, Appendices A–M).
- Added machine-readable coverage matrix and read-only validator (`make coverage`). Distinguished shared-core numeric reproduction, source inspection and four later paper-only extension analyses for which raw frozen extension evidence is absent.
- Added an explicit minimum-authority checklist for extension inclusion rather than inventing per-case data or new statistical protocols.
- Normalized reader-facing release/scope prose to V7; retained original historical source chronology and remaining Gate B limitations.
- Added foreground `make reviewer-check` chaining the existing local audit, coverage inventory, and unchanged full Tier A numerical workflow.
- **Protected scientific directories `analysis/`, `pipeline/`, `artifacts/`, `protocol/` remained byte-for-byte identical to V6**. No model/API/physical executions, new metrics or inferred missing data.
