# Guardian project loop

<!-- Lands at .claude/loop.md — customizes the bare `/loop` prompt for this repo.
     The unattended scheduled loop and the interactive `/loop` share ONE
     procedure: docs/loop/PLAYBOOK.md. Keep them convergent. -->

Run the Guardian self-learning loop trainer pass. Follow
**`docs/loop/PLAYBOOK.md`** exactly — ORIENT → SCOPE → FIX → VERIFY (full gate)
→ CHECK (adversarial subagent) → SHIP + STATE. One coherent unit per iteration.

Rules that survive every iteration (also enforced by the playbook):
- Read the repo CLAUDE.md contracts before editing; never commit credentials
  (`.env`, `.env.vm`, `scripts/loop/loop.env` stay local).
- Never push on a red gate or a checker rejection.
- The loop's memory is `.guardian-loop/state.json` + `docs/loop/state.md` — read
  it at the start (ORIENT) and write it at the end (SHIP + STATE).
- End the iteration after one unit (or a clean no-op).
