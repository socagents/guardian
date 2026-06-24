"""v0.2.71 skills loading — SKILL-F5 (category allowlist) + SKILL-F14 (plugin
skill resolution from the job scheduler).

SKILL-F16 (entrypoint boot-merge backup) is a shell change, validated by
`bash -n` + review, not pytest.
"""

from usecase.builtin_components import skills_crud
from usecase.job_scheduler import JobScheduler


def test_create_skill_accepts_all_four_categories(tmp_path, monkeypatch):
    monkeypatch.setattr(skills_crud, "SKILLS_DIR", tmp_path)
    for cat in ("foundation", "scenarios", "validation", "workflows"):
        res = skills_crud.create_skill(cat, f"{cat}_smoke.md", "# body\ncontent")
        assert res.get("success") is True, f"{cat}: {res}"
        assert (tmp_path / cat / f"{cat}_smoke.md").is_file()


def test_create_skill_rejects_unknown_category(tmp_path, monkeypatch):
    monkeypatch.setattr(skills_crud, "SKILLS_DIR", tmp_path)
    res = skills_crud.create_skill("bogus", "x.md", "y")
    assert res.get("success") is False
    assert "bogus" in res["error"]
    # the corrected message lists all four valid categories
    for cat in ("foundation", "scenarios", "validation", "workflows"):
        assert cat in res["error"]


def test_create_skill_rejects_non_md(tmp_path, monkeypatch):
    monkeypatch.setattr(skills_crud, "SKILLS_DIR", tmp_path)
    assert skills_crud.create_skill("foundation", "x.txt", "y").get("success") is False


def _load(name):
    # _load_skill_body doesn't use instance state — bind it to a bare object.
    return JobScheduler._load_skill_body(object(), name)


def test_load_skill_body_resolves_plugin_skill(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILLS_DIR", str(tmp_path))
    # category skill
    (tmp_path / "foundation").mkdir(parents=True)
    (tmp_path / "foundation" / "triage.md").write_text("FOUNDATION BODY", encoding="utf-8")
    # plugin skill: canonical name "example-vendor.my_skill" → plugins/example-vendor/my_skill.md
    (tmp_path / "plugins" / "example-vendor").mkdir(parents=True)
    (tmp_path / "plugins" / "example-vendor" / "my_skill.md").write_text(
        "PLUGIN BODY", encoding="utf-8"
    )

    assert _load("triage") == "FOUNDATION BODY"
    # the bug: a dotted plugin name fell through to None (ran unbound)
    assert _load("example-vendor.my_skill") == "PLUGIN BODY"
    # honors the trailing-.md form too
    assert _load("example-vendor.my_skill.md") == "PLUGIN BODY"
    # genuine miss still returns None
    assert _load("no-such.skill") is None
