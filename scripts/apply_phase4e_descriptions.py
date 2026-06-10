#!/usr/bin/env python3
"""v0.17.16 Phase 4e — Trend Micro + Claroty + FireEye + Mimecast.

# Why

After v0.17.14 the remaining top single-vendor gaps:
  Trend Micro 39 (Vision One + DeepSecurity + EmailSecurity)
  Claroty 38 (OT/ICS Continuous Threat Detection)
  FireEye 41 (HX + NX + ETP)
  Mimecast 34 (email gateway)

# Sources

* Claroty CEF mapping (Continuous Threat Detection): uses CEF custom-
  string fields cs1-cs22 + their labels. The labels describe what each
  `cs<N>` holds (e.g. cs1Label="AssetName" → cs1 holds the asset name).
* Mimecast SIEM log schema (Email Security Gateway):
  https://community.mimecast.com/s/article/SIEM-Log-Field-Definitions
* Trend Micro Vision One CEF schema:
  https://docs.trendmicro.com/en-us/documentation/article/
* Trend Micro Deep Security event format:
  https://help.deepsecurity.trendmicro.com/

# CEF extended cs7-cs22 range

The base CEF spec defines cs1-cs6 with labels (cs1Label etc.). Some
vendors (notably Claroty) extend this to cs7-cs22. The semantics are
identical to the base — `cs<N>` holds a device-custom string and
`cs<N>Label` names it. v0.17.11 covered cs1-cs6; this release extends
through cs22.
"""

from __future__ import annotations
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from extend_data_source_fields import update_one_yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
BUNDLE_ROOT = REPO_ROOT / "bundles" / "spark" / "data-sources"


# ─── Extended CEF custom-string range (cs7-cs22) ───────────────


def _extended_cef_dict() -> dict[str, str]:
    """Auto-generate cs<N> / cs<N>Label entries for N in 7..22.
    The base CEF spec defines cs1-cs6 (covered in v0.17.11). Some
    vendors (Claroty, FireEye HX) extend the range."""
    out: dict[str, str] = {}
    for n in range(7, 23):
        out[f"cs{n}"] = f"Device custom string {n} (see cs{n}Label)"
        out[f"cs{n}Label"] = f"Label/name for cs{n}"
        # Also handle lowercase variants since some vendors use them
        out[f"cs{n}label"] = f"Label/name for cs{n}"
    # cs1-cs6 lowercase labels (Claroty uses 'cs1label' lowercase)
    for n in range(1, 7):
        out[f"cs{n}label"] = f"Label/name for cs{n}"
    return out


