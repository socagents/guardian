"""Cognitive built-in MCP tools — Phase 8.

These are the tools the agent calls to manipulate its own memory and
read its own conversation history. They're "built-in" in the sense
that they don't come from any connector — the runtime serves them
directly. The manifest's `tools.allow` already lists them:

    - memory_search
    - memory_store
    - sessions_list
    - sessions_history
    - knowledge_search   ← Phase 10 will add this one

Implementation choice: thin wrappers around the singleton stores set
in `main.py`. The wrappers normalize the agent-facing arg shape (the
LLM's tool-use schema is just `{key: str, value: str}` — nothing
about scopes / TTL / pagination) and delegate to the typed stores.

# Why singleton lookup, not store-as-arg

The `_BUILTIN_LEGACY_TOOLS` registration in `connector_loader.py`
yields plain functions, no instance contextvar. Built-in tools also
don't currently take a per-instance config — they're agent-runtime
features, not connector-mediated. So they look up the active store
through the module's `singleton_accessor()` at call time. If the store
isn't wired (no DATA_ROOT, test harness), the call returns a clear
"runtime not initialized" error rather than crashing.
"""

from __future__ import annotations

import logging
from typing import Any


def _friendly_embed_error(exc: Exception, tool_label: str) -> str:
    """v0.1.26: turn a raw Vertex/embedding error into operator-actionable
    text. Pre-v0.1.26 the bare string was returned, which produced
    output like:

        search failed: vertex embed: 404 <!DOCTYPE html><html lang=en>...

    — accurate but useless to the operator. The 404 typically means
    one of three things, all on the operator's side; this surface
    can't fix any of them but should at least name them.
    """
    msg = str(exc)
    low = msg.lower()
    if "vertex embed" in low or "aiplatform" in low or "generativelanguage" in low:
        if "404" in msg:
            return (
                f"{tool_label} failed: Vertex AI embedding endpoint returned 404. "
                "Likely causes (in order of frequency): "
                "(1) embedding model name in your Vertex provider config "
                "doesn't exist in the configured region — try "
                "text-embedding-004 in us-central1; "
                "(2) wrong project_id in GOOGLE_APPLICATION_CREDENTIALS; "
                "(3) Vertex AI API not enabled for this project. "
                "Check /providers and the agent's GOOGLE_APPLICATION_CREDENTIALS."
            )
        if "401" in msg or "403" in msg or "permission" in low or "denied" in low:
            return (
                f"{tool_label} failed: Vertex AI credentials lack permission. "
                "The service account in GOOGLE_APPLICATION_CREDENTIALS needs "
                "the `aiplatform.user` role on the project."
            )
        if "429" in msg or "resource_exhausted" in low or "rate limit" in low:
            return (
                f"{tool_label} failed: Vertex AI quota exhausted. "
                "v0.1.25+ retries the chat path on 429 but embedding calls "
                "fail-fast — wait a minute and retry, or request quota."
            )
    # Fallback — preserve the original error so debug isn't lost.
    return f"{tool_label} failed: {msg}"

logger = logging.getLogger("Phantom MCP")


# ─────────────────────────────────────────────────────────────────
# Memory tools
# ─────────────────────────────────────────────────────────────────


def memory_store(
    key: str,
    value: str,
    scope: str = "agent",
    ttl_hours: int | None = None,
) -> dict[str, Any]:
    """Persist a key→value pair the agent can semantically recall later.

    Args:
        key: short label for the memory ("favorite-color", "ioc-host-x").
        value: the recallable content. Free-form text.
        scope: namespace. "agent" (default) is cross-session.
            "session:<id>" pins to a single conversation.
        ttl_hours: optional auto-expiry. Null = no TTL.

    Returns the persisted memory record (excluding the embedding vector).
    """
    from usecase.memory_store import memory_store as _store
    s = _store()
    if s is None:
        return {"error": "memory store not initialized on this MCP runtime"}
    ttl_seconds = int(ttl_hours * 3600) if ttl_hours else None
    try:
        m = s.store(key=key, value=value, scope=scope, ttl_seconds=ttl_seconds)
    except ValueError as exc:
        return {"error": str(exc)}
    return m.to_dict()


