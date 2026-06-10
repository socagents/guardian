"""Shared MCP runtime infrastructure.

v1.2 stage 3D: per-connector helpers that used to live here
(papi_client, xql_rag_service) have moved into each connector's
`src/_*.py` so connectors are self-contained. Only truly
cross-connector infra (logging) stays.
"""

from .setup_logging import setup_logging

__all__ = ["setup_logging"]
