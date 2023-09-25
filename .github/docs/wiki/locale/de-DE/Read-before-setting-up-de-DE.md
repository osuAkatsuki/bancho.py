# Lesen Sie vor der Einrichtung

## Voraussetzungen

Kenntnisse in Linux, Python und Datenbanken sind sicherlich hilfreich, aber
keinesfalls erforderlich.

(Viele Leute haben diesen Server ohne vorherige Programmiererfahrung
installiert!)

Wenn du an irgendeinem Punkt des Prozesses nicht weiterkommst -
wir haben oben einen öffentlichen Discord :)

Diese Anleitung ist auf Ubuntu ausgerichtet - andere Distributionen können leicht
abweichende Installationsprozesse haben.

## Anforderungen

**bancho.py** ist eine ~15.000 Zeilen lange Codebasis, die auf den Schultern von Riesen gebaut wurde.

Wir versuchen, unsere Abhängigkeiten zu minimieren, sind aber immer noch auf Abhängigkeiten wie

- python (Programmiersprache)
- mysql (relationale Datenbank)
- redis (speicherinterne Datenbank)
- nginx (http(s)-Reverse-Proxy)
- geoip2 (ein nginx-Modul)
- certbot (ssl-Zertifikatstool)
- build-essential (Build-Werkzeuge für C/C++)

als auch einige andere angewiesen.
