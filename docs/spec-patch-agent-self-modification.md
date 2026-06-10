# Spec patch: chat-driven agent self-modification

> **Audience**: maintainers of `kite-production/spark-agents/docs/spec.md`.
>
> Draft upstream-PR for `spec.md` v1.3, formalizing the model for
> agents that mutate their own runtime configuration via chat —
> jobs, settings, persona, skills, connector instances, API keys —
> gated by an inline approvals dance the operator resolves without
> leaving chat.
>
> Also serves as authoritative documentation for phantom's
> implementation while the upstream PR is in flight.

## Context

`spec.md` v1.2 anticipates **operator-driven** runtime CRUD over REST
(§7.7 runtime jobs, §6.10 settings/instances/providers) AND
**agent-driven** memory writes (§6.10 row "memory"). What it doesn't
connect: the *middle* of those two. Today agents can:

| Operation                                | v1.2 spec | Phantom shipped (Phase 11) |
|------------------------------------------|-----------|----------------------------|
| Read own state (jobs, settings, persona) | ❌ silent | ✅ 19 read tools           |
| Write own runtime data (jobs, settings)  | ❌ silent | ✅ 8 soft-write tools      |
| Destructive ops (delete, reset)          | ❌ silent | ✅ 6 destructive tools     |
| Credential ops (mint/rotate API keys)    | ❌ silent | ✅ 3 credential tools      |
| Approvals self-loop                      | ❌ silent | ✅ ApprovalSelfResolveError|
| Bundle-immutability boundary             | ⚠ implicit | ✅ tools.deny enforced    |

The §6.10 row 12 also notes a critical limitation: **`approvals.request()`
polls only — agents cannot create approval requests via the gateway in
v1.** This breaks platform-mode parity for the very thing chat-driven
self-mod needs.

## Proposal

Extend §6.10 + §7.2 + add a new §7.13 covering the four-tier model
phantom implements.

### Proposal A — Catalog of agent self-modification tools

Add a new built-in tool family alongside `memory_*`, `sessions_*`,
`knowledge_*`, `skills_*`. The runtime exposes them via the same
namespace (no connector prefix), and bundle authors enable them by
listing in `manifest.tools.allow[]`.

**Tier 1 — read** (no approval, surface for agent introspection):

```
jobs_list, jobs_get, jobs_runs
settings_get
personality_get
instances_list, instances_get
providers_list, providers_get
approvals_list_pending, approvals_list_history
notifications_list, notifications_unread_count
audit_search, audit_recent
api_keys_list                       # metadata only — never plaintext
manifest_get                        # the agent introspects its own contract
metrics_snapshot
health_status
```

**Tier 2 — soft writes** (approval-gated; default UI = green button):

```
jobs_create, jobs_update, jobs_run_now
personality_update                  # read-modify-write with diff
settings_update
notifications_dismiss, notifications_dismiss_all
approvals_resolve
```

**Tier 3 — destructive** (approval-gated; UI = red banner):

```
jobs_delete, skills_delete
personality_reset, settings_reset
instances_delete, providers_delete
```

**Tier 4 — credential** (approval-gated; UI = type-CONFIRM ceremony):

```
api_keys_create, api_keys_rotate, api_keys_revoke
```

### Proposal B — `risk_tier` on every approval row

Extend the `approvals` schema (spec §6.10 row "approvals", standalone
implementation `InProcessApprovalsBus` and platform implementation
`KafkaApprovalsBus`) with a `risk_tier` column:

```sql
risk_tier TEXT NOT NULL DEFAULT 'soft'
  -- one of: read | soft | destructive | credential
```

The field drives:

  - **UI rendering**: green / red banner / type-CONFIRM challenge.
  - **Audit filterability**: `WHERE risk_tier = 'destructive'` answers
    "every destructive op my agent attempted in the last 30 days."
  - **Future policy**: bundle authors can express tier-specific rules
    ("require two operators for credential tier"), once the spec
    grows multi-resolver semantics.

