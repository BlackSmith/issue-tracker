#!/bin/bash

set -euo pipefail

# Resolve the workspace independently of the caller's working directory.
workspace_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -f "$workspace_dir/backend/requirements.txt" ]]; then
    python -m venv "$workspace_dir/backend/.venv"
    "$workspace_dir/backend/.venv/bin/python" -m pip install --upgrade pip
    "$workspace_dir/backend/.venv/bin/python" -m pip install -r "$workspace_dir/backend/requirements.txt"
fi

if [[ -f "$workspace_dir/frontend/package.json" ]]; then
    if [[ -f "$workspace_dir/frontend/package-lock.json" ]]; then
        npm --prefix "$workspace_dir/frontend" ci
    else
        npm --prefix "$workspace_dir/frontend" install
    fi
fi
