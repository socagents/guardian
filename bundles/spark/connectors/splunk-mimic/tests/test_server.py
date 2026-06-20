"""splunk-mimic contract tests (Refs #56).

Three layers:
  * splunk_state — notable generator + SPL interpreter + job store;
  * responses    — the splunkd byte shapes (XML auth/sid, JSON status/results);
  * server       — the FastAPI routes via TestClient, incl. the namespaced
                   /servicesNS/<owner>/<app>/... prefix;
  * round-trip   — a REAL uvicorn+TLS server driven by the actual splunklib
                   SDK (the same SDK SplunkPy uses) — the authoritative
                   byte-compatibility proof.
"""

import os
import socket
import sys
import threading
import time
from datetime import datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient  # noqa: E402

from src import responses, splunk_state  # noqa: E402
from src.server import app  # noqa: E402

# The live round-trip tests need the real Splunk SDK (the same one the XSOAR
# SplunkPy integration uses). Skip them where it isn't installed; the unit +
# TestClient route tests still run everywhere.
try:
    import splunklib.client  # noqa: F401
    import splunklib.results  # noqa: F401

    _HAVE_SPLUNKLIB = True
except ImportError:
    _HAVE_SPLUNKLIB = False

needs_splunklib = pytest.mark.skipif(
    not _HAVE_SPLUNKLIB, reason="splunk-sdk not installed"
)

SPLUNK_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S"  # what SplunkPy parses

client = TestClient(app)


# ── splunk_state: generator + interpreter ───────────────────────────────

REQUIRED_KEYS = {
    "event_id", "_time", "_raw", "rule_name", "rule_title",
    "rule_description", "urgency", "security_domain", "drilldown_search",
}


def test_generate_notables_shape():
    notables = splunk_state.generate_notables(3)
    assert len(notables) == 3
    for n in notables:
        assert REQUIRED_KEYS <= set(n), f"missing keys: {REQUIRED_KEYS - set(n)}"
        assert n["urgency"] in splunk_state._URGENCIES


def test_generate_notables_time_parses_like_splunkpy():
    # SplunkPy splits _time on "." and parses %Y-%m-%dT%H:%M:%S.
    t = splunk_state.generate_notables(1)[0]["_time"]
    datetime.strptime(t.split(".")[0], SPLUNK_TIME_FORMAT)  # must not raise


def test_generate_notables_deterministic():
    a = splunk_state.generate_notables(5, earliest=1_700_000_000, latest=1_700_086_400)
    b = splunk_state.generate_notables(5, earliest=1_700_000_000, latest=1_700_086_400)
    assert [x["event_id"] for x in a] == [x["event_id"] for x in b]


def test_run_query_notable_macro_returns_notables():
    rows = splunk_state.run_query("search `notable` | head 10", count=10)
    assert len(rows) == 10
    assert all("rule_name" in r for r in rows)


def test_run_query_indicator_literal_echoes_indicator():
    rows = splunk_state.run_query("search index=main 1.2.3.4", count=25)
    assert len(rows) >= 1
    assert any("1.2.3.4" in str(r.get("indicator")) or "1.2.3.4" in r.get("_raw", "") for r in rows)


def test_run_query_unmatched_returns_empty():
    assert splunk_state.run_query("search index=empty someuniquetokenxyz") == []


def test_run_query_gentimes_returns_current_time():
    # SplunkPy v2's get_current_splunk_time probe — must return ONE row with
    # the field named in the eval, formatted per the query's strftime. An
    # empty result aborts the whole fetch ("Could not fetch Splunk time").
    q = '| gentimes start=-1 | eval clock = strftime(time(), "%Y-%m-%dT%H:%M:%S.%f%z") | table clock'
    rows = splunk_state.run_query(q, count=1)
    assert len(rows) == 1
    assert rows[0].get("clock")
    # the field name is parsed from the eval, not hardcoded
    q2 = '| gentimes start=-1 | eval now_ts = strftime(time(), "%Y-%m-%dT%H:%M:%S") | table now_ts'
    assert splunk_state.run_query(q2, count=1)[0].get("now_ts")


