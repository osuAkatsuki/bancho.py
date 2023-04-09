FROM python:3.9-slim

# install apps dependencies
RUN apt update && apt install -y \
    git \
    curl \
    build-essential=12.9 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home bpyuser
WORKDIR /home/bpyuser
USER bpyuser

ENV PATH "${PATH}:/home/bpyuser/.local/bin/"

# install python dependencies
COPY Makefile Pipfile Pipfile.lock ./
RUN python3.9 -m pip install -U pip==23.0.1 setuptools==67.6.0 pipenv==2023.2.18
RUN make install

# copy the source code in last, so that it doesn't
# repeat the previous steps for each change
COPY . .

# start bancho.py
ENTRYPOINT [ "/bin/bash", "-c" ]
CMD ["make run-prod"]
