#!/usr/bin/env bash
# Source from reproduce_all.sh after ROOT is defined. Zero API calls.
# Prefer a compatible active interpreter, then inspect nearby environments.
# No researcher-specific machine paths or identifiers are encoded here.

_decouple_compatible_python() {
    [ -n "${1:-}" ] && [ -x "$1" ] && "$1" "$ROOT/scripts/check_environment.py" >/dev/null 2>&1
}

_decouple_selected=""
if [ -n "${DECOUPLE_PYTHON:-}" ]; then
    if _decouple_compatible_python "$DECOUPLE_PYTHON"; then
        _decouple_selected="$DECOUPLE_PYTHON"
    else
        echo "FAIL DECOUPLE_PYTHON was set but is not a compatible offline reproduction interpreter"
        echo "NEXT=use a Python 3.10 environment with numpy and matplotlib (docs/ENVIRONMENT.md)"
        return 2
    fi
fi

if [ -z "$_decouple_selected" ]; then
    for _candidate in "${VIRTUAL_ENV:-}/bin/python3" "${CONDA_PREFIX:-}/bin/python3" "$(command -v python3 2>/dev/null || true)" "$ROOT/../decouple-review-venv/bin/python3"; do
        if _decouple_compatible_python "$_candidate"; then
            _decouple_selected="$_candidate"
            break
        fi
    done
fi

# Look only for conventional environment locations near the release checkout.
# This supports lab checkout locations without embedding a private home path.
if [ -z "$_decouple_selected" ]; then
    _ancestor="$ROOT"
    for _level in 0 1 2 3 4; do
        for _candidate in "$_ancestor"/02_ENVIRONMENT/*/bin/python3 "$_ancestor"/.venv/bin/python3 "$_ancestor"/venv/bin/python3 "$_ancestor"/envs/*/bin/python3; do
            if _decouple_compatible_python "$_candidate"; then
                _decouple_selected="$_candidate"
                break
            fi
        done
        [ -n "$_decouple_selected" ] && break
        [ "$_ancestor" = / ] && break
        _ancestor="$(dirname "$_ancestor")"
    done
fi

if [ -z "$_decouple_selected" ]; then
    echo "FAIL no compatible Python environment found (NumPy and Matplotlib required)"
    echo "NEXT=use the existing environment: DECOUPLE_PYTHON=/path/to/python3 make reviewer-check"
    echo "NEXT=or consult docs/ENVIRONMENT.md"
    return 2
fi

export DECOUPLE_PYTHON="$_decouple_selected"
export PATH="$(dirname "$_decouple_selected"):$PATH"
echo "PASS OFFLINE_PYTHON_RESOLVED"
echo "PYTHON_EXECUTABLE=$DECOUPLE_PYTHON"
return 0
