# Standalone Splunk-mimic HTTPS server. NOT the connector-runtime base —
# this is a plain splunkd emulator, so it builds from python:3.12-slim and
# serves HTTPS on 8089 directly (self-signed cert generated at boot, or a
# mounted operator cert via SPLUNK_MIMIC_TLS_CERT/_KEY).
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

# splunkd's default management port.
ENV SPLUNK_MIMIC_PORT=8089
EXPOSE 8089

# server.py generates a self-signed cert at boot (or uses a mounted cert)
# and serves HTTPS on :8089.
CMD ["python", "-m", "src.server"]
