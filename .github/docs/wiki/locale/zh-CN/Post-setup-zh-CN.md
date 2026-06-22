# 后续设置

## 启用 HTTPS 流量

### 使用 Cloudflare Full (strict)

首先你需要一个 Cloudflare 账号。前往 <https://dash.cloudflare.com/sign-up>，输入邮箱和密码，然后点击 `create account`。

![步骤 1](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_1.png)

接下来输入你的域名。这里必须填写实际域名（例如 `banchopy.com` 或 `banchopy.net`），不要包含特定主机名（例如 `www.banchopy.com` 或类似内容）。

![步骤 2](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_2.png)

然后选择套餐。对我们来说 `Free plan` 应该就够了，如果之后有需要也可以升级。

![步骤 3](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_3.png)

现在需要把 Cloudflare 要求的 nameserver 复制到你的域名注册商处。完成后点击 `check nameservers`。

![步骤 4](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_4.png)

完成以上步骤后，需要添加一些 DNS 记录（A 记录），让需要的域名指向运行 bancho.py 的服务器 IP。

你可以使用 `tools` 文件夹中的脚本生成可导入 Cloudflare 的记录。

```sh
cd tools && ./generate_cf_dns_records.sh && cd..
```

然后在 Cloudflare 控制台点击 `Import and Export`。

![步骤 5](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_5.png)

如果你使用 `.ml`、`.ga`、`.cf` 等免费 Freenom 域名，可能无法导入 DNS 记录。这是因为这些域名被大量滥用，Cloudflare API 对它们有限制。在这种情况下，你需要手动添加以下 DNS 记录：

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
            <img src="https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_6.png" alt="步骤 6">
        </th>
    </tr>
</table>

然后前往 `SSL/TLS > Overview`，启用 `Full (strict)`。

![步骤 7](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_7.png)

接下来需要创建由 Cloudflare 生成的证书。前往 `SSL/TLS > Origin Server`，点击 `create certificate`。

![步骤 8](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_8.png)

![步骤 9](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_9.png)

创建完成后，需要把源证书和私钥的内容分别保存到客户端的不同文件中。

![步骤 10](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/ssl_cf_10.png)

```sh
nano example.com.pem
# 粘贴源证书的内容

nano example.com.key
# 粘贴私钥的内容
```

### 使用自己的 SSL 证书

```sh
# 你需要修改：
# - YOUR_EMAIL_ADDRESS
# - YOUR_DOMAIN

# 为你的域名生成 SSL 证书
sudo certbot certonly \
    --manual \
    --preferred-challenges=dns \
    --email YOUR_EMAIL_ADDRESS \
    --server https://acme-v02.api.letsencrypt.org/directory \
    --agree-tos \
    -d *.YOUR_DOMAIN
```

## 启用 Cloudflare 地理位置数据

前往 Cloudflare 控制台，进入 `Rules > Transform rules`，然后点击 managed transforms，并启用 `add visitor location headers`。

![启用 CF 地理位置数据](https://github.com/osuAkatsuki/bancho.py/blob/master/.github/images/cf_geoloc.png)
