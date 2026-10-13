FROM python:3.12.13-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends osmium-tool=1.15.0-1 \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir pyproj==3.7.1
WORKDIR /workspace
