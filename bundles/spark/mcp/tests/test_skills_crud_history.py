"""skills_crud.update_skill — v0.2.12 history + listing-exclusion.

The autonomous investigation-judge edits the investigation skill via
skills_update. These tests pin the safety rails: every update keeps a
timestamped rollback copy under `.history/`, and those copies never leak
into the skills listing.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from usecase.builtin_components import skills_crud as sc  # noqa: E402


@pytest.fixture()
def skills_dir(tmp_path, monkeypatch):
    (tmp_path / "workflows").mkdir()
    (tmp_path / "workflows" / "demo.md").write_text(
        "---\nname: demo\n---\n# Demo\noriginal body\n", encoding="utf-8"
    )
    monkeypatch.setattr(sc, "SKILLS_DIR", tmp_path)
    return tmp_path


def test_update_skill_writes_bak_and_timestamped_history(skills_dir):
    res = sc.update_skill("workflows/demo.md", "# Demo\nnew body v2\n")
    assert res["success"] is True

    # Single-level .bak holds the original (immediate undo).
    bak = skills_dir / "workflows" / "demo.md.bak"
    assert bak.exists() and "original body" in bak.read_text(encoding="utf-8")

    # Timestamped history copy under .history/ holds the original too.
    assert res["history"]
    hist = skills_dir / res["history"]
    assert hist.exists() and "original body" in hist.read_text(encoding="utf-8")
    assert hist.parent.name == ".history"

    # The live file now carries the new content.
    assert "new body v2" in (
        skills_dir / "workflows" / "demo.md"
    ).read_text(encoding="utf-8")


def test_history_and_bak_never_listed_as_skills(skills_dir):
    sc.update_skill("workflows/demo.md", "# Demo\nv2\n")
    sc.update_skill("workflows/demo.md", "# Demo\nv3\n")  # 2 history files now

    listed = [s["file_path"] for s in sc.get_all_skills()]
    assert "workflows/demo.md" in listed
    assert all(".history" not in p for p in listed)
    assert all(not p.endswith(".bak") for p in listed)
    # exactly one record for the real skill — no history/bak duplicates
    assert listed.count("workflows/demo.md") == 1
