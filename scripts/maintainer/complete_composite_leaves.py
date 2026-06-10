#!/usr/bin/env python3
"""#118 partial-mapping fix: complete a composite field's dotted-leaf children
from its modeling rule's json_extract paths, so the generator's _build_nested
(xlog/app/dynamic_schema.py) synthesizes the nested JSON the rule actually reads.

Symptom this fixes: a source maps few/zero xdm despite routing+binding being fine,
because its `type: json` composite (e.g. `properties`) has no dotted leaves -> the
generator emits `{}` -> every `json_extract_scalar(properties, "$.x")` is null.

Minimal-diff: parse the MR for json_extract_scalar/array(<composite>, "$.<path>")
(+ to_number/to_integer wrappers -> numeric leaf), then INSERT the missing dotted
leaf fields immediately after the `fields:` line in the raw YAML (text insert, no
reformat). Idempotent (skips leaves already present).
"""
from __future__ import annotations
import re, pathlib, yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
DS = ROOT / "bundles" / "spark" / "data-sources"
XIFD = ROOT / "scripts" / "maintainer" / "modeling_rules"

TARGETS = {
 "AzureSecurityCenter__MicrosoftDefenderForCloudModelingRules__microsoft_defender_for_cloud_raw":
   "AzureSecurityCenter__MicrosoftDefenderForCloudModelingRules",
 "GoogleChrome__GoogleChrome__google_workspace_chrome_raw": "GoogleChrome__GoogleChrome",
 "AWS_ELB__AWS_ELB__aws_elb_raw": "AWS_ELB__AWS_ELB",
}

def extract(xif: str):
    """{composite: {leaf_path: type}} from the MR's nested reads."""
    out: dict[str, dict] = {}
    # numeric leaves: to_number/to_integer(json_extract_scalar(col,"$.path"))
    for col, path in re.findall(r'to_(?:number|integer)\(\s*json_extract_scalar\(\s*([A-Za-z_]\w*)\s*,\s*"\$\.([^"]+)"', xif):
        out.setdefault(col, {})[path] = "number"
    for col, path in re.findall(r'json_extract_(?:scalar|array)\(\s*([A-Za-z_]\w*)\s*,\s*"\$\.([^"]+)"', xif):
        out.setdefault(col, {}).setdefault(path, "string_short")
    for col, path in re.findall(r'\b([A-Za-z_]\w*)\s*->\s*([A-Za-z_][\w.]*)', xif):
        out.setdefault(col, {}).setdefault(path, "string_short")
    return out

def field_block(name: str, typ: str, col: str, leaf: str) -> str:
    ex = "42" if typ == "number" else "sample"
    return (f"- name: {name}\n"
            f"  type: {typ}\n"
            f"  description: Nested leaf of `{col}` the modeling rule reads at $.{leaf}.\n"
            f"  example: {ex}\n")

def main():
    for d, xb in TARGETS.items():
        yf = DS / d / "data_source.yaml"
        xif_path = XIFD / f"{xb}.xif"
        if not (yf.is_file() and xif_path.is_file()):
            print(f"  SKIP {d}"); continue
        doc = yaml.safe_load(yf.read_text())
        names = {f.get("name") for f in doc.get("fields", [])}
        composites = {n for n in names if "." not in n}
        paths = extract(xif_path.read_text())
        new_blocks, added = [], []
        for col, leafs in sorted(paths.items()):
            if col not in composites:
                continue
            for leaf, typ in sorted(leafs.items()):
                clean = leaf.replace("[]", "").rstrip(".")
                fname = f"{col}.{clean}"
                if fname in names:
                    continue
                new_blocks.append(field_block(fname, typ, col, clean))
                names.add(fname); added.append(fname)
        if not new_blocks:
            print(f"  {d.split('__')[-1]:34s} no new leaves"); continue
        raw = yf.read_text()
        m = re.search(r"(?m)^fields:[ \t]*\n", raw)
        if not m:
            print(f"  {d.split('__')[-1]:34s} NO fields: anchor"); continue
        ins = m.end()
        raw = raw[:ins] + "".join(new_blocks) + raw[ins:]
        yf.write_text(raw)
        ncomp = sorted(c for c in paths if c in composites)
        print(f"  {d.split('__')[-1]:34s} +{len(added)} leaves into composites {ncomp}")
    print("done")

if __name__ == "__main__":
    main()
