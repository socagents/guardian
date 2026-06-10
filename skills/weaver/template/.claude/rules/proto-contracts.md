---
paths:
  - "contracts/**"
---

# Proto Contract Conventions

## Tooling

- Schema management: Buf CLI (`buf.yaml` config).
- Lint: `buf lint`
- Generate: `buf generate`
- Breaking change check: `buf breaking --against .git#branch=main`

## Style Rules

- Package names: `kite.v1.<service>` (e.g., `kite.v1.gateway`).
- Service names: PascalCase matching the service (e.g., `GatewayService`).
- RPC names: PascalCase verb-noun (e.g., `CreateSession`, `ListTools`).
- Message names: PascalCase (e.g., `CreateSessionRequest`, `CreateSessionResponse`).
- Field names: snake_case (e.g., `session_id`, `created_at`).
- Enum values: UPPER_SNAKE_CASE with type prefix (e.g., `STATUS_ACTIVE`).

## Backwards Compatibility

- Never remove or rename existing fields — deprecate them instead.
- Never change field numbers.
- New fields must be optional (no required fields in proto3).
- Run `buf breaking` before merging any contract changes.
- Breaking changes require a new API version (`v2`).

## Generated Code

- Generated code goes in language-specific output directories (configured in `buf.gen.yaml`).
- Never edit generated files. Modify the `.proto` source instead.
- Regenerate after any proto change: `buf generate`.
