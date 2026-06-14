#!/usr/bin/env python3
"""gen_mitre — generate a MITRE ATT&CK knowledge base from the official STIX bundle.

Deterministic: one markdown doc per (sub-)technique, extracted faithfully from
the published STIX — NEVER LLM-authored, so it stays a true mirror of the
framework and regenerates cleanly on each MITRE refresh (~2x/yr).

Per technique we emit: description, tactic(s), platforms, DETECTION (v19 moved
detection out of the deprecated `x_mitre_detection` string into linked
Detection-Strategy → Analytic → data-component objects — we walk those), and
MITIGATIONS (linked course-of-action objects). The ATT&CK id is the doc id, so
re-loads are idempotent.

USAGE
  # Enterprise (default), fetching the latest bundle:
  python gen_mitre.py --domain enterprise --out ../mitre-attack-enterprise/entries

  # From a local bundle (reproducible / offline):
  python gen_mitre.py --stix /tmp/enterprise-attack.json \\
      --out ../mitre-attack-enterprise/entries

Domains: enterprise | ics | mobile (the bundle URL differs; --stix overrides).
Writes a NOTICE.txt (ATT&CK Terms-of-Use attribution) next to the entries dir.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any

STIX_URL = (
    "https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/"
    "{domain}-attack/{domain}-attack.json"
)
ECOSYSTEM = {"enterprise": "IT", "ics": "OT", "mobile": "Mobile"}

# ATT&CK Terms of Use require this attribution wherever the content is shipped.
NOTICE = """\
This knowledge base is generated from MITRE ATT&CK®.

