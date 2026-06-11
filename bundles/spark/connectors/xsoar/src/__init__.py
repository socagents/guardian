"""Cortex XSOAR connector — incident-investigation surface.

Wraps the Cortex XSOAR REST API for the Guardian incident-response
agent: list and drill into cases (incidents), read the war room,
document findings (entries + notes), update + close cases, and pull
supporting context (indicators, evidence, incident fields).

Dual-generation: XSOAR 6 (on-prem — single API key in the
Authorization header, base https://<server>) and XSOAR 8 / Cortex
cloud (API key + key id via the x-xdr-auth-id header, base
https://api-<fqdn> with a /xsoar/public/v1 path prefix). Detection is
config-driven: when api_id is set the client treats the instance as
v8; otherwise v6. Logical paths and request bodies are identical
across both generations — only the base URL and headers differ.
"""