# ── rotation contract: fixed grid, count-independent, disjoint windows ───
#
# These guard the SplunkPy fetch+dedup contract: a fetch must see NEW
# incidents as its window advances (rotation), and must NOT see duplicates
# when the same window is re-queried (stability). Both hinge on notable
# identity being a pure function of the absolute grid instant.

_T = 1_700_000_000  # fixed window anchor for the grid tests


def test_generate_notables_count_independent():
    # Same window, different count → the smaller set is a PREFIX of the
    # larger (count selects from the grid; it does not redefine it).
    a = splunk_state.generate_notables(5, earliest=_T, latest=_T + 3600)
    b = splunk_state.generate_notables(12, earliest=_T, latest=_T + 3600)
    ids_a = [n["event_id"] for n in a]
    ids_b = [n["event_id"] for n in b]
    assert len(ids_a) == 5
    assert ids_a == ids_b[:5], "count must SELECT, not redefine, the grid"


def test_generate_notables_window_advance_disjoint():
    # Adjacent non-overlapping windows MUST yield disjoint event_id sets —
    # half-open intervals → no boundary double-emit → genuine rotation.
    w = 1800
    a = {n["event_id"] for n in splunk_state.generate_notables(None, earliest=_T, latest=_T + w)}
    b = {n["event_id"] for n in splunk_state.generate_notables(None, earliest=_T + w, latest=_T + 2 * w)}
    assert a and b
    assert a.isdisjoint(b), f"advancing-window double-emit: {a & b}"


def test_generate_notables_stable_on_requery():
    # Re-querying an identical window returns byte-identical (id,_time,_raw)
    # so SplunkPy's found_incidents_ids dedup drops the re-fetch.
    a = splunk_state.generate_notables(None, earliest=_T, latest=_T + 600)
    b = splunk_state.generate_notables(None, earliest=_T, latest=_T + 600)
    key = lambda rows: [(n["event_id"], n["_time"], n["_raw"]) for n in rows]
    assert key(a) == key(b)


def test_generate_notables_offset_paginates():
    full = splunk_state.generate_notables(None, earliest=_T, latest=_T + 3600)
    assert len(full) > 6
    page1 = splunk_state.generate_notables(3, earliest=_T, latest=_T + 3600, offset=0)
    page2 = splunk_state.generate_notables(3, earliest=_T, latest=_T + 3600, offset=3)
    assert [n["event_id"] for n in page1] == [n["event_id"] for n in full[:3]]
    assert [n["event_id"] for n in page2] == [n["event_id"] for n in full[3:6]]
    assert {n["event_id"] for n in page1}.isdisjoint({n["event_id"] for n in page2})


def test_generate_notables_includes_indextime():
    n = splunk_state.generate_notables(1, earliest=_T, latest=_T + 600)[0]
    assert n["_indextime"] and n["_indextime"].isdigit()


# ── responses: byte shapes ───────────────────────────────────────────────

def test_auth_xml_has_session_key():
    assert "<sessionKey>K123</sessionKey>" in responses.auth_xml("K123")


def test_sid_xml_has_sid():
    assert "<sid>abc.1</sid>" in responses.sid_xml("abc.1")


def test_job_status_is_done():
    s = responses.job_status_json("s1", 7)
    content = s["entry"][0]["content"]
    assert content["isDone"] is True
    assert content["dispatchState"] == "DONE"
    assert content["resultCount"] == 7


def test_results_json_envelope():
    out = responses.results_json([{"a": "b"}])
    assert out["preview"] is False
    assert out["results"] == [{"a": "b"}]
    assert {"name": "a"} in out["fields"]


# ── server routes via TestClient ─────────────────────────────────────────

def test_auth_login_returns_session_key():
    r = client.post("/services/auth/login", data={"username": "admin", "password": "x"})
    assert r.status_code == 200
    assert "<sessionKey>" in r.text


