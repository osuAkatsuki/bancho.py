# Einrichtung

## Die osu!-Server-Codebasis herunterladen und auf deinem System installieren

```sh
# das bancho.py-Repository klonen
git clone https://github.com/osuAkatsuki/bancho.py

# in das neue bancho.py-Verzeichnis wechseln
cd bancho.py

# docker zum Bauen und Ausführen des Anwendungs-Images installieren
sudo apt install -y docker.io docker-compose-plugin

# wahlweise: uv für lokales Linting, Type-Checking und Unit-Tests installieren
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## bancho.py konfigurieren

Die Konfiguration des osu!-Servers (bancho.py) selbst erfolgt über die Dateien
`.env` und `logging.yaml`. Für beide Dateien gibt es Beispieldateien, die du als
Grundlage verwenden und nach Bedarf anpassen kannst.

```sh
# eine Konfigurationsdatei aus der Beispieldatei erstellen
cp .env.example .env

# eine Logging-Konfigurationsdatei aus der Beispieldatei erstellen
cp logging.yaml.example logging.yaml

# die Anwendung an deine Bedürfnisse anpassen
# dies ist erforderlich, bevor du mit den nächsten Schritten fortfährst
nano .env

# wenn du möchtest, kannst du auch das Logging konfigurieren;
# die Standardkonfiguration sollte für die meisten Nutzer ausreichen.
nano logging.yaml
```

## Einen Reverse-Proxy konfigurieren (wir verwenden nginx)

bancho.py verwendet einen Reverse-Proxy für TLS-Unterstützung (HTTPS) und zur
einfacheren Konfiguration. In dieser Anleitung verwenden wir den quelloffenen und
effizienten Webserver nginx; andere Optionen wie caddy oder h2o sind ebenfalls
möglich.

```sh
# nginx installieren
sudo apt install nginx

# nginx-Konfiguration mit den Werten aus deiner .env installieren
./scripts/install-nginx-config.sh
```

## Glückwunsch! Du hast gerade einen privaten osu!-Server eingerichtet

Wenn alles geklappt hat, kannst du deinen Server nun starten:

```sh
# die Anwendung bauen
make build

# die Anwendung starten
make run
```

Zusätzlich stehen dir die folgenden Befehle zur Verfügung:

```sh
# die Anwendung im Hintergrund starten
make run-bg

# Logs aller laufenden Container anzeigen
make logs

# alle automatisierten Tests ausführen
make test

# nur die Unit-Tests ohne docker ausführen
make utest

# Formatierer und Linter ausführen
make lint

# statisches Type-Checking ausführen
make type-check

# die lokale uv-virtualenv entfernen
make uninstall
```
