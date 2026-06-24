"""web connector — unit tests (#CDW-F15).

The web connector had zero test coverage. Unlike cortex-docs / xsoar /
xsiam, none of its guard logic was exercised. These tests cover the
PURE, importable helpers that don't need a live Chromium/CDP endpoint:

  1. `_check_allowed_domain` — the allow-list guard that gates every
     navigation. Exact-host + leading-dot-wildcard semantics, the
     "empty list = no restriction" rule, and the malformed-URL paths.
  2. `_resolve_cdp_url_to_ip` — leaves IP literals / localhost / bad
     input unchanged (the DNS-rewrite path needs real resolution and
     is covered by live smoke).
  3. `_truncate` — head-truncation return shape (text, was_truncated).

browser.py imports playwright defensively (try/except at import time),
so it imports fine here without playwright installed; the live tool
round-trip (session GC, click re-check, fill return shape) is covered
by live smoke, not this offline file.

Run:
  PYTHONPATH=src python3 -m pytest bundles/spark/connectors/web/tests -q
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make the connector's src importable (mirrors connector_loader's boot path).
SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import browser  # noqa: E402


# ─── _check_allowed_domain ───────────────────────────────────────────


def test_allow_empty_list_means_no_restriction():
    # Empty allow-list = unrestricted; any URL is permitted.
    assert browser._check_allowed_domain("https://anything.example", []) is None


def test_allow_exact_host_match():
    allowed = ["intel.example.com"]
    assert browser._check_allowed_domain("https://intel.example.com/x", allowed) is None


def test_allow_exact_host_rejects_other_host():
    allowed = ["intel.example.com"]
    err = browser._check_allowed_domain("https://evil.com/x", allowed)
    assert err is not None
    assert "blocked" in err
    assert "evil.com" in err


def test_allow_exact_host_rejects_subdomain():
    # Exact entry must NOT match a subdomain (only the leading-dot form does).
    allowed = ["example.com"]
    assert browser._check_allowed_domain("https://sub.example.com", allowed) is not None


def test_allow_leading_dot_matches_subdomain_and_apex():
    allowed = [".example.com"]
    assert browser._check_allowed_domain("https://a.example.com", allowed) is None
    # Apex itself is allowed too.
    assert browser._check_allowed_domain("https://example.com", allowed) is None


def test_allow_leading_dot_rejects_unrelated_host():
    allowed = [".example.com"]
    assert browser._check_allowed_domain("https://notexample.com", allowed) is not None


def test_allow_rejects_url_without_host():
    allowed = [".example.com"]
    err = browser._check_allowed_domain("not-a-url", allowed)
    assert err is not None  # no host component → blocked (fail-closed)


# ─── _resolve_cdp_url_to_ip ──────────────────────────────────────────


def test_cdp_resolve_leaves_localhost_unchanged():
    url = "http://localhost:9222"
    assert browser._resolve_cdp_url_to_ip(url) == url


def test_cdp_resolve_leaves_ip_literal_unchanged():
    url = "http://127.0.0.1:9222"
    assert browser._resolve_cdp_url_to_ip(url) == url


def test_cdp_resolve_returns_input_on_bad_url():
    # Garbage with no host resolves to itself (don't raise into _ensure_browser).
    url = "::::"
    assert browser._resolve_cdp_url_to_ip(url) == url


# ─── _truncate ───────────────────────────────────────────────────────


def test_truncate_under_limit_unchanged():
    text, cut = browser._truncate("hello", 100)
    assert text == "hello"
    assert cut is False


def test_truncate_over_limit_cuts_and_flags():
    text, cut = browser._truncate("abcdef", 3)
    assert text == "abc"
    assert cut is True


def test_truncate_negative_limit_means_no_truncation():
    text, cut = browser._truncate("abcdef", -1)
    assert text == "abcdef"
    assert cut is False
