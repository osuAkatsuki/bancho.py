FROM python:3.9-alpine

# install apps dependencies
RUN apk add --no-cache \
    git \
    bash \
    curl \
    gcompat \
    gnupg \
    build-base \
    libffi-dev \
    linux-headers

# install rust
RUN curl https://sh.rustup.rs -sSf | bash -s -- -y
ENV PATH /root/.cargo/bin:$PATH

# install python dependencies
WORKDIR /prod
COPY Makefile Pipfile Pipfile.lock ./
RUN python3.9 -m pip install -U pip setuptools pipenv
RUN make install

# copy the source code in last, so that it doesn't
# repeat the previous steps for each change
COPY . .

# start bancho.py
ENTRYPOINT [ "/bin/bash", "-c" ]
CMD ["./scripts/start_server.sh"]
