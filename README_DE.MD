# bancho.py
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Code Stil: schwarz](https://img.shields.io/badge/Code%20Stil-Schwarz-black)](https://github.com/ambv/black)
[![pre-commit.ci Status](https://results.pre-commit.ci/badge/github/osuAkatsuki/bancho.py/master.svg)](https://results.pre-commit.ci/latest/github/osuAkatsuki/bancho.py/master)
[![Discord](https://discordapp.com/api/guilds/748687781605408908/widget.png?style=shield)](https://discord.gg/ShEQgUx)

bancho.py ist eine in Arbeit befindliche osu!-Server-Implementierung für
Entwickler aller Erfahrungsstufen, die daran interessiert sind, ihre eigene(n)
private(n) osu-Server-Instanz(en) zu hosten

Das Projekt wird hauptsächlich vom [Akatsuki](https://akatsuki.pw/)-Team entwickelt,
und unser Ziel ist es, die am einfachsten zu wartende, zuverlässigste und
funktionsreichste osu!-Server-Implementierung auf dem Markt zu schaffen.

# Einrichtung
Kenntnisse in Linux, Python und Datenbanken sind sicherlich hilfreich, aber
keinesfalls erforderlich.

(Viele Leute haben diesen Server ohne vorherige Programmiererfahrung
installiert!)

Wenn du an irgendeinem Punkt des Prozesses nicht weiterkommst -
wir haben oben einen öffentlichen Discord :)

Diese Anleitung ist auf Ubuntu ausgerichtet - andere Distributionen können leicht
abweichende Installationsprozesse haben.

## Laden Sie die osu! Server-Codebasis auf Ihren Rechner herunter
```sh
# Klone das Repository von bancho.py
git clone https://github.com/osuAkatsuki/bancho.py

# gebe das neue Verzeichnis von bancho.py ein
cd bancho.py
```

## Installation der Anforderungen von bancho.py
bancho.py ist eine ~15.000 Zeilen lange Codebasis, die auf den Schultern von Riesen gebaut wurde.

Wir versuchen, unsere Abhängigkeiten zu minimieren, sind aber immer noch auf Abhängigkeiten wie
- python (Programmiersprache)
- rust (Programmiersprache)
- mysql (relationale Datenbank)
- redis (speicherinterne Datenbank)
- nginx (http(s)-Reverse-Proxy)
- certbot (ssl-Zertifikatstool)
- build-essential (Build-Werkzeuge für C/C++)

als auch einige andere angewiesen.
```sh
# python3.9 ist oft nicht nativ verfügbar,
# aber wir können uns auf Deadsnakes verlassen, um es bereitzustellen.
# https://github.com/deadsnakes/python3.9
sudo add-apt-repository -y ppa:deadsnakes

# Installiere die erforderlichen Programme für die Ausführung von bancho.py
sudo apt install -y python3.9-dev python3.9-distutils \
                    build-essential \
                    mysql-server redis-server \
                    nginx certbot

# Installieren rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Installieren Sie den Paketmanager von Python, pip
# Er wird verwendet, um python-spezifische Abhängigkeiten zu installieren
wget https://bootstrap.pypa.io/get-pip.py
python3.9 get-pip.py && rm get-pip.py

# Stellen Sie sicher, dass pip und setuptools auf dem neuesten Stand sind.
python3.9 -m pip install -U pip setuptools pipenv

# Installiere die python-spezifischen Abhängigkeiten von bancho.py
# (wenn Sie planen, als Entwickler zu arbeiten, können Sie `make install-dev` verwenden)
make install
```

## Erstellen einer Datenbank für bancho.py
Sie müssen eine Datenbank für bancho.py erstellen, um persistente Daten zu speichern.

Der Server benutzt diese Datenbank, um Metadaten und Logs zu speichern, wie z.B. Benutzerkonten
und Statistiken, Beatmaps und Beatmapsets, Chat-Kanäle, Turnier-Mappools und mehr.

```sh
# Starten Sie Ihren Datenbankserver
sudo service mysql start

# Melden Sie sich in der Shell von mysql mit root an - dem Standard-Admin-Konto.

# Beachten Sie, dass diese Shell ziemlich gefährlich sein kann - sie erlaubt Benutzern
# beliebige SQL-Befehle auszuführen, um mit der Datenbank zu interagieren.

# Sie ist aber auch sehr nützlich, mächtig und schnell, wenn sie richtig benutzt wird.
mysql -u root -p
```

Von dieser mysql-Shell aus wollen wir eine Datenbank anlegen, ein Benutzerkonto erstellen,
und dem Benutzer volle Rechte für die Datenbank geben.

Später werden wir dann bancho.py so konfigurieren, dass es diese Datenbank ebenfalls verwendet.
```sql
# Sie müssen ändern:
# - IHR_DB_NAME
# - IHR_DB_NUTZER
# - IHR_DB_PASSWORT

# Erstelle eine Datenbank, die bancho.py verwenden kann.
CREATE DATABASE IHR_DB_NAME;

# Lege einen Benutzer an, der die bancho.py-Datenbank benutzt.
CREATE USER 'IHR_DB_NUTZER'@'localhost' IDENTIFIED BY 'IHR_DB_PASSWORT';

# Gewähre dem Benutzer vollen Zugriff auf alle Tabellen in der bancho.py-Datenbank.
GRANT ALL PRIVILEGES ON IHR_DB_NAME.* TO 'IHR_DB_NUTZER'@'localhost';

# Stellen Sie sicher, dass die Änderungen der Privilegien sofort übernommen werden.
FLUSH PRIVILEGES;

# Verlasse die mysql-Shell, um zurück zur bash zu gelangen.
quit
```

## Einrichten der Datenbankstruktur für bancho.py
Haben wir nun eine leere Datenbank erstellt - Datenbanken sind voll von 2-dimensionalen
Tabellen mit Daten.

bancho.py hat viele Tabellen, die es benutzt, um Informationen zu organisieren, zum Beispiel gibt es
gibt es Tabellen wie `users` und `scores` zum Speichern der jeweiligen Informationen.

Die Spalten (vertikal) stellen die Arten von Daten dar, die für einen `user` oder eine `score` gespeichert werden.
Zum Beispiel die Anzahl der 300er in einer Punktzahl oder die Berechtigungen eines Benutzers.

Die Zeilen (horizontal) stellen die einzelnen Elemente oder Ereignisse in einer Tabelle dar.
Zum Beispiel eine einzelne Punktzahl in der Tabelle "Punkte".

Dieser Grundzustand der Datenbank wird in `ext/base.sql` gespeichert; es ist ein Bündel von
sql-Befehlen, die nacheinander ausgeführt werden können, um den gewünschten Grundzustand zu erzeugen.
```sh
# Sie müssen ändern:
# - IHR_DB_NAME
# - IHR_DB_NUTZER

# Importiere die mysql-Struktur von bancho.py in unsere neue db.
# Dies führt den Inhalt der Datei als SQL-Befehle aus.
mysql -u IHR_DB_NUTZER -p IHR_DB_NAME < migrations/base.sql
```

## Erstellung eines SSL-Zertifikats (um https-Verkehr zu ermöglichen)
```sh
# Sie müssen ändern:
# - IHRE_EMAIL_ADRESSE
# - IHRE_DOMAIN

# Erstellen eines SSL-Zertifikats für Ihre Domain:
sudo certbot certonly \
    --manual \
    --preferred-challenges=dns \
    --email IHRE_EMAIL_ADRESSE \
    --server https://acme-v02.api.letsencrypt.org/directory \
    --agree-tos \
    -d *.IHRE_DOMAIN
```

## Konfigurieren eines Reverse-Proxys (wir verwenden nginx)
bancho.py benötigt einen Reverse-Proxy für die tls (https)-Unterstützung und für die Benutzerfreundlichkeit der Konfiguration.
nginx ist ein effizienter Open-Source-Webserver, den wir für diese Anleitung verwenden.
Sie können sich auch andere effiziente Open-Source-Webserver ansehen, wie z.B. caddy und h2o.

```sh
# Kopieren Sie die Beispielkonfiguration von nginx nach /etc/nginx/sites-available,
# und erstellen Sie einen symbolischen Link zu /etc/nginx/sites-enabled.
sudo cp ext/nginx.conf /etc/nginx/sites-available/bancho.conf
sudo ln -s /etc/nginx/sites-available/bancho.conf /etc/nginx/sites-enabled/bancho.conf

# Jetzt können Sie die Konfigurationsdatei bearbeiten.
# Die Stellen, die Sie ändern müssen, sind markiert.
sudo nano /etc/nginx/sites-available/bancho.conf

# Laden Sie die Konfiguration von der Festplatte neu.
sudo nginx -s reload
```

## Konfiguration von bancho.py
Die gesamte Konfiguration des osu! Servers (bancho.py) selbst kann in der Datei
`.env`-Datei vorgenommen werden. Wir stellen eine Beispiel-Datei `.env.example` zur Verfügung, die Sie als Basis verwenden können.
```sh
# Erstelle eine Konfigurationsdatei aus dem mitgelieferten Beispiel.
cp .env.example .env

# Sie sollten *mindestens* DB_DSN (die Datenbankverbindungsurl) konfigurieren,
# sowie den OSU_API_KEY setzen, wenn Sie Informationen aus der osu! v1 api benötigen.
# (z.B. Beatmaps).

# Öffnen Sie die Konfigurationsdatei zum Bearbeiten.
nano .env
```

## Glückwunsch! Sie haben soeben einen privaten osu!-Server eingerichtet!

Wenn alles gut gegangen ist, sollten Sie in der Lage sein, Ihren Server zu starten

```sh
# Starte den Server.
make run
```

und Sie sollten sowas in der Art sehen:

![tada](https://cdn.discordapp.com/attachments/616400094408736779/993705619498467369/ld-iZXysVXqwhM8.png)

# Verzeichnisstruktur
    .
    ├── app                        # der Server - Logik, Klassen und Objekte
    |   ├── api                    # Code für die Bearbeitung externer Anfragen
    |   |   ├── domains            # Endpunkte, die von außen erreicht werden können
    |   |   |   ├── api.py         # endpoints available @ https://api.ppy.sh
    |   |   |   ├── cho.py         # endpoints available @ https://c.ppy.sh
    |   |   |   ├── map.py         # endpoints available @ https://b.ppy.sh
    |   |   |   └── osu.py         # endpoints available @ https://osu.ppy.sh
    |   |   |
    |   |   ├── init_api.py        # Logik zum Zusammenstellen des Servers
    |   |   └── middlewares.py     # Logik, die sich um die Endpunkte wickelt
    |   |
    |   ├── constants              # logic & data for constant server-side classes & objects
    |   |   ├── clientflags.py     # anticheat flags used by the osu! client
    |   |   ├── gamemodes.py       # osu! gamemodes, mit relax/autopilot Unterstützung
    |   |   ├── mods.py            # osu! gameplay modifiers
    |   |   ├── privileges.py      # Privilegien für Spieler, global & in Clans
    |   |   └── regexes.py         # Regexe, die in der gesamten Codebasis verwendet werden
    |   |
    |   ├── objects                # Logik & Daten für dynamische serverseitige Klassen & Objekte
    |   |   ├── achievement.py     # Darstellung der einzelnen Leistungen
    |   |   ├── beatmap.py         # Darstellung einzelner Map(set)s
    |   |   ├── channel.py         # Darstellung individueller Chat-Kanäle
    |   |   ├── clan.py            # Darstellung der einzelnen Clans
    |   |   ├── collection.py      # Sammlungen von dynamischen Objekten (zur Speicherung im Speicher)
    |   |   ├── match.py           # individuelle Multiplayer-Matches
    |   |   ├── menu.py            # (WIP) Konzept für interaktive Menüs in Chat-Kanälen
    |   |   ├── models.py          # Strukturen von Api-Anfragekörpern
    |   |   ├── player.py          # Darstellung der einzelnen Spieler
    |   |   └── score.py           # Darstellung einzelner Spielstände
    |   |
    |   ├── state                  # Objekte, die den Live-Server-Status darstellen
    |   |   ├── cache.py           # zu Optimierungszwecken gespeicherte Daten
    |   |   ├── services.py        # Instanzen von 3rd-Party-Diensten (z. B. Datenbanken)
    |   |   └── sessions.py        # aktive Sitzungen (Spieler, Kanäle, Matches usw.)
    |   |
    |   ├── bg_loops.py            # Schleifen, die laufen, während der Server läuft
    |   ├── commands.py            # Befehle, die im Chat von osu! verfügbar sind
    |   ├── packets.py             # ein Modul zur (De-)Serialisierung von osu!-Paketen
    |   └── settings.py            # verwaltet Konfigurationswerte des Benutzers
    |
    ├── ext                        # externe Entitäten, die beim Betrieb des Servers verwendet werden
    ├── migrations                 # Datenbankmigrationen - Aktualisierungen des Schemas
    ├── tools                      # verschiedene Tools aus der Geschichte von bancho.py
    └── main.py                    # ein Einstiegspunkt (Skript) zur Ausführung des Servers
