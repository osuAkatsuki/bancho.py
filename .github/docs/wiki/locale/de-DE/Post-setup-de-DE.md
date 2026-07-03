# Nach der Einrichtung

## HTTPS-Traffic aktivieren

### Cloudflare Full (strict) verwenden

Zuerst benötigst du ein Cloudflare-Konto. Gehe dafür zu <https://dash.cloudflare.com/sign-up>, gib deine E-Mail-Adresse und dein Passwort ein und klicke auf `create account`.

![Schritt 1](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_1.png)

Nun musst du deine Domain eingeben. Das muss deine tatsächliche Domain sein (z. B. `banchopy.com` oder `banchopy.net`) und darf keine host-spezifischen Namen enthalten (z. B. `www.banchopy.com` oder Ähnliches).

![Schritt 2](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_2.png)

Danach wählst du deinen Tarif aus. Für uns sollte der `Free plan` ausreichen; bei Bedarf kannst du später upgraden.

![Schritt 3](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_3.png)

Jetzt musst du die von Cloudflare geforderten Nameserver zu deinem Domain-Registrar übertragen. Wenn du das erledigt hast, klicke auf `check nameservers`.

![Schritt 4](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_4.png)

Nach den obigen Schritten musst du einige DNS-Einträge (A-Records) hinzufügen, damit die benötigten Domains auf die IP zeigen, auf der bancho.py läuft.

Die Einträge für den Import in Cloudflare kannst du mit dem Skript im Ordner `tools` erzeugen.

```sh
cd tools && ./generate_cf_dns_records.sh && cd..
```

Klicke anschließend im Cloudflare-Dashboard auf `Import and Export`.

![Schritt 5](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_5.png)

Wenn du kostenlose Freenom-Domains wie `.ml`, `.ga` oder `.cf` verwendest, kannst du die DNS-Einträge wahrscheinlich nicht importieren. Diese TLDs sind wegen häufiger Missbräuche in der Cloudflare-API eingeschränkt. In diesem Fall musst du die folgenden DNS-Einträge manuell hinzufügen:

<table>
    <tr>
        <th>
        <ul>
            <li>a.yourdomain.com</li>
            <li>api.yourdomain.com</li>
            <li>assets.yourdomain.com</li>
            <li>c.yourdomain.com</li>
            <li>c4.yourdomain.com</li>
            <li>ce.yourdomain.com</li>
            <li>yourdomain.com</li>
            <li>i.yourdomain.com</li>
            <li>osu.yourdomain.com</li>
            <li>s.yourdomain.com</li>
        </ul>
        <th>
            <img src="https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_6.png" alt="Schritt 6">
        </th>
    </tr>
</table>

Gehe danach zu `SSL/TLS > Overview` und aktiviere `Full (strict)`.

![Schritt 7](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_7.png)

Nun musst du von Cloudflare erzeugte Zertifikate erstellen. Gehe zu `SSL/TLS > Origin Server` und klicke auf `create certificate`.

![Schritt 8](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_8.png)

![Schritt 9](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_9.png)

Nach dem Erstellen musst du den Inhalt des Origin-Zertifikats und den privaten Schlüssel in getrennten Dateien auf deinem Client speichern.

![Schritt 10](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_10.png)

```sh
nano example.com.pem
# den Inhalt des Origin-Zertifikats einfügen

nano example.com.key
# den privaten Schlüssel einfügen
```

### Ein eigenes SSL-Zertifikat verwenden

```sh
# du musst Folgendes ändern:
# - YOUR_EMAIL_ADDRESS
# - YOUR_DOMAIN

# ein SSL-Zertifikat für deine Domain erzeugen
sudo certbot certonly \
    --manual \
    --preferred-challenges=dns \
    --email YOUR_EMAIL_ADDRESS \
    --server https://acme-v02.api.letsencrypt.org/directory \
    --agree-tos \
    -d *.YOUR_DOMAIN
```

## Cloudflare-Geolokalisierungsdaten aktivieren

Gehe im Cloudflare-Dashboard zu `Rules > Transform rules`, klicke anschließend auf managed transforms und aktiviere `add visitor location headers`.

![CF-Geolokalisierungsdaten aktivieren](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/cf_geoloc.png)

## Eine Website hinzufügen

bancho.py ist ein Backend — eine Website ist nicht enthalten. Passende Frontends:

- [bancho-web.ts](https://github.com/osuAkatsuki/bancho-web.ts) (empfohlen) — ein modernes
  React + TypeScript-Frontend auf Basis der v2-api von bancho.py, mit Ranglisten,
  Spielerprofilen, Beatmap-Seiten, Clans, Spielersuche sowie Registrierung und Anmeldung
  über die Website (mit optionaler Captcha-Unterstützung). Gepflegt vom bancho.py-Team.
- [guweb](https://github.com/varkaria/guweb) (Alternative) — das langjährige, von der
  Community gepflegte Python-Frontend, das direkt mit der Datenbank von bancho.py kommuniziert.
