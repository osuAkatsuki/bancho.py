# Leggere prima di configurare

## Prerequisiti

La conoscenza di Linux, Python e dei database sarà sicuramente utile, ma non è
assolutamente necessaria.

(Molte persone hanno installato questo server senza alcuna esperienza di programmazione!)

Se ti blocchi in qualsiasi punto del processo - abbiamo un server Discord pubblico sopra :)

Questa guida sarà orientata verso Ubuntu - altre distribuzioni potrebbero avere processi di configurazione leggermente diversi.

## Requisiti

**bancho.py** è una codebase di ~20.000 righe costruita sulle spalle di giganti.

Cerchiamo di minimizzare le nostre dipendenze, ma ci affidiamo comunque a strumenti come:

- Python (linguaggio di programmazione)
- Docker (runtime per container)
- Docker Compose plugin (orchestrazione dei container)
- MySQL (database relazionale, tramite Docker Compose)
- Redis (database in memoria, tramite Docker Compose)
- Nginx (proxy inverso HTTP(S))
- Certbot (strumento per certificati SSL)
- uv (project manager Python, facoltativo per lo sviluppo locale)

e alcuni altri.
