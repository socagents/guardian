#!/usr/bin/env python3
"""v0.17.17 Phase 4f — Cloudflare + Workday + Oracle + Palo Alto Networks.

# Sources

* Cloudflare WAF Logpush field reference:
  https://developers.cloudflare.com/logs/reference/log-fields/zone/http_requests/
* Cloudflare Zero Trust Audit Logs:
  https://developers.cloudflare.com/cloudflare-one/insights/logs/audit-logs/
* Workday Auth Logs schema (HR Tenant):
  https://doc.workday.com/admin-guide/en-us/security/auditing/sg
* Oracle Identity Audit Framework (IAU_* prefix):
  https://docs.oracle.com/en/middleware/idm/access-manager/audit-events.html
* Oracle Database Unified Auditing:
  https://docs.oracle.com/en/database/oracle/oracle-database/19/dbseg/auditing-the-database.html
* Palo Alto Prisma Cloud Compute Defender event schema:
  https://docs.prismacloud.io/en/compute-edition/30/api/events
* Palo Alto Prisma Cloud alert schema:
  https://prisma.pan.dev/api/cloud/cspm/alerts
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


DICTS: dict[str, dict[str, str]] = {
    "Cloudflare": {
        # WAF / HTTP request fields
        "EdgeResponseBytes": "Bytes returned to the client by the edge",
        "EdgePathingOp": "Edge pathing operation (request handling stage)",
        "EdgeServerIP": "Cloudflare edge server IP",
        "OriginIP": "Origin server IP",
        "EdgeResponseStatus": "Edge HTTP response status",
        "OriginResponseStatus": "Origin HTTP response status",
        "ClientRequestMethod": "Client HTTP request method",
        "ClientASN": "Client autonomous system number",
        "ClientCountry": "Client country code",
        "ClientDeviceType": "Client device type (desktop/mobile/tablet)",
        "ClientRegionCode": "Client region/state code",
        "ClientRequestBytes": "Bytes received from client",
        "ClientRequestHost": "HTTP Host header",
        "ClientRequestScheme": "Request scheme (http/https)",
        "ClientRequestURI": "Request URI",
        "ClientRequestReferer": "HTTP Referer header",
        "ClientRequestUserAgent": "HTTP User-Agent header",
        "ClientSSLCipher": "TLS cipher suite",
        "ClientSSLProtocol": "TLS protocol version",
        "ClientSrcPort": "Client source port",
        "RayID": "Cloudflare RayID (request trace id)",
        "RequestHeaders": "HTTP request headers (JSON)",
        "WAFAttackScore": "Cloudflare WAF attack score",
        "ZoneName": "Cloudflare zone (domain) name",
        "securityaction": "WAF security action taken",
        "edgeendtimestamp": "Edge response end timestamp",
        "Datetime": "Event datetime",
        # Zero Trust audit
        "ip_address": "Source IP",
        "metadata": "Event metadata (JSON)",
        "newValue": "New value (after change)",
        "newValueJson": "New value as JSON",
        "oldValue": "Old value (before change)",
        "oldValueJson": "Old value as JSON",
    },

    "Workday": {
        "ipAddress": "Client IP address",
        "requestTime": "Request time (UTC)",
        "access_restriction_reference": "Workday access restriction reference",
        "Account_Disabled_or_Expired": "Whether account was disabled or expired",
        "api_client_id": "API client id used for request",
        "authentication_channel": "Authentication channel (Web/API/Mobile)",
        "authentication_failure_message": "Authentication failure reason",
        "authentication_type": "Authentication type (Password/SAML/MFA)",
        "browser_type": "Browser type/name",
        "Device_is_Trusted": "Whether device is trusted",
        "device_type_reference": "Workday device type reference",
        "Failed_Signon": "Whether sign-on failed",
        "Forgotten_Password_Reset_Request": "Whether this is a forgotten-password reset request",
        "Has_Grace_Period_for_MFA": "Whether MFA grace period applies",
        "Invalid_for_Authentication_Channel": "Whether signon was invalid for channel",
        "Invalid_for_Authentication_Policy": "Whether signon was invalid per policy",
        "Invalid_Credentials": "Whether credentials were invalid",
        "location": "Geographic location",
        "MFA_Authentication_Exempt": "Whether MFA was exempted",
        "multi_factor_authentication_type_reference": "MFA type used (TOTP/Push/SMS)",
        "operating_system": "Client operating system",
        "Password_Changed": "Whether password was changed during signon",
        "Required_Password_Change": "Whether a password change is required",
        "Requires_MFA": "Whether MFA is required",
        "saml_identity_provider_reference": "SAML identity provider reference",
        "short_session_id": "Workday short session id",
        "signon_datetime": "Sign-on datetime (UTC)",
        "signoff_datetime": "Sign-off datetime (UTC)",
        "signon_ip_address": "Sign-on IP address",
        "Successful": "Whether signon succeeded",
        "Tenant_Access_Read_Only": "Whether tenant access was read-only",
        "tls_version": "TLS version negotiated",
        "user_name": "Workday username",
    },

    "Oracle": {
        # Oracle Identity Audit (IAU_*) - Oracle IAM
        "IAU_DOMAINNAME": "Oracle domain name",
        "IAU_HOSTID": "Audit host id",
        "IAU_HOSTNWADDR": "Audit host network address",
        "IAU_TSTZORIGINATING": "Originating event timestamp with timezone",
        "IAU_REMOTEIP": "Remote client IP",
        "IAU_FAILURECODE": "Failure code (if any)",
        "IAU_COMPONENTID": "Component id (Oracle component generating event)",
        "IAU_COMPONENTNAME": "Component name",
        "IAU_CONTEXTFIELDS": "Audit context fields (JSON)",
        "IAU_HOMEINSTANCE": "Home Oracle instance",
        "IAU_ROLES": "User roles at time of event",
        "IAU_APPLICATIONDOMAINNAME": "Application domain name",
        "IAU_AUTHENTICATIONSCHEMEID": "Authentication scheme id",
        "IAU_ADDITIONALINFO": "Additional audit info",
        "IAU_USERID": "User id performing the action",
        "IAU_REQUESTID": "Request id (audit correlation)",
        "IAU_OLDSETTINGS": "Old settings (before change)",
        "IAU_NEWSETTINGS": "New settings (after change)",
        "IAU_CLIENTIPADDRESS": "Client IP address",
        "IAU_EVENTSTATUS": "Event status (success/failure)",
        # Oracle Database Unified Auditing
        "EVENT_TIMESTAMP_UTC": "Event timestamp (UTC)",
        "ACTION_NAME": "Database action name (SELECT/UPDATE/DELETE/...)",
        "OS_USERNAME": "OS username invoking the database session",
        "SQL_TEXT": "SQL statement text",
        "USERHOST": "Host from which the user connected",
        "AUTHENTICATION_TYPE": "Authentication type (password/external/proxy)",
        "CLIENT_PROGRAM_NAME": "Client program name (sqlplus/SQLDeveloper/etc.)",
        "SESSIONID": "Oracle database session id",
        # Oracle Cloud Infrastructure
        "eventTime": "Event time (UTC)",
    },

    "Palo Alto Networks": {
        # Prisma Cloud Compute (Defender / runtime)
        "image": "Container image",
        "imageID": "Container image id (SHA)",
        "tags": "Resource tags",
        "provider": "Cloud provider",
        "osDistro": "OS distribution",
        "runtime": "Container runtime (docker/containerd/cri-o)",
        "appID": "Application id",
        "aggregated": "Whether events were aggregated",
        "rest": "REST API call detail",
        "forensics": "Forensic evidence captured",
        "cluster": "Kubernetes cluster name",
        "complianceIssues": "Compliance issues detected",
        "dropped": "Whether the event was dropped",
        "namespaces": "Kubernetes namespaces involved",
        "accountIDs": "Cloud account ids involved",
        "time": "Event time",
        # Prisma Cloud (CSPM alert schema)
        "alertAdditionalInfo": "Alert additional info (JSON)",
        "policy": "Policy that triggered the alert",
        "policyId": "Policy id",
        "resource": "Cloud resource targeted",
        "alertTime": "Alert generation time",
        # Prisma SaaS Security
        "timestamp": "Event timestamp",
        "admin_role": "Admin role",
        "source_ip": "Source IP",
        "target_name": "Target name",
        "_reporting_device_ip": "Reporting device IP",
    },
}


def main() -> int:
    print("=== v0.17.17 Phase 4f — CF + Workday + Oracle + PAN ===\n")
    import yaml
    total_filled = 0
    yamls_modified = 0
    stats: Counter[str] = Counter()

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
                stats[vendor] += 1
                any_changed = True
            else:
                new_fields.append(f)
        if any_changed:
            ok, msg = update_one_yaml(yaml_path, new_fields)
            if ok:
                yamls_modified += 1

    print(f"  Total filled    : {total_filled}")
    print(f"  YAMLs modified  : {yamls_modified}")
    for v, c in stats.most_common():
        print(f"    {v:25s} {c}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
