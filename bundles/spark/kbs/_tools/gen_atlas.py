#!/usr/bin/env python3
"""gen_atlas — generate a MITRE ATLAS knowledge base from the official ATLAS YAML.

MITRE ATLAS (Adversarial Threat Landscape for AI Systems) is the ATT&CK-style
framework for attacks on AI/ML systems (prompt injection, model evasion, data
poisoning, model theft, agent hijacking). Guardian is itself an AI agent and
customers increasingly run AI/LLM workloads, so ATLAS is the canonical TTP
language for investigating AI-targeting incidents.

Deterministic, like gen_mitre.py: two doc types —
  * attack-technique  (AML.T####)  — technique description, tactics, mitigations,
                                      and the mapped ATT&CK Enterprise id if any.
  * case-study        (AML.CS####)  — a real-world AI-incident report: summary,
                                      the step-by-step procedure (tactic →
                                      technique → what happened), target, actor.

USAGE
  python gen_atlas.py --atlas /tmp/atlas.yaml --out ../mitre-atlas/entries
  # or fetch the latest stable single-file distribution:
  python gen_atlas.py --out ../mitre-atlas/entries
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any

# Stable single-file ATLAS distribution (v5.x). The v6 multi-file format exists
# but splits objects across files; the v5 single file is self-contained.
ATLAS_URL = "https://raw.githubusercontent.com/mitre-atlas/atlas-data/main/dist/ATLAS.yaml"

# ATLAS markdown uses site-relative links like [foo](/techniques/AML.T0000).
_RELLINK = re.compile(r"\[([^\]]+)\]\(/[^)]+\)")


def _clean(text: str | None) -> str:
    if not text:
        return ""
    # keep the link text, drop the site-relative URL
    return _RELLINK.sub(r"\1", text).strip()


def _yaml_list(items: list[str]) -> str:
    return "".join(f"  - {i}\n" for i in items)


def build(atlas: dict[str, Any]) -> tuple[list[tuple[str, str]], str]:
    version = str(atlas.get("version") or "unknown")
    matrix = atlas["matrices"][0]
    tmap = {t["id"]: t["name"] for t in matrix["tactics"]}
    techs = matrix["techniques"]
    tech_name = {t["id"]: t["name"] for t in techs}

    # technique id -> [mitigation] (mitigations declare techniques[] they cover)
    mit_for: dict[str, list[dict]] = {}
    for m in matrix.get("mitigations", []):
        for tid in m.get("techniques", []) or []:
            # techniques may be a string id or a {id: ...} mapping
            tid = tid.get("id") if isinstance(tid, dict) else tid
            mit_for.setdefault(tid, []).append(m)

    docs: list[tuple[str, str]] = []

    # ── techniques ──
    for t in techs:
        tid = t["id"]
        name = t.get("name", tid)
        # ATLAS ids are AML.T#### (technique) or AML.T####.### (sub-technique);
        # the dot after the AML namespace is NOT a sub-technique separator, so a
        # sub-technique has 3 dotted segments.
        _parts = tid.split(".")
        parent = ".".join(_parts[:-1]) if len(_parts) >= 3 else ""
        tactics = [tmap.get(x, x) for x in (t.get("tactics") or [])]
        attack_ref = t.get("ATT&CK-reference") or {}
        attack_id = attack_ref.get("id") if isinstance(attack_ref, dict) else None

        tags = [tt.lower().replace(" ", "-") for tt in tactics] + ["ai", "atlas"]
        fm = ["---", f"id: {tid}", f"title: {json.dumps(name)}",
              "category: attack-technique", "tags:", _yaml_list(sorted(set(tags))).rstrip("\n"),
              "ecosystem: AI", "framework: mitre-atlas",
              f"framework_version: \"{version}\"",
              f"is_subtechnique: {str(bool(parent)).lower()}"]
        if parent:
            fm.append(f"parent_id: {parent}")
        if tactics:
            fm += ["tactics:", _yaml_list(tactics).rstrip("\n")]
        if attack_id:
            fm.append(f"attack_enterprise_ref: {attack_id}")
        fm.append("---")

        body = [f"# {tid} — {name}", ""]
        meta = []
        if tactics:
            meta.append(f"**Tactics:** {', '.join(tactics)}")
        if parent:
            meta.append(f"**Sub-technique of:** {parent} ({tech_name.get(parent, '')})")
        if attack_id:
            meta.append(f"**ATT&CK Enterprise mapping:** {attack_id}")
        if meta:
            body += ["  ·  ".join(meta), ""]
        desc = _clean(t.get("description"))
        if desc:
            body += ["## Description", "", desc, ""]
        mits = mit_for.get(tid, [])
        if mits:
            body += ["## Mitigations", ""]
            for m in mits:
                body.append(f"- **{_clean(m.get('name'))}** ({m.get('id')}): {_clean(m.get('description'))}")
            body.append("")
        docs.append((tid, "\n".join(fm) + "\n\n" + "\n".join(body) + "\n"))

    # ── case studies ──
    for c in atlas.get("case-studies", []):
        cid = c["id"]
        name = c.get("name", cid)
        tags = ["ai", "atlas", "case-study"]
        ct = c.get("case-study-type")
        if ct:
            tags.append(str(ct).lower())
        fm = ["---", f"id: {cid}", f"title: {json.dumps(name)}",
              "category: case-study", "tags:", _yaml_list(sorted(set(tags))).rstrip("\n"),
              "ecosystem: AI", "framework: mitre-atlas",
              f"framework_version: \"{version}\""]
        if c.get("incident-date"):
            fm.append(f"incident_date: \"{c.get('incident-date')}\"")
        fm.append("---")

        body = [f"# {cid} — {name}", ""]
        bits = []
        if c.get("target"):
            bits.append(f"**Target:** {c.get('target')}")
        if c.get("actor"):
            bits.append(f"**Actor:** {c.get('actor')}")
        if c.get("incident-date"):
            bits.append(f"**Date:** {c.get('incident-date')}")
        if bits:
            body += ["  ·  ".join(bits), ""]
        summary = _clean(c.get("summary"))
        if summary:
            body += ["## Summary", "", summary, ""]
        proc = c.get("procedure") or []
        if proc:
            body += ["## Procedure (attack chain)", ""]
            for step in proc:
                tac = step.get("tactic", "")
                tech = step.get("technique", "")
                label = " / ".join(x for x in (tac, tech) if x)
                body.append(f"- **{label}** — {_clean(step.get('description'))}")
            body.append("")
        refs = c.get("references") or []
        if refs:
            body += ["## References", ""]
            for r in refs[:8]:
                title = r.get("title") if isinstance(r, dict) else str(r)
                url = r.get("url") if isinstance(r, dict) else ""
                body.append(f"- {title}{(' — ' + url) if url else ''}")
            body.append("")
        docs.append((cid, "\n".join(fm) + "\n\n" + "\n".join(body) + "\n"))

    return docs, version


NOTICE = """\
This knowledge base is generated from MITRE ATLAS™.

