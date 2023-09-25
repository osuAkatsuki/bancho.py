#!/usr/bin/env bash
set -euo pipefail

# Run tests
echo "Running tests..."
python -m pytest -vv tests/
