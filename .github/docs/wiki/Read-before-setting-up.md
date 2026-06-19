# Read before setting up

## Prerequisites

knowledge of linux, python, and databases will certainly help, but are by no
means required.

(lots of people have installed this server with no prior programming experience!)

if you get stuck at any point in the process - we have a public discord above :)

this guide will be targetted towards ubuntu - other distros may have slightly
different setup processes.

## Requirements

**bancho.py** is a ~20,000 line codebase built on the shoulder of giants.

we aim to minimize our dependencies, but still rely on ones such as

- python (programming language)
- docker (container runtime)
- docker compose plugin (container orchestration)
- mysql (relational database, via docker compose)
- redis (in memory database, via docker compose)
- nginx (http(s) reverse proxy)
- certbot (ssl certificate tool)
- uv (python project manager, optional for local development)

as well as some others.
