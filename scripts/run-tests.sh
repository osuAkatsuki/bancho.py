#!/usr/bin/env bash
set -eo pipefail

export DB_HOST=mysql-test
export REDIS_HOST=redis-test

initDB() {
  echo "Initializing database..."
  if [[ "$DB_USE_SSL" == "true" ]]; then
    EXTRA_PARAMS="--ssl"
  else
    EXTRA_PARAMS=""
  fi

  DB_QUERIES=(
    "DROP DATABASE IF EXISTS $DB_NAME"
    "CREATE DATABASE $DB_NAME"
  )

  for query in "${DB_QUERIES[@]}"
  do
    mysql \
      --host=$DB_HOST \
      --port=$DB_PORT \
      --user=root \
      --database=mysql \
      --password=$DB_PASS \
      $EXTRA_PARAMS \
      --execute="$query"
  done

  redis-cli -h $REDIS_HOST -p $REDIS_PORT FLUSHALL
}

execDBStatement() {
  if [[ "$DB_USE_SSL" == "true" ]]; then
    EXTRA_PARAMS="--ssl"
  else
    EXTRA_PARAMS=""
  fi

  mysql \
    --host=$DB_HOST \
    --port=$DB_PORT \
    --user=root \
    --database=$DB_NAME \
    --password=$DB_PASS \
    $EXTRA_PARAMS \
    --execute="$1"
}


initDB

execDBStatement "source /srv/root/migrations/base.sql"

# Run tests
echo "Running tests..."
pytest -vv -s tests/
