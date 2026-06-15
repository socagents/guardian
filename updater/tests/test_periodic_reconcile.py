"""The connector reconcile must run on a timer, not only at updater startup.

v0.17.128 (#123) added the periodic digest-drift pass. Issue #42 extends the
loop to ALSO start missing containers each tick (self-heal): a create-time
start failure used to leave an instance container-less until the next updater
restart, because nothing started the missing container after the fact.

The loop fires once ~30s after boot (one-shot) AND every
PERIODIC_RECONCILE_INTERVAL_S thereafter — guardian-updater rarely restarts,
so a startup-only reconcile would never recover state that drifts between
restarts.
"""

import asyncio
import os

# Match test_main.py: set MCP_TOKEN before importing src.main so the auth
# middleware initializes with a known value.
os.environ.setdefault("MCP_TOKEN", "test-mcp-token")

from src import main as updater_main  # noqa: E402

_EMPTY_DRIFT = {"drifted": [], "recreated": [], "unchanged": [], "failed": []}
_EMPTY_CONTAINERS = {"reconciled": [], "skipped": [], "failed": []}


def _patch_container_reconcile(monkeypatch, sink=None):
    """Stub the missing-container self-heal pass so the loop doesn't make real
    HTTP calls to a (non-existent) agent during the test."""
    async def _fake_containers():
        if sink is not None:
            sink.append(1)
        return dict(_EMPTY_CONTAINERS)

    monkeypatch.setattr(
        updater_main, "reconcile_connector_containers", _fake_containers
    )


def test_periodic_reconcile_loops_repeatedly(monkeypatch):
    """The loop must keep invoking the reconcile, not fire once."""
    calls = []
    _patch_container_reconcile(monkeypatch)

    async def _fake_reconcile():
        calls.append(1)
        return dict(_EMPTY_DRIFT)

    monkeypatch.setattr(
        updater_main, "_reconcile_connector_digest_drift", _fake_reconcile
    )

    async def _run_briefly():
        task = asyncio.create_task(
            updater_main._periodic_reconcile(0.001)
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


def test_periodic_loop_self_heals_missing_containers(monkeypatch):
    """Issue #42 — each tick must invoke the missing-container reconcile, not
    only the digest-drift pass."""
    container_calls = []
    _patch_container_reconcile(monkeypatch, sink=container_calls)

    async def _fake_drift():
        return dict(_EMPTY_DRIFT)

    monkeypatch.setattr(
        updater_main, "_reconcile_connector_digest_drift", _fake_drift
    )

    async def _run_briefly():
        task = asyncio.create_task(updater_main._periodic_reconcile(0.001))
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(_run_briefly())
    assert len(container_calls) >= 2, (
        "periodic loop did not run the missing-container self-heal each tick"
    )


def test_periodic_reconcile_survives_a_failing_tick(monkeypatch):
    """A reconcile that raises must not kill the loop — the next tick runs."""
    calls = []
    _patch_container_reconcile(monkeypatch)

    async def _flaky_reconcile():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")  # first tick fails
        return dict(_EMPTY_DRIFT)

    monkeypatch.setattr(
        updater_main, "_reconcile_connector_digest_drift", _flaky_reconcile
    )

    async def _run_briefly():
        task = asyncio.create_task(
            updater_main._periodic_reconcile(0.001)
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


def test_reconcile_recreates_when_running_image_pruned(monkeypatch):
    """Regression: the digest-drift reconcile must NOT crash when the running
    container's image was pruned locally (common on the dev cycle once the new
    image is pulled). `container.image` then raises ImageNotFound — the old
    code let it bubble and 500'd the operator-callable reconcile/digests
    endpoint. The fix treats a missing image as definitely-drifted + recreates.
    """
    import httpx
    from docker.errors import ImageNotFound

    class _PrunedImageContainer:
        name = "guardian-connector-xsoar-primary-xsoar"
        attrs = {"Config": {"Env": ["INSTANCE_ID=inst-123"]}}

        @property
        def image(self):
            raise ImageNotFound("No such image: sha256:deadbeef")

    class _FakeContainers:
        def list(self, **kw):
            return [_PrunedImageContainer()]

    class _FakeDockerClient:
        containers = _FakeContainers()

    monkeypatch.setattr(updater_main, "_docker_client", lambda: _FakeDockerClient())
    monkeypatch.setattr(updater_main, "_connector_digest", lambda cid: "sha256:newpinneddigest00000000")
    monkeypatch.setattr(updater_main, "KNOWN_CONNECTORS", {"xsoar"})
    monkeypatch.setattr(updater_main, "MCP_TOKEN", "tok")

    posted: dict = {}

    class _FakeResp:
        status_code = 200
        text = "ok"

        def json(self):
            return {"ok": True}

    class _FakeAsyncClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, headers=None, json=None):
            posted["url"] = url
            posted["json"] = json
            return _FakeResp()

    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

    summary = asyncio.run(updater_main._reconcile_connector_digest_drift())

    # Did NOT crash; recreated the drifted (image-pruned) container.
    assert posted.get("url", "").endswith(
        "/api/v1/connectors/xsoar/instances/primary-xsoar/start"
    )
    assert posted.get("json") == {"instance_id": "inst-123"}
    assert len(summary["recreated"]) == 1
