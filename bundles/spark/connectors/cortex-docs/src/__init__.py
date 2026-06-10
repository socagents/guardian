"""cortex-docs connector — Palo Alto Networks Cortex public documentation
search + lookup, packaged as a Phantom tool connector.

Wraps four upstream scripts (preserved verbatim under `_search.py`,
`_fetch_topic.py`, `_xql_lookup.py`, `_research_planner.py`) with a
thin `connector.py` aggregator that exposes `cortex_*` tool functions
to the embedded MCP. The upstream scripts use `sys.exit(1)` on HTTP
errors (designed for CLI use); the wrappers catch `SystemExit` at the
boundary so a transient docs-API outage produces a structured error
return instead of taking down phantom-agent.
"""
