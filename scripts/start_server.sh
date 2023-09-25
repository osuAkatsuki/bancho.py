#!/usr/bin/env bash
set -euxo pipefail

# Checking MySQL TCP connection
scripts/wait-for-it.sh --timeout=60 $DB_HOST:$DB_PORT

# Checking Redis connection
scripts/wait-for-it.sh --timeout=60 $REDIS_HOST:$REDIS_PORT

python main.py
