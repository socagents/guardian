"""R3.A v0.12.0 — vendor-faithful UDP/TCP worker sender.

The external `rosetta-ce` library's `Sender` generates records on-the-fly
inside its tick loop using Rosetta's generic observables (`local_ip`,
`remote_port`, etc.). It doesn't accept a pre-built record stream for
UDP/TCP destinations, only for the XSIAM_WEBHOOK path.

`OverrideSender` is the schema-override-aware counterpart: it uses
`generate_records_with_override()` from `dynamic_schema.py` to produce
records whose top-level keys match the vendor's actual field names
(extracted from a Cortex ModelingRule via the agent's marketplace), then
streams them to a UDP or TCP destination on a tick.

Interface matches Sender's externally-accessed surface — see
`app/schema.py:list_workers` / `action_worker` for the contract.

This sender is INTENTIONALLY narrow: only UDP + TCP destinations, only
the override case. XSIAM and webhook destinations still flow through
the existing Sender / WebhookSender paths.

v0.17.26 — wire-format branching by `data_type`.
The original v0.12.0 implementation always JSON-encoded the wire
payload regardless of `data_type`. That broke the broker → XSIAM
ingestion path: XSIAM brokers route to `<vendor>_<product>_raw`
datasets BY PARSING THE CEF HEADER on incoming syslog. JSON over
UDP has no header → broker drops it (or routes to a fallback).
Now we branch:
  CEF    → `<134>TIMESTAMP HOSTNAME CEF:0|Vendor|Product|Version|SigID|Name|Severity|ext`
  SYSLOG → `<134>TIMESTAMP HOSTNAME vendor product: key=value key=value …`
  LEEF   → `<134>TIMESTAMP HOSTNAME LEEF:2.0|Vendor|Product|Version|EventID|ext`
  *      → JSON (existing behavior preserved for legacy callers)
"""

from __future__ import annotations

import datetime
import json
import logging
import socket
import socket as _socket_mod
import threading
from typing import Any, List, Optional

from app.dynamic_schema import generate_records_with_override

logger = logging.getLogger("xlog.override_sender")

# Syslog priority for facility=user (1), severity=informational (6) → 1*8+6=14.
# Most CEF-over-syslog deployments use facility=local0 (16) severity=info (6)
# → 16*8+6 = 134. XSIAM brokers don't care about the priority value — they
# parse the CEF/LEEF header out of the message body — but a syntactically
# valid syslog wrapper avoids broker-side warning logs.
_SYSLOG_PRIORITY = 134


def _syslog_timestamp() -> str:
    """RFC 3164 timestamp: 'Mon DD HH:MM:SS' in local server time.

    Using UTC is also accepted by all syslog parsers we test against
    (XSIAM broker, rsyslogd, syslog-ng) — keep it consistent.
    """
    now = datetime.datetime.utcnow()
    # `strftime('%b %e %H:%M:%S')` would give the right form but `%e`
    # isn't portable on all libc. Build by hand for determinism.
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return f"{months[now.month - 1]} {now.day:2d} {now.strftime('%H:%M:%S')}"


def _hostname() -> str:
    """Best-effort short hostname for the syslog wrapper.

    Falls back to 'xlog' if gethostname returns something unusable.
    """
    try:
        h = _socket_mod.gethostname() or "xlog"
        # Strip any FQDN suffix — RFC 3164 hostname field is the short form.
        return h.split(".")[0]
    except Exception:
        return "xlog"


def _escape_cef_header(s: str) -> str:
    """Escape backslash and pipe in CEF header fields (between the | chars)."""
    return str(s).replace("\\", "\\\\").replace("|", "\\|")


def _escape_cef_extension_value(s: Any) -> str:
    r"""Escape backslash, equals, and newline in CEF extension VALUES.

    Per ArcSight CEF spec: \\, \=, \n are the three required escapes for
    the extension portion. Keep tabs/spaces literal — values can contain
    spaces (the parser splits on `<space>key=` boundaries).
    """
    return (
        str(s)
        .replace("\\", "\\\\")
        .replace("=", "\\=")
        .replace("\n", "\\n")
        .replace("\r", "")
    )


