"""Tests for app/dynamic_schema.py — v0.8.0 Phase 3 (v0.7.10).

Covers the heuristic value generator that backs generate_fake_data_v2
when a SchemaOverrideInput is supplied. The generator must:

  - Honor explicit type hints (int → integer, datetime → ISO string)
  - Fall back to field-name pattern matching for generic-string types
  - Honor observable_overrides as the highest-priority strategy
  - Omit meta fields when omit_meta=True (default)
  - Produce arrays of values for is_array=True fields
  - Generate exactly `count` records
"""

from __future__ import annotations

import datetime
import re
from types import SimpleNamespace

from app.dynamic_schema import generate_records_with_override


def _field(name, **kw):
    """Build a SchemaOverrideField-shaped object (SimpleNamespace works
    because the generator reads attributes by getattr fallback)."""
    return SimpleNamespace(
        name=name,
        type=kw.get("type"),
        is_array=kw.get("is_array", False),
        is_meta=kw.get("is_meta", False),
    )


# ── Count + shape ─────────────────────────────────────────────────


def test_returns_exactly_count_records():
    records = generate_records_with_override(
        count=5,
        vendor_fields=[_field("srcip"), _field("dstip")],
    )
    assert len(records) == 5
    for r in records:
        assert set(r.keys()) == {"srcip", "dstip"}


def test_zero_vendor_fields_returns_empty_objects():
    """Defensive — caller passes an empty schema → don't crash, just emit
    empty objects for `count` records."""
    records = generate_records_with_override(count=3, vendor_fields=[])
    assert records == [{}, {}, {}]


# ── Meta field omission ───────────────────────────────────────────


def test_meta_fields_omitted_by_default():
    """The 6 standard meta fields (_id/_time/_raw_log/_vendor/_product/
    _collector_name) populate at ingest time from the ModelingRule's
    XDM mapping — including them in simulated logs would conflict."""
    records = generate_records_with_override(
        count=1,
        vendor_fields=[
            _field("_id", is_meta=True),
            _field("_time", is_meta=True),
            _field("_raw_log", is_meta=True),
            _field("srcip"),
            _field("action"),
        ],
    )
    keys = set(records[0].keys())
    assert keys == {"srcip", "action"}


def test_meta_fields_included_when_omit_meta_false():
    """Defensive — caller can override the omission if they explicitly
    want to inspect what the generator would produce for meta fields."""
    records = generate_records_with_override(
        count=1,
        vendor_fields=[_field("_id", is_meta=True), _field("srcip")],
        omit_meta=False,
    )
    assert "_id" in records[0]
    assert "srcip" in records[0]


# ── Field-name heuristics ─────────────────────────────────────────


def test_ip_field_name_yields_ipv4_string():
    records = generate_records_with_override(
        count=3,
        vendor_fields=[
            _field("srcip"),
            _field("dst_ip"),
            _field("source_ip_address"),
        ],
    )
    for r in records:
        for v in r.values():
            assert re.fullmatch(r"\d+\.\d+\.\d+\.\d+", v), v


def test_port_field_name_yields_int():
    records = generate_records_with_override(
        count=5,
        vendor_fields=[_field("srcport"), _field("dst_port")],
    )
    for r in records:
        assert isinstance(r["srcport"], int)
        assert 1024 <= r["srcport"] <= 65535
        assert isinstance(r["dst_port"], int)


def test_mac_field_yields_mac_format():
    records = generate_records_with_override(
        count=1, vendor_fields=[_field("mac_addr")],
    )
    assert re.fullmatch(r"[0-9a-f]{2}(:[0-9a-f]{2}){5}", records[0]["mac_addr"]), records[0]


def test_hash_field_yields_hex():
    records = generate_records_with_override(
        count=1, vendor_fields=[_field("sha256")],
    )
    assert re.fullmatch(r"[0-9a-f]{64}", records[0]["sha256"]), records[0]


def test_email_field_yields_email():
    records = generate_records_with_override(
        count=1, vendor_fields=[_field("recipient_email")],
    )
    assert "@" in records[0]["recipient_email"]


def test_action_field_yields_known_action():
    records = generate_records_with_override(
        count=10, vendor_fields=[_field("action")],
    )
    actions = {r["action"] for r in records}
    # All values must be from the known vocabulary
    valid = {"allow", "deny", "block", "pass", "drop", "accept", "reject"}
    assert actions <= valid


def test_protocol_field_yields_known_protocol():
    records = generate_records_with_override(
        count=10, vendor_fields=[_field("protocol")],
    )
    protocols = {r["protocol"] for r in records}
    assert protocols <= {"TCP", "UDP", "ICMP", "HTTP", "HTTPS"}


def test_unknown_field_name_yields_short_string():
    records = generate_records_with_override(
        count=1, vendor_fields=[_field("FTNTcustom123")],
    )
    val = records[0]["FTNTcustom123"]
    assert isinstance(val, str)
    assert 1 <= len(val) <= 20


# ── Type hints ────────────────────────────────────────────────────


