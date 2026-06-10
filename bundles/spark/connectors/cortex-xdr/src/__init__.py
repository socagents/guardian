"""Cortex XDR connector — v0.5.61 (issue #36).

Wraps the Cortex XDR Public API (/public_api/v1/...) for incident
listing + XQL query execution. Closes the agent-as-operator
detection-validation loop with the caldera connector: agent fires
Caldera adversary → queries this connector → reports detection
coverage.
"""