def _flatten_extension(rec: dict[str, Any]) -> str:
    """Build `key=value key=value …` from a record dict.

    Skips None/empty values. Lists/dicts are JSON-stringified (CEF doesn't
    have a native array form — embedding JSON is what most Cortex modeling
    rules tolerate).
    """
    parts: List[str] = []
    for k, v in rec.items():
        if v is None or v == "" or v == []:
            continue
        if isinstance(v, (list, dict)):
            # Compact separators (no spaces) so the embedded JSON survives
            # CEF's space-delimited extension parsing — `actor={"id":"x"}`
            # stays ONE extension value, not split at the spaces a default
            # json.dumps would insert. The MR's json_extract_scalar then
            # parses the composite at query time (smoke-campaign type:json fix).
            v_s = json.dumps(v, default=str, separators=(",", ":"))
        else:
            v_s = str(v)
        parts.append(f"{k}={_escape_cef_extension_value(v_s)}")
    return " ".join(parts)


def _parse_destination(destination: str) -> tuple[str, str, int]:
    """Parse `udp:host:port` or `tcp:host:port`. Returns (proto, host, port).

    Raises ValueError on malformed input.
    """
    parts = destination.split(":")
    if len(parts) != 3:
        raise ValueError(
            f"OverrideSender requires destination 'udp:host:port' or "
            f"'tcp:host:port', got {destination!r}"
        )
    proto, host, port_s = parts
    proto = proto.lower()
    if proto not in ("udp", "tcp"):
        raise ValueError(
            f"OverrideSender supports only udp/tcp protocols, got {proto!r}"
        )
    try:
        port = int(port_s)
    except ValueError as exc:
        raise ValueError(f"invalid port {port_s!r}") from exc
    return proto, host, port