def test_explicit_int_type_yields_integer():
    """type='int' on a non-port name → still integer (type wins)."""
    records = generate_records_with_override(
        count=1, vendor_fields=[_field("flow_rate", type="int")],
    )
    assert isinstance(records[0]["flow_rate"], int)


def test_explicit_boolean_type_yields_bool():
    records = generate_records_with_override(
        count=5, vendor_fields=[_field("is_blocked", type="boolean")],
    )
    for r in records:
        assert isinstance(r["is_blocked"], bool)


def test_explicit_datetime_type_yields_iso_string():
    base = datetime.datetime(2026, 1, 1, 12, 0, 0)
    records = generate_records_with_override(
        count=1,
        vendor_fields=[_field("event_at", type="datetime")],
        base_datetime=base,
    )
    val = records[0]["event_at"]
    assert isinstance(val, str)
    assert val.startswith("202")  # ISO format starting with the year


def test_explicit_ipv4_type_yields_ip():
    """type='ipv4' on a generic name like 'address1' should still produce IP."""
    records = generate_records_with_override(
        count=1, vendor_fields=[_field("address1", type="ipv4")],
    )
    assert re.fullmatch(r"\d+\.\d+\.\d+\.\d+", records[0]["address1"])


# ── Array fields ──────────────────────────────────────────────────


def test_is_array_yields_list():
    records = generate_records_with_override(
        count=1, vendor_fields=[_field("groups", is_array=True)],
    )
    val = records[0]["groups"]
    assert isinstance(val, list)
    assert 1 <= len(val) <= 3


# ── Observable overrides ──────────────────────────────────────────


def test_observable_override_takes_priority():
    """When an observable_overrides entry matches a field name exactly,
    that value is used regardless of what the heuristic would produce."""
    records = generate_records_with_override(
        count=3,
        vendor_fields=[_field("srcip"), _field("dstip")],
        observable_overrides={"srcip": "192.168.1.100"},
    )
    for r in records:
        assert r["srcip"] == "192.168.1.100"  # pinned
        # dstip is NOT in the overrides → heuristic still fires
        assert re.fullmatch(r"\d+\.\d+\.\d+\.\d+", r["dstip"])
        assert r["dstip"] != "192.168.1.100"  # heuristic produced something else


def test_observable_override_single_element_list_unwrapped():
    """`observables_dict` conventionally maps a field to a LIST of candidate
    values (rosetta semantics — pick one). A single-element list must yield
    the SCALAR element, not the bracketed list — otherwise a discriminator
    like eventType=['user.authentication.sso'] serializes on the CEF wire as
    `eventType=["user.authentication.sso"]` and the modeling-rule PR filter
    (which matches the bare literal) never routes to the sibling dataset."""
    records = generate_records_with_override(
        count=5,
        vendor_fields=[_field("eventType")],
        observable_overrides={"eventType": ["user.authentication.sso"]},
    )
    for r in records:
        assert r["eventType"] == "user.authentication.sso"


def test_observable_override_multi_element_list_picks_from_set():
    """A multi-element override list picks one element per record (never the
    raw list)."""
    records = generate_records_with_override(
        count=25,
        vendor_fields=[_field("category")],
        observable_overrides={"category": ["AuditLogs", "SignInLogs"]},
    )
    vals = {r["category"] for r in records}
    assert vals <= {"AuditLogs", "SignInLogs"}
    for r in records:
        assert not isinstance(r["category"], list)


# ── FortiGate-shape sanity check ──────────────────────────────────


def test_realistic_fortigate_schema_produces_plausible_records():
    """Smoke: feed a tiny slice of a real FortiGate ModelingRule's vendor
    fields + verify the output looks like a FortiGate log record."""
    fortigate_fields = [
        _field("_raw_log", is_meta=True),
        _field("_time", is_meta=True),
        _field("srcip"),
        _field("dstip"),
        _field("srcport"),
        _field("dstport"),
        _field("proto"),
        _field("action"),
        _field("user"),
        _field("sentbyte"),
        _field("rcvdbyte"),
    ]
    records = generate_records_with_override(
        count=10, vendor_fields=fortigate_fields,
    )
    assert len(records) == 10
    for r in records:
        # Meta fields omitted
        assert "_raw_log" not in r
        assert "_time" not in r
        # Vendor fields present
        assert re.fullmatch(r"\d+\.\d+\.\d+\.\d+", r["srcip"])
        assert isinstance(r["srcport"], int)
        assert r["action"] in {"allow", "deny", "block", "pass", "drop", "accept", "reject"}
        assert isinstance(r["sentbyte"], int)


# ── Composite (type:json) synthesis — smoke-campaign fix ──────────


def test_composite_json_synthesized_from_leaves():
    """A `type: json` field with dotted-leaf children becomes a nested dict
    (not a random string), and the leaves are NOT emitted as flat keys."""
    fields = [
        _field("actor", type="json"),
        _field("actor.id", type="string_short"),
        _field("actor.alternateId", type="email"),
        _field("actor.type", type="enum"),
        _field("eventType", type="string_short"),  # flat sibling
    ]
    rec = generate_records_with_override(count=1, vendor_fields=fields)[0]
    assert isinstance(rec["actor"], dict), rec["actor"]
    assert set(rec["actor"]) == {"id", "alternateId", "type"}
    # Every leaf key is present with a non-empty value (key-presence is what
    # the MR's json_extract_scalar needs; value-shape fidelity is separate).
    assert all(rec["actor"][k] for k in ("id", "alternateId", "type"))
    assert "actor.id" not in rec and "actor.alternateId" not in rec  # leaves folded
    assert "eventType" in rec                            # flat sibling preserved