The bus's `request()` API gains a `risk_tier=` parameter; all tools in
Tier 2-4 pass their tier explicitly. Older deploys migrate via a
PRAGMA-driven `ALTER TABLE` that backfills with `'soft'`.

### Proposal C — `ApprovalSelfResolveError` defense

The bus's `resolve(approval_id, resolver, decision, ...)` MUST raise
when the row's `actor` (requester) equals the supplied `resolver`.
This is defense-in-depth for the chat-driven self-mod surface:

> An agent that issued a `personality_update` request must NOT also
> be able to call `approvals_resolve` to approve it. Without this
> check, the human-in-the-loop contract collapses to a no-op.

The check is at the **bus level**, not just the tool layer. So the
invariant holds regardless of which write path created the request:
REST endpoint, MCP tool, future cron-driven self-mod, etc.

### Proposal D — Inline approvals over the chat stream

Spec §6.10 row "approvals" today says *"agents cannot create approval
requests via the gateway in v1."* This is the platform-mode
limitation that breaks chat-driven self-mod parity.

Two extensions to lift it:

1. **Standalone (already works in phantom v0.2)**: gated tool calls
   create rows via `bus.request(actor='agent', risk_tier=…)` and
   block on `bus.wait_async`. The chat route detects the new pending
   row by polling `/api/v1/approvals?status=pending` (max 6s race),
   emits an `approval_pending` SSE event, the chat UI renders an
   inline approval card. Operator clicks Approve → bus resolves →
   tool call returns.

2. **Platform mode (proposed)**: extend the approvals gateway to
   accept agent-initiated requests. The agent's MCP-side tool gets
   a synchronous handle that resolves when the operator clicks
   Approve in the platform UI. Same external shape; different
   transport.

The SSE event contract for inline cards:

```jsonc
// "approval_pending" event
{
  "tool_call_id": "tc_<uuid>",      // correlates to the originating
                                     // tool_call event
  "approval_id":  "<uuid>",
  "tool":         "personality_update",
  "args":         { "blob_keys": ["responseStyle", "personalityMd"] },
  "risk_tier":    "soft",
  "created_at":   "2026-05-01T12:34:56.789012Z"
}
```

The args payload carries **key names, never values**, for two reasons:

  - **Privacy**: the approval row persists; full proposed values
    would land in a less-protected store.
  - **UX**: the card UI fetches current state and computes the diff
    at render time — cheaper than dumping the full diff into the row.

### Proposal E — Hard security boundary (Tier 5 deny)

Bundle-immutability at runtime is implicit in spec v1.2. Make it
explicit. The following tools MUST appear in `manifest.tools.deny[]`
and MUST NOT be available even with operator approval:

```yaml
tools:
  deny:
    - "manifest_set"              # bundle is immutable at runtime
    - "manifest_update"
    - "system_prompt_update"      # prompts/system.md ships with bundle
    - "tools_allow_update"        # agent cannot mutate own allow list
    - "tools_deny_update"
    - "approvals_humanrequired_update"  # cannot remove gates from itself
    - "shell_exec"                # already conventional
    - "file_write"                # already conventional
```

This is the security guarantee that makes the entire self-mod
surface safe to ship. The agent can configure its own *runtime data*
(jobs, settings, persona, runtime knowledge), but cannot alter its
own *bundle code* or escape the approvals gate.

## Why a four-tier model

