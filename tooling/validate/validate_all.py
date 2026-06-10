"""validate_all — confirm the AI Layer is well-formed.

Runs every fast, deterministic check on the harness components. Slow checks
that actually spawn external processes (MCP handshake, pyright initialize)
live in their own files (`check_mcp.py`, `check_lsp.py`) and are invoked by
this script; failure of either fails the overall run.

The article: *"the harness — the ecosystem built around the model —
determines how Claude Code performs more than the model alone."* This file
is how the team keeps that harness from rotting. CI runs it on every push
that touches AI Layer paths.

Usage:  python3 tooling/validate/validate_all.py
Exit:   0 if every check passes, 1 if any fails.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK_DIR = Path(__file__).resolve().parent

EXPECTED_SUBDIR_CLAUDE_MDS = {
    "mcp/agent",
    "bundles/spark/mcp",
    "bundles/spark/connectors",
    "installer",
    "updater",
}

# The plugin must be SELF-CONTAINED, so files are duplicated between the
# plugin payload and the repo-local copies. The validator's job is to keep
# the duplicates in sync — any drift becomes a CI failure.
PLUGIN_SYNC_PAIRS = [
    (
        ROOT / ".claude/hooks/propose_claude_md.py",
        ROOT / "tooling/guardian-ai-layer/hooks/propose_claude_md.py",
    ),
    (
        ROOT / ".claude/hooks/reflect_claude_md.py",
        ROOT / "tooling/guardian-ai-layer/hooks/reflect_claude_md.py",
    ),
    (
        ROOT / "tooling/mcp/codebase_search.py",
        ROOT / "tooling/guardian-ai-layer/mcp/codebase_search.py",
    ),
]

# Directories that must have every matching file tracked in git. Catches the
# v0.8.1-class regression where `.gitignore`'s blanket `*.png` rule silently
# dropped 93 baked vendor logos because a new content directory didn't get an
# `!`-exception added. Each tuple: (repo-relative dir, glob pattern, label).
SILENT_DROP_GUARDS = [
    (
        "bundles/spark/connectors/cortex-content/baked",
        "*.png",
        "baked vendor logos",
    ),
]


EXPECTED_PLUGIN_FILES = [
    "tooling/.claude-plugin/marketplace.json",
    "tooling/guardian-ai-layer/.claude-plugin/plugin.json",
    "tooling/guardian-ai-layer/README.md",
    "tooling/guardian-ai-layer/agents/explorer.md",
    "tooling/guardian-ai-layer/hooks/hooks.json",
    "tooling/guardian-ai-layer/hooks/propose_claude_md.py",
    "tooling/guardian-ai-layer/hooks/reflect_claude_md.py",
    "tooling/guardian-ai-layer/mcp/codebase_search.py",
    "tooling/guardian-ai-layer/skills/scoped-tests/SKILL.md",
]


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


# ---------- Foundation checks (Phase 1) -------------------------------------


def check_claude_md_hierarchy() -> Check:
    """Root + every expected subdirectory CLAUDE.md exists."""
    missing: list[str] = []
    if not (ROOT / "CLAUDE.md").is_file():
        missing.append("CLAUDE.md (root)")
    for subdir in sorted(EXPECTED_SUBDIR_CLAUDE_MDS):
        path = ROOT / subdir / "CLAUDE.md"
        if not path.is_file():
            missing.append(f"{subdir}/CLAUDE.md")
    if missing:
        return Check(
            "CLAUDE.md hierarchy", False, f"missing: {', '.join(missing)}"
        )
    return Check(
        "CLAUDE.md hierarchy",
        True,
        f"root + {len(EXPECTED_SUBDIR_CLAUDE_MDS)} subdirectory files present",
    )


def check_claudeignore() -> Check:
    """`.claudeignore` exists and excludes the baked vendor catalog."""
    ignore = ROOT / ".claudeignore"
    if not ignore.is_file():
        return Check(".claudeignore", False, "missing")
    text = ignore.read_text(encoding="utf-8")
    if "bundles/spark/connectors/cortex-content/baked" not in text:
        return Check(
            ".claudeignore",
            False,
            "does NOT exclude bundles/spark/connectors/cortex-content/baked/ — "
            "576 vendor files would bloat agent context",
        )
    return Check(".claudeignore", True, "excludes baked vendor catalog + caches")


def check_pack_theme_variants_complete() -> Check:
    """v0.10.0 — Every pack in vendor_map.yaml maps to a vendor whose light + dark
    SVG variants both exist in baked/vendor_svgs/.

    This is the structural guarantee for R1's theme-aware logo route: if every
    pack resolves to a vendor and every vendor ships both variants, the route
    never falls through to the legacy PNG/dark.svg fallback chain in practice.
    """
    try:
        import yaml  # type: ignore
    except ImportError:
        return Check("pack theme variants", False, "PyYAML not installed; required for vendor_map.yaml parsing")

    baked = ROOT / "bundles/spark/connectors/cortex-content/baked"
    vmap_path = baked / "vendor_map.yaml"
    vsvgs_dir = baked / "vendor_svgs"
    packs_dir = baked / "Packs"

    if not vmap_path.is_file():
        return Check("pack theme variants", False, f"missing {vmap_path.relative_to(ROOT)}")
    if not vsvgs_dir.is_dir():
        return Check("pack theme variants", False, f"missing {vsvgs_dir.relative_to(ROOT)}")

    try:
        vmap = yaml.safe_load(vmap_path.read_text())
    except Exception as exc:
        return Check("pack theme variants", False, f"vendor_map.yaml unparseable: {exc}")
    vendors = (vmap or {}).get("vendors") or {}
    if not vendors:
        return Check("pack theme variants", False, "vendor_map.yaml has no vendors")

    # Build the inverse: pack → vendor
    pack_to_vendor: dict[str, str] = {}
    for vk, info in vendors.items():
        for pack in info.get("packs") or []:
            pack_to_vendor[pack] = vk

    # Check 1: every pack on disk is in some vendor's packs[]
    disk_packs = {p.name for p in packs_dir.iterdir() if p.is_dir()}
    unmapped = sorted(disk_packs - set(pack_to_vendor.keys()))
    if unmapped:
        sample = unmapped[:3]
        return Check(
            "pack theme variants",
            False,
            f"{len(unmapped)} pack(s) on disk not in vendor_map.yaml (e.g. {sample})",
        )

    # Check 2: every vendor in the map has both _light.svg + _dark.svg
    missing: list[str] = []
    for vk in vendors.keys():
        light = vsvgs_dir / f"{vk}_light.svg"
        dark = vsvgs_dir / f"{vk}_dark.svg"
        if not light.is_file():
            missing.append(f"{vk}_light.svg")
        if not dark.is_file():
            missing.append(f"{vk}_dark.svg")
    if missing:
        sample = missing[:3]
        return Check(
            "pack theme variants",
            False,
            f"{len(missing)} variant file(s) missing in vendor_svgs/ (e.g. {sample})",
        )

    # Check 3: every pack-in-map references a vendor that exists
    stale = sorted(set(pack_to_vendor.values()) - set(vendors.keys()))
    if stale:
        return Check(
            "pack theme variants",
            False,
            f"vendor reference(s) in pack_to_vendor not found in vendors[]: {stale[:3]}",
        )

    return Check(
        "pack theme variants",
        True,
        f"{len(disk_packs)} packs → {len(vendors)} vendors, all light+dark SVG present",
    )


def check_no_silent_gitignore_drops() -> Check:
    """For each SILENT_DROP_GUARDS entry, every filesystem file matching the
    pattern must also be tracked in git. Catches the v0.8.1 class of bug
    where a `.gitignore` blanket rule silently dropped files because no
    `!`-exception covered the directory."""
    from fnmatch import fnmatch

    drops: list[str] = []
    checked: list[str] = []

    for rel_dir, pattern, label in SILENT_DROP_GUARDS:
        abs_dir = ROOT / rel_dir
        if not abs_dir.is_dir():
            drops.append(f"{rel_dir}: directory missing")
            continue

        fs_files = {
            p.relative_to(ROOT).as_posix()
            for p in abs_dir.rglob(pattern)
            if p.is_file()
        }

        try:
            tracked_raw = subprocess.run(
                ["git", "ls-files", rel_dir],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            ).stdout.splitlines()
        except (subprocess.SubprocessError, FileNotFoundError) as exc:
            drops.append(f"{rel_dir}: git ls-files failed: {exc}")
            continue

        tracked_matching = {
            line for line in tracked_raw if fnmatch(Path(line).name, pattern)
        }

        untracked = fs_files - tracked_matching
        if untracked:
            sample = sorted(untracked)[:3]
            drops.append(
                f"{rel_dir}/**/{pattern}: "
                f"{len(untracked)} file(s) on disk but not tracked "
                f"(e.g. {sample}) — likely .gitignore silent drop, add exception"
            )
            continue

        checked.append(f"{label} ({len(fs_files)} {pattern})")

    if drops:
        return Check("gitignore silent-drop guard", False, "; ".join(drops))
    return Check(
        "gitignore silent-drop guard",
        True,
        f"all tracked — {', '.join(checked)}" if checked else "no guards registered",
    )


def check_codebase_map() -> Check:
    """CODEBASE_MAP.md exists and mentions top-level entries."""
    cmap = ROOT / "CODEBASE_MAP.md"
    if not cmap.is_file():
        return Check("CODEBASE_MAP.md", False, "missing")
    text = cmap.read_text(encoding="utf-8")
    required = ["mcp/agent/", "bundles/spark/", "installer/", "updater/"]
    missing = [token for token in required if token not in text]
    if missing:
        return Check(
            "CODEBASE_MAP.md",
            False,
            f"missing top-level entries: {', '.join(missing)}",
        )
    return Check("CODEBASE_MAP.md", True, "covers all top-level service paths")


def check_ai_layer_md() -> Check:
    """AI-LAYER.md exists and references the helpline pattern."""
    ail = ROOT / "AI-LAYER.md"
    if not ail.is_file():
        return Check("AI-LAYER.md", False, "missing")
    text = ail.read_text(encoding="utf-8")
    if "helpline" not in text.lower() or "anthropic" not in text.lower():
        return Check(
            "AI-LAYER.md",
            False,
            "must reference the Anthropic article + helpline reference impl",
        )
    return Check("AI-LAYER.md", True, "documents article alignment + phases")


# ---------- Infrastructure checks (Phase 2) ---------------------------------


def check_settings_json() -> Check:
    """`.claude/settings.json` is valid JSON with permissions + hooks declared."""
    settings = ROOT / ".claude/settings.json"
    if not settings.is_file():
        return Check(".claude/settings.json", False, "missing")
    try:
        config = json.loads(settings.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return Check(".claude/settings.json", False, f"invalid JSON: {exc}")
    if "permissions" not in config:
        return Check(".claude/settings.json", False, "missing 'permissions' key")
    if "hooks" not in config:
        return Check(".claude/settings.json", False, "missing 'hooks' key")
    perms = config["permissions"]
    if "allow" not in perms or "deny" not in perms:
        return Check(
            ".claude/settings.json",
            False,
            "permissions.allow + permissions.deny both required",
        )
    deny = perms["deny"]
    if not any("rm -rf" in rule for rule in deny):
        return Check(
            ".claude/settings.json",
            False,
            "permissions.deny must block `rm -rf:*`",
        )
    return Check(
        ".claude/settings.json",
        True,
        f"valid JSON, {len(perms['allow'])} allow rules, {len(deny)} deny rules, "
        f"hooks: {sorted(config['hooks'].keys())}",
    )


def check_subagent_readonly() -> Check:
    """guardian-explorer subagent has NO Write/Edit/Bash tools."""
    agent = ROOT / ".claude/agents/guardian-explorer.md"
    if not agent.is_file():
        return Check("guardian-explorer subagent", False, "missing")
    text = agent.read_text(encoding="utf-8")
    fm_match = re.match(r"---\n(.*?)\n---", text, re.DOTALL)
    if not fm_match:
        return Check("guardian-explorer subagent", False, "missing frontmatter")
    frontmatter = fm_match.group(1)
    tools_line_match = re.search(r"^tools:\s*(.+)$", frontmatter, re.MULTILINE)
    if not tools_line_match:
        return Check(
            "guardian-explorer subagent",
            False,
            "frontmatter missing 'tools:' key",
        )
    tools = {t.strip() for t in tools_line_match.group(1).split(",")}
    forbidden = {"Write", "Edit", "Bash", "MultiEdit"} & tools
    if forbidden:
        return Check(
            "guardian-explorer subagent",
            False,
            f"FORBIDDEN write tools granted: {sorted(forbidden)} — "
            "the article's split-exploration pattern requires read-only",
        )
    expected = {"Read", "Grep", "Glob"}
    if tools != expected:
        return Check(
            "guardian-explorer subagent",
            False,
            f"unexpected tool set {sorted(tools)} (expected {sorted(expected)})",
        )
    return Check(
        "guardian-explorer subagent",
        True,
        "read-only (Read, Grep, Glob); no Write/Edit/Bash",
    )


def check_hooks_compile() -> Check:
    """All hook scripts compile."""
    hooks_dir = ROOT / ".claude/hooks"
    if not hooks_dir.is_dir():
        return Check(".claude/hooks/", False, "directory missing")
    expected = {
        "session_start_context.py",
        "propose_claude_md.py",
        "reflect_claude_md.py",
    }
    found = {p.name for p in hooks_dir.glob("*.py")}
    missing = expected - found
    if missing:
        return Check(".claude/hooks/", False, f"missing scripts: {sorted(missing)}")
    failures = []
    for name in sorted(expected):
        path = hooks_dir / name
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, OSError) as exc:
            failures.append(f"{name}: {exc}")
    if failures:
        return Check(".claude/hooks/", False, "; ".join(failures))
    return Check(".claude/hooks/", True, f"{len(expected)} scripts, all parse cleanly")


def check_skills_have_paths() -> Check:
    """Every path-scoped skill has `paths:` frontmatter."""
    skills_dir = ROOT / ".claude/skills"
    if not skills_dir.is_dir():
        return Check(".claude/skills/", False, "directory missing")
    expected_guardian_skills = {
        "connector-add",
        "mcp-tool-add",
        "release-tag-flow",
        "help-page-update",
        "agent-page-add",
    }
    failures = []
    for skill_name in expected_guardian_skills:
        skill_md = skills_dir / skill_name / "SKILL.md"
        if not skill_md.is_file():
            failures.append(f"{skill_name}: missing SKILL.md")
            continue
        text = skill_md.read_text(encoding="utf-8")
        fm_match = re.match(r"---\n(.*?)\n---", text, re.DOTALL)
        if not fm_match:
            failures.append(f"{skill_name}: no frontmatter")
            continue
        if "paths:" not in fm_match.group(1):
            failures.append(f"{skill_name}: missing 'paths:' in frontmatter")
    if failures:
        return Check(".claude/skills/ paths-scoping", False, "; ".join(failures))
    return Check(
        ".claude/skills/ paths-scoping",
        True,
        f"{len(expected_guardian_skills)} skills, all have `paths:` frontmatter",
    )


def check_mcp_json() -> Check:
    """`.mcp.json` references a valid script path."""
    mcp_json = ROOT / ".mcp.json"
    if not mcp_json.is_file():
        return Check(".mcp.json", False, "missing")
    try:
        config = json.loads(mcp_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return Check(".mcp.json", False, f"invalid JSON: {exc}")
    servers = config.get("mcpServers", {})
    if not servers:
        return Check(".mcp.json", False, "no mcpServers declared")
    for name, server in servers.items():
        if "args" not in server:
            return Check(".mcp.json", False, f"{name}: missing args")
        script = ROOT / server["args"][0]
        if not script.is_file():
            return Check(
                ".mcp.json",
                False,
                f"{name}: references missing script {server['args'][0]}",
            )
    return Check(".mcp.json", True, f"{len(servers)} server(s) declared, scripts exist")


def check_codebase_search_imports() -> Check:
    """`tooling/mcp/codebase_search.py` parses cleanly and declares 3 MCP tools."""
    script = ROOT / "tooling/mcp/codebase_search.py"
    if not script.is_file():
        return Check("tooling/mcp/codebase_search.py", False, "missing")
    try:
        tree = ast.parse(script.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        return Check("tooling/mcp/codebase_search.py", False, f"syntax error: {exc}")
    tool_funcs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in node.decorator_list:
                if (
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr == "tool"
                ):
                    tool_funcs.add(node.name)
    expected = {"where_is", "find_references", "outline"}
    if tool_funcs != expected:
        return Check(
            "tooling/mcp/codebase_search.py",
            False,
            f"declared tools {sorted(tool_funcs)} != expected {sorted(expected)}",
        )
    return Check(
        "tooling/mcp/codebase_search.py",
        True,
        f"declares {sorted(tool_funcs)}",
    )


# ---------- Governance checks (Phase 3) -------------------------------------


def check_plugin_marketplace() -> Check:
    """`tooling/.claude-plugin/marketplace.json` references the plugin."""
    marketplace = ROOT / "tooling/.claude-plugin/marketplace.json"
    if not marketplace.is_file():
        return Check("plugin marketplace.json", False, "missing")
    try:
        config = json.loads(marketplace.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return Check("plugin marketplace.json", False, f"invalid JSON: {exc}")
    plugins = config.get("plugins") or []
    if not plugins:
        return Check("plugin marketplace.json", False, "no plugins declared")
    names = {p.get("name") for p in plugins}
    if "guardian-ai-layer" not in names:
        return Check(
            "plugin marketplace.json",
            False,
            f"guardian-ai-layer not registered (found {names})",
        )
    return Check(
        "plugin marketplace.json",
        True,
        f"{len(plugins)} plugin(s) registered: {sorted(names)}",
    )


def check_plugin_payload() -> Check:
    """Every expected plugin payload file exists."""
    missing = [p for p in EXPECTED_PLUGIN_FILES if not (ROOT / p).is_file()]
    if missing:
        return Check(
            "plugin payload",
            False,
            f"missing {len(missing)} file(s): {missing[:3]}{'…' if len(missing) > 3 else ''}",
        )
    return Check(
        "plugin payload",
        True,
        f"all {len(EXPECTED_PLUGIN_FILES)} expected files present",
    )


def check_plugin_sync() -> Check:
    """Plugin duplicates stay in sync with their .claude/ + tooling/ originals."""
    drift = []
    for source, plugin_copy in PLUGIN_SYNC_PAIRS:
        if not source.is_file() or not plugin_copy.is_file():
            drift.append(f"{source.name}: one side missing")
            continue
        a = hashlib.sha256(source.read_bytes()).hexdigest()
        b = hashlib.sha256(plugin_copy.read_bytes()).hexdigest()
        if a != b:
            drift.append(
                f"{source.name}: SHA mismatch — "
                f"{source.relative_to(ROOT)} vs {plugin_copy.relative_to(ROOT)}"
            )
    if drift:
        return Check("plugin/repo sync", False, "; ".join(drift))
    return Check(
        "plugin/repo sync",
        True,
        f"{len(PLUGIN_SYNC_PAIRS)} duplicated file(s) match by SHA",
    )


def check_pyright_declared() -> Check:
    """Root pyproject.toml declares pyright as a dev-dep."""
    pyproject = ROOT / "pyproject.toml"
    if not pyproject.is_file():
        return Check(
            "pyright declared",
            False,
            "pyproject.toml missing at repo root",
        )
    text = pyproject.read_text(encoding="utf-8")
    if "pyright" not in text:
        return Check(
            "pyright declared",
            False,
            "pyproject.toml does not mention pyright",
        )
    return Check("pyright declared", True, "pyright listed in root pyproject.toml")


# ---------- External-process checks (delegate to sibling scripts) -----------


def _run_subscript(name: str, script: Path) -> Check:
    if not script.is_file():
        return Check(name, True, f"(skipped — {script.name} not present)")
    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.SubprocessError as exc:
        return Check(name, False, f"subprocess error: {exc}")
    if result.returncode != 0:
        last = (result.stdout or result.stderr).strip().splitlines()
        tail = " ".join(last[-3:]) if last else "(no output)"
        return Check(name, False, f"exit {result.returncode}: {tail}")
    tail = result.stdout.strip().splitlines()
    return Check(name, True, (tail[-1] if tail else "passed") )


def check_mcp_handshake() -> Check:
    return _run_subscript("MCP server handshake", CHECK_DIR / "check_mcp.py")


def _references_dropped_request(node: ast.AST) -> bool:
    """v0.17.115 — True if a function references a bare `request` (Load) that is
    NOT bound anywhere in its tree. This catches the incomplete-flatten class:
    when a tool's signature is flattened off the pre-v0.17.92 `request: Model`
    envelope but the body still references `request` (the v0.17.114
    guardian_kill_worker bug: `payload.get("worker", request.worker_id)` after the
    signature lost `request` → `NameError` on every call).

    Nested-function params count as bound (a Playwright `_route_handler(route,
    request)` legitimately uses an inner `request`), so we never false-positive
    on inner-scope args. Conservative by design: ANY binding → not flagged.
    """
    bound = False
    referenced = False
    for n in ast.walk(node):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            a = n.args
            allp = list(a.posonlyargs) + list(a.args) + list(a.kwonlyargs)
            if any(p.arg == "request" for p in allp):
                bound = True
            if a.vararg and a.vararg.arg == "request":
                bound = True
            if a.kwarg and a.kwarg.arg == "request":
                bound = True
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name) and t.id == "request":
                    bound = True
        elif isinstance(n, ast.AnnAssign):
            if isinstance(n.target, ast.Name) and n.target.id == "request":
                bound = True
        elif isinstance(n, (ast.For, ast.comprehension)):
            tgt = getattr(n, "target", None)
            if isinstance(tgt, ast.Name) and tgt.id == "request":
                bound = True
        elif isinstance(n, ast.Name) and n.id == "request" and isinstance(n.ctx, ast.Load):
            referenced = True
    return referenced and not bound


def check_connector_tool_args_flat() -> Check:
    """v0.17.114 (#111) — every connector tool takes FLAT kwargs that match its
    connector.yaml args. No tool may take a single `request: Model` parameter,
    and every connector.yaml arg name must appear as a function parameter. This
    keeps the central MCP's tool-calling uniform — the v0.17.77
    guardian_create_data_worker shape — so the agent never has to guess whether
    a tool wants flat args or a {request:{...}} wrapper.

    v0.17.115 — also fails if a tool's body references a `request` the flattened
    signature no longer provides (the kill_worker incomplete-flatten regression).
    """
    try:
        import yaml  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover
        return Check("connector tools flat-args", False, f"required dep missing: {exc}")

    conn_root = ROOT / "bundles" / "spark" / "connectors"
    if not conn_root.is_dir():
        return Check("connector tools flat-args", True, "no connectors dir")

    violations: list[str] = []
    checked = 0
    for ydir in sorted(p for p in conn_root.iterdir() if p.is_dir()):
        yf = ydir / "connector.yaml"
        if not yf.is_file():
            continue
        try:
            spec = (yaml.safe_load(yf.read_text()) or {}).get("spec", {}) or {}
        except Exception as exc:  # noqa: BLE001
            violations.append(f"{ydir.name}: connector.yaml parse failed: {exc}")
            continue
        tools = spec.get("tools", []) or []
        if not tools:
            continue

        # Collect every function signature in src/*.py (ast — robust vs regex).
        # Value = (param names sans ctx/self, has **kwargs). A function with
        # **kwargs absorbs any arg, so the name-match check is skipped for it
        # (the single-`request:` check still applies).
        sigs: dict[str, tuple[list[str], bool]] = {}
        for pyf in sorted((ydir / "src").glob("*.py")):
            try:
                tree = ast.parse(pyf.read_text())
            except Exception:  # noqa: BLE001
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    params = [a.arg for a in node.args.args] + [a.arg for a in node.args.kwonlyargs]
                    sig = [p for p in params if p not in ("ctx", "self", "cls")]
                    sigs[node.name] = (
                        sig,
                        node.args.kwarg is not None,
                        _references_dropped_request(node),
                    )

        for tool in tools:
            name = tool.get("name")
            if not name:
                continue
            yargs = {a.get("name") for a in (tool.get("args") or []) if a.get("name")}
            # Connector tool funcs are named <prefix>_<tool> (the dispatched
            # name, e.g. guardian_/xsiam_/cortex_) or bare <tool>. Prefer the
            # PREFIXED function over a bare-named internal helper that happens
            # to share the tool name (else the helper shadows the real tool).
            cand = next(
                (fn for fn in sigs if fn.endswith("_" + name)), None
            ) or (name if name in sigs else None)
            if cand is None:
                continue  # REST-only / not python-backed
            checked += 1
            sig, has_kwargs, dropped_req = sigs[cand]
            if sig == ["request"]:
                violations.append(
                    f"{ydir.name}.{name}: single `request:` param — flatten to kwargs"
                )
                continue
            if dropped_req:
                violations.append(
                    f"{ydir.name}.{name}: body references `request` but the flattened "
                    f"signature has no `request` param (incomplete flatten — NameError at runtime)"
                )
                continue
            if has_kwargs:
                continue  # **kwargs absorbs any arg — name-match not enforceable
            missing = yargs - set(sig)
            if missing:
                violations.append(
                    f"{ydir.name}.{name}: connector.yaml args not in signature: {sorted(missing)}"
                )

    if not violations:
        return Check(
            "connector tools flat-args",
            True,
            f"all {checked} python-backed connector tools use flat kwargs matching connector.yaml",
        )
    shown = "; ".join(violations[:12])
    more = f" … (+{len(violations) - 12} more)" if len(violations) > 12 else ""
    return Check("connector tools flat-args", False, f"{len(violations)} violation(s): {shown}{more}")


def check_factory_default_clean_slate() -> Check:
    """v0.17.114 (#111 factory-default contract) — the customer release is a CLEAN
    SLATE: it ships catalog + connectors + skills + KB as CONTENT, but NO installed
    state (no installed data sources, no connector instances, no chats/jobs/runs, no
    log destinations, no tech stack). Static guards:
      1. No operator-state SQLite db committed under an image build context.
      2. The installer .env template does NOT pre-set WEBHOOK_ENDPOINT / WEBHOOK_KEY /
         TECHNOLOGY_STACK uncommented — those would auto-seed a log destination or a
         tech stack on first boot and break the clean slate.
    """
    problems: list[str] = []
    state_db = re.compile(
        r"(marketplace|instances|log_destinations|operator_state|chats?|jobs?|"
        r"sessions?|simulation_runs?)\.db$",
        re.I,
    )
    try:
        tracked = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, timeout=30
        ).stdout.splitlines()
    except Exception as exc:  # noqa: BLE001
        return Check("factory-default clean slate", False, f"git ls-files failed: {exc}")
    for f in tracked:
        if state_db.search(f) and any(
            seg in f for seg in ("bundles/spark/mcp", "mcp/agent", "installer/")
        ):
            problems.append(f"committed state db in image context: {f}")
    env_ex = ROOT / "installer" / ".env.example"
    if env_ex.is_file():
        for ln in env_ex.read_text().splitlines():
            if re.match(r"^(WEBHOOK_ENDPOINT|WEBHOOK_KEY|TECHNOLOGY_STACK)\s*=\s*\S", ln.strip()):
                problems.append(
                    f".env.example pre-sets {ln.strip().split('=')[0]} (auto-seeds on fresh install)"
                )
    if not problems:
        return Check(
            "factory-default clean slate",
            True,
            "no installed state baked; installer .env auto-seed vars commented",
        )
    return Check("factory-default clean slate", False, "; ".join(problems[:8]))


# ---------- Driver ----------------------------------------------------------


def _print_results(checks: list[Check]) -> bool:
    print(f"\nguardian AI Layer validation — {len(checks)} checks\n")
    passed = sum(1 for c in checks if c.ok)
    width = max(len(c.name) for c in checks)
    for check in checks:
        mark = "✓" if check.ok else "✗"
        print(f"  {mark}  {check.name:<{width}}  — {check.detail}")
    overall = passed == len(checks)
    status = "PASS" if overall else "FAIL"
    print(f"\n{status}: {passed}/{len(checks)} checks green\n")
    return overall


def main() -> int:
    checks = [
        check_claude_md_hierarchy(),
        check_claudeignore(),
        check_no_silent_gitignore_drops(),
        check_pack_theme_variants_complete(),
        check_codebase_map(),
        check_ai_layer_md(),
        check_settings_json(),
        check_subagent_readonly(),
        check_hooks_compile(),
        check_skills_have_paths(),
        check_mcp_json(),
        check_codebase_search_imports(),
        check_plugin_marketplace(),
        check_plugin_payload(),
        check_plugin_sync(),
        check_pyright_declared(),
        check_mcp_handshake(),
        check_connector_tool_args_flat(),
        check_factory_default_clean_slate(),
    ]
    return 0 if _print_results(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
