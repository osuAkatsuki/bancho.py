# Modifiche importanti

## 2023-09-25

Le variabili d'ambiente `SERVER_HOST` e `SERVER_PORT` sono state rinominate rispettivamente in `APP_HOST` e `APP_PORT`.

## 2023-09-21

La versione minima di Python richiesta è stata aggiornata alla 3.11.

## 2023-07-19

Il comportamento del pp complessivo e della precisione è stato modificato per includere tutti i punteggi di un utente anziché i primi 100, al fine di corrispondere al comportamento di Bancho. Questo implica la necessità di ricalcolare le statistiche degli utenti. bancho.py dispone di uno strumento di ricalcolo che può essere trovato in `tools/recalc.py` per facilitare questa operazione.

## 2023-04-09

La variabile d'ambiente `MIRROR_URL` è stata suddivisa in `MIRROR_SEARCH_ENDPOINT` e `MIRROR_DOWNLOAD_ENDPOINT`.

```diff
-MIRROR_URL=https://api.chimu.moe/v1

+# Chimu: https://api.chimu.moe/cheesegull/search - https://api.chimu.moe/v1/download
+# Kitsu: https://kitsu.moe/api/search - https://kitsu.moe/d
+MIRROR_SEARCH_ENDPOINT=https://catboy.best/api/search
+MIRROR_DOWNLOAD_ENDPOINT=https://catboy.best/d
```
