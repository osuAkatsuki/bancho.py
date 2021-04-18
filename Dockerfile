FROM python:3.9-buster

# Update and install essentials
RUN apt update && apt install -y build-essential

# Install dependencies
COPY ./ext/requirements.txt requirements.txt
RUN pip install -r requirements.txt

# Temporary workaround
RUN touch /var/run/nginx.pid

# Create and switch to the workdir
RUN mkdir /gulag
WORKDIR /gulag

# Copy and build oppai-ng
COPY ./oppai-ng ./oppai-ng
RUN cd oppai-ng && chmod +x ./build && ./build && cd ..

# Expose port and set entrypoint
EXPOSE 8080
CMD [ "python3.9", "./main.py" ]

# Creat gulag user, chown the workdir and switch to it
RUN addgroup --system --gid 1000 gulag && adduser --system --uid 1000 --gid 1000 gulag
RUN chown -R gulag:gulag /gulag
USER gulag

# Copy over the rest of gulag
COPY ./ ./