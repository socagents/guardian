"""v0.17.128 (#123) — the connector digest-drift reconcile must run on a
timer, not only at updater startup.

The v0.6.66 reconcile fired once ~30s after boot. But guardian-updater rarely
restarts (its image isn't rebuilt on the dev cycle), so a connector pin that
changed between restarts never reconciled into the running container — the
cortex-xdr container went stale twice this way. The periodic loop closes that.
"""

import asyncio
import os

# Match test_main.py: set MCP_TOKEN before importing src.main so the auth
# middleware initializes with a known value.
os.environ.setdefault("MCP_TOKEN", "test-mcp-token")

from src import main as updater_main  # noqa: E402


def test_periodic_drift_reconcile_loops_repeatedly(monkeypatch):
    """The loop must keep invoking the reconcile, not fire once."""
    calls = []

    async def _fake_reconcile():
        calls.append(1)
        return {"drifted": [], "recreated": [], "unchanged": [], "failed": []}

    monkeypatch.setattr(
        updater_main, "_reconcile_connector_digest_drift", _fake_reconcile
    )

    async def _run_briefly():
        task = asyncio.create_task(
            updater_main._periodic_drift_reconcile(0.001)
        )
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(_run_briefly())
    assert len(calls) >= 2, (
        f"periodic reconcile fired only {len(calls)}x — expected a loop"
    )


def test_periodic_reconcile_survives_a_failing_tick(monkeypatch):
    """A reconcile that raises must not kill the loop — the next tick runs."""
    calls = []

    async def _flaky_reconcile():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")  # first tick fails
        return {"drifted": [], "recreated": [], "unchanged": [], "failed": []}

    monkeypatch.setattr(
        updater_main, "_reconcile_connector_digest_drift", _flaky_reconcile
    )

    async def _run_briefly():
        task = asyncio.create_task(
            updater_main._periodic_drift_reconcile(0.001)
        )
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(_run_briefly())
    assert len(calls) >= 2, "loop died after a failing tick instead of continuing"


def test_periodic_reconcile_interval_is_positive():
    assert updater_main.PERIODIC_RECONCILE_INTERVAL_S > 0
