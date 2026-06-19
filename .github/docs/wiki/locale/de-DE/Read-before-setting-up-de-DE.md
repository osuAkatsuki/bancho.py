# Vor der Einrichtung lesen

## Voraussetzungen

Kenntnisse in Linux, Python und Datenbanken sind sicherlich hilfreich, aber nicht
zwingend erforderlich.

(Viele Leute haben diesen Server ohne vorherige Programmiererfahrung
installiert!)

Wenn du an irgendeinem Punkt des Prozesses nicht weiterkommst, gibt es oben
einen öffentlichen Discord :)

Diese Anleitung ist auf Ubuntu ausgerichtet - andere Distributionen können leicht
abweichende Installationsprozesse haben.

## Anforderungen

**bancho.py** ist eine Codebasis mit etwa 20.000 Zeilen, die auf vielen
bewährten Projekten aufbaut.

Wir versuchen, unsere Abhängigkeiten zu minimieren, benötigen aber weiterhin
Komponenten wie:

- python (Programmiersprache)
- docker (Container-Laufzeitumgebung)
- docker compose plugin (Container-Orchestrierung)
- mysql (relationale Datenbank, über docker compose)
- redis (In-Memory-Datenbank, über docker compose)
- nginx (HTTP(S)-Reverse-Proxy)
- certbot (SSL-Zertifikatstool)
- uv (Python-Projektmanager, wahlweise für lokale Entwicklung)

sowie einige weitere.
