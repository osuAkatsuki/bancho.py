FROM python:3.9-buster

# Update and install essentials
RUN apt update && apt install -y build-essential

# Install dependencies
COPY ./ext/requirements.txt requirements.txt
RUN pip install -r requirements.txt

# Create directory for gulag
RUN mkdir /gulag
WORKDIR /gulag

# Copy and build oppai-ng
COPY ./oppai-ng ./oppai-ng
RUN cd oppai-ng && ./build && cd ..

# Copy over the rest of gulag
COPY ./ ./

# Temporary workaround
RUN touch /var/run/nginx.pid

# Create user for gulag and chown
RUN addgroup --system --gid 1000 gulag && adduser --system --uid 1000 --gid 1000 gulag
RUN chown -R gulag:gulag /gulag

EXPOSE 8080
CMD [ "python3.9", "./main.py" ]