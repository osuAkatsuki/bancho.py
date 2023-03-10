#!/usr/bin/env bash
set -euo pipefail

# ensure admin privileges
if (( $EUID != 0 )); then
    printf "This script must be run with administrative privileges."
    exit
fi

root_dir=$(pwd)
nginx_version=$(nginx -v 2>&1 | awk -F' ' '{print $3}' | grep -o '[0-9.]*$')

# download the nginx source and the geoip2 module in a temp folder
mkdir "temp" && cd "temp"
wget http://nginx.org/download/nginx-$nginx_version.tar.gz
tar zxvf nginx-$nginx_version.tar.gz
wget -O ngx_http_geoip2_module.tar.gz https://github.com/leev/ngx_http_geoip2_module/archive/master.tar.gz
tar zxvf ngx_http_geoip2_module.tar.gz

# install essentials apps to compile software and add ppas
apt update && apt install -y \
    software-properties-common \
    build-essential

# install maxmind's ppa and the libraries required to build nginx
add-apt-repository ppa:maxmind/ppa -y
apt install -y \
    libmaxminddb0 \
    libmaxminddb-dev \
    mmdb-bin \
    geoipupdate \
    libpcre3 \
    libpcre3-dev \
    zlib1g \
    zlib1g-dev \
    libssl-dev

# build nginx with the geoip2 module
cd nginx-$nginx_version
./configure  --add-dynamic-module=../ngx_http_geoip2_module-master $(nginx -V) --with-compat
make

# install the new dynamic module in nginx
mkdir -p /etc/nginx/modules-available /etc/nginx/modules-enabled
cp objs/ngx_http_geoip2_module.so /usr/lib/nginx/modules
echo "load_module modules/ngx_http_geoip2_module.so;" > /etc/nginx/modules-available/mod-http-geoip2.conf
rm -f /etc/nginx/modules-enabled/60-mod-http-geoip2.conf
ln -s /etc/nginx/modules-available/mod-http-geoip2.conf /etc/nginx/modules-enabled/60-mod-http-geoip2.conf

cd "$root_dir" && rm -r temp

printf "The GeoIP2 module has been installed and enabled."
