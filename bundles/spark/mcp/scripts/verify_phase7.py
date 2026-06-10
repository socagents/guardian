"""Phase 7 verification — exercise the approvals bus end-to-end.

Run inside the guardian-mcp container with PYTHONPATH=/app/src:
  docker compose exec -T guardian-mcp python /app/src/../scripts/verify_phase7.py

What it covers:
  1. request() inserts a pending row
  2. resolve() in a parallel coroutine wakes wait_async()
  3. wait_async() returns ("approved", reason) — cross-loop signal works
  4. resolve() is idempotent — second call returns the original decision
  5. timeout path: a request never resolved transitions to "timeout"
"""

from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, "/app/src")

from usecase.approvals_bus import (
    InProcessApprovalsBus,
    set_approvals_bus,
)
from usecase.audit_log import SqliteAuditLog, set_audit_log


async def main() -> int:
    audit = SqliteAuditLog()
    set_audit_log(audit)
    bus = InProcessApprovalsBus()
    set_approvals_bus(bus)
    print("[1] bus initialized")

    # ─── Happy path: request → wait → resolve(approve) ─────
    aid = bus.request(
        tool="create_operation",
        namespaced="xsiam.run_xql_query",
        actor="agent",
        args={"adversary_id": "abc-123", "name": "phase7-verify"},
    )
    print(f"[2] requested: {aid}")

    async def resolver() -> None:
        await asyncio.sleep(0.5)
        approval = bus.resolve(
            aid, resolver="user:operator",
            decision="approved",
            reason="purple-team drill OK",
        )
        print(f"[3] resolved: status={approval.status if approval else None}")

    asyncio.create_task(resolver())
    status, reason = await bus.wait_async(aid, timeout=5)
    print(f"[4] waiter unblocked: status={status} reason={reason}")
    assert status == "approved", f"expected approved, got {status}"

    # ─── Idempotency ───────────────────────────────────────
    second = bus.resolve(aid, resolver="someone-else", decision="denied")
    assert second is not None
    assert second.status == "approved"  # still approved
    assert second.resolver == "user:operator"  # original resolver preserved
    print(f"[5] idempotent OK: status still {second.status}, "
          f"resolver still {second.resolver}")

    # ─── Timeout path ──────────────────────────────────────
    aid2 = bus.request(
        tool="send_webhook_log",
        namespaced="xsiam.send_webhook_log",
        actor="agent",
        args={},
    )
    print(f"[6] requested timeout-test: {aid2}")
    s2, r2 = await bus.wait_async(aid2, timeout=2)
    print(f"[7] timeout path: status={s2} reason={r2}")
    assert s2 == "timeout"

    # ─── Listing ───────────────────────────────────────────
    pending = bus.list_pending()
    recent = bus.list_recent(limit=10)
    print(f"[8] pending count={len(pending)}, recent={len(recent)} "
          f"(first status={recent[0].status if recent else None})")

    # ─── Unknown decision ──────────────────────────────────
    aid3 = bus.request(
        tool="create_operation",
        namespaced="xsiam.run_xql_query",
        actor="agent",
        args={},
    )
    try:
        bus.resolve(aid3, resolver="user:operator", decision="maybe")
        raise AssertionError("expected ValueError on bad decision")
    except ValueError as exc:
        print(f"[9] bad decision rejected: {exc}")

    print("\nAll Phase 7 bus assertions passed.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
