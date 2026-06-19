"""Splunk-mimic splunkd server — the ASGI app the XSOAR SplunkPy integration
talks to as if it were a real splunkd management endpoint (HTTPS :8089).

It implements only the slice of the splunkd REST API splunklib exercises:
auth/login, search/jobs (create + oneshot), job status, results,
notable_update, plus a handful of minimal acks (server/info, data/indexes,
saved/searches, kvstore, receivers/HEC) so splunklib's connect + SplunkPy's
command paths don't 404.

Routing: splunklib uses BOTH `/services/<rest>` and the namespaced
`/servicesNS/<owner>/<app>/<rest>` forms. A tiny ASGI middleware rewrites the
namespaced form to `/services/<rest>` so every route is defined once.

TLS: splunkd is HTTPS on 8089. By default the server generates a self-signed
cert at boot (lab/demo — the operator sets SplunkPy `unsecure=true`, mirroring
how SplunkPy already trusts a real on-prem splunkd's self-signed cert). For a
production-faithful posture, mount an operator cert via SPLUNK_MIMIC_TLS_CERT /
SPLUNK_MIMIC_TLS_KEY and leave SplunkPy `unsecure=false`. Verification-off is
purely the XSOAR-side toggle — never hard-coded here.
"""

from __future__ import annotations

import logging
import os
import secrets
import urllib.parse
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from src import responses
from src.splunk_state import JobStore

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s splunk-mimic %(message)s",
)
log = logging.getLogger("splunk-mimic")

# ── config (env only — this is a standalone server, not the MCP) ─────────

# When unset, the mimic accepts ANY username/password (lab default — the
# updater does not pass instance config into a service container, so creds
# are theatre for testing). Set these to enforce specific creds.
_ACCEPT_USERNAME = os.environ.get("SPLUNK_MIMIC_USERNAME") or None
_ACCEPT_PASSWORD = os.environ.get("SPLUNK_MIMIC_PASSWORD") or None
_DEFAULT_NOTABLE_COUNT = int(os.environ.get("SPLUNK_MIMIC_NOTABLE_COUNT", "25"))

_JOBS = JobStore()

app = FastAPI(title="splunk-mimic", docs_url=None, redoc_url=None)


# ── namespace rewrite: /servicesNS/<owner>/<app>/X -> /services/X ────────

class _NamespaceRewrite:
    """ASGI middleware that (a) rewrites the namespaced splunkd path form to
    the plain form, and (b) injects ``Connection: Keep-Alive`` on every
    response.

    (b) is load-bearing for splunklib compatibility: splunklib's HTTP handler
    sends ``Connection: Close``, then closes the client socket in a ``finally``
    block — BEFORE it reads the response body — UNLESS the RESPONSE carries a
    ``Connection: keep-alive`` header (its ``is_keepalive`` check). uvicorn
    emits no Connection header, so without this injection splunklib reads an
    empty body and login fails with an XML ParseError. Real splunkd replies
    keep-alive; we mirror that. (The socket may still be closed server-side,
    but because splunklib then does NOT close it client-side, the buffered
    body stays readable.)
    """

    # Starlette's add_middleware instantiates this as cls(app=<inner_asgi>),
    # so the first param MUST be named `app`.
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        scope = dict(scope)
        path = scope.get("path", "")

        # /servicesNS/<owner>/<app>/X -> /services/X
        if path.startswith("/servicesNS/"):
            parts = path.split("/")  # ['', 'servicesNS', owner, app, *rest]
            if len(parts) >= 5:
                path = "/services/" + "/".join(parts[4:])

        # splunklib uses trailing-slash collection paths (e.g.
        # "search/jobs/"). FastAPI would 307-redirect those to the
        # slash-less route, but splunklib's HTTP handler doesn't follow
        # redirects — it reads the empty 307 body (oneshot/create returned
        # nothing). Normalise the trailing slash so the route matches
        # directly. (Login + server/info carry no trailing slash, which is
        # why they worked while the jobs paths didn't.)
        if len(path) > 1 and path.endswith("/"):
            path = path.rstrip("/")

        scope["path"] = path
        scope["raw_path"] = path.encode("utf-8")

        async def send_with_keepalive(message):
            if message.get("type") == "http.response.start":
                headers = list(message.get("headers") or [])
                headers = [
                    (k, v) for (k, v) in headers if k.lower() != b"connection"
                ]
                headers.append((b"connection", b"Keep-Alive"))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_keepalive)


app.add_middleware(_NamespaceRewrite)


# ── helpers ──────────────────────────────────────────────────────────────

def _creds_ok(username: str, password: str) -> bool:
    if _ACCEPT_USERNAME is not None and username != _ACCEPT_USERNAME:
        return False
    if _ACCEPT_PASSWORD is not None and password != _ACCEPT_PASSWORD:
        return False
    return True


