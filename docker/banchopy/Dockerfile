FROM python:3.11-slim

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
RUN python3.11 -m pip install -U pip==23.2.1 setuptools==68.2.0 pipenv==2023.9.8
RUN make install

# create data directory
RUN mkdir /home/bpyuser/.data

# copy the source code in last, so that it doesn't
# repeat the previous steps for each change
COPY . .

# start bancho.py
ENTRYPOINT [ "/bin/bash", "-c" ]
CMD ["make run"]
