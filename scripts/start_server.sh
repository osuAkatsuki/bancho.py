#!/usr/bin/env bash
set -euxo pipefail

# Checking MySQL TCP connection
wait4x mysql $DB_USER:$DB_PASS@tcp'('$DB_HOST:$DB_PORT')'/$DB_NAME

# Checking Redis connection
wait4x redis redis://$REDIS_USER:$REDIS_PASS@$REDIS_HOST:$REDIS_PORT/$REDIS_DB

make run