def test_composite_json_without_declared_parent():
    """Leaves present but no top-level `client` field declared → still
    synthesizes the `client` composite from the dotted prefix."""
    fields = [_field("client.ipAddress", type="ipv4"), _field("client.id", type="string_short")]
    rec = generate_records_with_override(count=1, vendor_fields=fields)[0]
    assert isinstance(rec.get("client"), dict)
    assert re.fullmatch(r"\d+\.\d+\.\d+\.\d+", rec["client"]["ipAddress"])
    assert "id" in rec["client"]
    assert "client.ipAddress" not in rec


def test_composite_array_of_objects():
    fields = [_field("target", type="json", is_array=True), _field("target.id", type="string_short")]
    rec = generate_records_with_override(count=1, vendor_fields=fields)[0]
    assert isinstance(rec["target"], list) and isinstance(rec["target"][0], dict)
    assert "id" in rec["target"][0]


def test_deeply_nested_composite():
    fields = [_field("properties", type="json"),
              _field("properties.log.user.username", type="user")]
    rec = generate_records_with_override(count=1, vendor_fields=fields)[0]
    assert rec["properties"]["log"]["user"]["username"]


# ── Semantic-type realism (value-realism enhancement) ─────────────
# The cortex extractor emits a precise type vocabulary; honoring it produces
# values the modeling rule's regex / typed reads accept (vs random tokens).


def test_type_ipv6_yields_ipv6():
    rec = generate_records_with_override(count=1, vendor_fields=[_field("addr", type="ipv6")])[0]
    assert rec["addr"].count(":") == 7 and re.fullmatch(r"[0-9a-f:]+", rec["addr"]), rec


def test_type_country_code_yields_two_letter_country():
    recs = generate_records_with_override(count=10, vendor_fields=[_field("geo", type="country_code")])
    for r in recs:
        assert re.fullmatch(r"[A-Z]{2}", r["geo"]), r


def test_type_url_yields_url():
    rec = generate_records_with_override(count=1, vendor_fields=[_field("u", type="url")])[0]
    assert rec["u"].startswith("http"), rec


def test_type_integer_port_yields_port_int():
    rec = generate_records_with_override(count=1, vendor_fields=[_field("p", type="integer_port")])[0]
    assert isinstance(rec["p"], int) and 1024 <= rec["p"] <= 65535


def test_type_email_yields_email():
    rec = generate_records_with_override(count=1, vendor_fields=[_field("e", type="email")])[0]
    assert "@" in rec["e"]


def test_type_mac_yields_mac():
    rec = generate_records_with_override(count=1, vendor_fields=[_field("m", type="mac")])[0]
    assert re.fullmatch(r"[0-9a-f]{2}(:[0-9a-f]{2}){5}", rec["m"]), rec


def test_type_hash_md5_yields_32_hex():
    rec = generate_records_with_override(count=1, vendor_fields=[_field("h", type="hash_md5")])[0]
    assert re.fullmatch(r"[0-9a-f]{32}", rec["h"]), rec


def test_type_byte_count_yields_int():
    rec = generate_records_with_override(count=1, vendor_fields=[_field("b", type="integer_byte_count")])[0]
    assert isinstance(rec["b"], int)


def test_type_host_yields_nonempty_string():
    rec = generate_records_with_override(count=1, vendor_fields=[_field("h", type="host")])[0]
    assert isinstance(rec["h"], str) and rec["h"]


# ── Name-pattern fixes — string-typed stragglers (Azure WAF) ──────


def test_string_typed_client_ip_yields_ipv4():
    """clientIP_s is typed `string` (not ipv4) in real schemas — the name must
    still drive an IP so the modeling rule's IP regex extracts something."""
    rec = generate_records_with_override(count=1, vendor_fields=[_field("clientIP_s", type="string")])[0]
    assert re.fullmatch(r"\d+\.\d+\.\d+\.\d+", rec["clientIP_s"]), rec


def test_country_name_not_mistaken_for_byte_count():
    """Regression: clientCountry_s contains 'count' → previously matched the
    byte-count pattern and returned an integer (Azure WAF clientCountry_s=3638).
    Must be a country code, never an int."""
    recs = generate_records_with_override(count=10, vendor_fields=[_field("clientCountry_s", type="string")])
    for r in recs:
        assert isinstance(r["clientCountry_s"], str), r          # NOT an int
        assert re.fullmatch(r"[A-Z]{2}", r["clientCountry_s"]), r


def test_http_method_name_yields_method():
    recs = generate_records_with_override(count=10, vendor_fields=[_field("httpMethod_s", type="string")])
    valid = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}
    for r in recs:
        assert r["httpMethod_s"] in valid, r
