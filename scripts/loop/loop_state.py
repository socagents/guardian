#!/usr/bin/env python3
"""Guardian self-learning loop — on-disk state (the loop's own memory).

Two files (the loop's persistent "sixth element"):
  - .guardian-loop/state.json  — machine state (SOURCE OF TRUTH)
  - docs/loop/state.md         — human-readable mirror, rendered from the JSON

This module is the ONLY writer of both. The trainer pass calls the CLI at the
end of each cycle: `record` then `render`. Counters are DERIVED from cycles[]
at render time, so there is a single source of truth and nothing to keep in sync.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

SCHEMA_VERSION = 2  # v2 adds active_unit + deferred (Phase 1.5)
VALID_OUTCOMES = ("fixed", "no-op", "gate-failed", "checker-rejected")
VALID_MODES = ("narrow", "wide")
K_NARROW = 2  # defer a narrow unit after this many checker rejections
K_WIDE = 3    # wide (atomic) units get one more attempt


def default_state() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "cycles": [],
        "next_focus": (
            "self-heal: doc-sync audit "
            "(sidebar nav vs pages; architecture page service list vs docker compose)"
        ),
        "open_findings": [],
        "active_unit": None,
        "deferred": [],
    }


def load_state(path: Path) -> dict:
    path = Path(path)
    if not path.exists():
        return default_state()
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"cannot parse {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object, got {type(data).__name__}")
    data.setdefault("schema_version", SCHEMA_VERSION)
    data.setdefault("cycles", [])
    data.setdefault("next_focus", "")
    data.setdefault("open_findings", [])
    data.setdefault("active_unit", None)
    data.setdefault("deferred", [])
    return data


def save_state(path: Path, state: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")


def record_cycle(state: dict, cycle: dict) -> dict:
    outcome = cycle.get("outcome")
    if outcome not in VALID_OUTCOMES:
        raise ValueError(f"unknown outcome {outcome!r}; expected one of {VALID_OUTCOMES}")
    numbered = {"n": len(state["cycles"]) + 1}
    numbered.update(cycle)
    state["cycles"].append(numbered)
    return state


def set_next_focus(state: dict, focus: str) -> dict:
    state["next_focus"] = focus
    return state


def active_unit(state: dict) -> dict | None:
    return state.get("active_unit")


def open_unit(state: dict, *, id: str, title: str, scope: str, mode: str = "narrow") -> dict:
    if mode not in VALID_MODES:
        raise ValueError(f"unknown mode {mode!r}; expected one of {VALID_MODES}")
    state["active_unit"] = {
        "id": id,
        "title": title,
        "scope": scope,
        "mode": mode,
        "remaining_scope": [],
        "rejections": 0,
        "reasons": "",
        "status": "active",
    }
    return state


def complete_unit(state: dict) -> dict:
    state["active_unit"] = None
    return state


def set_remaining(state: dict, slices: list) -> dict:
    u = state.get("active_unit")
    if not u:
        raise ValueError("no active unit")
    u["remaining_scope"] = list(slices)
    return state


def record_rejection(state: dict, reasons: str) -> dict:
    u = state.get("active_unit")
    if not u:
        raise ValueError("no active unit")
    u["rejections"] += 1
    u["reasons"] = reasons  # latest accumulated checker reasons
    return state


def _defer_threshold(mode: str) -> int:
    return K_WIDE if mode == "wide" else K_NARROW


def should_defer(state: dict) -> bool:
    u = state.get("active_unit")
    return bool(u) and u["rejections"] >= _defer_threshold(u.get("mode", "narrow"))


def defer_unit(state: dict, *, issue: str | None = None) -> dict:
    u = state.get("active_unit")
    if not u:
        raise ValueError("no active unit")
    state["deferred"].append({
        "id": u["id"],
        "title": u["title"],
        "scope": u["scope"],
        "reasons": u.get("reasons", ""),
        "issue": issue,
    })
    state["active_unit"] = None
    return state


def is_deferred(state: dict, unit_id: str) -> bool:
    return any(d.get("id") == unit_id for d in state.get("deferred", []))


def compute_counters(state: dict) -> dict:
    cycles = state["cycles"]
    return {
        "cycles_total": len(cycles),
        "fixes_shipped": sum(1 for c in cycles if c.get("outcome") == "fixed"),
        "noops": sum(1 for c in cycles if c.get("outcome") == "no-op"),
        "gate_failures": sum(1 for c in cycles if c.get("outcome") == "gate-failed"),
        "checker_rejections": sum(1 for c in cycles if c.get("outcome") == "checker-rejected"),
    }


def _cell(v) -> str:
    return str(v if v not in (None, "") else "—").replace("|", "\\|")


def render_markdown(state: dict) -> str:
    c = compute_counters(state)
    lines = [
        "# Guardian self-learning loop — state",
        "",
        "> Rendered from `.guardian-loop/state.json` by `scripts/loop/loop_state.py`.",
        "> Do not hand-edit; change the JSON (or use the CLI) and re-render.",
        "",
        "## Counters",
        "",
        f"- Cycles total: **{c['cycles_total']}**",
        f"- Fixes shipped: **{c['fixes_shipped']}**",
        f"- No-ops: **{c['noops']}**",
        f"- Gate failures: **{c['gate_failures']}**",
        f"- Checker rejections: **{c['checker_rejections']}**",
        "",
    ]

    # --- Active unit (Phase 1.5) ---
    lines += ["## Active unit", ""]
    u = state.get("active_unit")
    if u:
        lines += [
            f"- **{u.get('id', '')}** — {u.get('title', '')}",
            f"  - mode: `{u.get('mode', '')}` · rejections: {u.get('rejections', 0)}"
            f" · remaining slices: {len(u.get('remaining_scope', []))}",
            f"  - scope: {u.get('scope', '')}",
            "",
        ]
    else:
        lines += ["_none active_", ""]

    # --- Deferred — needs human (Phase 1.5) ---
    lines += ["## Deferred — needs human", ""]
    deferred = state.get("deferred", [])
    if deferred:
        for d in deferred:
            issue = d.get("issue") or "(no issue)"
            lines.append(f"- **{d.get('id', '')}** — {d.get('title', '')} → {issue}")
            if d.get("reasons"):
                lines.append(f"  - blocked on: {d['reasons']}")
    else:
        lines.append("_none_")
    lines.append("")

    lines += [
        "## Next focus",
        "",
        state["next_focus"],
        "",
        "## Open findings",
        "",
    ]
    if state["open_findings"]:
        for f in state["open_findings"]:
            lines.append(f"- [{f.get('status', 'open')}] {f.get('id', '')}: {f.get('desc', '')}")
    else:
        lines.append("_none_")
    lines += ["", "## Recent cycles (last 10)", ""]
    if state["cycles"]:
        lines.append("| # | started | focus | outcome | commit | gate | checker |")
        lines.append("|---|---|---|---|---|---|---|")
        for cyc in state["cycles"][-10:]:
            lines.append(
                f"| {_cell(cyc.get('n'))} | {_cell(cyc.get('started_at'))} | {_cell(cyc.get('focus'))} | "
                f"{_cell(cyc.get('outcome'))} | {_cell(cyc.get('commit'))} | "
                f"{_cell(cyc.get('gate'))} | {_cell(cyc.get('checker'))} |"
            )
    else:
        lines.append("_no cycles yet_")
    lines.append("")
    return "\n".join(lines)


# --------------------------- CLI ---------------------------

def _paths(repo: str) -> tuple[Path, Path]:
    root = Path(repo)
    return root / ".guardian-loop" / "state.json", root / "docs" / "loop" / "state.md"


def cmd_init(args):
    json_path, md_path = _paths(args.repo)
    state = load_state(json_path)  # preserve existing state if present
    save_state(json_path, state)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_markdown(state))
    print(f"init: wrote {json_path} and {md_path}")


def cmd_record(args):
    json_path, _ = _paths(args.repo)
    state = load_state(json_path)
    record_cycle(state, {
        "started_at": args.started_at,
        "focus": args.focus,
        "outcome": args.outcome,
        "summary": args.summary,
        "commit": args.commit,
        "gate": args.gate,
        "checker": args.checker,
    })
    if args.next_focus:
        set_next_focus(state, args.next_focus)
    save_state(json_path, state)
    print(f"recorded cycle #{len(state['cycles'])} outcome={args.outcome}")


def cmd_render(args):
    json_path, md_path = _paths(args.repo)
    state = load_state(json_path)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_markdown(state))
    print(f"rendered {md_path}")


def _save_and_render(args, mutate):
    json_path, md_path = _paths(args.repo)
    state = load_state(json_path)
    mutate(state)
    save_state(json_path, state)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_markdown(state))


def cmd_open_unit(args):
    _save_and_render(args, lambda s: open_unit(
        s, id=args.id, title=args.title, scope=args.scope, mode=args.mode))
    print(f"opened unit {args.id} ({args.mode})")


def cmd_set_remaining(args):
    _save_and_render(args, lambda s: set_remaining(s, args.slices or []))
    print(f"remaining slices: {len(args.slices or [])}")


def cmd_record_rejection(args):
    _save_and_render(args, lambda s: record_rejection(s, args.reasons))
    print("recorded rejection")


def cmd_defer_unit(args):
    _save_and_render(args, lambda s: defer_unit(s, issue=args.issue or None))
    print("deferred active unit")


def cmd_complete_unit(args):
    _save_and_render(args, lambda s: complete_unit(s))
    print("completed active unit")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Guardian self-learning loop state")
    p.add_argument("--repo", default=".", help="repo root (default: cwd)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init").set_defaults(func=cmd_init)
    r = sub.add_parser("record")
    r.set_defaults(func=cmd_record)
    r.add_argument("--started-at", required=True, dest="started_at")
    r.add_argument("--focus", required=True)
    r.add_argument("--outcome", required=True, choices=VALID_OUTCOMES)
    r.add_argument("--summary", default="")
    r.add_argument("--commit", default="")
    r.add_argument("--gate", default="", choices=["", "pass", "fail"])
    r.add_argument("--checker", default="", choices=["", "approved", "rejected", "n/a"])
    r.add_argument("--next-focus", default="", dest="next_focus")
    sub.add_parser("render").set_defaults(func=cmd_render)

    o = sub.add_parser("open-unit"); o.set_defaults(func=cmd_open_unit)
    o.add_argument("--id", required=True)
    o.add_argument("--title", required=True)
    o.add_argument("--scope", required=True)
    o.add_argument("--mode", default="narrow", choices=list(VALID_MODES))

    sr = sub.add_parser("set-remaining"); sr.set_defaults(func=cmd_set_remaining)
    sr.add_argument("--slices", nargs="*", default=[])

    rr = sub.add_parser("record-rejection"); rr.set_defaults(func=cmd_record_rejection)
    rr.add_argument("--reasons", required=True)

    du = sub.add_parser("defer-unit"); du.set_defaults(func=cmd_defer_unit)
    du.add_argument("--issue", default="")

    sub.add_parser("complete-unit").set_defaults(func=cmd_complete_unit)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
