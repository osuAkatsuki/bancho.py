#!/usr/bin/env bash

echo "waiting for mysql server"
while ! nc -z localhost 3306; do
    sleep 0.25
done

echo "waiting for redis server"
while ! nc -z localhost 6379; do
    sleep 0.25
done

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
python3.9 $SCRIPT_DIR/../main.py
