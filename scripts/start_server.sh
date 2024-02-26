#!/usr/bin/env bash
set -euxo pipefail

# Wait for healthy database connections to be established
scripts/wait-for-it.sh --timeout=60 $DB_HOST:$DB_PORT
scripts/wait-for-it.sh --timeout=60 $REDIS_HOST:$REDIS_PORT

# Run the db migrations
scripts/run-database-migrations.sh

# Run the application
python main.py
