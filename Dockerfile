FROM python:3.9-slim

# install apps dependencies
RUN apt update && apt install -y \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

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
