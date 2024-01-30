#!/usr/bin/env bash
read -p "What's your server domain? " domain
domain=${domain:-example.com}

read -p "What's your server IP? " ip
ip=${ip:-0.0.0.0}

printf '%s\n' \
    "a	1	IN	A	$ip"\
    "api	1	IN	A	$ip"\
    "assets	1	IN	A	$ip"\
    "b	1	IN	A	$ip"\
    "c	1	IN	A	$ip"\
    "c4	1	IN	A	$ip"\
    "ce	1	IN	A	$ip"\
    "$domain	1	IN	A	$ip"\
    "i	1	IN	A	$ip"\
    "osu	1	IN	A	$ip"\
    "s	1	IN	A	$ip" >> "cf_records.txt"

printf "Your Cloudflare DNS records have been generated."