def test_oneshot_search_returns_notable_rows():
    r = client.post(
        "/services/search/jobs",
        data={"search": "search `notable`", "exec_mode": "oneshot", "count": "5", "output_mode": "json"},
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["results"]) == 5
    assert "rule_name" in body["results"][0]


def test_create_job_then_status_then_results():
    r = client.post(
        "/services/search/jobs",
        data={"search": "search `notable`", "count": "4"},
    )
    assert r.status_code == 200
    assert "<sid>" in r.text
    sid = r.text.split("<sid>")[1].split("</sid>")[0]

    st = client.get(f"/services/search/jobs/{sid}", params={"output_mode": "json"})
    assert st.json()["entry"][0]["content"]["isDone"] is True

    res = client.get(f"/services/search/jobs/{sid}/results", params={"output_mode": "json", "count": "4"})
    assert len(res.json()["results"]) == 4


def test_namespaced_path_prefix_tolerated():
    # splunklib uses /servicesNS/<owner>/<app>/... when an app context is set.
    r = client.post(
        "/servicesNS/nobody/SplunkEnterpriseSecuritySuite/search/jobs",
        data={"search": "search `notable`", "exec_mode": "oneshot", "count": "3", "output_mode": "json"},
    )
    assert r.status_code == 200
    assert len(r.json()["results"]) == 3


def test_notable_update_ack():
    r = client.post("/services/notable_update", data={"ruleUIDs": "x"})
    assert r.json()["success"] is True


def test_server_info_has_version():
    r = client.get("/services/server/info", params={"output_mode": "json"})
    assert r.json()["entry"][0]["content"]["version"]


# ── round-trip against the REAL splunklib SDK over TLS ───────────────────
#
# NOTE on verify=False below: these tests connect to a LOCALHOST mimic that
# serves an ephemeral, per-boot self-signed cert (no CA to pin against). The
# test deliberately plays the role of the XSOAR-side SplunkPy client running
# with `unsecure=true` — the documented lab posture. The mimic's own code
# NEVER disables verification (it only SERVES TLS); verification-off is purely
# this client-side toggle. The production-faithful path mounts an operator CA
# cert (SPLUNK_MIMIC_TLS_CERT/_KEY) and leaves the SplunkPy side verifying.

def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="module")
def live_server():
    import uvicorn

    from src.server import _ensure_cert

    cert, key = _ensure_cert()
    port = _free_port()
    config = uvicorn.Config(
        app, host="127.0.0.1", port=port,
        ssl_certfile=cert, ssl_keyfile=key, log_level="warning",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    assert server.started, "uvicorn did not start"
    yield port
    server.should_exit = True
    thread.join(timeout=5)


@needs_splunklib
def test_splunklib_oneshot_roundtrip(live_server):
    """The SDK SplunkPy uses must connect + oneshot against the mimic."""
    import splunklib.client as splunk_client
    import splunklib.results as splunk_results

    service = splunk_client.connect(
        host="127.0.0.1", port=live_server, scheme="https",
        username="admin", password="changeme", verify=False,
    )
    reader = splunk_results.JSONResultsReader(
        service.jobs.oneshot("search `notable`", output_mode="json", count=5)
    )
    rows = [r for r in reader if isinstance(r, dict)]
    assert len(rows) == 5
    assert any("rule_name" in r for r in rows)


@needs_splunklib
def test_splunklib_create_search_roundtrip(live_server):
    """splunk-search's create→poll→results path against the mimic."""
    import splunklib.client as splunk_client
    import splunklib.results as splunk_results

    service = splunk_client.connect(
        host="127.0.0.1", port=live_server, scheme="https",
        username="admin", password="changeme", verify=False,
    )
    job = service.jobs.create("search `notable`", count=4)
    # mimic completes instantly; bounded poll just in case.
    for _ in range(50):
        if job.is_done():
            break
        time.sleep(0.05)
    assert job.is_done()
    reader = splunk_results.JSONResultsReader(job.results(output_mode="json", count=4))
    rows = [r for r in reader if isinstance(r, dict)]
    assert len(rows) == 4
