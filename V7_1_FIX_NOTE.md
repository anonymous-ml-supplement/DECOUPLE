# V7.1 minimal environment-launch fix

- Corrected `scripts/reproduce_all.sh` to find a compatible local Python before numerical reproduction.
- Added `scripts/select_offline_python.sh` using generic, nonidentifying environment discovery and an explicit `DECOUPLE_PYTHON` override.
- Updated `docs/ENVIRONMENT.md` accordingly.
- No scientific pipeline, analysis, artifact, or protocol bytes changed.
- This fix addresses `PYTHON_EXECUTABLE=/usr/bin/python3` with missing NumPy/Matplotlib on lab hosts.
- Full numerical reproduction requires a compatible environment and may still take substantial CPU time. No final scientific PASS is claimed by this packaging fix alone.
