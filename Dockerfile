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

# Create gulag user, chown the workdir and switch to it
RUN addgroup --system --gid 1000 gulag && adduser --system --uid 1000 --gid 1000 gulag
RUN chown -R gulag:gulag /gulag
USER gulag

# Expose port and set entrypoint
EXPOSE 8080
CMD [ "python3.9", "./main.py" ]

# Copy and build oppai-ng
COPY --chown=gulag:gulag ./oppai-ng ./oppai-ng
RUN cd oppai-ng && chmod +x ./build && ./build && cd ..

# Copy over the rest of gulag
COPY --chown=gulag:gulag ./ ./