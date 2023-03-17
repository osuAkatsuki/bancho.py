#!/usr/bin/env bash
read -p "What's your server domain? " domain
domain=${domain:-example.com}

read -p "What's your server IP? " ip
ip=${ip:-0.0.0.0}

printf '%s\n' \
    "a.$domain	1	IN	A	$ip"\
    "api.$domain	1	IN	A	$ip"\
    "assets.$domain	1	IN	A	$ip"\
    "b.$domain	1	IN	A	$ip"\
    "c1.$domain	1	IN	A	$ip"\
    "c2.$domain	1	IN	A	$ip"\
    "c3.$domain	1	IN	A	$ip"\
    "c4.$domain	1	IN	A	$ip"\
    "c5.$domain	1	IN	A	$ip"\
    "c6.$domain	1	IN	A	$ip"\
    "ce.$domain	1	IN	A	$ip"\
    "cho.$domain	1	IN	A	$ip"\
    "c.$domain	1	IN	A	$ip"\
    "$domain	1	IN	A	$ip"\
    "i.$domain	1	IN	A	$ip"\
    "map.$domain	1	IN	A	$ip"\
    "osu.$domain	1	IN	A	$ip"\
    "s.$domain	1	IN	A	$ip"\
    "web.$domain	1	IN	A	$ip" >> "cf_records.txt"

printf "Your Cloudflare DNS records have been generated."
