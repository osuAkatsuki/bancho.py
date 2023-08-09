#!/usr/bin/env bash
set -euo pipefail

read -r -p "Insert your domain name (Default value: example.com): " domain
domain=${domain:-example.com}

read -r -p "Insert your cloudflare origin ca key (Get it from https://dash.cloudflare.com/profile/api-tokens): " cloudflare_origin_ca_key

echo "Generating certificate request..."
openssl req -nodes -newkey rsa:2048 -keyout banchopy.key -out request.csr -subj "/CN=$domain"
dns_csr=$(awk 'NF {sub(/\r/, ""); printf "%s\\n",$0;}' request.csr)

echo "Requesting certificate from cloudflare..."
cert_result=(curl -X POST "https://api.cloudflare.com/client/v4/certificates"
  -H "X-Auth-User-Service-Key: $cloudflare_origin_ca_key"
  -H "Content-Type: application/json"
  --data "{\"hostnames\":[\"$domain\", \"*.$domain\"],\"requested_validity\":5475,\"request_type\":\"origin-rsa\",\"csr\":\"$dns_csr\"}")

# TODO: Check result and exit if error

echo "The certificate has been generated successfully! You can now start bancho.py!"
