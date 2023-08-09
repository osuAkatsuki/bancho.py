#!/usr/bin/env bash
set -eo pipefail

main() {
  # ensure admin privileges
  if ((EUID != 0)); then
    printf "This script must be run with administrative privileges."
    exit
  fi

  ip=$(curl -s -X GET -4 https://ifconfig.co)

  print_title "Welcome to the banchopy setup docker script!\nYour public ip is: ${ip}. This'll be used in the bancho.py setup."

  print_title_2 "Reverse proxy setup (nginx)"

  read -r -p "Domain name (Default value: example.com): " domain
  domain=${domain:-example.com}

  echo "Checking if ${domain} is a valid domain..."
  if check_valid_domain "${domain}"; then
    echo "${domain} is a valid domain. The script will continue."
  else
    echo "${domain} is not a valid domain. Run this script again and insert a valid domain."
    exit 1
  fi

  read -r -p "Certificate path (Default value: Actual path + banchopy.crt): " ssl_cert_path
  ssl_cert_path=${ssl_cert_path:-$(pwd)/banchopy.crt}

  read -r -p "Private key path (Default value: Actual path + banchopy.key): " ssl_key_path
  ssl_key_path=${ssl_key_path:-$(pwd)/banchopy.key}

  print_title "Database setup (MySQL)"

  read -r -p "Database name (Default value: banchopy): " db_name
  db_name=${db_name:-banchopy}

  read -r -p "Database password (Default value: banchopy): " db_password
  db_password=${db_password:-banchopy}

  read -r -p "Database user (Default value: banchopy_user): " db_user
  db_user=${db_user:-banchopy_user}

  print_title "Cache setup (Redis)"

  read -r -p "Redis user (Default value: redis): " redis_user
  redis_user=${redis_user:-redis}

  read -r -s -p "Redis password: " redis_password

  printf "\n"
  print_title "osu! api setup"

  read -r -p $'Your osu! api key: ' osu_api_key

  if [[ -z "${osu_api_key}" ]]; then
    echo "You must insert an osu! api key. Run this script again and insert an osu! api key."
    echo "You can get it from https://osu.ppy.sh/home/account/edit#legacy-api"
    exit 1
  fi

  echo "Setting up .env file..."
  if [ ! -f ../.env ]; then
    echo "Copying .docker.env.example to .env..."
    cp ../docker.env.example ../.env
  else
    echo ".env file already exists. Skipping..."
  fi

  # Nginx
  modify_env_value "DOMAIN" "${domain}"
  modify_env_value "HOST_PORT" "443"
  modify_env_value "SSL_CERT_PATH" "${ssl_cert_path}"
  modify_env_value "SSL_KEY_PATH" "${ssl_key_path}"

  # MySQL
  modify_env_value "DB_NAME" "${db_name}"
  modify_env_value "DB_PASS" "${db_password}"
  modify_env_value "DB_USER" "${db_user}"

  # Redis
  modify_env_value "REDIS_USER" "${redis_user}"
  modify_env_value "REDIS_PASS" "${redis_password}"

  # osu!
  modify_env_value "OSU_API_KEY" "${osu_api_key}"

  read -r -p "Would you like to use cloudflare or use your own certificates? (Y/n) (Default value: y): " cloudflare_option
  cloudflare_option=${cloudflare_option:-y}

  case "${cloudflare_option}" in
  [yY][eE][sS] | [yY])
    use_cloudflare=true
    ;;
  [nN][oO] | [nN])
    use_cloudflare=false
    ;;
  *)
    echo "You must insert a valid option. Run this script again and insert a valid option."
    exit 1
    ;;
  esac

  if [[ "${use_cloudflare}" == true ]]; then
    setup_cloudflare
  else
    cd .. # Go to root folder of the project where docker-compose.yml is located
    echo "Bancho.py has been configured successfully. Run it with docker-compose up -d"
  fi
}

setup_cloudflare() {
  print_title "Cloudflare setup"

  read -r -p "Your cloudflare email: " cloudflare_email
  read -r -p "Your cloudflare id (https://dash.cloudflare.com/{THIS_IS_YOUR_CF_ID}): " cloudflare_user_id
  read -r -p "Your cloudflare global api key (Get it from https://dash.cloudflare.com/profile/api-tokens): " cloudflare_global_api_key

  echo "Adding ${domain} to cloudflare..."
  created_result=$(curl -X POST -H "X-Auth-Key: ${cloudflare_global_api_key}" -H "X-Auth-Email: $cloudflare_email" -H "Content-Type: application/json" "https://api.cloudflare.com/client/v4/zones" --data '{"account": {"id": "'"${cloudflare_user_id}"'"}, "name":"'"${domain}"'","jump_start":true}')
  echo "Uploading DNS records to cloudflare..."

  # TODO: Check result and exit if error

  printf "%s\n%s" "${domain}" "${ip}" | ./generate_cf_dns_records.sh
  zone_id=$(echo "${created_result}" | jq -r '.result.id')

  cd ..
  base_path=$(pwd)
  cd tools

  curl -X POST "https://api.cloudflare.com/client/v4/zones/${zone_id}/dns_records/import" \
    -H "X-Auth-Email: ${cloudflare_email}" \
    -H "X-Auth-Key: ${cloudflare_global_api_key}" \
    --form "file=@$base_path/tools/cf_records.txt" \
    --form "proxied=true"

  # TODO: Check result and exit if error
  
  echo "Bancho.py has been configured successfully. After your domain is no longer in pending status, run generate_cf_certs.sh to generate your certificates from cloudflare."
}

# Utils
print_separator() {
  printf "=%.0s" $(seq 1 128)
  printf "\n"
}

print_title() {
  print_separator
  echo -e $"$1"
  print_separator
}

print_title_2() {
  echo -e $"$1"
  print_separator
}

check_valid_domain() {
  regex_domain=$(echo "$1" | grep -P '(?=^.{4,253}$)(^(?:[a-zA-Z](?:(?:[a-zA-Z0-9\-]){0,61}[a-zA-Z])?\.)+[a-zA-Z]{2,}$)')
  if [[ -z "${regex_domain}" ]]; then
    return 1
  else
    return 0
  fi
}

modify_env_value() {
  key=$1
  value=$(echo "$2" | sed 's/\//\\\//g')
  find ../.env -type f -exec sed -i "s/^\($key\s*=\s*\).*/\1$value/" {} \;
}

main "$@"
