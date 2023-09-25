#!/usr/bin/env bash
set -euo pipefail

echo "Sourcing environment from .env file"
set -a
source .env
set +a

echo "Installing nginx configuration"
envsubst < ext/nginx.conf.example > /etc/nginx/sites-available/bancho.conf
ln -s /etc/nginx/sites-available/bancho.conf /etc/nginx/sites-enabled/bancho.conf

echo "Restarting nginx"
nginx -s reload

echo "Nginx configuration installed with current"
