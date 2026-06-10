#!/usr/bin/env python3
"""v0.17.75 — Per-pack TRANSPORT INTENT classifier.

# Why this exists

Phantom simulates data sources by sending events into Cortex. For the
event to land in the right dataset + survive parsing + modeling without
loss, Phantom must emit it in the SAME shape Cortex expects on the wire.

That shape is determined by ONE question: does the pack's
parsing-rule OR modeling-rule reference `_raw_log` or `_raw_json`?

  - References `_raw_json` → Cortex's HTTP collector splits the inbound
    JSON body into `_raw_json` for the parsing/modeling layer. Phantom
    must POST a JSON object to the HTTP collector endpoint.

  - References `_raw_log` → Cortex's syslog collector keeps the raw
    line in `_raw_log`. Phantom must emit a syslog line that embeds
    the documented fields somewhere parseable.

  - References NEITHER → Cortex relies on the broker / HTTP collector
    to pre-parse the wire format into named columns BEFORE the dataset
    sees it. Phantom emits either CEF, LEEF, key=value syslog, or a
    direct API-shape JSON — whatever the column set implies.

Output: a markdown table to stdout + a JSON sidecar at
`scripts/maintainer/transport_intent.json`.

# Re-runnable

Pure read-only over fetched .xif files + Cortex schemas. Safe to run
any time the demisto/content fetch has refreshed.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
BUNDLE_ROOT = REPO_ROOT / "bundles" / "spark" / "data-sources"
MODELING_ROOT = REPO_ROOT / "scripts" / "maintainer" / "modeling_rules"
PARSING_ROOT = REPO_ROOT / "scripts" / "maintainer" / "parsing_rules"
SCHEMA_ROOT = (
    REPO_ROOT / "bundles" / "spark" / "connectors" / "cortex-content"
    / "baked" / "Packs"
)
OUT_PATH = REPO_ROOT / "scripts" / "maintainer" / "transport_intent.json"

# Word-boundary matches — avoid false hits on `_raw_log_count` etc.
RE_RAW_LOG = re.compile(r"\b_raw_log\b")
RE_RAW_JSON = re.compile(r"\b_raw_json\b")


def read_yaml_header(yaml_path: Path) -> dict[str, str]:
    header: dict[str, str] = {}
    for line in yaml_path.read_text().split("\n"):
        if not line or line.startswith(" "):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if key in ("pack_name", "rule_name", "dataset_name", "vendor", "product"):
            header[key] = value
        if {"pack_name", "rule_name", "dataset_name"}.issubset(header):
            # we still want vendor + product if present in the header,
            # so let the loop run; but bail out as soon as we have both
            pass
    return header


def load_cortex_schema_cols(pack: str, rule: str, dataset: str) -> list[str]:
    p = SCHEMA_ROOT / pack / "ModelingRules" / rule / f"{rule}_schema.json"
    if not p.is_file():
        return []
    try:
        d = json.loads(p.read_text())
    except json.JSONDecodeError:
        return []
    if isinstance(d, dict) and dataset in d:
        cols = d[dataset]
        if isinstance(cols, dict):
            return list(cols.keys())
    return []


def classify(pack: str, rule: str, dataset: str) -> dict[str, Any]:
    """Return per-pack transport-intent verdict."""
    pr_files = sorted(PARSING_ROOT.glob(f"{pack}__*.xif"))
    mr_file = MODELING_ROOT / f"{pack}__{rule}.xif"

    pr_text = "\n".join(f.read_text(errors="replace") for f in pr_files)
    mr_text = mr_file.read_text(errors="replace") if mr_file.is_file() else ""

    pr_has_raw_log  = bool(RE_RAW_LOG.search(pr_text))
    pr_has_raw_json = bool(RE_RAW_JSON.search(pr_text))
    mr_has_raw_log  = bool(RE_RAW_LOG.search(mr_text))
    mr_has_raw_json = bool(RE_RAW_JSON.search(mr_text))

    schema_cols = load_cortex_schema_cols(pack, rule, dataset)
    schema_has_raw_log  = "_raw_log"  in schema_cols
    schema_has_raw_json = "_raw_json" in schema_cols

    refs_raw_log  = pr_has_raw_log  or mr_has_raw_log  or schema_has_raw_log
    refs_raw_json = pr_has_raw_json or mr_has_raw_json or schema_has_raw_json

    # Precedence: raw_json wins over raw_log when both appear (rare).
    # Reasoning: if a pack reads both, the HTTP-collector path is the
    # primary ingest and _raw_log is a legacy artifact.
    if refs_raw_json:
        transport = "raw_json"
    elif refs_raw_log:
        transport = "raw_log"
    else:
        transport = "direct"

    # Evidence list — where each reference was found
    evidence_bits: list[str] = []
    if pr_has_raw_log:     evidence_bits.append("PR:_raw_log")
    if mr_has_raw_log:     evidence_bits.append("MR:_raw_log")
    if schema_has_raw_log: evidence_bits.append("SCHEMA:_raw_log")
    if pr_has_raw_json:    evidence_bits.append("PR:_raw_json")
    if mr_has_raw_json:    evidence_bits.append("MR:_raw_json")
    if schema_has_raw_json: evidence_bits.append("SCHEMA:_raw_json")
    if not evidence_bits:
        evidence_bits.append("none")

    return {
        "pack": pack,
        "rule": rule,
        "dataset": dataset,
        "transport": transport,
        "evidence": evidence_bits,
        "has_parsing_rule": bool(pr_files),
        "has_modeling_rule": mr_file.is_file(),
        "schema_col_count": len(schema_cols),
    }


def main() -> int:
    yaml_paths = sorted(BUNDLE_ROOT.glob("*/data_source.yaml"))
    rows: list[dict[str, Any]] = []
    for yp in yaml_paths:
        h = read_yaml_header(yp)
        pack = h.get("pack_name", "")
        rule = h.get("rule_name", "")
        dataset = h.get("dataset_name", "")
        vendor = h.get("vendor", "")
        if not pack or not dataset:
            continue
        v = classify(pack, rule, dataset)
        v["vendor"] = vendor
        rows.append(v)

    counts = Counter(r["transport"] for r in rows)

    # Print a markdown table sorted by transport then pack_name
    order = {"raw_log": 0, "raw_json": 1, "direct": 2}
    rows.sort(key=lambda r: (order[r["transport"]], r["pack"], r["dataset"]))

    print("# Phantom — per-pack transport intent\n")
    print(f"Total packs: **{len(rows)}**\n")
    print("| transport | count | meaning |")
    print("|---|---|---|")
    print(f"| **raw_log**  | {counts.get('raw_log', 0)} | Cortex ingests generic syslog into `_raw_log`. Phantom must emit a syslog line embedding the documented fields. |")
    print(f"| **raw_json** | {counts.get('raw_json', 0)} | Cortex ingests via HTTP collector into `_raw_json`. Phantom must POST JSON. |")
    print(f"| **direct**   | {counts.get('direct', 0)} | Cortex uses pre-parsed native columns. Phantom emits CEF / LEEF / direct API JSON matching the schema column set. |")
    print()
    print("---\n")
    print("## Full table\n")
    print("| pack | rule | dataset | vendor | transport | evidence | cols | has_PR | has_MR |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        ev = ",".join(r["evidence"])
        print(
            f"| {r['pack']} | {r['rule']} | {r['dataset']} | {r['vendor']} | "
            f"**{r['transport']}** | {ev} | {r['schema_col_count']} | "
            f"{'✓' if r['has_parsing_rule'] else '–'} | "
            f"{'✓' if r['has_modeling_rule'] else '–'} |"
        )

    OUT_PATH.write_text(json.dumps({
        "summary": dict(counts),
        "rows": rows,
    }, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
