FROM ubuntu:bionic

# Update system
RUN apt update

# Add ppa for py3.9 (required since it's new)
RUN apt-get -y install software-properties-common && add-apt-repository ppa:deadsnakes/ppa
RUN DEBIAN_FRONTEND="noninteractive" apt-get -y install wget git python3.9 python3.9-dev python3.9-distutils build-essential

# Install pip for py3.9
RUN wget https://bootstrap.pypa.io/get-pip.py
RUN python3.9 get-pip.py && rm get-pip.py

# Copy over gulag
RUN mkdir /gulag
WORKDIR /gulag
COPY ./ ./

# Install dependencies
RUN pip install -r ext/requirements.txt
RUN cd oppai-ng && ./build && cd ..

# Temporary workaround
RUN touch /var/run/nginx.pid

EXPOSE 8080
CMD [ "python3.9", "./main.py" ]