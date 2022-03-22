FROM python:3.9-slim-buster

WORKDIR /bancho.py
COPY . /bancho.py

RUN pip install -r requirements.txt
CMD ["python", "main.py"]
