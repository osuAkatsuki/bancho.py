FROM python:3.9-alpine

WORKDIR /usr/src/app

# install linux requirements
RUN apk update && \
    apk add \
    gcc libffi-dev musl-dev \
    rust cargo

# install python requirements
COPY requirements.txt ./
RUN pip install -U pip setuptools && \
    pip install --no-cache-dir -r requirements.txt

# export port for http
EXPOSE 80/tcp

# copy gulag dir
COPY . .

# set our entry point - starting gulag
CMD ["/usr/src/app/scripts/start_server.sh"]
