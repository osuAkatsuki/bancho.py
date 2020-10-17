#!/usr/bin/env bash
read -p "What's the name of your server?" name
server_name=${name=Gulag}
read -p "What country is this based in? (ISO country code)" location
country_name=${location=CA}

args="/CN=*.ppy.sh/O=$name/C=$location"
openssl req -subj $args -new -newkey rsa:4096 -sha256 -days 36500 -nodes -x509 -keyout key.pem -out cert.pem
openssl x509 -outform der -in cert.pem -out cert.crt

printf "Your certificates have been generated."