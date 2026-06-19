# Standalone Splunk-mimic HTTPS server. NOT the connector-runtime base —
# this is a plain splunkd emulator, so it builds from python:3.12-slim and
# serves HTTPS on 8089 directly (self-signed cert generated at boot, or a
# mounted operator cert via SPLUNK_MIMIC_TLS_CERT/_KEY).
FROM python:3.12-slim

WORKDIR /app

# Build context is the REPO ROOT (CI builds every connector with context '.'
# so the Dockerfile path and the source paths are repo-relative — same as
# xsoar/xsiam). COPY paths are therefore repo-root-relative, NOT relative to
# this Dockerfile's directory.
COPY bundles/spark/connectors/splunk-mimic/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bundles/spark/connectors/splunk-mimic/src/ ./src/

# splunkd's default management port.
ENV SPLUNK_MIMIC_PORT=8089
EXPOSE 8089

# server.py generates a self-signed cert at boot (or uses a mounted cert)
# and serves HTTPS on :8089.
CMD ["python", "-m", "src.server"]