def _xml(body: str, status: int = 200) -> Response:
    return Response(content=body, media_type="application/xml", status_code=status)


def _int(form: Any, key: str, default: int) -> int:
    try:
        v = form.get(key)
        return int(v) if v not in (None, "") else default
    except (TypeError, ValueError):
        return default


async def _params(request: Request) -> dict[str, str]:
    """Merge query-string + body params, tolerating a MISSING Content-Type.

    splunklib's HTTP handler builds a urlencoded body via _encode(**kwargs)
    but does NOT set Content-Type for its main request path — so Starlette's
    request.form() (which gates on Content-Type) returns nothing and we'd
    lose `search`, `exec_mode`, even `username`. We therefore parse the raw
    body as urlencoded ourselves. Query string wins is irrelevant here since
    splunklib puts everything in the body; body overrides query on collision.
    """
    merged: dict[str, str] = dict(request.query_params)
    raw = await request.body()
    if raw:
        parsed = urllib.parse.parse_qs(
            raw.decode("utf-8", "replace"), keep_blank_values=True
        )
        for k, v in parsed.items():
            merged[k] = v[-1] if v else ""
    return merged


# ── auth ───────────────────────────────────────────────────────────────

@app.post("/services/auth/login")
async def auth_login(request: Request) -> Response:
    params = await _params(request)
    username = str(params.get("username", ""))
    password = str(params.get("password", ""))
    if not _creds_ok(username, password):
        log.warning("auth/login rejected for username=%r", username)
        return _xml(responses.auth_error_xml("Login failed"), status=401)
    key = secrets.token_hex(32)
    log.info("auth/login ok username=%r", username)
    return _xml(responses.auth_xml(key))


# ── search jobs ──────────────────────────────────────────────────────────

@app.post("/services/search/jobs")
async def create_search_job(request: Request) -> Response:
    # splunklib sends everything in a urlencoded body, often with NO
    # Content-Type, so _params parses the raw body itself.
    params = await _params(request)

    search = str(params.get("search", "") or params.get("q", ""))
    exec_mode = str(params.get("exec_mode", "normal")).lower()
    # Honour both creation-time (earliest_time/latest_time) AND index-time
    # (index_earliest/index_latest) windows — SplunkPy sends the latter when
    # notable_time_source='index time'. Without this it would silently fall
    # back to the default 24h window and change rotation/dedup semantics.
    earliest = params.get("earliest_time") or params.get("index_earliest")
    latest = params.get("latest_time") or params.get("index_latest")
    count = _int(params, "count", _DEFAULT_NOTABLE_COUNT)
    offset = _int(params, "offset", 0)
    output_mode = str(params.get("output_mode", "")).lower()

    if exec_mode == "oneshot":
        # oneshot returns the results directly (no sid). splunklib reads them
        # via JSONResultsReader off this response. offset is load-bearing:
        # SplunkPy paginates a >FETCH_LIMIT window by re-issuing oneshot with
        # an advancing offset — ignoring it loops on the first slice forever.
        from src.splunk_state import run_query

        rows = run_query(search, earliest, latest, count, offset=offset)
        log.info(
            "oneshot search -> %d rows (offset=%d count=%d search=%.80s)",
            len(rows), offset, count, search,
        )
        return JSONResponse(responses.results_json(rows))

    # Non-oneshot: the job holds the FULL in-window set (count=None) so the
    # create->poll->results path paginates via get_job_results.
    sid = _JOBS.create(search, earliest, latest, count=None)
    log.info("created job %s (search=%.80s)", sid, search)
    # splunklib's _load_sid parses JSON when the request set output_mode=json,
    # else XML (<response><sid>). Honour both.
    if output_mode == "json":
        return JSONResponse({"sid": sid})
    return _xml(responses.sid_xml(sid))


@app.get("/services/search/jobs/{sid}")
async def get_job_status(sid: str, request: Request) -> Response:
    job = _JOBS.get(sid)
    if job is None:
        return _xml(responses.auth_error_xml(f"Unknown sid {sid}"), status=404)
    # splunklib reads the job entity as ATOM XML (its Job.refresh /
    # _load_atom_entry). Only when a caller explicitly asks output_mode=json
    # do we hand back JSON.
    if str(request.query_params.get("output_mode", "")).lower() == "json":
        return JSONResponse(responses.job_status_json(sid, job.result_count))
    return _xml(responses.job_status_atom(sid, job.result_count))


@app.post("/services/search/jobs/{sid}")
async def control_job_post(sid: str) -> Response:
    # set_ttl / share / touch — splunklib POSTs to the job resource. Ack.
    return JSONResponse({"messages": [{"type": "INFO", "text": "ok"}]})


