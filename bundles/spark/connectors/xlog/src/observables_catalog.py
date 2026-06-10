"""MCP tools for generating observables and technology stack configuration."""

import json
import logging
from typing import Any, Dict, List, Optional

from fastmcp import Context
from pydantic import BaseModel, Field, field_validator

from config.config import get_config
from ._graphql_client import PhantomGraphQLClient
from ._xlog_url_resolver import resolve_xlog_url

logger = logging.getLogger("Phantom MCP")


class GenerateObservablesRequest(BaseModel):
    """Request model for generating observables from threat intel feeds."""

    count: int = Field(
        default=10,
        description="Number of observables to generate. Example: 10",
        ge=1,
        le=1000,
    )
    observable_type: str = Field(
        description=(
            "Type of observable to generate. Must be one of: IP, URL, SHA256, CVE, TERMS. "
            "- IP: Malicious/benign IP addresses from threat intel feeds\n"
            "- URL: Malicious/benign URLs\n"
            "- SHA256: File hashes (malware samples or known-good files)\n"
            "- CVE: CVE identifiers\n"
            "- TERMS: Security-related search terms (MITRE techniques, threat names)"
        )
    )
    known: str = Field(
        default="BAD",
        description=(
            "Whether to generate known-malicious or known-benign observables. "
            "Must be one of: BAD, GOOD. "
            "- BAD: Known malicious indicators (default)\n"
            "- GOOD: Known benign/safe indicators"
        )
    )


async def phantom_generate_observables(
    *,
    observable_type: str,
    count: int = 10,
    known: str = "BAD",
    ctx: Context = None,
) -> Dict[str, Any]:
    """
    Generate observables (IPs, URLs, hashes, CVEs, terms) from threat intelligence feeds.

    This tool leverages rosetta-ce's Observables.generator() to fetch real indicators
    from curated threat intel sources. If sources are unavailable, it falls back to
    generating realistic fake values.

    Use cases:
    - Generate malicious IPs for testing detection rules
    - Create realistic threat scenarios with known-bad URLs
    - Populate test environments with sample IOCs
    - Generate benign indicators for allowlist testing

    Args:
        request: Request containing count, observable_type, and known status
        ctx: MCP context

    Returns:
        Dictionary containing:
        - observables: List of generated observable values
        - observable_type: The type of observables generated
        - known: Whether they are BAD (malicious) or GOOD (benign)
        - count: Number of observables returned

    Example Request:
        {
          "count": 10,
          "observable_type": "IP",
          "known": "BAD"
        }

    Example Response:
        {
          "observables": ["192.168.1.100", "10.0.0.50", ...],
          "observable_type": "ip",
          "known": "bad",
          "count": 10
        }
    """
    # v0.17.114 (#111) — signature flattened from (request:
    # GenerateObservablesRequest) to flat kwargs so the agent's MCP-proxy layer
    # (which sends FLAT arguments per connector.yaml spec.tools[].args) reaches
    # this tool. The body keeps using `request.X` accessors by rebuilding the
    # model from the kwargs; the Pydantic model still validates types/bounds on
    # construction.
    request = GenerateObservablesRequest(
        count=count,
        observable_type=observable_type,
        known=known,
    )
    # Validate observable_type
    valid_types = ["IP", "URL", "SHA256", "CVE", "TERMS"]
    observable_type = request.observable_type.upper()
    if observable_type not in valid_types:
        return {
            "error": f"Invalid observable_type '{request.observable_type}'. Must be one of: {', '.join(valid_types)}",
            "valid_types": valid_types,
        }

    # Validate known
    valid_known = ["BAD", "GOOD"]
    known = request.known.upper()
    if known not in valid_known:
        return {
            "error": f"Invalid known value '{request.known}'. Must be one of: {', '.join(valid_known)}",
            "valid_known": valid_known,
        }

    # Build GraphQL query
    query = """
    query GenerateObservables($input: GenerateObservablesInput!) {
        generateObservables(requestInput: $input) {
            observables
            observableType
            known
            count
        }
    }
    """

    variables = {
        "input": {
            "count": request.count,
            "observableType": observable_type,
            "known": known,
        }
    }

    try:
        client = PhantomGraphQLClient(resolve_xlog_url(ctx))
        result = await client.execute_query(query, variables)

        logger.info(
            f"Generated {result.get('generateObservables', {}).get('count', 0)} {observable_type} observables (known={known})"
        )
        return result.get("generateObservables", {})

    except Exception as e:
        logger.error(f"Error generating observables: {e}")
        return {"error": str(e), "query": query, "variables": variables}


