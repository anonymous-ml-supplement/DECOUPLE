# TMLR v5 extension evidence requirements (no new experiments)

This repository's default Tier A rebuilds the shared frozen core. It does **not** currently reproduce every analysis reported in the later TMLR v5 manuscript. Absence is explicit in `TMLR_V5_COVERAGE_MATRIX.tsv`; the `make coverage` target validates the classification and its available file references, not scientific completeness.

| Published extension | Existing evidence required for an independent zero-API check | Current release | Acceptance rule for a future addition |
|---|---|---|---|
| Math-Shepherd no-critique control (13/20 vs 14/20) | Immutable 20-case manifest and identity mapping; actual no-critique per-case physical output JSON; corresponding original-refine outcomes; exact matching / pairing script and operator/request metadata; original timestamp/hash ledger | **NOT INCLUDED** (paper reports aggregates only) | Cross-check all 20 identities, paired transitions, operator differences and all relevant hashes; do not use abstract counts in place of physical inputs |
| ToolAlpaca simulator-noise extension | Frozen case / replicate manifests; actual alternative simulator-run outputs; analysis source; original success and failure rules; comparison table and hashes | **NOT INCLUDED** | Rebuild existing published sensitivity without new generation, retain all original simulator variants |
| Position-controlled score–gain Spearman | Original step-level gain/score/position join, exact positional covariate control and tie rules, original analysis implementation, published estimates and uncertainty | **NOT INCLUDED** (unadjusted Spearman covered separately) | Require exact published statistic, study unit, and an immutable original join; no substitute newly selected adjustment |
| Deterministic hash tie-frequency | Original score equivalence/tolerance rules, tie-candidate lists and selections, unchanged tie-breaking script, reported per-benchmark tie counts | **NOT INCLUDED** (selection algorithm included) | Reproduce reported counts from the identical frozen selection authority and original counting definition |

## Safe integration policy

1. Add an extension only from **existing original, frozen, evidence-bearing files**, plus a corresponding read-only zero-API validator. Do not synthesize or regenerate missing physical outcomes, labels, or sampling decisions.
2. Record original-source SHA256 and public release SHA256 when the artifact is normalized for anonymity. Remove contextual identifiers from the released text; keep the original authority mapping in a private ledger.
3. Record reviewer-visible denominators, cohort rules, original inferential unit, comparison direction and limits. Keep adverse and null findings intact.
4. Add a separate, isolated `artifacts/extensions/<analysis>/` directory only after validation. Do not edit the shared `artifacts/frozen_inputs/` or `artifacts/expected/` authority trees.
5. Update coverage class, manifest and changelog. Never upgrade an item to `CORE_REPLAY` solely because the paper includes its table or aggregated counts.
6. The published anonymous mirror and its metadata require an independent post-upload check. Local scans cannot establish remote anonymity.

No missing extension is required to be recreated by paid model/API calls. Lack of original frozen inputs is an explicit reproducibility limitation, not a reason to fabricate an alternative analysis.
