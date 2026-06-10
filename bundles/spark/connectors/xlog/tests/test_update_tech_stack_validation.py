"""Pydantic validation tests for the `phantom_update_technology_stack`
tool's input model.

The model is the schema gate the agent's model sees — its descriptions
become the tool's parameter docs, and its constraints (min_length on
vendors / formats, required fields) reject malformed payloads BEFORE
they ever hit the GraphQL mutation.

These tests don't spin up xlog or hit the network — they exercise only
the `UpdateTechnologyStackRequest` Pydantic model. Roundtrip behavior
(model → GraphQL → store → read) is covered by xlog/tests/.
"""

from __future__ import annotations

import sys
import types as _types
from pathlib import Path

import pytest

# `observables_catalog` imports `config.config import get_config` at
# module load. Stub the module so tests stay hermetic — we don't need
# real config to exercise the Pydantic schema.
if "config.config" not in sys.modules:
    config_pkg = _types.ModuleType("config")
    config_mod = _types.ModuleType("config.config")

    class _Cfg:
        technology_stack = None
        xlog_url = "http://localhost:8000"

    config_mod.get_config = lambda: _Cfg()  # type: ignore[attr-defined]
    config_pkg.config = config_mod  # type: ignore[attr-defined]
    sys.modules["config"] = config_pkg
    sys.modules["config.config"] = config_mod

# Add the connector's parent dir to sys.path so we can import the
# module as `src.observables_catalog` — that way the relative
# `from ._graphql_client import …` inside it resolves correctly.
_CONNECTOR_ROOT = Path(__file__).resolve().parent.parent
if str(_CONNECTOR_ROOT) not in sys.path:
    sys.path.insert(0, str(_CONNECTOR_ROOT))

from src.observables_catalog import UpdateTechnologyStackRequest  # noqa: E402


# ─── Happy path ──────────────────────────────────────────────────────


def test_minimal_valid_payload():
    """Bare minimum: stack_name + one vendor with all required fields."""
    req = UpdateTechnologyStackRequest(
        stack_name="My Stack",
        vendors=[
            {
                "vendor": "Fortinet",
                "product": "FortiGate",
                "category": "Firewall",
                "formats": ["CEF"],
            }
        ],
    )
    assert req.stack_name == "My Stack"
    assert len(req.vendors) == 1
    assert req.vendors[0].formats == ["CEF"]
    assert req.log_destination is None


def test_full_payload_with_destination():
    """Operator provides everything including a syslog destination."""
    req = UpdateTechnologyStackRequest(
        stack_name="Acme SOC",
        log_destination={
            "type": "syslog",
            "protocol": "udp",
            "host": "10.10.0.8",
            "port": 514,
            "full_address": "udp:10.10.0.8:514",
        },
        vendors=[
            {
                "vendor": "CrowdStrike",
                "product": "Falcon",
                "category": "EDR",
                "formats": ["JSON"],
                "description": "Endpoint Detection",
            }
        ],
    )
    assert req.log_destination is not None
    assert req.log_destination.full_address == "udp:10.10.0.8:514"
    assert req.vendors[0].description == "Endpoint Detection"


# ─── Rejection paths ─────────────────────────────────────────────────


def test_empty_stack_name_rejected():
    """min_length=1 on stack_name guards against the LLM passing ''."""
    with pytest.raises(Exception) as excinfo:
        UpdateTechnologyStackRequest(stack_name="", vendors=[
            {
                "vendor": "V",
                "product": "P",
                "category": "C",
                "formats": ["JSON"],
            }
        ])
    assert "stack_name" in str(excinfo.value).lower() or "min_length" in str(excinfo.value).lower()


def test_empty_vendors_rejected():
    """At least one vendor entry is required — empty stacks are
    pointless and likely a model hallucination."""
    with pytest.raises(Exception):
        UpdateTechnologyStackRequest(stack_name="Empty", vendors=[])


def test_vendor_missing_required_field_rejected():
    """Each vendor needs vendor/product/category/formats. Missing any
    of these should fail validation."""
    with pytest.raises(Exception):
        UpdateTechnologyStackRequest(
            stack_name="X",
            vendors=[
                {
                    "vendor": "V",
                    "product": "P",
                    # category missing
                    "formats": ["JSON"],
                }
            ],
        )


def test_vendor_empty_formats_rejected():
    """The format list MUST have at least one entry — without one the
    log generator can't pick a wire format."""
    with pytest.raises(Exception) as excinfo:
        UpdateTechnologyStackRequest(
            stack_name="X",
            vendors=[
                {
                    "vendor": "V",
                    "product": "P",
                    "category": "C",
                    "formats": [],
                }
            ],
        )
    assert "formats" in str(excinfo.value).lower()


def test_log_destination_partial_ok():
    """log_destination doesn't strictly require every field — only
    `type` is required. The mutation will derive `full_address` if
    not provided. Extra leniency here vs vendors because some sinks
    (e.g. type='file') legitimately don't have host/port."""
    req = UpdateTechnologyStackRequest(
        stack_name="X",
        log_destination={"type": "file"},
        vendors=[
            {
                "vendor": "V",
                "product": "P",
                "category": "C",
                "formats": ["JSON"],
            }
        ],
    )
    assert req.log_destination is not None
    assert req.log_destination.type == "file"
    assert req.log_destination.host is None
