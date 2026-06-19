"""Schema guard for the emulated-service marketplace kind (Refs #56).

v0.2.42 adds a `kind` discriminator to connector.yaml — `"connector"`
(the implicit default) vs `"service"` (an emulated service like the
Splunk mimic). Services advertise zero agent tools and instead publish
a host port that external systems (XSOAR) reach. The schema change:

  * `kind` is an optional enum {connector, service}, default connector.
  * `service.ports[]` carries the published-port spec for services.
  * `spec.tools` minItems relaxes 1 → 0 (services have none); the
    "connector needs ≥1 tool" rule moves into validate_connector_spec
    so it stays enforced for connectors but not for services.

`validate_connector_spec` raises ConnectorSpecError on the first
problem and returns None on success — these tests assert against that
contract (NOT a (ok, errs) tuple).
"""

from __future__ import annotations

import pytest

from usecase.connector_schema import ConnectorSpecError, validate_connector_spec

# A minimal spec that satisfies every required root field of
# connector.schema.json. secretSlots is required (empty list is valid).
BASE = {
    "id": "splunk-mimic",
    "version": "0.0.1",
    "description": "d",
    "source": {"language": "python", "entrypoint": "src.server"},
    "runtimeMapping": {"style": "container"},
    "configSchema": {"type": "object", "properties": {}},
    "secretSlots": [],
    "spec": {"tools": []},
}


def test_kind_defaults_to_connector_when_absent():
    # No `kind` key + at least one tool → a valid connector.
    spec = {**BASE, "spec": {"tools": [{"name": "t", "description": "d"}]}}
    validate_connector_spec(spec)  # must not raise


def test_service_kind_allows_empty_tools_and_ports():
    spec = {
        **BASE,
        "kind": "service",
        "service": {
            "ports": [
                {"container_port": 8089, "host_port": 8089, "protocol": "tcp"}
            ]
        },
    }
    validate_connector_spec(spec)  # must not raise


def test_invalid_kind_rejected():
    spec = {
        **BASE,
        "kind": "bogus",
        "spec": {"tools": [{"name": "t", "description": "d"}]},
    }
    with pytest.raises(ConnectorSpecError):
        validate_connector_spec(spec)


def test_connector_kind_requires_at_least_one_tool():
    # Default kind (connector) with zero tools must still be rejected
    # even after spec.tools minItems relaxes to 0.
    spec = {**BASE, "spec": {"tools": []}}
    with pytest.raises(ConnectorSpecError):
        validate_connector_spec(spec)


def test_service_kind_requires_ports():
    # A service with no published ports is meaningless — reject it.
    spec = {**BASE, "kind": "service"}
    with pytest.raises(ConnectorSpecError):
        validate_connector_spec(spec)