# Vendor → field → description
DICTS: dict[str, dict[str, str]] = {
    "Claroty": _extended_cef_dict(),

    "Mimecast": {
        # Standard SIEM fields
        "Act": "Action taken on the email (Acc/Hld/Rjt/Bnc/...)",
        "Action": "Action taken on the email",
        "datetime": "Event datetime",
        "eventTime": "Event time (UTC)",
        "eventInfo": "Event info / message",
        "timestamp": "Event timestamp",
        "IP": "Source IP",
        "SourceIP": "Source IP",
        "Rcpt": "Recipient email address",
        "Recipient": "Recipient email address",
        "Sender": "Sender email address",
        "Subject": "Email subject",
        "MsgId": "Mimecast message id",
        "Virus": "Virus / malware name",
        "AttNames": "Attachment file names",
        "fileExt": "File extension",
        "fileMime": "File MIME type",
        "md5": "Attachment MD5 hash",
        "sha256": "Attachment SHA-256 hash",
        "ScanResultInfo": "Scan result detail",
        "xsiem_classifier": "Mimecast XSIEM event classifier",
        # Audit fields
        "category": "Event category",
        "auditType": "Audit type",
        "user": "User who performed the action",
        "id": "Event id",
        "acc": "Account id",
        "aCode": "Audit code",
    },

    "Trend Micro": {
        # Vision One
        "entityName": "Entity name (host/user/app)",
        "deviceMacAddress": "Device MAC address",
        "endpointMacAddress": "Endpoint MAC address",
        "hostName": "Hostname",
        "interestedMacAddress": "Subject MAC address (of interest)",
        "mDevice": "Managed device id",
        "mitreMapping": "MITRE ATT&CK mapping",
        "objectName": "Object name (file/process/registry)",
        "processCmd": "Process command line",
        "processName": "Process name",
        "pver": "Product version",
        "rt_utc": "Receipt time (UTC)",
        "score": "Risk / detection score",
        "severity": "Severity",
        "impactScope": "Impact scope",
        "indicators": "IoC indicators",
        "investigationResult": "Investigation result",
        "malName": "Malware name",
        # Email Security
        "action": "Action taken (allow/block/quarantine)",
        "sender": "Email sender",
        "genTime": "Event generation time",
        "logType": "Log type",
        "recipient": "Email recipient",
        "domainName": "Domain name",
        "policyAction": "Policy action applied",
        "attachments": "Attachment names",
        "recipients": "Email recipients",
        "deliveryTime": "Email delivery time",
        "embeddedUrls": "URLs embedded in the email",
        # Deep Security
        "cefVersion": "CEF format version",
        "result": "Operation result",
        "TrendMicroDsCve": "Trend Micro Deep Security CVE id",
        "TrendMicroDsMitre": "Trend Micro Deep Security MITRE id",
        "TrendMicroDsMalwareTarget": "Trend Micro Deep Security malware target",
        "TrendMicroDsMalwareTargetType": "Trend Micro Deep Security malware target type",
        "TrendMicroDsTags": "Trend Micro Deep Security tags",
    },

    "FireEye": {
        "event_values": "FireEye event values (key-value extras)",
        "condition": "Detection condition / rule",
        "categoryTupleDescription": "FireEye event category tuple description",
        "cefVersion": "CEF format version",
        # cs7-cs10 are handled by the extended CEF dict but FireEye may
        # use them with specific semantics — include them explicitly
        "cs7": "Device custom string 7 (see cs7Label)",
        "cs7Label": "Label/name for cs7",
        "cs8": "Device custom string 8 (see cs8Label)",
        "cs8Label": "Label/name for cs8",
        "cs9": "Device custom string 9 (see cs9Label)",
        "cs9Label": "Label/name for cs9",
        "cs10": "Device custom string 10 (see cs10Label)",
        "cs10Label": "Label/name for cs10",
    },
}


def main() -> int:
    print("=== v0.17.16 Phase 4e — Trend Micro + Claroty + FireEye + Mimecast ===\n")
    import yaml
    total_filled = 0
    yamls_modified = 0
    stats_per_vendor: Counter[str] = Counter()

    for ds_dir in sorted(BUNDLE_ROOT.glob("*/")):
        yaml_path = ds_dir / "data_source.yaml"
        if not yaml_path.is_file():
            continue
        d = yaml.safe_load(yaml_path.read_text()) or {}
        vendor = d.get("vendor")
        if vendor not in DICTS:
            continue
        vdict = DICTS[vendor]
        fields = d.get("fields") or []
        any_changed = False
        new_fields: list[dict[str, Any]] = []
        for f in fields:
            if not isinstance(f, dict):
                new_fields.append(f)
                continue
            if (f.get("description") or "").strip():
                new_fields.append(f)
                continue
            name = f.get("name")
            desc = vdict.get(name) if name else None
            if desc:
                nf = dict(f)
                nf["description"] = desc
                new_fields.append(nf)
                total_filled += 1
                stats_per_vendor[vendor] += 1
                any_changed = True
            else:
                new_fields.append(f)
        if any_changed:
            ok, msg = update_one_yaml(yaml_path, new_fields)
            if ok:
                yamls_modified += 1

    print(f"  Total filled    : {total_filled}")
    print(f"  YAMLs modified  : {yamls_modified}")
    for v, c in stats_per_vendor.most_common():
        print(f"    {v:20s} {c}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
