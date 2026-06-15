"""Issue #42 — connector container-name parsing must round-trip hyphenated
connector ids (cortex-docs).

The old ``rest.partition("-")`` split on the FIRST hyphen, so a
``guardian-connector-cortex-docs-<inst>`` container parsed to connector_id
``cortex`` → failed the KNOWN_CONNECTORS check → was silently dropped from
both the digests listing and digest-drift reconcile. The longest-known-prefix
parser fixes that.
"""

import os

os.environ.setdefault("MCP_TOKEN", "test-mcp-token")

from src import main as updater_main  # noqa: E402

_split = updater_main._split_connector_container_name


def test_single_word_connector_id():
    assert _split("guardian-connector-web-Web_Browser") == ("web", "Web_Browser")


def test_instance_name_with_hyphens():
    # xsoar instance "primary-xsoar" → container ...-xsoar-primary-xsoar
    assert _split("guardian-connector-xsoar-primary-xsoar") == (
        "xsoar",
        "primary-xsoar",
    )


def test_hyphenated_connector_id_round_trips():
    # The core regression: cortex-docs must NOT parse to "cortex".
    assert _split("guardian-connector-cortex-docs-Cortex_Docs") == (
        "cortex-docs",
        "Cortex_Docs",
    )


def test_xsiam_connector_id():
    assert _split("guardian-connector-xsiam-primary") == ("xsiam", "primary")


def test_non_connector_name_returns_none():
    assert _split("guardian_agent") is None
    assert _split("some-other-container") is None


def test_unknown_connector_id_returns_none():
    assert _split("guardian-connector-bogus-instance") is None


def test_missing_instance_name_returns_none():
    # Prefix present but no instance segment.
    assert _split("guardian-connector-web-") is None
    assert _split("guardian-connector-web") is None
