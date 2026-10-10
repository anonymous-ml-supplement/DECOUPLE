# DECOUPLE V7 — TMLR v5 anonymous release audit

## Scope

V7 is a **documentation, coverage-disclosure, and reviewer workflow revision** of the supplied V6 anonymous frozen-core package. It is not a new scientific run or a promise of full TMLR v5 extension replay. No new API, model, or physical intervention executions were performed. No original selection, branch, terminal outcome, analysis rule, primary metric, or statistical decision was altered.

## Immutable scientific authority

All 108 protected files in `analysis/` (15), `pipeline/` (24), `artifacts/` (68), and `protocol/` (1) are retained byte-for-byte from V6. V7 adds `docs/TMLR_V5_COVERAGE_MATRIX.tsv`, `docs/EXTENSION_EVIDENCE_REQUIREMENTS.md` and `scripts/audit_tmlr_v5_coverage.py`, alongside README, paper map, provenance, scope, Makefile and changelog updates. Protected numerical hashes must still pass `make audit`.

## Local validation performed on V7 staging

- **PASS:** static compilation of 55 Python files (54 V6 + 1 V7), including model-facing files for inspection only.
- **PASS:** frozen input SHA256 17/17, expected-output SHA256 48/48.
- **PASS:** anonymous generic scanner includes its own source; contextual and remote identity cannot be certified by regex alone.
- **PASS:** coverage matrix verifies 18 paper-level items: 10 CORE_REPLAY, 4 SOURCE_INSPECTION, 4 NOT_INCLUDED; these classes do not measure scientific accuracy or complete extensions.
- **PASS (partial numerical run):** exact-budget, absolute VEF, non-envelope, grid stability, downstream cross-fit, original upstream LOO (187 rows/1,870 numeric cells), and zero-anchor-fast (BFCL=0.32, Math-Shepherd=0.40). The realized-displacement computation printed completion in its stage log, but no full integration final marker was emitted in this sandbox run.
- **OPEN (integrated execution):** the foreground `scripts/reproduce_all.sh` attempt exceeded the container execution allowance after the realized-displacement stage, before its last integration checks. Consequently **`FINAL_REPRODUCTION_STATUS=PASS` has not been observed for V7 here**. The V4 original-lab end-to-end PASS remains historical supporting context, not a surrogate V7 PASS.
- **Environment difference:** this sandbox uses Python 3.13.5, NumPy 2.3.5, Matplotlib 3.10.8, while the original validated lab profile is Python 3.10.12, NumPy 2.2.6, Matplotlib 3.10.9.

## Reproducibility and public anonymity boundaries

The frozen shared core has Tier A zero-API numerical replay; the four later TMLR v5 extension analyses remain incomplete in this exact release due to missing original frozen extension inputs. This includes no-critique continuation control, simulator-noise extension, position-controlled association, and hash tie-frequency. See `docs/EXTENSION_EVIDENCE_REQUIREMENTS.md` for exact evidence needed, without assuming new experiments.

Original STEP3E source snapshot equivalence and LOO upstream reconstruction are documented; original runtime/checkpoint authentication and freeze-chronology provenance are distinct, still-limited claims. Provider-effective settings across all calls and PRE-only alpha cohort chronology remain partly OPEN.

The **published remote anonymous mirror is OPEN** until its actual served files, exposed metadata, account/commit history, downloadable archive contents, and file hashes are inspected against this V7 release. Local anonymity PASS cannot close that gate.

## Lab completion gate

Run from a clean extraction in the tested lab environment, with all output in the foreground:

```bash
make reviewer-check
```

Save the terminal log and check `FINAL_REPRODUCTION_STATUS=PASS`, `FINAL_OUTPUT_COMPARISON_STATUS=PASS`, the claim-validation result, the local anonymity gate and the V7 manifest. Only then upgrade the V7 **lab full-integrated reproduction** from OPEN to PASS. The full suite calls no external models or APIs.

`make figures` is separate and optional after successful numerical reproduction. Additional historical Tier B heavy inference is optional and not covered by a default Tier A PASS.
