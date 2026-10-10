# Retained research pipeline source

This directory contains curated publication copies of the actual first-party source used to construct the frozen experiment, not simplified pseudocode.

- `method/`: semantic uncertainty, structural consequence, availability gating/product score, and deterministic exact-budget selection.
- `baselines/`: Step-PRM, PRM@BoK, and specialized ToolPRM preparation/scoring/selection.
- `data_generation/`: frozen panel/base-trajectory and K=8 local-continuation construction, including the BFCL Docker worker used by the retained generator.
- `execution/`: practical refinement request materialization, exact checkpoint replay, execution state machine/ledger, and post-outcome materialization.
- `vendor/bfcl_tool_conversion/`: the small first-party BFCL/OpenAI Responses compatibility helper used by the frozen trajectory generator.

Private machine paths and non-scientific cluster/environment labels are replaced by neutral placeholders. The default reviewer reproduction does not invoke these expensive model-facing stages; it operates on included frozen scientific authorities.

Third-party benchmark/model repositories are not vendored. The exact interfaces expected by the retained source are listed in `docs/EXTERNAL_DEPENDENCIES.md`.
