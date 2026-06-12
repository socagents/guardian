"""Tests for the Guardian loop state module. Run from scripts/loop/:
    python3 -m pytest test_loop_state.py -v
"""
import pytest
import loop_state as ls


def test_load_missing_returns_default(tmp_path):
    state = ls.load_state(tmp_path / "nope.json")
    assert state["schema_version"] == ls.SCHEMA_VERSION
    assert state["cycles"] == []
    assert "next_focus" in state
    assert state["open_findings"] == []


def test_record_cycle_appends_and_numbers():
    state = ls.default_state()
    ls.record_cycle(state, {"outcome": "fixed", "focus": "x"})
    ls.record_cycle(state, {"outcome": "no-op", "focus": "y"})
    assert [c["n"] for c in state["cycles"]] == [1, 2]
    assert state["cycles"][0]["outcome"] == "fixed"


def test_compute_counters():
    state = ls.default_state()
    for o in ["fixed", "fixed", "no-op", "gate-failed", "checker-rejected"]:
        ls.record_cycle(state, {"outcome": o, "focus": "f"})
    c = ls.compute_counters(state)
    assert c == {
        "cycles_total": 5,
        "fixes_shipped": 2,
        "noops": 1,
        "gate_failures": 1,
        "checker_rejections": 1,
    }


def test_render_contains_next_focus_and_latest_cycle():
    state = ls.default_state()
    ls.set_next_focus(state, "FOCUS-MARKER")
    ls.record_cycle(state, {
        "outcome": "fixed", "focus": "CYCLE-MARKER",
        "started_at": "2026-06-11T02:30:00Z", "commit": "abc1234",
        "gate": "pass", "checker": "approved",
    })
    md = ls.render_markdown(state)
    assert "FOCUS-MARKER" in md
    assert "CYCLE-MARKER" in md
    assert "abc1234" in md


def test_roundtrip_save_load(tmp_path):
    p = tmp_path / "state.json"
    state = ls.default_state()
    ls.record_cycle(state, {"outcome": "fixed", "focus": "f"})
    ls.save_state(p, state)
    again = ls.load_state(p)
    assert again["cycles"][0]["outcome"] == "fixed"


def test_record_cycle_rejects_unknown_outcome():
    state = ls.default_state()
    with pytest.raises(ValueError, match="banana"):
        ls.record_cycle(state, {"outcome": "banana", "focus": "f"})


def test_load_state_rejects_non_dict(tmp_path):
    p = tmp_path / "state.json"
    p.write_text("[1, 2, 3]")
    with pytest.raises(ValueError, match="JSON object"):
        ls.load_state(p)


def test_default_state_has_active_unit_and_deferred():
    s = ls.default_state()
    assert s["active_unit"] is None
    assert s["deferred"] == []
    assert s["schema_version"] == ls.SCHEMA_VERSION


def test_load_state_backfills_new_keys_for_old_schema(tmp_path):
    # An old (Phase-1) state.json with no active_unit/deferred must load cleanly.
    p = tmp_path / "state.json"
    p.write_text('{"schema_version": 1, "cycles": [], "next_focus": "x", "open_findings": []}')
    s = ls.load_state(p)
    assert s["active_unit"] is None
    assert s["deferred"] == []


def test_open_unit_sets_active():
    s = ls.default_state()
    ls.open_unit(s, id="jobs-chat-prompt", title="chat→prompt", scope="renderers + docs", mode="narrow")
    u = ls.active_unit(s)
    assert u["id"] == "jobs-chat-prompt"
    assert u["mode"] == "narrow"
    assert u["rejections"] == 0
    assert u["status"] == "active"
    assert u["remaining_scope"] == []


def test_open_unit_rejects_bad_mode():
    s = ls.default_state()
    import pytest
    with pytest.raises(ValueError, match="mode"):
        ls.open_unit(s, id="x", title="t", scope="s", mode="banana")


def test_complete_unit_clears_active():
    s = ls.default_state()
    ls.open_unit(s, id="x", title="t", scope="s", mode="narrow")
    ls.complete_unit(s)
    assert ls.active_unit(s) is None


def test_set_remaining():
    s = ls.default_state()
    ls.open_unit(s, id="x", title="t", scope="s", mode="narrow")
    ls.set_remaining(s, ["slice-b", "slice-c"])
    assert ls.active_unit(s)["remaining_scope"] == ["slice-b", "slice-c"]


def test_record_rejection_increments_and_stores_reasons():
    s = ls.default_state()
    ls.open_unit(s, id="x", title="t", scope="s", mode="narrow")
    ls.record_rejection(s, "missed file A")
    ls.record_rejection(s, "missed file A and B")
    u = ls.active_unit(s)
    assert u["rejections"] == 2
    assert u["reasons"] == "missed file A and B"


def test_should_defer_narrow_after_2():
    s = ls.default_state()
    ls.open_unit(s, id="x", title="t", scope="s", mode="narrow")
    ls.record_rejection(s, "r1")
    assert ls.should_defer(s) is False
    ls.record_rejection(s, "r2")
    assert ls.should_defer(s) is True


def test_should_defer_wide_after_3():
    s = ls.default_state()
    ls.open_unit(s, id="x", title="t", scope="s", mode="wide")
    ls.record_rejection(s, "r1")
    ls.record_rejection(s, "r2")
    assert ls.should_defer(s) is False
    ls.record_rejection(s, "r3")
    assert ls.should_defer(s) is True


def test_should_defer_no_active_unit_is_false():
    s = ls.default_state()
    assert ls.should_defer(s) is False


def test_defer_unit_moves_to_deferred_and_clears_active():
    s = ls.default_state()
    ls.open_unit(s, id="hard", title="t", scope="files X,Y,Z", mode="wide")
    ls.record_rejection(s, "still missing Z")
    ls.defer_unit(s, issue="https://example/issues/9")
    assert ls.active_unit(s) is None
    assert len(s["deferred"]) == 1
    d = s["deferred"][0]
    assert d["id"] == "hard"
    assert d["reasons"] == "still missing Z"
    assert d["issue"] == "https://example/issues/9"
    assert ls.is_deferred(s, "hard") is True
    assert ls.is_deferred(s, "other") is False
