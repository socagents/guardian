"""Web connector — aggregator module.

Re-exports the public tool functions under one namespace so the
embedded MCP and `connector.yaml.source.entrypoint` can both point at a
single import target. One module per connector exposing the standard
concern, this file pulls them together) — for v0.1 the surface is
small enough to live in a single `browser.py`, but the aggregator
shape is preserved so future modules (e.g. a `pdf.py` for inline PDF
fetch+extract, or `harvester.py` for multi-link batch retrieval) can
slot in without touching the manifest.

Tool names in `connector.yaml.spec.tools[].name` are bare verbs
(`navigate`, `get_text`, ...). The `runtimeMapping.functionPrefix` is
`guardian_web_` so the actual callables are
`guardian_web_navigate`, `guardian_web_get_text`, ... — the
`guardian_` prefix makes audit-row tool names self-identifying even
when the namespace is stripped.
"""

from .browser import (
    guardian_web_click,
    guardian_web_close_session,
    guardian_web_extract_links,
    guardian_web_fill,
    guardian_web_get_html,
    guardian_web_get_text,
    guardian_web_list_sessions,
    guardian_web_navigate,
    guardian_web_screenshot,
    guardian_web_wait_for,
)

__all__ = [
    "guardian_web_navigate",
    "guardian_web_get_text",
    "guardian_web_get_html",
    "guardian_web_screenshot",
    "guardian_web_click",
    "guardian_web_fill",
    "guardian_web_wait_for",
    "guardian_web_extract_links",
    "guardian_web_close_session",
    "guardian_web_list_sessions",
]
