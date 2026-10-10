# Environment specification and verified execution

## Tier A/B: zero-API numerical reproduction

**Independently tested on the original lab host** with CPython **3.10.12**, NumPy **2.2.6**, and Matplotlib **3.10.9**. The original lab run reported 32/32 expected output comparisons, zero failures, successful claim validation, and `FINAL_REPRODUCTION_STATUS=PASS`. This is evidence for the **V4 scientific core**; V6 changes packaging, dependency declarations, and verification entrypoints, not frozen scientific values.

`requirements.txt` pins the exact two **direct** third-party requirements of the offline scripts. It is **not** a fully resolved, platform-independent package-lock file: transitive dependencies, compiled wheel hashes, GPU drivers, benchmark runtime, and provider SDK are not locked. Do not interpret this file as historical full model-execution environment provenance. `environment.yml` is an optional Conda alternative with Python 3.10 and the same direct package versions; its Python patch can differ from 3.10.12.

### Fresh venv (outside the repository directory)

```bash
python3.10 -m venv ../decouple-review-venv
../decouple-review-venv/bin/python -m pip install -r requirements.txt
PATH="$(cd ../decouple-review-venv/bin && pwd):$PATH" python3 scripts/check_environment.py
PATH="$(cd ../decouple-review-venv/bin && pwd):$PATH" bash scripts/reproduce_all.sh
```

Venv is placed **next to**, not inside, `DECOUPLE/`, so the release-manifest/anonymity scans do not treat the user's installed libraries as files to distribute. On Windows, a platform-compatible shell/venv adaptation is required for the Bash entrypoint.

### Automatic environment selection for `make reviewer-check`

`make reviewer-check` automatically uses a compatible active Python or an
existing environment in a conventional nearby directory (including an
ancestor `02_ENVIRONMENT/*/bin/python3`). It does not install dependencies,
run model APIs, or modify frozen artifacts. If a compatible environment is
not found, the failure message shows how to choose one explicitly:

```bash
DECOUPLE_PYTHON=/path/to/existing/bin/python3 make reviewer-check
```

The static audits use standard-library `python3`; the numerical entrypoint
resolves the Python environment before any numerical script executes.

### An already installed lab environment

Use your existing virtual environment if installed; do **not** upgrade or overwrite historical packages just to audit this release. Its `bin` path can be put first in `PATH` before running `bash scripts/reproduce_all.sh`. No absolute researcher paths are embedded in this release.

### What a version check means

```bash
python3 scripts/check_environment.py
python3 scripts/check_environment.py --strict
```

Default checks direct-package presence/declared broad compatibility and clearly marks when versions differ from the successfully tested lab. `--strict` requires exact Python 3.10.12 / NumPy 2.2.6 / Matplotlib 3.10.9. A full `FINAL_REPRODUCTION_STATUS=PASS` establishes regenerated scientific output agreement; it does not prove all original physical API branches are reproducible.

## Tier C: historical model/API execution

`requirements-full.txt` records **unlocked lower bounds** for some direct imports and is **not** an installable substitute for the original external benchmarks, pretrained weights, provider service, CUDA and driver versions, or the full historical lab environment. See `docs/EXTERNAL_DEPENDENCIES.md` and `docs/PROVENANCE_GATES.md`. These remain explicitly NOT fully reproducible from this archive alone.
