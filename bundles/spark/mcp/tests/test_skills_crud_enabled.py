"""#SKILL-F7 — per-skill enable/disable persists to frontmatter.

Pre-fix the /skills toggle mutated React state only (cosmetic, reset on
refresh; disabled skills were still injected into the prompt + loadable).
This pins the backend: set_skill_enabled writes the `enabled` flag into
the skill's YAML frontmatter (preserving the body), get_all_skills /
_build_record surface it, and absence defaults to enabled=True.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from usecase.builtin_components import skills_crud as sc  # noqa: E402
from usecase import audit_log as audit_mod  # noqa: E402


@pytest.fixture()
def skills_dir(tmp_path, monkeypatch):
    (tmp_path / "workflows").mkdir()
    (tmp_path / "workflows" / "demo.md").write_text(
        "---\nname: demo\ndescription: a demo skill\n---\n# Demo\nbody text here\n",
        encoding="utf-8",
    )
    # A skill with no frontmatter at all (legacy) — toggling should still work.
    (tmp_path / "workflows" / "bare.md").write_text(
        "# Bare\njust a body, no frontmatter\n", encoding="utf-8"
    )
    monkeypatch.setattr(sc, "SKILLS_DIR", tmp_path)
    return tmp_path


class _FakeAudit:
    def __init__(self):
        self.calls = []

    def record(self, **kw):
        self.calls.append(kw)
        return "id"


def _record_for(skills_dir, name: str) -> dict:
    rows = sc.get_all_skills()
    match = [r for r in rows if r["filename"] == name]
    assert match, f"{name} not listed"
    return match[0]


def test_default_enabled_true_when_flag_absent(skills_dir):
    # demo.md has no `enabled` key → record must default to True.
    rec = _record_for(skills_dir, "demo.md")
    assert rec["enabled"] is True


def test_disable_writes_frontmatter_and_preserves_body(skills_dir, monkeypatch):
    fake = _FakeAudit()
    monkeypatch.setattr(audit_mod, "audit_log", lambda: fake)

    result = sc.set_skill_enabled("workflows/demo.md", False)
    assert result["success"] is True
    assert result["enabled"] is False

    # Frontmatter now carries enabled: false; body is untouched.
    fm, body = sc.parse_frontmatter(
        (skills_dir / "workflows" / "demo.md").read_text(encoding="utf-8")
    )
    assert fm["enabled"] is False
    assert fm["name"] == "demo"  # existing keys preserved
    assert "body text here" in body

    # The listing reflects the persisted flag.
    assert _record_for(skills_dir, "demo.md")["enabled"] is False
    # And it audited as skill_disabled.
    assert any(c["action"] == "skill_disabled" for c in fake.calls)


def test_reenable_round_trips(skills_dir, monkeypatch):
    monkeypatch.setattr(audit_mod, "audit_log", lambda: _FakeAudit())
    sc.set_skill_enabled("workflows/demo.md", False)
    sc.set_skill_enabled("workflows/demo.md", True)
    assert _record_for(skills_dir, "demo.md")["enabled"] is True


def test_disable_skill_without_frontmatter(skills_dir, monkeypatch):
    # bare.md had no frontmatter block — toggling must create one and
    # keep the body, without crashing.
    monkeypatch.setattr(audit_mod, "audit_log", lambda: _FakeAudit())
    result = sc.set_skill_enabled("workflows/bare.md", False)
    assert result["success"] is True
    fm, body = sc.parse_frontmatter(
        (skills_dir / "workflows" / "bare.md").read_text(encoding="utf-8")
    )
    assert fm["enabled"] is False
    assert "just a body" in body


def test_missing_skill_errors(skills_dir):
    result = sc.set_skill_enabled("workflows/nope.md", False)
    assert result["success"] is False
    assert "not found" in result["error"].lower()
