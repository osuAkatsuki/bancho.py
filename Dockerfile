FROM python:3.9-slim

# install dependencies for building oppai_ng
ENV DEBIAN_FRONTEND=noninteractive
RUN apt update && apt install -y cmake build-essential

COPY oppai_ng/ /oppai_ng/
WORKDIR oppai_ng/
RUN cmake . -DPYTHON_EXECUTABLE=/usr/local/bin/python -G "Unix Makefiles" && make

# install python dependencies
WORKDIR /
COPY requirements.txt ./
RUN pip install -r requirements.txt

# copy the source code in last, so that it doesn't
# repeat the previous steps for each change
COPY . .

ENTRYPOINT ["python3"]
CMD ["main.py"]
