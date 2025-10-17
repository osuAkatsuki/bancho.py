# Configurazione

## scaricare e installare il codice del server osu! sulla tua macchina

```sh
# clona il repository di bancho.py sulla tua macchina
git clone https://github.com/osuAkatsuki/bancho.py

# entra nella nuova directory di bancho.py
cd bancho.py

# installa docker per costruire l'immagine dell'applicazione
sudo apt install -y docker
```

## configurare bancho.py

Tutta la configurazione per il server osu! (bancho.py) può essere effettuata dai file
`.env` e `logging.yaml`. Forniremo file di esempio per ciascuno, che puoi utilizzare
come base e modificare a tuo piacimento.

```sh
# crea un file di configurazione dall'esempio fornito
cp .env.example .env

# crea un file di configurazione di logging dall'esempio fornito
cp logging.yaml.example logging.yaml

# configura l'applicazione secondo le tue esigenze
# questo è necessario per passare ai passaggi successivi
nano .env

# puoi inoltre configurare il logging se lo desideri,
# ma la configurazione predefinita dovrebbe funzionare bene per la maggior parte degli utenti.
nano logging.yaml
```

## configurare un reverse proxy (useremo nginx)

bancho.py si basa su un reverse proxy per il supporto TLS (https) e per semplificare
la configurazione. Nginx è un server web open-source ed efficiente che utilizzeremo
in questa guida, ma sentiti libero di esplorare altre opzioni, come caddy e h2o.

```sh
# installa nginx
sudo apt install nginx

# installa la configurazione di nginx utilizzando i valori del tuo file .env
./scripts/install-nginx-config.sh
```

## congratulazioni! hai appena configurato un server privato osu!

Se tutto è andato bene, dovresti essere in grado di avviare il tuo server:

```sh
# costruisci l'applicazione
make build

# esegui l'applicazione
make run
```

Inoltre, sono disponibili i seguenti comandi per la tua introspezione:

```sh
# esegui l'applicazione in background
make run-bg

# visualizza i log di tutti i container in esecuzione
make logs

# esegui tutti i test automatici
make test

# esegui formattatori e linters
make lint

# esegui il controllo statico dei tipi
make type-check

# rimuovi tutte le dipendenze inutilizzate
make clean
```
