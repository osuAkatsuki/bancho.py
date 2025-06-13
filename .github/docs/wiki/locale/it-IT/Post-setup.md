# Configurazione post-installazione

## Abilitare il traffico HTTPS

### Utilizzo di Cloudflare Full (Strict)

Per prima cosa, è necessario un account Cloudflare. Per crearne uno, vai su <https://dash.cloudflare.com/sign-up>, inserisci la tua email e password e clicca su `crea account`.

![Passaggio 1](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_1.png)

Ora devi inserire il tuo dominio. Questo deve essere il tuo dominio effettivo (ad esempio, `banchopy.com` o `banchopy.net`) e non deve includere alcun hostname specifico del dominio (ad esempio, `www.banchopy.com` o simili).

![Passaggio 2](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_2.png)

Successivamente, devi scegliere il tuo piano. Per noi dovrebbe essere sufficiente il `Piano gratuito`, ma puoi effettuare un upgrade in seguito se necessario.

![Passaggio 3](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_3.png)

Ora dovrai copiare i nameserver richiesti da Cloudflare nel tuo registrar di domini. Una volta fatto, clicca su `verifica nameserver`.

![Passaggio 4](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_4.png)

Una volta completati i passaggi precedenti, dovrai aggiungere alcuni record DNS (record A) affinché i domini necessari puntino all'IP su cui bancho.py è in esecuzione.

Puoi generare i record da importare in Cloudflare utilizzando lo script nella cartella `tools`.

```sh
cd tools && ./generate_cf_dns_records.sh && cd..
```

Nel dashboard di Cloudflare, clicca su Importa ed Esporta.

![Passaggio 5](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_5.png)

Se utilizzi domini gratuiti Freenom come `.ml`, `.ga`, `.ml`, `.cf`, probabilmente non puoi importare i DNS. Questo perché sono limitati nell'API di Cloudflare a causa di abusi significativi. In tal caso, dovrai aggiungere manualmente i seguenti record DNS:

<table>
    <tr>
        <th>
        <ul>
            <li>a.tuodominio.com</li>
            <li>api.tuodominio.com</li>
            <li>assets.tuodominio.com</li>
            <li>c.tuodominio.com</li>
            <li>c4.tuodominio.com</li>
            <li>ce.tuodominio.com</li>
            <li>tuodominio.com</li>
            <li>i.tuodominio.com</li>
            <li>osu.tuodominio.com</li>
            <li>s.tuodominio.com</li>
        </ul>
        <th>
            <img src="https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_6.png" alt="Passaggio 6">
        </th>
    </tr>
</table>

Poi vai su SSL/TLS > Panoramica e attiva Full (Strict).

![Passaggio 7](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_7.png)

Ora dovrai creare certificati generati da Cloudflare. Vai su SSL>TLS > Origin Server e clicca su `crea certificato`.

![Passaggio 8](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_8.png)

![Passaggio 9](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_9.png)

Dopo averlo creato, dovrai salvare il contenuto del certificato di origine e della chiave privata in file separati sul tuo client.

![Passaggio 10](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_10.png)

```sh
nano example.com.pem
# incolla il contenuto del certificato di origine

nano example.com.key
# incolla il contenuto della chiave privata
```

### Utilizzo di un certificato SSL personale

```sh
# Dovrai modificare:
# - IL_TUO_INDIRIZZO_EMAIL
# - IL_TUO_DOMINIO

# Genera un certificato SSL per il tuo dominio
sudo certbot certonly \
    --manual \
    --preferred-challenges=dns \
    --email IL_TUO_INDIRIZZO_EMAIL \
    --server https://acme-v02.api.letsencrypt.org/directory \
    --agree-tos \
    -d *.IL_TUO_DOMINIO
```

## Abilitare i dati di geolocalizzazione di Cloudflare

Devi andare sul dashboard di Cloudflare e accedere a Regole > Regole di trasformazione. Dopo di che, clicca su trasformazioni gestite e attiva `aggiungi intestazioni di posizione del visitatore`.

![Abilitare i dati di geolocalizzazione CF](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/cf_geoloc.png)
