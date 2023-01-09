#!/usr/bin/env bash
set -euxo pipefail

make shell

# Checking MySQL TCP connection
scripts/wait-for-it.sh $DB_HOST:$DB_PORT

# Checking Redis connection
scripts/wait-for-it.sh $REDIS_HOST:$REDIS_PORT

make run
