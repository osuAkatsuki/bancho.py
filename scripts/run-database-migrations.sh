#!/usr/bin/env bash
set -euxo pipefail

alembic upgrade head

# If an error occurs the first time the migrations run, we'll
# assume that the schema already exists and the user is migrating
# from a previous version (< v5.3.0) of bancho.py. We'll need to
# tell alembic the current migration represents the state of the db
if [ $? -ne 0 ] && [ ! -f /srv/root/.data/migrations_run_before ]; then
    alembic stamp head
    touch /srv/root/.data/migrations_run_before
fi
