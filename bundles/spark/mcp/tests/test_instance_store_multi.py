"""v0.2.29 (#43) — multi-active-instance support.

Two ENABLED instances of the same connector (e.g. an XSOAR 6 tenant + an
XSOAR 8 tenant) may now coexist. The former one-active-per-connector guard
in InstanceStore.create()/update() was lifted in lockstep with the
connector_loader change that adds an `instance` selector argument. The only
remaining uniqueness rule is UNIQUE(connector_id, name).
"""

import pytest

from usecase.instance_store import InstanceStore


def test_two_enabled_instances_same_connector_coexist(tmp_path):
    store = InstanceStore(data_root=tmp_path)
    v6 = store.create("xsoar", "xsoar-v6", {"api_url": "https://v6"}, {}, enabled=True)
    # Pre-v0.2.29 this raised ValueError ("already has an active instance").
    v8 = store.create("xsoar", "xsoar-v8", {"api_url": "https://v8"}, {}, enabled=True)

    assert v6.enabled is True
    assert v8.enabled is True
    rows = store.list_for("xsoar")
    assert {r.name for r in rows} == {"xsoar-v6", "xsoar-v8"}
    assert all(r.enabled for r in rows), "both instances must be enabled"


def test_duplicate_name_same_connector_still_rejected(tmp_path):
    store = InstanceStore(data_root=tmp_path)
    store.create("xsoar", "primary", {"api_url": "https://a"}, {}, enabled=True)
    # UNIQUE(connector_id, name) is the one remaining uniqueness rule.
    with pytest.raises(ValueError):
        store.create("xsoar", "primary", {"api_url": "https://b"}, {}, enabled=True)


def test_enable_second_instance_via_update_succeeds(tmp_path):
    store = InstanceStore(data_root=tmp_path)
    store.create("xsoar", "xsoar-v6", {"api_url": "https://v6"}, {}, enabled=True)
    dormant = store.create(
        "xsoar", "xsoar-v8", {"api_url": "https://v8"}, {}, enabled=False
    )
    # Pre-v0.2.29 enabling the second one raised; now it succeeds.
    updated = store.update(dormant.id, enabled=True)
    assert updated is not None and updated.enabled is True
    assert sum(1 for r in store.list_for("xsoar") if r.enabled) == 2


def test_other_connectors_unaffected(tmp_path):
    store = InstanceStore(data_root=tmp_path)
    store.create("xsoar", "xsoar-v6", {"api_url": "https://v6"}, {}, enabled=True)
    web = store.create("web", "primary", {"cdp_url": "http://b:9222"}, {}, enabled=True)
    assert web.enabled is True
    assert {r.name for r in store.list_for("web")} == {"primary"}
