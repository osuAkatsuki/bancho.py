# После установки

## включение https-трафика

### через cloudflare full (strict)

прежде всего вам понадобится аккаунт cloudflare. чтобы создать его, перейдите на <https://dash.cloudflare.com/sign-up>, введите email и пароль и нажмите `create account`

![Шаг 1](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_1.png)

теперь нужно ввести ваш домен. это должен быть именно корневой домен (например, `banchopy.com` или `banchopy.net`), без хостнеймов (например, `www.banchopy.com` и подобных)

![Шаг 2](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_2.png)

затем выберите тариф. нам будет достаточно `Free plan`; при необходимости его можно повысить позже

![Шаг 3](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_3.png)

теперь скопируйте nameserver'ы, которые требует cloudflare, к вашему регистратору домена. когда закончите, нажмите `check nameservers`

![Шаг 4](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_4.png)

после этого нужно добавить dns-записи (A-записи), чтобы необходимые домены указывали на ip, где работает bancho.py.

записи для импорта в cloudflare можно сгенерировать скриптом из папки `tools`

```sh
cd tools && ./generate_cf_dns_records.sh && cd..
```

а в панели cloudflare нажмите Import and Export

![Шаг 5](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_5.png)

если вы используете бесплатные домены freenom вроде `.ml`, `.ga`, `.ml`, `.cf`, импорт dns, скорее всего, не сработает: из-за массовых злоупотреблений они ограничены в API Cloudflare. в этом случае добавьте следующие dns-записи вручную

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
            <img src="https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_6.png" alt="Шаг 6">
        </th>
    </tr>
</table>

затем перейдите в SSL/TLS > overview и включите Full (strict)

![Шаг 7](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_7.png)

теперь создайте сертификаты, выпускаемые cloudflare: SSL/TLS > Origin Server, нажмите `create certificate`

![Шаг 8](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_8.png)

![Шаг 9](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_9.png)

после создания сохраните содержимое origin-сертификата и приватного ключа в отдельные файлы на вашей машине

![Шаг 10](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_10.png)

```sh
nano example.com.pem
# вставьте содержимое origin-сертификата

nano example.com.key
# вставьте содержимое приватного ключа
```

### используя собственный ssl-сертификат

```sh
# вам нужно заменить:
# - YOUR_EMAIL_ADDRESS
# - YOUR_DOMAIN

# сгенерируйте ssl-сертификат для вашего домена
sudo certbot certonly \
    --manual \
    --preferred-challenges=dns \
    --email YOUR_EMAIL_ADDRESS \
    --server https://acme-v02.api.letsencrypt.org/directory \
    --agree-tos \
    -d *.YOUR_DOMAIN
```

## включение геолокации cloudflare

перейдите в панель cloudflare: Rules > Transform rules, затем нажмите managed transforms и включите `add visitor location headers`.

![Включение геолокации CF](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/cf_geoloc.png)

## Добавление сайта

bancho.py — это только бэкенд, сайт в него не входит. Варианты фронтенда:

- [bancho-web.ts](https://github.com/osuAkatsuki/bancho-web.ts) (рекомендуется) —
  современный фронтенд на React + TypeScript, построенный на v2 api bancho.py:
  таблицы лидеров, профили игроков, страницы карт, кланы, поиск игроков, а также
  регистрация и вход через сайт (с опциональной поддержкой капчи).
  Поддерживается командой bancho.py.
- [guweb](https://github.com/varkaria/guweb) (альтернатива) — давний фронтенд
  на python, поддерживаемый сообществом; работает напрямую с базой данных bancho.py.
