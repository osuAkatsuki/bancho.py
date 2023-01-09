#!/usr/bin/env bash
read -p "What's the name of your server? " name
name=${name=Bancho}
read -p "What's the base domain of your server? " domain
domain=*.${domain=ppy.sh}
read -p "What country is this based in? (ISO country code) " location
location=${location=CA}

args="/CN=$domain/O=$name/C=$location"
openssl req -subj $args -new -newkey rsa:4096 -sha256 -days 36500 -nodes -x509 -keyout key.pem -out cert.pem
openssl x509 -outform der -in cert.pem -out cert.crt

printf "Your certificates have been generated."
