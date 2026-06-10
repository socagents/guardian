#!/usr/bin/env python3
"""Build the JSON body for the CI bootstrap step's POST /api/v1/setup.

Runs on the CI host (not inside the agent container). Supplies
placeholder values for XSIAM + Vertex (instance materializes; runtime
calls would fail against the placeholder URL — that's intentional, the
smoke test asserts on tool advertisement, not on every tool actually
completing).

Usage:
    python3 scripts/ci_bootstrap_setup_body.py > /tmp/setup-body.json

Lives as a separate file (not inline in the workflow) because YAML's
mandatory leading-space indentation breaks heredoc'd Python: top-
level statements with indent raise IndentationError. Putting the
body builder in a real file sidesteps that.
"""

from __future__ import annotations

import json
import sys


def main() -> int:
    body = {
        "values": {
            # XSIAM is external; CI doesn't have a tenant, so placeholder
            # values let the connector instance MATERIALIZE (tools
            # advertise) but runtime calls would 404. That's fine for
            # the smoke test's tool-advertisement assertions.
            "xsiamPapiUrl":           "https://ci-placeholder.xsiam.invalid/api",
            "xsiamPapiAuthId":        "ci-placeholder",
            "xsiamPapiAuthHeader":    "ci-placeholder",
            "xsiamPlaygroundId":      "ci-placeholder",
            "xsiamWebhookEndpoint":   "https://ci-placeholder.xsiam.invalid/webhook",
            "xsiamWebhookKey":        "ci-placeholder",
            # Vertex provider — same placeholder strategy. The
            # serviceAccountJson must parse as valid JSON for the
            # provider __init__ to accept it; minimal stub passes that.
            "vertexProjectId": "ci-placeholder",
            "vertexRegion":    "us-central1",
            "vertexServiceAccountJson":
                '{"type":"service_account","project_id":"ci-placeholder"}',
            # Operator UI: gated behind a password. CI doesn't actually
            # log in via the browser; setting it here just prevents the
            # setup endpoint from rejecting the body for missing fields.
            "uiPassword": "ci-placeholder-not-a-real-password",
        },
        # NON-DESTRUCTIVE bootstrap: replace=False means "only create
        # instances that don't yet exist; leave operator-supplied
        # real values alone". Critical because the same persistent
        # runner state can hold values an operator filled in via the
        # setup form. Earlier replace=True silently overwrote real
        # creds with these placeholders — surfaced as the OpenSSL
        # DECODER error when chat tried to use the placeholder
        # vertex SA JSON.
        "replace": False,
    }
    json.dump(body, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
