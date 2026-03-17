## Summary

Design validation detected a significant deviation between the merged build
and the original spec.

**This is a correction issue** — the coding agent should adjust the existing
implementation to better align with the spec's design intent.

## Source

- **Original Issue:** #{{ORIGINAL_ISSUE}}
- **Merged PR:** #{{MERGED_PR}}
- **Spec:** `{{SPEC_PATH}}`
- **Spec Commit:** `{{SPEC_COMMIT}}`
- **Validation Run:** [{{RUN_ID}}]({{RUN_URL}})

## Deviation Details

{{DEVIATION_SUMMARY}}

### What the spec expected

{{SPEC_EXPECTED}}

### What was built

{{BUILD_DELIVERED}}

### Impact

{{IMPACT}}

## Scope

{{SUGGESTED_FIX}}

This issue should **only** address the deviation described above.
Do not refactor or expand beyond what is needed to bring the build
closer to the spec's intent.

## Out of Scope

- Bug fixes unrelated to the deviation
- Code quality improvements
- Additional features not in the spec
- Changes to the spec itself

## Acceptance Criteria

- [ ] The deviation described above is resolved
- [ ] Existing functionality is preserved (no regressions)
- [ ] The build is closer to the spec's design intent

## Dependencies

depends on #{{ORIGINAL_ISSUE}} (the original implementation)

<!-- AGENT_MSG agent=validation action=deviation-issue spec={{SPEC_PATH}} original=#{{ORIGINAL_ISSUE}} -->
