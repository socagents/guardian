"""v0.2.42 (Refs #56) — guardian-updater publishes host ports for
emulated services (kind:service) and leaves connectors internal-only.

Covers the pure port-resolution helpers that feed
client.containers.run(..., ports=...):

  * _ports_kwarg_from_spec  — connector.yaml service.ports → docker-py ports
  * _published_ports_of     — running container's bindings → docker-py ports
                              (reconcile re-publish path)
  * KNOWN_SERVICES + _is_known_id — start/stop/restart/reconcile gates
  * SERVICE_DEFAULT_PORTS   — boot-spawn fallback when no body/existing ports
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from src import main as updater_main  # noqa: E402


# ── _ports_kwarg_from_spec ──────────────────────────────────────────────

def test_service_ports_map_to_docker_kwarg():
    spec = [{"container_port": 8089, "host_port": 8089, "protocol": "tcp"}]
    assert updater_main._ports_kwarg_from_spec(spec) == {"8089/tcp": 8089}


def test_host_port_defaults_to_container_port():
    spec = [{"container_port": 8089}]
    assert updater_main._ports_kwarg_from_spec(spec) == {"8089/tcp": 8089}


def test_connector_start_computes_no_ports():
    # A normal connector passes no service_ports → ports kwarg is None,
    # so Docker publishes nothing (connectors stay internal-only).
    assert updater_main._ports_kwarg_from_spec([]) is None
    assert updater_main._ports_kwarg_from_spec(None) is None


def test_multiple_ports_and_udp():
    spec = [
        {"container_port": 8089, "host_port": 18089, "protocol": "tcp"},
        {"container_port": 514, "protocol": "udp"},
    ]
    assert updater_main._ports_kwarg_from_spec(spec) == {
        "8089/tcp": 18089,
        "514/udp": 514,
    }


# ── _published_ports_of (reconcile re-publish) ──────────────────────────

class _FakeContainer:
    def __init__(self, bindings):
        self.attrs = {"HostConfig": {"PortBindings": bindings}}


def test_published_ports_inherited_from_existing_container():
    c = _FakeContainer({"8089/tcp": [{"HostIp": "", "HostPort": "8089"}]})
    assert updater_main._published_ports_of(c) == {"8089/tcp": 8089}


def test_published_ports_none_when_no_bindings():
    assert updater_main._published_ports_of(_FakeContainer({})) is None
    assert updater_main._published_ports_of(_FakeContainer(None)) is None


# ── gating: services are accepted alongside connectors ──────────────────

def test_known_id_accepts_service_and_connector():
    assert updater_main._is_known_id("splunk-mimic") is True
    assert updater_main._is_known_id("xsoar") is True
    assert updater_main._is_known_id("not-a-thing") is False


def test_service_container_name_parses():
    # The digest-drift reconcile loop must recognise a service container.
    parsed = updater_main._split_connector_container_name(
        "guardian-connector-splunk-mimic-default"
    )
    assert parsed == ("splunk-mimic", "default")


# ── SERVICE_DEFAULT_PORTS (boot-spawn fallback) ─────────────────────────

def test_default_ports_publish_splunkd_port():
    fallback = updater_main.SERVICE_DEFAULT_PORTS.get("splunk-mimic")
    assert updater_main._ports_kwarg_from_spec(fallback) == {"8089/tcp": 8089}