_TECH_STACK_QUERY = """
query TechnologyStack {
  technologyStack {
    stackName
    logDestination {
      type
      protocol
      host
      port
      fullAddress
    }
    vendors {
      vendor
      product
      category
      formats
      description
    }
    totalVendors
    configured
    updatedAt
    source
  }
}
"""


def _camel_dest_to_snake(dest: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The xlog GraphQL response uses camelCase field names (Strawberry's
    default). The MCP tool's documented response shape is snake_case
    (preserving the env-var JSON convention). Translate one to the other
    so consumers don't see two different shapes depending on which
    backend served the request."""
    if not dest:
        return None
    return {
        "type": dest.get("type"),
        "protocol": dest.get("protocol"),
        "host": dest.get("host"),
        "port": dest.get("port"),
        "full_address": dest.get("fullAddress"),
    }


def _format_response(
    payload: Dict[str, Any], message: Optional[str] = None
) -> Dict[str, Any]:
    """Shape the response for the agent. Keeps backwards compatibility
    with the previous env-var-only implementation: snake_case keys,
    `configured` boolean, optional `message` when not configured."""
    response: Dict[str, Any] = {
        "stack_name": payload.get("stackName") or payload.get("stack_name"),
        "log_destination": (
            _camel_dest_to_snake(payload.get("logDestination"))
            if "logDestination" in payload
            else payload.get("log_destination")
        ),
        "vendors": payload.get("vendors") or [],
        "total_vendors": int(
            payload.get("totalVendors")
            if payload.get("totalVendors") is not None
            else payload.get("total_vendors") or 0
        ),
        "configured": bool(payload.get("configured", False)),
        "updated_at": payload.get("updatedAt") or payload.get("updated_at"),
        "source": payload.get("source") or "default",
    }
    if message:
        response["message"] = message
    return response


def _env_fallback_stack() -> Optional[Dict[str, Any]]:
    """Parse the MCP-side TECHNOLOGY_STACK env var if xlog isn't
    reachable. This is the same fallback xlog itself uses, mirrored
    here so that an MCP that can't reach xlog still serves a useful
    answer instead of silently degrading."""
    cfg = get_config()
    raw = (cfg.technology_stack or "").strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("MCP-side TECHNOLOGY_STACK not valid JSON: %s", exc)
        return None
    if not isinstance(parsed, dict):
        return None
    vendors = parsed.get("vendors") or []
    if not isinstance(vendors, list):
        vendors = []
    return {
        "stack_name": parsed.get("stack_name"),
        "log_destination": parsed.get("log_destination"),
        "vendors": vendors,
        "total_vendors": len(vendors),
        "configured": bool(parsed.get("stack_name") or vendors),
        "updated_at": None,
        "source": "env",
    }


async def phantom_get_technology_stack(ctx: Context) -> Dict[str, Any]:
    """
    Get the organization's custom technology stack configuration.

    Reads from xlog (the source of truth), falling back to the MCP-side
    `TECHNOLOGY_STACK` env var if xlog can't be reached. xlog itself
    layers its own lookup: sqlite singleton (operator-set via the
    `phantom_update_technology_stack` tool) → its own
    `TECHNOLOGY_STACK` env var → empty.

    Use this BEFORE generating logs to discover which vendors/products
    the org has deployed; match `vendor` × `product` × `formats` when
    calling `phantom_create_data_worker`. If `log_destination` is set,
    use `log_destination.full_address` as the default sink unless the
    user explicitly asks for a different destination.

    Returns:
        Dictionary with:
        - stack_name (str|null): Operator-chosen label
        - log_destination (object|null): Default sink — type, protocol,
          host, port, full_address
        - vendors (list): Each entry has vendor, product, category,
          formats (list of log formats), description
        - total_vendors (int): Count
        - configured (bool): True iff a stack_name OR vendors are set
        - updated_at (str|null): ISO8601 timestamp of last update
        - source (str): "manual" (operator-set in xlog), "env" (legacy
          env-var fallback), or "default" (no stack configured)
        - message (str): Only present when configured=False, describes
          how to set up a stack

    Example (configured):
        {
            "stack_name": "Enterprise SOC Stack",
            "log_destination": {
                "type": "syslog", "protocol": "udp",
                "host": "10.10.0.8", "port": 514,
                "full_address": "udp:10.10.0.8:514"
            },
            "vendors": [
                {"vendor": "F5", "product": "ASM", "category": "WAF",
                 "formats": ["CEF", "JSON"], "description": "WAF"}
            ],
            "total_vendors": 1,
            "configured": true,
            "updated_at": "2026-04-30T12:00:00Z",
            "source": "manual"
        }
    """
    # Try xlog GraphQL first. This is the source of truth — operators
    # update it via the mutation and it survives MCP restarts.
    try:
        client = PhantomGraphQLClient(resolve_xlog_url(ctx))
        result = await client.execute_query(_TECH_STACK_QUERY)
        payload = result.get("technologyStack")
        if payload is not None:
            response = _format_response(payload)
            if not response["configured"]:
                response["message"] = (
                    "No technology stack configured. Use the "
                    "`phantom_update_technology_stack` tool to set one, "
                    "or set the TECHNOLOGY_STACK env var on xlog/MCP."
                )
            logger.info(
                "Technology stack via xlog: name=%s vendors=%d source=%s",
                response.get("stack_name"),
                response.get("total_vendors"),
                response.get("source"),
            )
            return response
    except Exception as exc:  # pragma: no cover - covered by fallback path
        logger.warning("xlog tech-stack query failed (%s); falling back", exc)

    # Fallback: MCP-side env var. Lets a degraded deploy still answer.
    env_stack = _env_fallback_stack()
    if env_stack is not None:
        logger.info(
            "Technology stack via MCP env-var fallback: name=%s vendors=%d",
            env_stack.get("stack_name"),
            env_stack.get("total_vendors"),
        )
        return _format_response(env_stack)

    return _format_response(
        {
            "stackName": None,
            "logDestination": None,
            "vendors": [],
            "totalVendors": 0,
            "configured": False,
            "updatedAt": None,
            "source": "default",
        },
        message=(
            "No technology stack configured. Use the "
            "`phantom_update_technology_stack` tool to set one — "
            "the agent can call it directly when the operator says "
            "things like 'use Fortinet for firewalls' or 'add "
            "CrowdStrike Falcon as our EDR'."
        ),
    )


# ─── Update tool ─────────────────────────────────────────────────────


class _LogDestinationModel(BaseModel):
    """Default log destination — where simulated logs get sent unless
    the operator overrides at worker-creation time."""

    type: str = Field(
        description=(
            "Sink type. One of: 'syslog' (UDP/TCP to a host:port), "
            "'webhook' (HTTPS POST), 'file' (local path on xlog). "
            "Most SOC sims use 'syslog'."
        )
    )
    protocol: Optional[str] = Field(
        default=None,
        description=(
            "Transport for syslog ('udp' or 'tcp'). Required when "
            "type='syslog'."
        ),
    )
    host: Optional[str] = Field(
        default=None,
        description="IP or hostname for syslog/webhook sinks.",
    )
    port: Optional[int] = Field(
        default=None,
        description="Port number for syslog/webhook sinks.",
    )
    full_address: Optional[str] = Field(
        default=None,
        description=(
            "Convenience string in the form 'protocol:host:port' (e.g. "
            "'udp:10.10.0.8:514'). If omitted, xlog will derive it from "
            "protocol/host/port. The agent reads this when calling "
            "phantom_create_data_worker as the default destination."
        ),
    )


class _VendorEntryModel(BaseModel):
    """One vendor/product combo the org has deployed. Generated logs
    will favor these vendors when no other override is given."""

    vendor: str = Field(
        description=(
            "Vendor name as it should appear in generated log lines. "
            "Use the canonical name (e.g. 'Fortinet', not 'FortiNet')."
        )
    )
    product: str = Field(
        description=(
            "Product name (e.g. 'FortiGate', 'Falcon', 'Splunk Enterprise')."
        )
    )
    category: str = Field(
        description=(
            "Device class. Common values: Firewall, IDS/IPS, WAF, EDR, "
            "EPP, VPN, Proxy, DNS, DHCP, Identity, MDM, DLP, NDR, "
            "Email Gateway, Vuln Management, SIEM, SOAR. Use whatever "
            "the operator's org calls this category — phantom doesn't "
            "validate it against a closed list."
        )
    )
    formats: List[str] = Field(
        description=(
            "Log formats this product supports. Phantom generates one "
            "of: 'JSON', 'CEF', 'LEEF', 'SYSLOG', 'WINEVENT'. Include "
            "every format the org actually ingests for this product so "
            "the agent can pick a compatible one. At least one entry "
            "is required."
        )
    )
    description: Optional[str] = Field(
        default=None,
        description=(
            "Free-form one-liner the agent can surface to the operator "
            "when it picks this vendor. Optional but improves UX."
        ),
    )

    @field_validator("formats")
    @classmethod
    def _formats_nonempty(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError(
                "vendor.formats must contain at least one log format "
                "(e.g. 'JSON', 'CEF', 'LEEF', 'SYSLOG', 'WINEVENT')"
            )
        return v


class UpdateTechnologyStackRequest(BaseModel):
    """Full-replacement payload for the org's technology stack.

    The mutation is a complete overwrite — `vendors` replaces the entire
    existing list, not a merge. To add a vendor, fetch the current stack
    via `phantom_get_technology_stack`, append the new entry, then call
    update with the combined list.
    """

    stack_name: str = Field(
        description=(
            "Operator-chosen label for the stack (e.g. 'Acme SOC Q2', "
            "'Lab Tier 1'). Shown in the MCP UI and in the agent's "
            "system context."
        ),
        min_length=1,
    )
    vendors: List[_VendorEntryModel] = Field(
        description=(
            "Vendor/product entries. Must include at least one. Each "
            "entry needs vendor, product, category, and formats."
        ),
        min_length=1,
    )
    log_destination: Optional[_LogDestinationModel] = Field(
        default=None,
        description=(
            "Default log destination for generated workers. If omitted, "
            "phantom_create_data_worker callers must specify a "
            "destination per-call."
        ),
    )


_UPDATE_TECH_STACK_MUTATION = """
mutation UpdateTechnologyStack($stack: TechnologyStackInput!) {
  updateTechnologyStack(stack: $stack) {
    stackName
    logDestination {
      type
      protocol
      host
      port
      fullAddress
    }
    vendors {
      vendor
      product
      category
      formats
      description
    }
    totalVendors
    configured
    updatedAt
    source
  }
}
"""


async def phantom_update_technology_stack(
    *,
    stack_name: str,
    vendors: List[_VendorEntryModel],
    log_destination: Optional[_LogDestinationModel] = None,
    ctx: Context = None,
) -> Dict[str, Any]:
    """
    Replace the org's technology stack with the given catalog.

    USE THIS TOOL WHEN the operator describes their environment in
    natural language and you need to teach phantom what's actually
    deployed. Examples that should trigger this tool:

      - "We use Fortinet FortiGate for firewalls and CrowdStrike
         Falcon for EDR; send all logs to udp:10.10.0.8:514"
      - "Add Microsoft Defender for Endpoint as another EDR"
      - "Reset our stack to just Palo Alto for everything"

    BEFORE calling, ALWAYS call `phantom_get_technology_stack` first
    if the operator asked to ADD or REMOVE a vendor — the mutation is
    a full overwrite, so you need the current list to compose the new
    one. Skip the read only when the operator is explicitly REPLACING
    the entire stack.

    YOU MUST PASS the complete payload — `stack_name` and a non-empty
    `vendors` list with vendor, product, category, and at least one
    format per entry. Phantom rejects partial payloads.

    REQUIRED JSON SCHEMA (exact field names, snake_case):
    {
      "stack_name": "Enterprise SOC",
      "log_destination": {                  // optional
        "type": "syslog",                   // syslog | webhook | file
        "protocol": "udp",                  // udp | tcp | https
        "host": "10.10.0.8",
        "port": 514,
        "full_address": "udp:10.10.0.8:514" // auto-derived if omitted
      },
      "vendors": [                          // at least one entry
        {
          "vendor": "Fortinet",
          "product": "FortiGate",
          "category": "Firewall",
          "formats": ["CEF", "SYSLOG", "JSON"],  // at least one
          "description": "NGFW"             // optional
        },
        {
          "vendor": "CrowdStrike",
          "product": "Falcon",
          "category": "EDR",
          "formats": ["JSON"]
        }
      ]
    }

    Returns the new stack in the same shape as
    `phantom_get_technology_stack`. The change persists across xlog
    restarts (sqlite-backed) and supersedes any TECHNOLOGY_STACK env
    var until cleared.
    """
    # v0.17.114 (#111) — signature flattened from (request:
    # UpdateTechnologyStackRequest) to flat kwargs so the agent's MCP-proxy
    # layer (which sends FLAT arguments per connector.yaml spec.tools[].args)
    # reaches this tool. The body keeps using `request.X` accessors by
    # rebuilding the model from the kwargs; Pydantic coerces the vendor /
    # log_destination dicts to their sub-models and enforces min_length here.
    request = UpdateTechnologyStackRequest(
        stack_name=stack_name,
        vendors=vendors,
        log_destination=log_destination,
    )
    # Build the GraphQL variables. Strawberry input types coerce
    # snake_case Python -> camelCase wire automatically when defined
    # via @strawberry.input, but variables we pass in still need
    # camelCase keys for the GQL parser. Translate at this boundary.
    vars_stack: Dict[str, Any] = {
        "stackName": request.stack_name,
        "vendors": [
            {
                "vendor": v.vendor,
                "product": v.product,
                "category": v.category,
                "formats": list(v.formats),
                "description": v.description,
            }
            for v in request.vendors
        ],
    }
    if request.log_destination is not None:
        ld = request.log_destination
        full_address = ld.full_address
        if not full_address and ld.protocol and ld.host and ld.port is not None:
            full_address = f"{ld.protocol}:{ld.host}:{ld.port}"
        vars_stack["logDestination"] = {
            "type": ld.type,
            "protocol": ld.protocol,
            "host": ld.host,
            "port": ld.port,
            "fullAddress": full_address,
        }

    try:
        client = PhantomGraphQLClient(resolve_xlog_url(ctx))
        result = await client.execute_query(
            _UPDATE_TECH_STACK_MUTATION, {"stack": vars_stack}
        )
        payload = result.get("updateTechnologyStack")
        if payload is None:
            return {
                "error": "xlog returned no payload from updateTechnologyStack",
                "configured": False,
            }
        response = _format_response(payload)
        logger.info(
            "Technology stack updated via xlog: name=%s vendors=%d",
            response.get("stack_name"),
            response.get("total_vendors"),
        )
        return response
    except Exception as exc:
        logger.error("Failed to update technology stack: %s", exc)
        return {"error": str(exc), "configured": False}
