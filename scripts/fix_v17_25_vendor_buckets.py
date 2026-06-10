"""v0.17.27 — fix v0.17.25's pack→vendor bucketing.

The v0.17.25 migration (`scripts/migrate_missing_packs.py`) set
`vendor: <pack_name>` for every new YAML when vendor_map.yaml had no
entry for that pack. Result: F5LTM/F5APM/F5BigIPAWAF show up as their
own isolated cards instead of grouping under F5; Apache* under Apache;
Cisco* under Cisco; etc.

Also: the migration set `is_rawlog_only: true` for packs with no
modeling-rule schema, but many of those packs DO have schema-derived
fields populated from the .xif alter-intermediate extraction in v0.17.24.
Anything with fields[] populated should be `is_rawlog_only: false` so it
shows in the default Browse view (which filters out rawlog-only by
default).

This script:
  1. Reads every bundles/spark/data-sources/*/data_source.yaml.
  2. If `vendor:` matches a known mis-bucketed pack pattern, rewrites
     to the canonical vendor display name.
  3. If `is_rawlog_only: true` AND fields[] has at least 1 entry,
     flips to `is_rawlog_only: false`.
  4. Reports what it changed, doesn't touch anything else.

Idempotent: running twice = no-op the second time.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_SOURCES_DIR = REPO_ROOT / "bundles" / "spark" / "data-sources"

# ─── Canonical vendor map ──────────────────────────────────────────────
#
# The KEY is the `vendor:` string the v0.17.25 migration wrote (which
# equals the pack name). The VALUE is the canonical vendor display name
# (which becomes vendor_key after _slugify+lowercase, and groups all
# packs of that vendor into one card).
#
# Mapping rules:
#   - "F5*"      → "F5"             (LTM, APM, BigIPAWAF, ASM)
#   - "Apache*"  → "Apache"         (Tomcat, WebServer)
#   - "Cisco*"   → "Cisco"          (ASR, ISR, SMA, Nexus, etc.)
#   - "Brocade*" → "Brocade"
#   - "Microsoft*" → "Microsoft"    (NPS, WSUS, ECM, IIS)
#   - "Symantec*" → "Symantec"
#   - "VMware*"  → "VMware"
#   - "Beyond*"  → "BeyondTrust"
#   - "Tanium*"  → "Tanium"
#   - "Thinkst*" → "Thinkst"
#   - "Okta*"    → "Okta"
#   - "Ivanti*"  → "Ivanti"
#   - "Juniper*" → "Juniper"
#   - "McAfee*"  → "McAfee"
#   - "Barracuda*" → "Barracuda"
#   - "MySQL*"   → "MySQL"
#   - "Citrix*"  → "Citrix"
#   - … plus standalone vendors not following a pattern (Kubernetes, Squid, etc.)

VENDOR_REBUCKET = {
    # F5 family — operator's primary complaint
    "F5LTM": "F5",
    "F5APM": "F5",
    "F5BigIPAWAF": "F5",
    "F5ASM": "F5",
    # Apache family
    "ApacheTomcat": "Apache",
    "ApacheWebServer": "Apache",
    # Cisco family (large)
    "CiscoASR": "Cisco",
    "CiscoISR": "Cisco",
    "CiscoSMA": "Cisco",
    "CiscoNexus": "Cisco",
    "Cisco_Wireless_LAN_Controller": "Cisco",
    "IronPort": "Cisco",  # IronPort is a Cisco brand
    # Microsoft family
    "MicrosoftNPS": "Microsoft",
    "MicrosoftWSUS": "Microsoft",
    "MicrosoftECM": "Microsoft",
    "MicrosoftIISWebServer": "Microsoft",
    # Symantec family
    "SymantecDLP": "Symantec",
    "SymantecEndpointProtection": "Symantec",
    "SymantecCloudSecureWebGateway": "Symantec",
    # VMware family
    "VMwareVCenter": "VMware",
    "VMwareESXi": "VMware",
    # Brocade
    "BrocadeSwitch": "Brocade",
    # BeyondTrust family
    "BeyondTrustPrivilegedRemoteAccess": "BeyondTrust",
    "BeyondTrustRemoteSupport": "BeyondTrust",
    "BeyondTrust_Password_Safe": "BeyondTrust",
    # Tanium
    "Tanium": "Tanium",
    "TaniumThreatResponse": "Tanium",
    # Okta
    "OktaOAG": "Okta",
    # Ivanti family
    "IvantiConnectSecure": "Ivanti",
    "IvantiPulseSecureVTM": "Ivanti",
    # Juniper
    "JuniperSRX": "Juniper",
    # McAfee family
    "McAfeeWebGateway": "McAfee",
    "McAfeeNSM": "McAfee",
    # Barracuda family
    "BarracudaWAF": "Barracuda",
    "BarracudaEmailProtection": "Barracuda",
    # MySQL
    "MySQLEnterprise": "MySQL",
    # Citrix
    "CitrixADC": "Citrix",
    # NGINX
    "NGINXWebServer": "NGINX",
    # Thinkst
    "ThinkstCanary": "Thinkst",
    # Tableau
    "Tableau": "Tableau",
    # Radware
    "RadwareCloudServices": "Radware",
    # SonicWall
    "SonicWallNSv": "SonicWall",
    # RSA
    "RSASecureID": "RSA",
    # ManageEngine
    "ManageEngine-ADManager": "ManageEngine",
    # Cisco network/identity (kebab-case variants from upstream)
    "cisco-meraki": "Cisco",
    "cisco-ise": "Cisco",
    # Other vendors mistakenly bucketed under their full pack name
    "AristaSwitch": "Arista",
    "HuaweiNetworkDevices": "Huawei",
    "HPESwitch": "HPE",
    "DellEMCUnity": "Dell EMC",
    "BluecatAddressManager": "Bluecat",
    "AvayaAuraCommunicationManager": "Avaya",
    "ClearswiftDLP": "Clearswift",
    "FortiManager": "Fortinet",
    "Siemens_SiPass": "Siemens",
    "SemperisDSP": "Semperis",
    "SecureAuthIdentityPlatform": "SecureAuth",
    "TigeraCalico": "Tigera",
    "TrendMicroInterScanWebSecurity": "Trend Micro",
    "HashiCorp-Vault": "HashiCorp",
    "IBM_AIX": "IBM",
    "MacOS": "Apple",
    "AWS_ELB": "Amazon",
    "AWSCloudTrail": "Amazon",
    # Genuinely standalone (don't change, but list for clarity)
    "Kubernetes": "Kubernetes",
    "Kiteworks": "Kiteworks",
    "Squid": "Squid",
    "Auditd": "Linux",
    "Infoblox": "Infoblox",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Report changes without writing")
    args = ap.parse_args()

    if not DATA_SOURCES_DIR.is_dir():
        print(f"ERROR: {DATA_SOURCES_DIR} not found")
        return 1

    vendor_changes: list[tuple[str, str, str]] = []  # (dir, old, new)
    rawlog_flips: list[tuple[str, int]] = []          # (dir, field_count)

    for d in sorted(DATA_SOURCES_DIR.iterdir()):
        if not d.is_dir():
            continue
        yaml_path = d / "data_source.yaml"
        if not yaml_path.is_file():
            continue
        try:
            doc = yaml.safe_load(yaml_path.read_text())
        except Exception as exc:
            print(f"  ⚠ skip {d.name}: {exc}")
            continue
        if not isinstance(doc, dict):
            continue

        changed = False

        # Fix 1: rebucket vendor
        current_vendor = doc.get("vendor")
        if current_vendor in VENDOR_REBUCKET:
            canonical = VENDOR_REBUCKET[current_vendor]
            if current_vendor != canonical:
                vendor_changes.append((d.name, current_vendor, canonical))
                doc["vendor"] = canonical
                changed = True

        # Fix 2: un-flag is_rawlog_only when fields[] populated
        if doc.get("is_rawlog_only") is True:
            fields = doc.get("fields") or []
            if len(fields) >= 1:
                rawlog_flips.append((d.name, len(fields)))
                doc["is_rawlog_only"] = False
                changed = True

        if changed and not args.dry_run:
            # Preserve file shape: dump back via yaml with default style
            # and explicit unicode-safe text.
            with yaml_path.open("w", encoding="utf-8") as f:
                yaml.safe_dump(doc, f, default_flow_style=False, sort_keys=False, allow_unicode=True, width=120)

    print(f"\n=== Vendor rebucketing ({len(vendor_changes)} changes) ===")
    for d, old, new in vendor_changes:
        print(f"  {d:60s}  {old!r:30s} → {new!r}")

    print(f"\n=== is_rawlog_only flips ({len(rawlog_flips)} changes) ===")
    for d, n in rawlog_flips[:20]:
        print(f"  {d:60s}  fields={n}")
    if len(rawlog_flips) > 20:
        print(f"  ... + {len(rawlog_flips) - 20} more")

    if args.dry_run:
        print("\n(dry-run; no files written)")
    else:
        print(f"\nWrote {len(vendor_changes) + len(rawlog_flips)} YAML files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
