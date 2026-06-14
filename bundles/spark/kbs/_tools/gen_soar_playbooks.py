#!/usr/bin/env python3
"""gen_soar_playbooks — build the SOAR-playbooks KB from the demisto/content repo.

The operator's intent: pull the Cortex XSOAR out-of-the-box playbooks, EMBED a
good searchable DESCRIPTION of each (so semantic search matches intent, not raw
YAML), KEEP the raw YAML alongside it, and DUAL-LABEL by (1) product/pack origin
and (2) investigation-type / use-case. Future payoff: worked examples for an
agent that learns to BUILD playbooks.

Scope: SOC-relevant pack categories only (Endpoint, Network Security, Email,
Forensics & Malware, Threat-Intel, Case Management, IAM, Vuln-Mgmt, Cloud
Security, Analytics & SIEM) — ~900 playbooks, not the full ~1,170 long tail.
Deprecated playbooks are skipped.

Each doc is a JSON entry: {id, title, category:"playbook", content:<embedded
description>, raw_yaml:<full YAML>, product, pack, support_tier, use_cases, tags}.
The kb_loader embeds `content`; raw_yaml rides in metadata. Embeddings are baked
separately by kb_embed.py.

USAGE
  python gen_soar_playbooks.py --content /tmp/content --out ../soar-playbooks/entries

Licensing: demisto/content is MIT — playbook YAML is redistributable with the
MIT notice + attribution (written to NOTICE.txt). Vendor names are nominative.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import yaml

SOC_CATEGORIES = {
    "Endpoint", "Network Security", "Analytics & SIEM",
    "Data Enrichment & Threat Intelligence", "Forensics & Malware Analysis",
    "Email", "Identity and Access Management", "Vulnerability Management",
    "Case Management", "Cloud Security",
}

# pack useCase / category → normalized investigation-type tags
USECASE_TAGS = {
    "Phishing": "phishing", "Malware": "malware", "Ransomware": "ransomware",
    "Hunting": "threat-hunting", "Incident Response": "incident-response",
    "Threat Intelligence Management": "threat-intel",
    "Identity And Access Management": "identity", "Network Security": "network-security",
    "Vulnerability Management": "vulnerability-management",
    "Case Management": "case-management", "Breach Notification": "breach-notification",
}
CATEGORY_TAGS = {
    "Endpoint": "endpoint", "Network Security": "network-security",
    "Email": "email", "Forensics & Malware Analysis": "forensics-malware",
    "Data Enrichment & Threat Intelligence": "threat-intel",
    "Identity and Access Management": "identity", "Cloud Security": "cloud-security",
    "Vulnerability Management": "vulnerability-management",
    "Case Management": "case-management", "Analytics & SIEM": "siem",
}

_SLUG = re.compile(r"[^a-z0-9]+")


def _slug(s: str, maxlen: int = 60) -> str:
    return _SLUG.sub("-", (s or "").lower()).strip("-")[:maxlen].strip("-")


def _is_deprecated(pb: dict[str, Any]) -> bool:
    if pb.get("deprecated") or pb.get("hidden"):
        return True
    desc = (pb.get("description") or "").strip().lower()
    return desc.startswith("deprecated") or desc.startswith("this playbook is deprecated")


def _integrations_used(pb: dict[str, Any]) -> list[str]:
    """Distinct integration brands / scripts the playbook's tasks call —
    a strong signal of what the playbook actually does."""
    out: set[str] = set()
    tasks = pb.get("tasks") or {}
    if isinstance(tasks, dict):
        tasks = tasks.values()
    for t in tasks:
        if not isinstance(t, dict):
            continue
        sub = t.get("task") or {}
        script = sub.get("script") or t.get("scriptName") or sub.get("scriptName")
        if isinstance(script, str) and script:
            brand = script.split("|||")[0].strip() or script.split("|||")[-1].strip()
            if brand and brand not in ("Builtin", "DeleteContext"):
                out.add(brand)
    return sorted(out)[:20]


def _description(pb: dict[str, Any], product: str, pack: str, support: str,
                 use_cases: list[str]) -> str:
    parts: list[str] = []
    desc = (pb.get("description") or "").strip()
    if desc:
        parts.append(desc)
    parts.append(
        f"Cortex XSOAR/XSIAM SOAR playbook from the {product} pack "
        f"({pack}, {support}-supported)."
    )
    if use_cases:
        parts.append(f"Use cases: {', '.join(use_cases)}.")
    inputs = [i for i in (pb.get("inputs") or []) if isinstance(i, dict)]
    if inputs:
        lines = [
            f"{i.get('key')}: {(i.get('description') or '').strip()}".strip(": ")
            for i in inputs[:10] if i.get("key")
        ]
        if lines:
            parts.append("Inputs — " + "; ".join(lines) + ".")
    outputs = [o for o in (pb.get("outputs") or []) if isinstance(o, dict)]
    if outputs:
        lines = [
            f"{o.get('contextPath')}: {(o.get('description') or '').strip()}".strip(": ")
            for o in outputs[:10] if o.get("contextPath")
        ]
        if lines:
            parts.append("Outputs — " + "; ".join(lines) + ".")
    integrations = _integrations_used(pb)
    if integrations:
        parts.append("Integrations/scripts used: " + ", ".join(integrations) + ".")
    return "\n\n".join(parts)


def build(content_root: Path) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for meta_path in sorted(glob.glob(str(content_root / "Packs" / "*" / "pack_metadata.json"))):
        pack_dir = Path(meta_path).parent
        pack = pack_dir.name
        try:
            meta = json.loads(Path(meta_path).read_text("utf-8"))
        except Exception:
            continue
        cats = meta.get("categories") or []
        if not (set(cats) & SOC_CATEGORIES):
            continue
        product = meta.get("author") or meta.get("name") or pack
        support = meta.get("support") or "community"
        use_cases = [u for u in (meta.get("useCases") or []) if isinstance(u, str)]
        # normalized investigation/use-case tags from pack useCases + categories
        inv_tags = sorted({
            *(USECASE_TAGS[u] for u in use_cases if u in USECASE_TAGS),
            *(CATEGORY_TAGS[c] for c in cats if c in CATEGORY_TAGS),
        })

        for pb_path in sorted(glob.glob(str(pack_dir / "Playbooks" / "playbook-*.yml"))):
            raw = Path(pb_path).read_text("utf-8")
            try:
                pb = yaml.safe_load(raw)
            except Exception:
                continue
            if not isinstance(pb, dict) or _is_deprecated(pb):
                continue
            name = pb.get("name") or pb.get("id") or Path(pb_path).stem
            stem = _slug(Path(pb_path).stem.replace("playbook-", ""))
            doc_id = f"pb-{_slug(pack, 28)}-{stem}"[:90].strip("-")
            while doc_id in seen:
                doc_id += "-x"
            seen.add(doc_id)

            tags = sorted({
                "soar", "playbook", f"product:{_slug(product, 40)}",
                f"support:{support}", *inv_tags,
            })
            docs.append({
                "id": doc_id,
                "title": name,
                "category": "playbook",
                "content": _description(pb, product, pack, support, use_cases),
                "raw_yaml": raw,
                "product": product,
                "pack": pack,
                "support_tier": support,
                "use_cases": use_cases,
                "fromversion": pb.get("fromversion"),
                "source_repo": "demisto/content (MIT)",
                "tags": tags,
            })
    return docs


NOTICE = """\
SOAR playbooks reproduced from the Cortex XSOAR Content repository
(https://github.com/demisto/content), which is licensed under the MIT License.

MIT License — Copyright (c) Palo Alto Networks / Demisto.
Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files, to deal in the Software
without restriction, including the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies, subject to including this copyright
+ permission notice. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY.

Vendor and product names are nominative references to identify the integration a
playbook targets; no endorsement is implied. Only playbook YAML is bundled (no
vendor logo binaries or integration code).
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate the SOAR-playbooks KB from demisto/content.")
    ap.add_argument("--content", type=Path, required=True, help="demisto/content checkout root")
    ap.add_argument("--out", type=Path, required=True, help="entries/ output dir")
    args = ap.parse_args()

    if not (args.content / "Packs").is_dir():
        sys.exit(f"no Packs/ under {args.content}")
    docs = build(args.content)
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    for d in docs:
        (out / f"{d['id']}.json").write_text(json.dumps(d, ensure_ascii=False, indent=2), "utf-8")
    (out.parent / "NOTICE.txt").write_text(NOTICE, "utf-8")

    products = len({d["product"] for d in docs})
    print(f"gen_soar_playbooks: wrote {len(docs)} playbook docs "
          f"({products} products) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
