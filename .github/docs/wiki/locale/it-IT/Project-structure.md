# Struttura del Progetto

    .
    ├── app                   # il server - logica, classi e oggetti
    |   ├── api                 # codice relativo alla gestione delle richieste esterne
    |   |   ├── domains           # endpoint accessibili esternamente
    |   |   |   ├── cho.py        # endpoint disponibili @ https://c.cmyui.xyz
    |   |   |   ├── map.py        # endpoint disponibili @ https://b.cmyui.xyz
    |   |   |   └── osu.py        # endpoint disponibili @ https://osu.cmyui.xyz
    |   |   |
    |   |   ├── v1
    |   |   |   └── api.py          # endpoint disponibili @ https://api.cmyui.xyz/v1
    |   |   |
    |   |   ├── v2
    |   |   |   ├── clans.py        # endpoint disponibili @ https://api.cmyui.xyz/v2/clans
    |   |   |   ├── maps.py         # endpoint disponibili @ https://api.cmyui.xyz/v2/maps
    |   |   |   ├── players.py      # endpoint disponibili @ https://api.cmyui.xyz/v2/players
    |   |   |   └── scores.py       # endpoint disponibili @ https://api.cmyui.xyz/v2/scores
    |   |   |
    |   |   ├── init_api.py       # logica per assemblare il server
    |   |   └── middlewares.py    # logica che avvolge gli endpoint
    |   |
    |   ├── constants           # logica e dati per classi e oggetti costanti lato server
    |   |   ├── clientflags.py    # flag anticheat utilizzati dal client di osu!
    |   |   ├── gamemodes.py      # modalità di gioco di osu!, con supporto relax/autopilot
    |   |   ├── mods.py           # modificatori di gioco di osu!
    |   |   ├── privileges.py     # privilegi per i giocatori, globalmente e nei clan
    |   |   └── regexes.py        # regex utilizzate nel codice
    |   |
    |   ├── objects             # logica e dati per classi e oggetti dinamici lato server
    |   |   ├── achievement.py    # rappresentazione di singoli obiettivi
    |   |   ├── beatmap.py        # rappresentazione di singole mappe(set)
    |   |   ├── channel.py        # rappresentazione di singoli canali di chat
    |   |   ├── clan.py           # rappresentazione di singoli clan
    |   |   ├── collection.py     # collezioni di oggetti dinamici (per archiviazione in memoria)
    |   |   ├── match.py          # singole partite multiplayer
    |   |   ├── models.py         # strutture dei corpi delle richieste API
    |   |   ├── player.py         # rappresentazione di singoli giocatori
    |   |   └── score.py          # rappresentazione di singoli punteggi
    |   |
    |   ├── state               # oggetti che rappresentano lo stato attivo del server
    |   |   ├── cache.py          # dati salvati per scopi di ottimizzazione
    |   |   ├── services.py       # istanze di servizi di terze parti (es. database)
    |   |   └── sessions.py       # sessioni attive (giocatori, canali, partite, ecc.)
    |   |
    |   ├── bg_loops.py           # cicli in esecuzione mentre il server è attivo
    |   ├── commands.py           # comandi disponibili nella chat di osu!
    |   ├── packets.py            # modulo per (de)serializzazione dei pacchetti di osu!
    |   └── settings.py           # gestisce i valori di configurazione dell'utente
    |
    ├── ext                   # entità esterne utilizzate durante l'esecuzione del server
    ├── migrations            # migrazioni del database - aggiornamenti dello schema
    ├── tools                 # vari strumenti creati nella storia di bancho.py
    └── main.py               # un punto di ingresso (script) per eseguire il server
