"""v0.2.24 — the playbook-builder's structural validator."""
from __future__ import annotations

import yaml

from usecase.builtin_components.playbook_tools import playbook_validate

VALID = yaml.dump({
    "id": "block-ip-generic",
    "name": "Block IP - Generic",
    "description": "Blocks a malicious IP across configured firewalls.",
    "starttaskid": "0",
    "inputs": [{"key": "IP", "description": "IP to block"}],
    "tasks": {
        "0": {"id": "0", "type": "start", "task": {"name": "start"}, "nexttasks": {"#none#": ["1"]}},
        "1": {"id": "1", "type": "regular", "task": {"name": "Block IP"}, "nexttasks": {"#none#": ["2"]}},
        "2": {"id": "2", "type": "title", "task": {"name": "Done"}},
    },
})


def test_valid_playbook_passes() -> None:
    r = playbook_validate(VALID)
    assert r["valid"] is True, r
    assert r["errors"] == []
    assert r["task_count"] == 3


def test_missing_required_field() -> None:
    pb = yaml.safe_load(VALID); del pb["name"]
    r = playbook_validate(yaml.dump(pb))
    assert r["valid"] is False
    assert any("name" in e for e in r["errors"])


def test_starttaskid_not_in_tasks() -> None:
    pb = yaml.safe_load(VALID); pb["starttaskid"] = "99"
    r = playbook_validate(yaml.dump(pb))
    assert r["valid"] is False
    assert any("starttaskid" in e for e in r["errors"])


def test_nexttasks_references_unknown_task() -> None:
    pb = yaml.safe_load(VALID)
    pb["tasks"]["1"]["nexttasks"] = {"#none#": ["404"]}
    r = playbook_validate(yaml.dump(pb))
    assert r["valid"] is False
    assert any("unknown task '404'" in e for e in r["errors"])


def test_unreachable_task_warns_but_valid() -> None:
    pb = yaml.safe_load(VALID)
    pb["tasks"]["9"] = {"id": "9", "type": "regular", "task": {"name": "orphan"}}
    r = playbook_validate(yaml.dump(pb))
    assert r["valid"] is True  # unreachable is a warning, not an error
    assert any("unreachable" in w for w in r["warnings"])


def test_not_yaml_or_not_mapping() -> None:
    assert playbook_validate(":\n  - [unbalanced")["valid"] is False
    assert playbook_validate("just a string")["valid"] is False


def test_missing_start_type_warns() -> None:
    pb = yaml.safe_load(VALID)
    pb["tasks"]["0"]["type"] = "regular"
    r = playbook_validate(yaml.dump(pb))
    assert any("type 'start'" in w for w in r["warnings"])


def test_empty_tasks_errors() -> None:
    pb = yaml.safe_load(VALID); pb["tasks"] = {}
    r = playbook_validate(yaml.dump(pb))
    assert r["valid"] is False
