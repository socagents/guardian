"""Cohere North provider — minimal class wrapper for the embedded MCP runtime.

Per spark-agents spec v1.2 §7.6 the runtime imports this module's `Provider`
class, instantiates it once per configured provider instance, and uses it to:

  - `list_models()` → enumerate the model catalog (returns [] → the runtime
    uses the static spec.models[] from provider.yaml; Cohere North has no
    model-discovery endpoint).
  - `chat(model_id, messages, **kwargs)` → NOT used here. Guardian's chat
    dispatch to Cohere North happens in the Next.js agent layer (the
    CohereProvider adapter in mcp/agent/lib/llm/cohere-provider.ts), which
    translates the Gemini-shaped request to Cohere's /api/v1/chat + polls the
    conversation. This class is a contract holder + config validator.
  - `embed(model_id, text)` → NOT supported. Cohere North exposes no embedding
    model; embeddings stay on Vertex (text-embedding-004).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("Guardian MCP")


class Provider:
    """Cohere North provider — operates against one configured instance."""

    def __init__(self, config: dict[str, Any], secrets: dict[str, Any]) -> None:
        self._endpoint_url = (config.get("endpoint_url") or "").rstrip("/")
        self._agent_id = config.get("agent_id")
        self._tls_verify = config.get("tls_verify", True)
        self._ca_pem = config.get("ca_pem")
        self._conversation_mode = config.get("conversation_mode", "stateless")
        self._bearer_token = secrets.get("bearer_token")
        if not self._endpoint_url:
            raise ValueError("cohere-north provider: config.endpoint_url is required")
        if not self._agent_id:
            raise ValueError("cohere-north provider: config.agent_id is required")
        if not self._bearer_token:
            raise ValueError("cohere-north provider: secrets.bearer_token is required")

    def list_models(self) -> list[dict[str, Any]]:
        """Empty → runtime falls back to the static spec.models[] in provider.yaml."""
        return []

    def chat(self, model_id: str, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError(
            "cohere-north chat dispatch happens in the Next.js CohereProvider adapter, "
            "not in the Python provider class."
        )

    def embed(self, model_id: str, text: str) -> list[float]:
        raise NotImplementedError(
            "cohere-north exposes no embedding model; embeddings stay on Vertex "
            "(text-embedding-004)."
        )