class OverrideSender:
    """Schema-override-aware tick sender for UDP/TCP destinations.

    Lifecycle: __init__ → start() → tick loop in worker thread →
    stop() signals exit. Workers are in-memory (per xlog convention);
    container restart drops them.
    """

    def __init__(
        self,
        worker_name: str,
        data_type: str,
        destination: str,
        vendor_fields: List[Any],
        count: int = 1,
        interval: int = 2,
        verify_ssl: bool = False,
        vendor: Optional[str] = None,
        product: Optional[str] = None,
        observable_overrides: Optional[dict[str, Any]] = None,
    ) -> None:
        self.worker_name = worker_name
        self.data_type = data_type  # informational — kept for list_workers surface
        self.destination = destination
        self.count = count
        self.interval = interval
        self.verify_ssl = verify_ssl  # informational — UDP/TCP don't use TLS in xlog today
        self.vendor = vendor
        self.product = product
        self.vendor_fields = vendor_fields
        self.observable_overrides = observable_overrides or {}
        self.status = "Pending"
        self.created_at = datetime.datetime.utcnow()

        # Parse destination upfront so a malformed value fails at create
        # time (HTTP 400) rather than silently in the worker thread.
        self._proto, self._host, self._port = _parse_destination(destination)

        # Threading state
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ─── lifecycle ───────────────────────────────────────────────────

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            logger.warning("OverrideSender %s already running", self.worker_name)
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name=f"override-sender-{self.worker_name}", daemon=True
        )
        self.status = "Running"
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self.status = "Stopped"
        # Don't join — workers stop is async per the existing Sender contract.

    # ─── tick loop ───────────────────────────────────────────────────

    def _run(self) -> None:
        """Per-tick: generate `count` records, encode, send to destination.

        Loops until stop_event is set. Sleeps interval between ticks.
        """
        try:
            sock = self._open_socket()
        except Exception as exc:
            logger.exception("OverrideSender %s: socket open failed: %s",
                             self.worker_name, exc)
            self.status = "Error"
            return

        try:
            while not self._stop_event.is_set():
                try:
                    records = generate_records_with_override(
                        count=self.count,
                        vendor_fields=self.vendor_fields,
                        observable_overrides=self.observable_overrides,
                    )
                    for rec in records:
                        payload = self.format_record(rec).encode("utf-8")
                        if self._proto == "udp":
                            sock.sendto(payload, (self._host, self._port))
                        else:  # tcp
                            sock.sendall(payload + b"\n")
                except Exception as exc:
                    logger.exception(
                        "OverrideSender %s: tick failed: %s",
                        self.worker_name, exc,
                    )
                # Sleep interval, but wake up if stop fires mid-sleep.
                self._stop_event.wait(self.interval)
        finally:
            try:
                sock.close()
            except Exception:
                pass

    # ─── wire-format encoders ─────────────────────────────────────────
    #
    # v0.17.26 — branch on data_type so XSIAM brokers can route by header.
    # Public-method-shaped (not `_format_*`) so tests can call directly
    # without instantiating the socket / thread.

    def format_record(self, rec: dict[str, Any]) -> str:
        """Encode `rec` for the wire per `self.data_type`.

        Dispatches to one of the format-specific encoders below. Anything
        not recognized falls back to JSON (preserving the v0.12.0 default
        for legacy callers).
        """
        dt = (self.data_type or "").upper()
        if dt == "CEF":
            return self._format_cef(rec)
        if dt == "SYSLOG":
            return self._format_syslog(rec)
        if dt == "LEEF":
            return self._format_leef(rec)
        # JSON / WINEVENT / Incident / XSIAM_* and any future enum:
        # keep JSON. WINEVENT could one day get its own XML/event-log
        # encoder; not required for the broker → vendor_product_raw path.
        return json.dumps(rec, default=str)

    def _format_cef(self, rec: dict[str, Any]) -> str:
        """Build a syslog-wrapped CEF line.

        Shape: `<134>Mon DD HH:MM:SS hostname CEF:0|Vendor|Product|Version|SigID|Name|Severity|ext`

        Vendor/Product come from the constructor (the agent always passes
        them when invoking generateDataWorker via the schema_override
        path — that's what determines the dataset name on the broker).
        SignatureID/Name/Severity have neutral defaults; some records
        will overlay them via fields named exactly `signatureId` / `name`
        / `severity` (best-effort hoisting below).
        """
        vendor = _escape_cef_header(self.vendor or "Phantom")
        product = _escape_cef_header(self.product or "xlog")
        version = "1.0"

        # Hoist any record-level overrides for the CEF header columns.
        # Look up both camelCase and snake_case to be tolerant of
        # vendor-faithful schemas using different naming conventions.
        sig_id = _escape_cef_header(
            rec.get("signatureId") or rec.get("signature_id") or "100"
        )
        name = _escape_cef_header(
            rec.get("name") or rec.get("msg") or rec.get("event") or "Event"
        )
        sev_raw = rec.get("severity")
        try:
            severity = str(int(sev_raw)) if sev_raw is not None else "5"
        except (TypeError, ValueError):
            severity = "5"

        # Build extension from ALL fields (including the hoisted ones —
        # extension is allowed to repeat header fields, broker parsers
        # handle that).
        ext = _flatten_extension(rec)
        header = f"CEF:0|{vendor}|{product}|{version}|{sig_id}|{name}|{severity}|"
        return (
            f"<{_SYSLOG_PRIORITY}>{_syslog_timestamp()} {_hostname()} "
            f"{header}{ext}"
        )

    def _format_syslog(self, rec: dict[str, Any]) -> str:
        """Build a syslog line with vendor/product tag + key=value body.

        Shape: `<134>Mon DD HH:MM:SS hostname vendor-product: key=value …`

        XSIAM brokers parse the tag for routing hints when the inner
        payload isn't CEF/LEEF. Most Cortex modeling rules then use
        regextract against the key=value body in their .xif rules.
        """
        vendor = (self.vendor or "phantom").lower().replace(" ", "_")
        product = (self.product or "xlog").lower().replace(" ", "_")
        body = _flatten_extension(rec)
        return (
            f"<{_SYSLOG_PRIORITY}>{_syslog_timestamp()} {_hostname()} "
            f"{vendor}-{product}: {body}"
        )

    def _format_leef(self, rec: dict[str, Any]) -> str:
        """Build a syslog-wrapped LEEF 2.0 line (QRadar/SIEM-flex).

        Shape: `<134>Mon DD HH:MM:SS hostname LEEF:2.0|Vendor|Product|Version|EventID|ext`

        Less common than CEF in our cohort, but the few connectors that
        prefer LEEF (some IBM/QRadar-targeted ones) get clean output
        instead of mistaken JSON.
        """
        vendor = _escape_cef_header(self.vendor or "Phantom")
        product = _escape_cef_header(self.product or "xlog")
        version = "1.0"
        event_id = _escape_cef_header(
            rec.get("eventId") or rec.get("event_id") or "100"
        )
        ext = _flatten_extension(rec)
        header = f"LEEF:2.0|{vendor}|{product}|{version}|{event_id}|"
        return (
            f"<{_SYSLOG_PRIORITY}>{_syslog_timestamp()} {_hostname()} "
            f"{header}{ext}"
        )

    def _open_socket(self) -> socket.socket:
        if self._proto == "udp":
            return socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # TCP: connect upfront so listener auth/handshake errors surface
        # at start time, not on every tick.
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect((self._host, self._port))
        s.settimeout(None)
        return s