@app.post("/services/search/jobs/{sid}/control")
async def control_job(sid: str) -> Response:
    return JSONResponse({"messages": [{"type": "INFO", "text": "ok"}]})


@app.get("/services/search/jobs/{sid}/results")
async def get_job_results(sid: str, request: Request) -> Response:
    job = _JOBS.get(sid)
    if job is None:
        return JSONResponse(responses.results_json([]))
    count = _int(request.query_params, "count", 0)
    offset = _int(request.query_params, "offset", 0)
    rows = job.results[offset:]
    if count > 0:
        rows = rows[:count]
    return JSONResponse(responses.results_json(rows))


@app.get("/services/search/jobs/{sid}/events")
async def get_job_events(sid: str, request: Request) -> Response:
    # ES sometimes reads events instead of results; same payload here.
    return await get_job_results(sid, request)


# ── notable update (splunk-update-notable-events / mirroring) ────────────

@app.post("/services/notable_update")
async def notable_update(request: Request) -> Response:
    return JSONResponse(
        {"success": True, "message": "Successfully updated notable events."}
    )


# ── minimal acks so splunklib connect + SplunkPy paths don't 404 ─────────

@app.get("/services/server/info")
async def server_info(request: Request) -> Response:
    # splunklib reads server/info as ATOM XML (_load_atom on .info access),
    # using the version to gate the v1/v2 search API. ATOM by default; JSON
    # only on explicit output_mode=json.
    if str(request.query_params.get("output_mode", "")).lower() == "json":
        return JSONResponse(
            {
                "entry": [
                    {"name": "server-info", "content": {"version": "8.2.0"}}
                ]
            }
        )
    return _xml(responses.server_info_atom())


@app.get("/services/data/indexes")
async def data_indexes() -> Response:
    entries = [
        {"name": name, "content": {"currentDBSizeMB": 1, "totalEventCount": "100"}}
        for name in ("notable", "main", "_internal")
    ]
    return JSONResponse({"entry": entries, "paging": {"total": len(entries)}})


@app.get("/services/saved/searches")
async def saved_searches() -> Response:
    entries = [
        {
            "name": "Splunk_SOAR_Notables",
            "content": {"search": "`notable`", "is_scheduled": False},
        }
    ]
    return JSONResponse({"entry": entries, "paging": {"total": len(entries)}})


@app.api_route(
    "/services/storage/collections/{rest:path}",
    methods=["GET", "POST", "DELETE"],
)
async def kvstore(rest: str, request: Request) -> Response:
    # Empty-collection stubs — SplunkPy's kv-store-backed dedup is optional.
    if request.method == "GET":
        return JSONResponse([])
    return JSONResponse({"acknowledged": True})


@app.post("/services/receivers/simple")
async def receivers_simple() -> Response:
    return JSONResponse({"text": "Success", "code": 0})


@app.post("/services/collector/event")
async def hec_event() -> Response:
    return JSONResponse({"text": "Success", "code": 0})


@app.get("/services/healthz")
@app.get("/healthz")
async def healthz() -> Response:
    return JSONResponse({"status": "ok"})


# ── TLS bootstrap + run ──────────────────────────────────────────────────

def _ensure_cert() -> tuple[str, str]:
    """Return (cert_path, key_path). Use a mounted operator cert when both
    SPLUNK_MIMIC_TLS_CERT and SPLUNK_MIMIC_TLS_KEY point to readable files
    (production-faithful); otherwise generate a self-signed cert (lab)."""
    cert_env = os.environ.get("SPLUNK_MIMIC_TLS_CERT")
    key_env = os.environ.get("SPLUNK_MIMIC_TLS_KEY")
    if cert_env and key_env and os.path.isfile(cert_env) and os.path.isfile(key_env):
        log.info("using mounted TLS cert %s", cert_env)
        return cert_env, key_env

    from datetime import datetime, timedelta, timezone

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "splunk-mimic")])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost")]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    cert_path = "/tmp/mimic.crt"  # noqa: S108 — container-local, ephemeral
    key_path = "/tmp/mimic.key"  # noqa: S108
    with open(cert_path, "wb") as fh:
        fh.write(cert.public_bytes(serialization.Encoding.PEM))
    with open(key_path, "wb") as fh:
        fh.write(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            )
        )
    log.info("generated self-signed TLS cert at %s", cert_path)
    return cert_path, key_path


def main() -> None:
    import uvicorn

    port = int(os.environ.get("SPLUNK_MIMIC_PORT", "8089"))
    cert_path, key_path = _ensure_cert()
    log.info("splunk-mimic listening on https://0.0.0.0:%d", port)
    uvicorn.run(
        app,
        host="0.0.0.0",  # noqa: S104 — service must be reachable by external XSOAR
        port=port,
        ssl_certfile=cert_path,
        ssl_keyfile=key_path,
        log_level=os.environ.get("LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
