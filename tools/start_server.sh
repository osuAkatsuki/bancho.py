#!/usr/bin/env bash
set -euxo pipefail

# Checking MySQL TCP connection
tools/wait-for-it.sh --timeout=60 $DB_HOST:$DB_PORT

# Checking Redis connection
tools/wait-for-it.sh --timeout=60 $REDIS_HOST:$REDIS_PORT

python main.py
