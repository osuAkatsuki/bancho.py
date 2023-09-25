# Read before setting up

## Prerequisites

knowledge of linux, python, and databases will certainly help, but are by no
means required.

(lots of people have installed this server with no prior programming experience!)

if you get stuck at any point in the process - we have a public discord above :)

this guide will be targetted towards ubuntu - other distros may have slightly
different setup processes.

## Requirements

**bancho.py** is a ~15,000 line codebase built on the shoulder of giants.

we aim to minimize our dependencies, but still rely on ones such as

- python (programming language)
- mysql (relational database)
- redis (in memory database)
- nginx (http(s) reverse proxy)
- geoip2 (an nginx module)
- certbot (ssl certificate tool)
- build-essential (build tools for c/c++)

as well as some others.
