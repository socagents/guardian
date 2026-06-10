# Guardian AI Layer — Article Alignment & Adoption Status

This repo is bringing its coding-agent layer into alignment with Anthropic's article *"How Claude Code works in large codebases: best practices and where to start"* ([read it here](https://claude.com/blog/how-claude-code-works-in-large-codebases-best-practices-and-where-to-start)).

The article's thesis: **the harness — the ecosystem built around the model — determines how Claude Code performs more than the model alone.**

> *"AI Layer" is our name for that harness, borrowed from [coleam00/helpline](https://github.com/coleam00/helpline) (the article's reference implementation). Anthropic's article describes the harness and its components; it does not use the phrase "AI Layer."*

This file documents which article components Guardian has adopted, and where each one lives. Updated as adoption progresses.

---

## Phase tracking (4 phases per the article)

| Phase | What it ships | Status | Issue |
|---|---|---|---|
| **1 — Foundation** | Lean root CLAUDE.md, subdirectory CLAUDE.md hierarchy, CODEBASE_MAP.md, .claudeignore, AI-LAYER.md (this file) | **✓ Done** | [#77](https://github.com/kite-production/guardian/issues/77) (closed) |
| **2 — Infrastructure** | `.claude/settings.json`, explorer subagent, SessionStart + Stop hooks, path-scoped skills, codebase-search MCP | **✓ Done** | [#78](https://github.com/kite-production/guardian/issues/78) (closed) |
| **3 — Governance** | guardian-ai-layer plugin, marketplace.json, validator harness, CICD review cadence | **✓ Done** | [#79](https://github.com/kite-production/guardian/issues/79) (closed) |
| **4 — Guardian product (optional)** | Harness validation observability page (`/observability/harness`) | P3, deferred | [#80](https://github.com/kite-production/guardian/issues/80) |

---

## The extension points — article → artifact → status

| Extension point | What the article says | Guardian artifact | Status |
|---|---|---|---|
| **CLAUDE.md files** | Loaded first; lean root, subdirectory files load additively as Claude walks the tree | Root [`CLAUDE.md`](CLAUDE.md) (lean) + 6 subdirectory files: [`mcp/agent/`](mcp/agent/CLAUDE.md), [`bundles/spark/mcp/`](bundles/spark/mcp/CLAUDE.md), [`bundles/spark/connectors/`](bundles/spark/connectors/CLAUDE.md), [`scripts/`](scripts/CLAUDE.md), [`installer/`](installer/CLAUDE.md), [`updater/`](updater/CLAUDE.md) | **✓ Phase 1** |
| **Hooks** | Best use is *self-improving* setup, not just prevention. *"A start hook can load team-specific context dynamically. A stop hook can reflect on what happened during a session and propose CLAUDE.md updates while the context is fresh."* | [`.claude/hooks/session_start_context.py`](.claude/hooks/session_start_context.py) (dynamic SessionStart — branch + areas + in-flight issues + recent commits), [`.claude/hooks/propose_claude_md.py`](.claude/hooks/propose_claude_md.py) + [`.claude/hooks/reflect_claude_md.py`](.claude/hooks/reflect_claude_md.py) (self-improving Stop hook with recursion guard + diff-fingerprint dedup + deterministic fallback) | **✓ Phase 2** |
| **Skills** | On-demand expertise, progressive disclosure, scoped to specific paths | [`.claude/skills/`](.claude/skills/) with 5 path-scoped coding skills: `connector-add`, `mcp-tool-add`, `release-tag-flow`, `help-page-update`, `agent-page-add`. Each carries `paths:` frontmatter (validator asserts). NB: Guardian's RUNTIME skills (`bundles/spark/mcp/skills/`) already follow this pattern for the chat agent — the AI Layer brings the same pattern to the CODING-agent layer | **✓ Phase 2** |
| **Plugins** | Bundle skills/hooks/MCP into installable packages, distribute via a marketplace | [`tooling/guardian-ai-layer/`](tooling/guardian-ai-layer/) + [`tooling/.claude-plugin/marketplace.json`](tooling/.claude-plugin/marketplace.json). Bundles ONLY the repo-agnostic parts (explorer subagent, propose/reflect hooks, codebase-search MCP, generic scoped-tests skill). Guardian-specific skills intentionally stay in `.claude/skills/`. NB: Guardian's RUNTIME has the connector marketplace (analog) — Phase 3 brought the pattern to the coding-agent layer | **✓ Phase 3** |
| **LSP** | Symbol-level precision instead of text-pattern false positives | [`pyproject.toml`](pyproject.toml) (repo root) configures `[tool.pyright]` with include/exclude paths covering every Python source tree; documents `pip install pyright "mcp[cli]"` as the canonical dev-tool install. Validator asserts pyright is declared. TypeScript LSP via Next.js (already wired) | **✓ Phase 3** |
| **MCP servers** | Expose structured search as a callable tool | [`.mcp.json`](.mcp.json) + [`tooling/mcp/codebase_search.py`](tooling/mcp/codebase_search.py) (AST-based `where_is` / `find_references` / `outline` over every Python source tree). Validator's [`check_mcp.py`](tooling/validate/check_mcp.py) does a real stdio handshake. TypeScript coverage tracked as Phase 4+ follow-up | **✓ Phase 2 + Phase 3 (handshake)** |
| **Subagents** | Split exploration from editing — read-only mapper, separate context window | [`.claude/agents/guardian-explorer.md`](.claude/agents/guardian-explorer.md) — tools: `Read, Grep, Glob` ONLY (no Write/Edit/Bash). Validator asserts no write tools | **✓ Phase 2** |
| **Validator** | Confirms the harness still wires up correctly + catches drift in CI | [`tooling/validate/validate_all.py`](tooling/validate/validate_all.py) — 15 checks covering hierarchy, ignore, settings, subagent read-only, hooks compile, skills `paths:`, MCP config + handshake, plugin marketplace, plugin/repo SHA sync, pyright. Wired in [`.github/workflows/ai-layer-validate.yml`](.github/workflows/ai-layer-validate.yml) | **✓ Phase 3** |
| **Review cadence** | Pattern 2 — *"actively maintain CLAUDE.md as models evolve"* — 3-6 month review + post-major-model-release trigger | [`docs/CICD.md § AI Layer review cadence`](docs/CICD.md) — codifies when to review, the audit checklist, what to delete vs keep | **✓ Phase 3** |

---

## Pattern adoption (article's 3 configuration patterns)

### Pattern 1 — Make the codebase navigable at scale

- **Lean, layered CLAUDE.md** — root holds only repo-wide agent-behavior contracts + critical gotchas; each major subsystem carries its own conventions. **✓ Phase 1.**
- **Initialized in subdirectories**, not just the root — Claude walks up the tree, so local context never gets lost. **✓ Phase 1** (6 subdirectory files at `mcp/agent/`, `bundles/spark/mcp/`, `bundles/spark/connectors/`, `scripts/`, `installer/`, `updater/`).
  <!-- [guardian v0.1.0] Retired: xlog/CLAUDE.md from the subdirectory list — simulation subsystem removed; scripts/CLAUDE.md took its slot -->
- **`CODEBASE_MAP.md`** — find where a feature lives before exploring. **✓ Phase 1.**
- **`.claudeignore`** — generated files, baked vendor data, caches, node_modules, lockfiles excluded. **✓ Phase 1** (notable inclusion: `bundles/spark/connectors/cortex-content/baked/` — 576 vendor catalog files that ship in the agent image but aren't source).
- **Scoped test commands** — each subdirectory `CLAUDE.md` documents its local pytest + tsc + lint snippet. **✓ Phase 1** (root's full pre-deploy gate stays in root; per-directory commands in each subdirectory file). Plus a portable `scoped-tests` skill in the plugin payload at `tooling/guardian-ai-layer/skills/scoped-tests/`. **✓ Phase 3.**
- **LSP** — symbol search instead of grep false-positives. `pyright` configured at root `pyproject.toml` covering every Python source tree. **✓ Phase 3.**

### Pattern 2 — Actively maintain CLAUDE.md as models evolve

- **The `Stop` hook** is the proactive half — `propose_claude_md.py` (deterministic trigger) + `reflect_claude_md.py` (background reflector invoking headless `claude -p` against the session diff to draft `CLAUDE.md` edits into `.claude/claude-md-review.md`). Recursion guard + deterministic fallback. **✓ Phase 2.**
- **Review cadence:** a full `CLAUDE.md` / skills / hooks review every **3–6 months**, and after any major model release (Opus 4.8, Sonnet 5, etc.). Codified in [`docs/CICD.md § AI Layer review cadence`](docs/CICD.md) as part of Phase 3 — includes the audit checklist + ownership + concrete trigger phrasing. **✓ Phase 3.**
- **Validator** as the third leg — runs in CI on every AI Layer push to catch drift the moment it happens. **✓ Phase 3.**

### Pattern 3 — Assign ownership

- The **Platform Team** (a DRI) owns `tooling/`, `.claude/`, and the `CLAUDE.md` hierarchy. Designation pending — codified in Phase 3.
- The **plugin is the distribution mechanism** — a new repo or new engineer runs one install and gets the team's baseline layer on day one. Pending Phase 3.

---

## Getting started — the article's 4 phases mapped to Guardian

| Phase | Article | Guardian artifacts |
|---|---|---|
| **Foundation** | CLAUDE.md hierarchy, ignore rules, LSP | Root + 6 subdirectory `CLAUDE.md`, `CODEBASE_MAP.md`, `.claudeignore`. LSP verification deferred to Phase 2. |
| **Infrastructure** | skills, MCP, plugin distribution | `.claude/skills/`, `.claude/agents/`, `.claude/hooks/`, `.mcp.json` + `tooling/mcp/codebase_search.py`. |
| **Governance** | review requirements, DRI, approvals | `tooling/guardian-ai-layer/` plugin + marketplace.json, `tooling/validate/validate_all.py`, `docs/CICD.md` § AI Layer review cadence. |
| **Scale** | expand skills/plugins, iterate CLAUDE.md, periodic review | The `Stop` hook + the 3–6 month cadence (Phase 3 mechanics). Long-term: the Guardian-product harness validation page ([#80](https://github.com/kite-production/guardian/issues/80)). |

---

## Guardian-runtime vs coding-agent layer — both exist

Guardian is itself an agentic platform. Some article concepts map cleanly onto Guardian's runtime as well as the coding agent:

| Concept | Guardian RUNTIME (the product) | CODING-AGENT layer (this AI Layer) |
|---|---|---|
| Skills | `bundles/spark/mcp/skills/` — used by the chat agent at runtime | `.claude/skills/` — used by Claude Code when editing the repo |
| Hooks | Guardian's hooks framework (settings/hooks page) — fires on chat events | `.claude/hooks/` — fires on Claude Code session events |
| Subagents | Guardian's `/agents` page — runtime agent definitions | `.claude/agents/guardian-explorer.md` — read-only mapper for coding sessions |
| MCP servers | The embedded MCP at `bundles/spark/mcp/` — drives the chat agent | `tooling/mcp/codebase_search.py` — symbol search for coding sessions |
| Plugin marketplace | The connector marketplace at `/connectors` + the marketplace.db | `tooling/.claude-plugin/marketplace.json` — coding-agent plugins |

Phase 4 ([#80](https://github.com/kite-production/guardian/issues/80)) optionally mirrors the validator pattern INTO Guardian's runtime — a `/observability/harness` page that surfaces Guardian's own runtime equivalents (skills well-formed, agents runnable, hooks valid, MCP tool count). Marked P3 / optional because most of the data is already surfaced piecemeal on individual pages.

---

## Caveats

- Guardian is **not** a green-field implementation of the article's harness — it's a substantial existing product where the patterns are being layered in incrementally. Phase 1's lean root still carries ~540 lines because the agent-behavior contracts (spec-driven workflow, pre-deploy gate, smoke-test discipline, credential guardrail, release-readiness gate, canonical-state discipline) are genuinely load-bearing repo-wide. The article's "lean root" guidance presumes simpler base contracts; Guardian's enterprise discipline keeps the root substantive.
- Architecture content (which the article would NOT want in root) is now split into subdirectory `CLAUDE.md` files + `CODEBASE_MAP.md`. That's where the 363-line reduction in the root came from.
- The CODING-agent layer (this file) does NOT replace Guardian's RUNTIME documentation (`/help/architecture`, `/help/user`, `journeys.ts`). Those are operator-facing; the AI Layer is contributor-facing.

---

## Validation

After Phase 3 lands, run:

```bash
python tooling/validate/validate_all.py
```

This will check that every article component is well-formed:
- CLAUDE.md hierarchy exists (root + N subdirectory files)
- `.claudeignore` excludes baked catalog
- `.claude/settings.json` is valid JSON + has expected schema
- `.claude/agents/guardian-explorer.md` has NO write tools
- All hooks compile
- All skills have `paths:` frontmatter
- `.mcp.json` references a valid script
- `tooling/mcp/codebase_search.py` initializes correctly
- pyright is configured + initializes

CI integration: `.github/workflows/build-agent.yml` will run the validator and fail the build if any check fails. Until Phase 3, the validator doesn't exist — track gaps manually here.

---

## Related issues

- [#77 — Phase 1 Foundation](https://github.com/kite-production/guardian/issues/77)
- [#78 — Phase 2 Infrastructure](https://github.com/kite-production/guardian/issues/78)
- [#79 — Phase 3 Governance](https://github.com/kite-production/guardian/issues/79)
- [#80 — Phase 4 P3 Guardian-product harness validation page](https://github.com/kite-production/guardian/issues/80)
