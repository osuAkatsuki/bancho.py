# Projectsstruktur

    .
    ├── app                        # der Server - Logik, Klassen und Objekte
    |   ├── api                    # Code für die Bearbeitung externer Anfragen
    |   |   ├── domains            # Endpunkte, die von außen erreicht werden können
    |   |   |   ├── cho.py         # Endpunkte verfügbar @ https://c.cmyui.xyz
    |   |   |   ├── map.py         # Endpunkte verfügbar @ https://b.cmyui.xyz
    |   |   |   └── osu.py         # Endpunkte verfügbar @ https://osu.cmyui.xyz
    |   |   |
    |   |   ├── v1                 # Version 1 der API
    |   |   |   └── api.py         # Endpunkte verfügbar @ https://api.cmyui.xyz/v1
    |   |   |
    |   |   ├── v2                 # Version 2 der API
    |   |   |   ├── clans.py       # Endpunkte verfügbar @ https://api.cmyui.xyz/v2/clans
    |   |   |   ├── maps.py        # Endpunkte verfügbar @ https://api.cmyui.xyz/v2/maps
    |   |   |   ├── players.py     # Endpunkte verfügbar @ https://api.cmyui.xyz/v2/players
    |   |   |   └── scores.py      # Endpunkte verfügbar @ https://api.cmyui.xyz/v2/scores
    |   |   |
    |   |   ├── init_api.py        # Logik zum Zusammenstellen des Servers
    |   |   └── middlewares.py     # Logik, die sich um die Endpunkte wickelt
    |   |
    |   ├── constants              # Logik & Daten für statische serverseitige Konstanten
    |   |   ├── clientflags.py     # Anti-Cheat-Flags, die von osu!-Clients gesendet werden
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