ATLAS™ (Adversarial Threat Landscape for AI Systems) is a project of The MITRE
Corporation. Content reproduced from https://github.com/mitre-atlas/atlas-data
(framework version {version}) with copyright preserved; distribution unlimited.
Guardian is not endorsed or certified by MITRE.
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate a MITRE ATLAS KB from the ATLAS YAML.")
    ap.add_argument("--atlas", help="local ATLAS.yaml path (default: fetch latest)")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    import yaml

    if args.atlas:
        atlas = yaml.safe_load(Path(args.atlas).read_text("utf-8"))
    else:
        print(f"fetching {ATLAS_URL} ...", file=sys.stderr)
        with urllib.request.urlopen(ATLAS_URL) as r:  # noqa: S310 — trusted MITRE host
            atlas = yaml.safe_load(r.read().decode("utf-8"))

    docs, version = build(atlas)
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    for cid, text in docs:
        (out / f"{cid}.md").write_text(text, "utf-8")
    (out.parent / "NOTICE.txt").write_text(NOTICE.format(version=version), "utf-8")

    techs = sum(1 for a, _ in docs if a.startswith("AML.T"))
    cs = sum(1 for a, _ in docs if a.startswith("AML.CS"))
    print(f"gen_atlas[v{version}]: wrote {len(docs)} docs ({techs} techniques + {cs} case-studies) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
