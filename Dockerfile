#syntax=docker/dockerfile:1
FROM python:3.8.2-slim

COPY . /pinbot
WORKDIR /pinbot
RUN python -m pip install pip --upgrade
RUN python -m pip install -r requirements.txt
ENTRYPOINT ["python", "main.py"]
