FROM python:3.9-slim

# install apps dependencies
RUN apt update && apt install -y \
    git \
    curl \
    build-essential

# install rust
ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:$PATH \
    RUST_VERSION=stable
RUN set -eux; \
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs -o rustup-init; \
    chmod +x rustup-init; \
    ./rustup-init -y --no-modify-path --profile minimal --default-toolchain $RUST_VERSION; \
    rm rustup-init; \
    chmod -R a+w $RUSTUP_HOME $CARGO_HOME;

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
CMD ["make run-prod"]