ATT&CK® is a registered trademark of The MITRE Corporation. The ATT&CK content
is reproduced here under the ATT&CK Terms of Use
(https://attack.mitre.org/resources/legal-and-branding/terms-of-use/).

© The MITRE Corporation. This product is not endorsed or certified by MITRE.
Source: https://github.com/mitre-attack/attack-stix-data (framework version {version}).
"""

_CITATION = re.compile(r"\(Citation:[^)]*\)")
_WS = re.compile(r"[ \t]+\n")


def _clean(text: str | None) -> str:
    if not text:
        return ""
    text = _CITATION.sub("", text)
    text = _WS.sub("\n", text)
    return text.strip()


def _attack_id(obj: dict[str, Any]) -> str | None:
    for r in obj.get("external_references", []):
        if r.get("source_name") in ("mitre-attack", "mitre-ics-attack", "mitre-mobile-attack"):
            return r.get("external_id")
    return None


def _attack_url(obj: dict[str, Any]) -> str | None:
    for r in obj.get("external_references", []):
        if r.get("source_name", "").startswith("mitre") and r.get("url"):
            return r.get("url")
    return None


def _yaml_list(items: list[str]) -> str:
    return "".join(f"  - {i}\n" for i in items)


def build(stix: dict[str, Any], domain: str) -> tuple[list[tuple[str, str]], str]:
    objs = stix["objects"]
    by_id = {o["id"]: o for o in objs}

    version = "unknown"
    for o in objs:
        if o.get("type") == "x-mitre-collection":
            version = str(o.get("x_mitre_version") or "unknown")
            break

    shortname2name = {
        o["x_mitre_shortname"]: o["name"]
        for o in objs
        if o.get("type") == "x-mitre-tactic"
    }

    # technique stix id -> [detection-strategy obj], [course-of-action obj]
    detects: dict[str, list[dict]] = {}
    mitigates: dict[str, list[dict]] = {}
    for r in objs:
        if r.get("type") != "relationship" or r.get("revoked"):
            continue
        rt, tgt, src = r.get("relationship_type"), r.get("target_ref"), r.get("source_ref")
        if rt == "detects" and (so := by_id.get(src)):
            detects.setdefault(tgt, []).append(so)
        elif rt == "mitigates" and (so := by_id.get(src)):
            mitigates.setdefault(tgt, []).append(so)

    def detection_section(tech_id: str) -> str:
        out: list[str] = []
        for ds in detects.get(tech_id, []):
            if ds.get("x_mitre_deprecated") or ds.get("revoked"):
                continue
            analytics = []
            for ref in ds.get("x_mitre_analytic_refs", []):
                a = by_id.get(ref)
                if not a or a.get("x_mitre_deprecated"):
                    continue
                logs = sorted({
                    ls.get("name") for ls in a.get("x_mitre_log_source_references", [])
                    if ls.get("name")
                })
                desc = _clean(a.get("description"))
                if desc:
                    src = f" _(log sources: {', '.join(logs)})_" if logs else ""
                    analytics.append(f"- {desc}{src}")
            if analytics:
                out.append(f"**{_clean(ds.get('name'))}**\n" + "\n".join(analytics))
        return "\n\n".join(out)

    def mitigation_section(tech_id: str) -> str:
        rows = []
        for m in mitigates.get(tech_id, []):
            if m.get("x_mitre_deprecated") or m.get("revoked"):
                continue
            name, desc = _clean(m.get("name")), _clean(m.get("description"))
            if name:
                rows.append(f"- **{name}** ({_attack_id(m) or 'M????'}): {desc}")
        return "\n".join(rows)

    docs: list[tuple[str, str]] = []
    for t in objs:
        if t.get("type") != "attack-pattern" or t.get("revoked") or t.get("x_mitre_deprecated"):
            continue
        aid = _attack_id(t)
        if not aid:
            continue
        name = t.get("name", aid)
        is_sub = bool(t.get("x_mitre_is_subtechnique"))
        parent = aid.split(".")[0] if is_sub and "." in aid else ""
        tactics = [
            shortname2name.get(p["phase_name"], p["phase_name"])
            for p in t.get("kill_chain_phases", [])
            if p.get("kill_chain_name", "").startswith("mitre")
        ]
        platforms = t.get("x_mitre_platforms") or []

        # frontmatter
        fm = ["---", f"id: {aid}", f"title: {json.dumps(name)}",
              "category: attack-technique", "tags:"]
        # tags = tactic slugs (filterable) + platforms
        tag_vals = [tt.lower().replace(" ", "-") for tt in tactics] + \
                   [p.lower().replace(" ", "-") for p in platforms]
        fm.append(_yaml_list(sorted(set(tag_vals))).rstrip("\n"))
        fm += [
            f"ecosystem: {ECOSYSTEM[domain]}",
            f"framework: mitre-attack-{domain}",
            f"framework_version: \"{version}\"",
            f"is_subtechnique: {str(is_sub).lower()}",
        ]
        if parent:
            fm.append(f"parent_id: {parent}")
        if tactics:
            fm.append("tactics:")
            fm.append(_yaml_list(tactics).rstrip("\n"))
        if platforms:
            fm.append("platforms:")
            fm.append(_yaml_list(platforms).rstrip("\n"))
        fm.append("---")

        # body
        body = [f"# {aid} — {name}", ""]
        meta_line = []
        if tactics:
            meta_line.append(f"**Tactics:** {', '.join(tactics)}")
        if platforms:
            meta_line.append(f"**Platforms:** {', '.join(platforms)}")
        if parent:
            meta_line.append(f"**Sub-technique of:** {parent}")
        if meta_line:
            body += ["  ·  ".join(meta_line), ""]
        desc = _clean(t.get("description"))
        if desc:
            body += ["## Description", "", desc, ""]
        det = detection_section(t["id"])
        if det:
            body += ["## Detection", "", det, ""]
        mit = mitigation_section(t["id"])
        if mit:
            body += ["## Mitigations", "", mit, ""]
        url = _attack_url(t)
        if url:
            body += ["## Reference", "", f"- ATT&CK: {url}", ""]

        docs.append((aid, "\n".join(fm) + "\n\n" + "\n".join(body) + "\n"))

    return docs, version


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate a MITRE ATT&CK KB from STIX.")
    ap.add_argument("--domain", choices=("enterprise", "ics", "mobile"), default="enterprise")
    ap.add_argument("--stix", help="local STIX bundle path (default: fetch latest)")
    ap.add_argument("--out", type=Path, required=True, help="entries/ output dir")
    args = ap.parse_args()

    if args.stix:
        stix = json.loads(Path(args.stix).read_text("utf-8"))
    else:
        url = STIX_URL.format(domain=args.domain)
        print(f"fetching {url} ...", file=sys.stderr)
        with urllib.request.urlopen(url) as r:  # noqa: S310 — trusted MITRE host
            stix = json.loads(r.read().decode("utf-8"))

    docs, version = build(stix, args.domain)
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    for aid, text in docs:
        (out / f"{aid}.md").write_text(text, "utf-8")
    (out.parent / "NOTICE.txt").write_text(NOTICE.format(version=version), "utf-8")

    n_sub = sum(1 for a, _ in docs if "." in a)
    print(f"gen_mitre[{args.domain} v{version}]: wrote {len(docs)} docs "
          f"({len(docs) - n_sub} techniques + {n_sub} sub-techniques) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
