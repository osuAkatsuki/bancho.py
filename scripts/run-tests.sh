#!/usr/bin/env bash
set -euo pipefail

# Run tests
echo "Running tests..."
pytest -vv -s tests/
