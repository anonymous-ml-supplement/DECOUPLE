# TMLR v5 paper-to-code map

This map refers to the **TMLR v5 single-PDF manuscript** (main text, then References, then Appendices A–M), **not** the older NAACL section numbering. Locations and labels were checked against the supplied `decouple_tmlr_v5.tex`. Script names and historical experiment directories are retained for reproducibility, not as manuscript section names. `TMLR_V5_COVERAGE_MATRIX.tsv` provides machine-checkable evidence scope.

| TMLR v5 location / result | Code or replay entrypoint | Available frozen authority | Coverage |
|---|---|---|---|
| §3 Decision Formulation | Mathematical definitions in the paper, implementation interpretation in `pipeline/method/` | Decision-time pre-scores / base outcomes | FORMULATION; not causal value identification |
| §4.1 Semantic uncertainty | `pipeline/method/compute_semantic_classes_and_pt.py` | Frozen semantic class index and candidate scores | Source + frozen classes |
| §4.2 Dependency graph | `pipeline/method/build_hybrid_graph_and_hhat.py` | Dependency / pre-score evidence | Source review; alpha freeze chronology OPEN |
| §4.3 Availability gating / deterministic selection | `pipeline/method/build_decouple_pre_scores.py`, `pipeline/method/build_static_exact_budget_selections.py` | Static scores, exact-budget selections | Source + frozen selection |
| §4.4 Selection vs execution | `pipeline/execution/step3e_execution_state_machine.py`, `run_step3e_formal_replay.py` | STEP3E execution manifest | Source inspection; historical runtime not recreated |
| §5.1 Budget objects / operating-budget choice | `scripts/rebuild_loo_from_d11.py`, `analysis/provenance/run_vef_v1_audit_archived.py` | D11 logical outcomes; 187-row cross-fit authority | Tier A replay; within-panel only |
| §5.2 Panel and comparators | `pipeline/baselines/`, `pipeline/data_generation/` | Frozen scores, outcomes, selections | Source + frozen data |
| §5.3 Frozen intervention operator | `pipeline/execution/run_step3e_formal_replay.py`, `step3e_execution_state_machine.py` | STEP3E manifest, H2 execution authority | Source-equivalence scope only |
| §6.1 Exact-quota dynamics; Fig. 1 | `build_d11_detailed_primary_tables.py`, `scripts/rebuild_paper_figures.py` | D11 logical outcomes; exact curves | Tier A; `make figures` |
| §6.2 Math 0%→5% harm | `scripts/rebuild_math_zero_to_5.py` | Frozen base and 5%-quota outcomes | Tier A |
| §6.2 No-critique diagnostic; Appendix J | No packaged extension replay | Original no-critique per-case outputs absent | **NOT INCLUDED** |
| §7.1 VEF CORE15; Table 1; Appendix C/E | VEF manuscript and inference scripts | Frozen D11, final inference tables | Tier A / optional heavy inference |
| §7.1 Grid sensitivity; Appendix I | `run_positive_vef_grid_stability.py` | 24-cell grid authority | Tier A |
| §7.2 Non-envelope; Table 2; Appendix D | `run_t4_nonenvelope_inference.py` | Frozen non-envelope summaries | Tier A |
| §7.3 Allocation-active; Appendix G | `scripts/rebuild_allocation_active.py` | Frozen D11 | Tier A |
| §7.4 Specialized ToolPRM; Appendix I | ToolPRM audit and VEF manuscript scripts | Frozen matched-subset authority | Tier A, restricted coverage |
| §7.5 Displacement regret; Table 3; Appendix H | `build_realized_displacement_regret.py` | Singleton gains, score-gain estimates | Tier A; no causal identification |
| §7.5 Position-controlled correlation; Appendix H | Original position-adjusted script/inputs unavailable | Unadjusted Spearman only | **NOT INCLUDED** |
| Appendix B Exact utility / Appendix C capacity | `build_d11_detailed_primary_tables.py` | Frozen exact and envelope tables | Tier A |
| Appendix F Saturation / Appendix I LOO, zero anchor | Saturation scripts, LOO replayer, zero-anchor script | Frozen D11 and expected tables | Tier A |
| Appendix H Earliest-step coverage | `scripts/rebuild_earliest_step_coverage.py` | Existing physical-coverage authority | Tier A; 172 missing remain missing |
| Appendix K Implementation / tie-frequency | Selection source and hash tie-breaking logic | Frequency-specific authority not bundled | **PARTIAL**: code only |
| Appendix K K=4 retrospective sensitivity | `scripts/rebuild_k4_sensitivity.py` | Frozen K=8 classes and expected K=4 tables | Tier A |
| Appendix I Simulator-noise extension | No packaged extension replay | Raw simulator noise experiment inputs absent | **NOT INCLUDED** |
| Appendices L–M execution/provenance | `docs/EXECUTION_SEMANTICS.md`, `docs/PROVENANCE_GATES.md` | Source, hash and compute authorities | Documented limits remain |

## Reviewer commands

```bash
make audit        # source/hash/generic anonymity/inventory checks; zero API
make coverage     # exact available/unavailable TMLR v5 evidence matrix
make reproduce    # full Tier A numerical reproduction; zero API, may take time
make figures      # after Tier A, render manuscript figure files
```

**Not interchangeable:** a source-present flag is not a frozen-output replay; shared-core numerical replay is not full historical model/physical re-execution; local privacy checks are not remote release-anonymity verification.
