# Optional private lab checks (not a publication pass condition)

Do not edit the original research tree. These are purely read-only source checks.

From a fresh V4 repository and a lab account with access to the original frozen files:

```bash
ROOT=/path/to/original/research/tree
python3 scripts/verify_step3e_source_equivalence.py \
  --private-runner "$ROOT/10_PILOT/STEP3/01_CODE/STEP3E_EXACT_CHECKPOINT_REPLAY/run_step3e_formal_replay.py" \
  --private-state-machine "$ROOT/10_PILOT/STEP3/01_CODE/STEP3E_EXACT_CHECKPOINT_REPLAY/step3e_execution_state_machine.py"
python3 scripts/rebuild_loo_from_d11.py
```

For α, locate the **pre-outcome** graph development-cohort manifest, cohort membership, timestamped freeze signoff and corresponding recorded input hashes. Verify chronological order and nonintersection with any outcome-used set. The graph builder implementing alpha is not itself that independent proof.

For provider settings, inspect archived per-request provider acknowledgements and rejected-parameter retry records, distinguishing request parameters, transport errors, and accepted effective decoding. Do not issue new requests to infer past settings.

After anonymous publication, independently download the exposed mirror ZIP and compare its SHA-256 and path-by-path manifest to the locally approved release. Inspect account/commit metadata visible to anonymous viewers. No local script claims remote inspection happened automatically.
