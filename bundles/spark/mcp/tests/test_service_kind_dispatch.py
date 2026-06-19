"""v0.2.42 (Refs #56) — emulated-service catalogue + zero-tool dispatch.

Two guarantees for the `kind: service` marketplace kind:

(a) `_connector_summary` surfaces `kind` (default "connector"); a
    service reports `kind:"service"` and `tools_count` 0.
(b) `iter_registrations` skips `kind:service` entirely — even a
    configured + ENABLED service connector advertises NO agent tools,
    preserving the credential/catalog boundary (the agent never gets a
    handle to a service; external systems reach it over a host port).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from api.marketplace import _connector_summary
from usecase import connector_loader
from usecase.instance_store import InstanceStore

CONNECTOR_SPEC = {
    "id": "demo",
    "version": "0.0.1",
    "description": "d",
    "source": {"language": "python", "entrypoint": "src.connector"},
    "runtimeMapping": {"style": "container"},
    "configSchema": {"type": "object", "properties": {}},
    "secretSlots": [],
    "spec": {"tools": [{"name": "t", "description": "d"}]},
}

SERVICE_SPEC = {
    "id": "svc",
    "kind": "service",
    "version": "0.0.1",
    "description": "d",
    "source": {"language": "python", "entrypoint": "src.server"},
    "runtimeMapping": {"style": "container"},
    "service": {
        "ports": [{"container_port": 8089, "host_port": 8089, "protocol": "tcp"}]
    },
    "configSchema": {"type": "object", "properties": {}},
    "secretSlots": [],
    "spec": {"tools": []},
}


def _write_yaml(path: Path, spec: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(spec), encoding="utf-8")


# ── (a) catalogue summary surfaces kind ─────────────────────────────────

def test_summary_defaults_kind_connector(tmp_path):
    p = tmp_path / "connector.yaml"
    _write_yaml(p, CONNECTOR_SPEC)
    summary = _connector_summary("demo", p, "bundle")
    assert summary["kind"] == "connector"
    assert summary["tools_count"] == 1


def test_summary_service_kind_zero_tools(tmp_path):
    p = tmp_path / "connector.yaml"
    _write_yaml(p, SERVICE_SPEC)
    summary = _connector_summary("svc", p, "bundle")
    assert summary["kind"] == "service"
    assert summary["tools_count"] == 0


# ── (b) iter_registrations skips a kind:service connector ───────────────

def test_iter_registrations_skips_service(tmp_path, monkeypatch):
    # Sandbox every store under tmp; plaintext escape-hatch so the
    # default SecretStore() iter_registrations builds doesn't refuse.
    monkeypatch.setenv("DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("GUARDIAN_SECRET_KEK_ALLOW_PLAINTEXT", "1")

    # Temp bundle root: manifest + a single service connector dir.
    bundle = tmp_path / "bundle"
    _write_yaml(bundle / "connectors" / "svc" / "connector.yaml", SERVICE_SPEC)
    _write_yaml(
        bundle / "manifest.yaml",
        {"toolConnectors": [{"id": "svc", "path": "connectors/svc"}]},
    )
    monkeypatch.setattr(connector_loader, "_bundle_root", lambda: bundle)

    # A configured + ENABLED instance for the service. A normal
    # connector in this state would advertise its tools; the service
    # must still register none.
    store = InstanceStore(data_root=tmp_path / "data")
    store.create(
        "svc", "default", {"container_url": "http://x:9000"}, enabled=True
    )

    regs = list(
        connector_loader.iter_registrations(
            include_legacy_aliases=False, store=store
        )
    )
    assert all(r.connector_id != "svc" for r in regs), (
        "kind:service connector must advertise zero agent tools"
    )