def memory_search(
    query: str,
    limit: int = 5,
    scope: str | None = None,
) -> dict[str, Any]:
    """Semantic search over the agent's memory.

    Args:
        query: free-form text. Embedded and matched by cosine similarity.
        limit: max results (1-100). Default 5.
        scope: restrict to a single scope (e.g. "agent" or
            "session:<id>"); when null, search all scopes.

    Returns a list of {key, value, score} dicts ordered by relevance.
    """
    from usecase.memory_store import memory_store as _store
    s = _store()
    if s is None:
        return {"error": "memory store not initialized on this MCP runtime"}
    try:
        hits = s.search(query, limit=limit, scope=scope)
    except Exception as exc:
        return {"error": _friendly_embed_error(exc, "memory_search")}
    return {
        "results": [m.to_dict(score=score) for m, score in hits],
        "count": len(hits),
    }


# ─────────────────────────────────────────────────────────────────
# Session tools
# ─────────────────────────────────────────────────────────────────


def sessions_list(
    user: str | None = None,
    limit: int = 20,
    active_only: bool = False,
) -> dict[str, Any]:
    """List the agent's recent sessions, newest first.

    Args:
        user: filter to one user. Null = all users (today there is
            only "operator", but multi-user is on the roadmap).
        limit: max sessions (1-500). Default 20.
        active_only: if true, return only sessions that haven't ended.

    Returns {sessions: [...], count}.
    """
    from usecase.session_store import session_store as _store
    s = _store()
    if s is None:
        return {"error": "session store not initialized on this MCP runtime"}
    sessions = s.list_sessions(user=user, limit=limit, active_only=active_only)
    return {
        "sessions": [sess.to_dict() for sess in sessions],
        "count": len(sessions),
    }


# ─────────────────────────────────────────────────────────────────
# Knowledge base tools (Phase 10)
# ─────────────────────────────────────────────────────────────────


def knowledge_search(
    query: str,
    kb_name: str | None = None,
    category: str | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Semantic search over the bundle's knowledge bases.

    Args:
        query: free-form text. Embedded and matched by cosine similarity.
        kb_name: restrict to a single KB (e.g. "phantom-soc"). When
            null, search every loaded KB.
        category: restrict to one schema category (e.g. "simulation").
        limit: max results (1-100). Default 5.

    Returns {results: [...], count}. Each result includes the doc's
    metadata, content, and the similarity score. KB content is
    READ-ONLY at the agent surface — there's intentionally no
    `knowledge_store` tool (manifest.kbWrites: []).
    """
    from usecase.kb_store import knowledge_base
    kb = knowledge_base()
    if kb is None:
        return {"error": "knowledge base not initialized on this MCP runtime"}
    try:
        hits = kb.search(query, kb_name=kb_name, category=category, limit=limit)
    except Exception as exc:
        return {"error": _friendly_embed_error(exc, "knowledge_search")}
    return {
        "results": [doc.to_dict(score=score) for doc, score in hits],
        "count": len(hits),
    }


def knowledge_list(kb_name: str, limit: int = 20) -> dict[str, Any]:
    """List documents in a knowledge base (no semantic search).

    Args:
        kb_name: the KB to list (e.g. "phantom-soc").
        limit: max docs (1-500). Default 20.

    Useful for the agent to discover what's available before
    deciding whether to search.
    """
    from usecase.kb_store import knowledge_base
    kb = knowledge_base()
    if kb is None:
        return {"error": "knowledge base not initialized on this MCP runtime"}
    docs = kb.list_docs(kb_name, limit=limit)
    return {
        "kb_name": kb_name,
        "documents": [d.to_dict(include_content=False) for d in docs],
        "count": len(docs),
    }


def sessions_history(
    session_id: str,
    limit: int | None = None,
    offset: int = 0,
    ascending: bool = True,
) -> dict[str, Any]:
    """Return ordered messages for a session.

    Args:
        session_id: the session uuid.
        limit: max messages. When omitted (or None / 0), returns every
               message in the session. Pre-v0.6.6 this defaulted to 100;
               that default truncated long transcripts silently.
               Compaction (`lib/compaction.ts`) is the legitimate
               context-window manager — this tool always returns the
               complete persisted history unless paginating explicitly.
        offset: pagination offset.
        ascending: oldest-first when true (default), newest-first when false.

    Returns {session_id, messages: [...], count}. The session must
    exist; non-existent ids return an error so the agent doesn't
    silently confuse "no messages" with "session not found".
    """
    from usecase.session_store import session_store as _store
    s = _store()
    if s is None:
        return {"error": "session store not initialized on this MCP runtime"}
    sess = s.get_session(session_id)
    if sess is None:
        return {"error": f"session {session_id!r} not found"}
    msgs = s.get_history(
        session_id, limit=limit, offset=offset, ascending=ascending
    )
    return {
        "session_id": session_id,
        "messages": [m.to_dict() for m in msgs],
        "count": len(msgs),
    }