The tiers arose from operator-experience patterns rather than
neat-hierarchy theory:

  - **Tier 1 (reads)** is the *introspection* surface. A SOC operator
    typing "what jobs do I have scheduled?" expects the agent to
    actually look — not paraphrase from memory of an older turn. No
    gate is needed because no audit-worthy state changes.

  - **Tier 2 (soft)** is the *common chat-driven config* surface.
    "Schedule a daily X", "always reply in three bullets", "change
    the default scenario". The default green-button approval is a
    one-click confirmation; the operator's mental cost is trivial
    once they trust the diff renderer.

  - **Tier 3 (destructive)** earns the *red banner* because the
    operator's attention is the friction. Without the banner an
    operator burning through 20 approvals could click Approve on a
    `jobs_delete` thinking it was a `jobs_update`. The visual
    difference catches the mistake before it fires.

  - **Tier 4 (credential)** earns the *type CONFIRM ceremony* because
    plaintext is unique: lost forever if not captured at approval
    time. No analog in destructive (a deleted job is recoverable by
    recreate; a reset persona is recoverable from history). The
    operator must be FORCED to read what's about to happen — the
    `kubectl delete` and `terraform destroy` precedent for irreversible
    operations.

## Reference implementation

In `kite-production/phantom`:

| Layer | File |
|---|---|
| Built-in tool catalog | `bundles/spark/mcp/src/usecase/builtin_components/self_mod_tools.py` |
| Approval gate helper | `bundles/spark/mcp/src/usecase/builtin_components/_approval_gate.py` |
| Bus extensions (risk_tier, self-resolve) | `bundles/spark/mcp/src/usecase/approvals_bus.py` |
| Personality store + REST | `bundles/spark/mcp/src/usecase/personality_store.py`, `bundles/spark/mcp/src/api/personality.py` |
| Chat-route SSE event | `mcp/agent/app/api/chat/route.ts` (search `approval_pending`) |
| Chat-route gating-aware polling | `mcp/agent/lib/approvals-config.ts`, same `route.ts` |
| Inline approval card | `mcp/agent/components/chat/approval-card.tsx` |
| Tier-5 deny boundary | `bundles/spark/manifest.yaml` `tools.deny[]` |
| Tests | `bundles/spark/mcp/tests/test_approvals_bus.py`, `test_approval_gate.py`, `test_personality_store.py` |

The phantom tree across the 8 commits:
- 36 self-mod tools (19 read + 8 soft + 6 destructive + 3 credential)
- 17 gated via `humanRequired[]`
- 8 forbidden via `tools.deny[]` (Tier-5 boundary)
- ~3000 lines added across backend, frontend, tests, journeys, and this patch

## Backwards compatibility

Every proposal is **additive**:

- Bundles that don't list any self-mod tools in `tools.allow[]`
  continue to work unchanged. The runtime simply doesn't expose
  them.

- Bundles that don't set `risk_tier` on existing approvals get
  `'soft'` by default — same UX as before this patch (default green
  button). Schema migration is idempotent ALTER TABLE on first boot.

- The `ApprovalSelfResolveError` change is back-compat at the
  contract level: `resolve()` previously had no constraint on
  resolver vs actor, so existing callers that pass distinct values
  (the operator UI's normal flow) keep working. Only new callers
  that re-introduce self-resolution are blocked.

- The Tier-5 deny list is opt-in: bundle authors who don't add it to
  `tools.deny[]` can ship a less-restricted bundle (at their own
  risk). Spec recommendation is the additive denylist for any bundle
  that allows Tier 2-4 self-mod tools.

## Open questions for upstream review

1. **Should `risk_tier` values be an enum or open string?** Phantom
   ships `read | soft | destructive | credential`. A future bundle
   might want `pii` or `external_api` tiers; an open string allows
   that, but loses static checking. Spec recommendation: closed enum
   in v1.3; reconsider if real demand for new tiers emerges.

2. **Two-operator approval for credential tier?** Some compliance
   regimes require N-of-M operator approvals. The current bus is
   single-operator-resolves. Worth a follow-up patch.

3. **Approval timeouts per tier?** Currently fixed at 5 minutes.
   Credential ops might warrant longer (operator might need to
   coordinate with a colleague before approving).

4. **Rate-limiting agent-initiated approvals.** A misbehaving agent
   could DoS the operator with hundreds of pending requests. The
   bus could enforce a per-actor rate limit (e.g. 10 pending
   requests per 5 minutes). Not implemented today; worth scoping.

These are explicitly OUT of v1.3 scope; documented here as v1.4+
candidates.
