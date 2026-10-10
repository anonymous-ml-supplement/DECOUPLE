# Reproducibility scope

## Tier A — one-command zero-API paper reproduction

`bash scripts/reproduce_all.sh` uses only included frozen inputs. It verifies hashes, checks the retained source tree, materializes a disposable worktree with portable paths, reruns the deterministic/statistical paper analyses, reconstructs Math 0%→5% harm accounting, allocation-active effects, the K=4 sensitivity, and earliest-step physical coverage, compares regenerated tables with frozen expected outputs, validates headline numbers, and runs the anonymity gate.

No API calls, model calls, or new physical intervention executions occur in Tier A.

## Tier B — optional CPU-heavier inference

The repository retains the original final procedures for the 10,000-cluster-bootstrap VEF/A+ analysis, the 100,000-permutation/Holm-5 test, and zero-anchor bootstrap/permutation analysis. These are zero-API but are separated from the default path because they can take materially longer than the reviewer smoke reproduction.

## Tier C — full historical model / physical execution

Actual first-party source for the decision-time method, baseline preparation/scoring, base-trajectory and K=8 proposal construction, refinement, exact checkpoint replay, execution-ledger construction, and post-outcome materialization is retained under `pipeline/`. First-party BFCL compatibility helpers used by the retained source are also bundled.

Full historical re-execution still requires external benchmark assets, model checkpoints/repositories, benchmark-specific runtime environments, and model/API access. See `docs/EXTERNAL_DEPENDENCIES.md`. Those third-party assets are not redistributed in this anonymous snapshot.

## Claim boundaries preserved by the release

- The positive-budget capacity envelope is retrospective and outcome-accessed.
- Exact forced-quota outcomes are a separate estimand and remain visible.
- Zero intervention is an adverse sensitivity, not the replacement primary estimand.
- Cross-fitting is a within-dataset selector-transfer diagnostic, not external validation.
- Point ties are not equivalence findings.
- Component-level compute records are not collapsed into an unsupported unified end-to-end efficiency metric.

Environment profile: see `docs/ENVIRONMENT.md`. Public checking scripts remain deliberately provided because a publication-quality reproduction archive must allow reviewers to verify the expected outputs and data hashes. Redundant check shell wrappers were removed in V6.

## TMLR v5 extensions (V7 release)

The shared frozen-core Tier A scope is not equal to all reported TMLR v5 analyses. Exact coverage classes and per-result evidence are published in `docs/TMLR_V5_COVERAGE_MATRIX.tsv`; missing original frozen extension outputs are tracked in `docs/EXTENSION_EVIDENCE_REQUIREMENTS.md`. Run `make coverage` to audit the claims and source paths, but note that this validates availability and documented scope, not scientific replay of missing experiments.
