# R1 — Data Sources Logo Infrastructure (v0.10.0)

**Status**: Approved 2026-05-22 — proceeding in autonomous build/deploy/test loop.

## Goal

Replace the current mixed PNG/SVG logo state with theme-aware SVG variants for every one of the 197 packs in the cortex-content catalog, while capturing vendor identity as a side-effect that R2 consumes for UI grouping.

## Non-goals (deferred)

- Vendor-grouped UI rendering (R2)
- Card layout redesign — icon-left, click-to-expand (R2)
- Category labels on outer card (R2)
- "Agentix-only" filter (R2)
- YAML-per-data-source + CRUD operations (R3)
- Operator-uploaded custom logos (R3)

## Architecture

### File layout

```
bundles/spark/connectors/cortex-content/baked/
  vendor_map.yaml                                       ← NEW (single source of truth for vendor→pack)
  LICENSES.md                                           ← NEW (per-source SVG provenance)
  Packs/<pack>/
    pack_metadata.json                                  ← existing
    Integrations/<int>/
      <int>_image_light.svg                             ← NEW (per-vendor light variant, brand-color on light bg)
      <int>_image_dark.svg                              ← NEW (per-vendor dark variant, lightened/inverted)
      <int>_image.png                                   ← REMOVED at end of R1
      <int>_dark.svg                                    ← REMOVED at end of R1 (subsumed by _image_dark.svg)
```

### Vendor map shape

```yaml
# Single source of truth: pack → canonical vendor. Consumed by:
#   • R1's sourcing pipeline (one SVG per vendor, shared across packs)
#   • R2's UI for vendor-grouped cards
#   • R3's future per-data-source YAML migration
vendors:
  microsoft:
    display_name: "Microsoft"
    aliases: [Azure, "Microsoft 365", Defender, Sentinel]
    primary_color: "#0078D4"
    packs: [AzureFlowLogs, AzureAppService, AzureDevOps, ...]
    light_svg: vendor_svgs/microsoft_light.svg          # symlink target
    dark_svg: vendor_svgs/microsoft_dark.svg
    sources: {light: "gilbarbara/logos@v3.x", dark: "gilbarbara/logos@v3.x"}
    fidelity: branded                                   # branded | approximate | wordmark
```

Per-pack override is supported via an optional `pack_logo_override` field for cases where a pack's product logo differs meaningfully from the vendor's corporate logo.

### Theme-aware route

```
GET /api/v1/data-sources/logo/<pack>                 → light variant (backwards-compat default)
GET /api/v1/data-sources/logo/<pack>?theme=light     → <int>_image_light.svg
GET /api/v1/data-sources/logo/<pack>?theme=dark      → <int>_image_dark.svg
```

Server-side: resolve pack → vendor via `vendor_map.yaml`, serve vendor's SVG. Multiple packs sharing a vendor return the SAME bytes (browser cache key = vendor URL).

### UI consumption

`mcp/agent/app/data-sources/page.tsx`'s `BrowsePackCard` component reads the active theme from the Material 3 token system (`[data-theme="light"]` attribute) and passes it to the logo URL. React re-renders on theme switch → URL changes → browser fetches the matching variant.

## Sourcing pipeline

New maintainer script: `scripts/source_vendor_svgs.py`

Priority order per vendor:
1. **Online repos**: gilbarbara/logos → svglogos.dev → worldvectorlogo → SimpleIcons (fallback)
2. **demisto/content**: existing fetch pattern from v0.9.3 — reuse `_dark.svg` if quality is good, plus fetch light variants
3. **LLM-rendered**: hand-crafted SVG for gaps; both light + dark variants produced

Staging workflow:
- Fetched candidates land in `_staging/<vendor>/{light,dark}/source-N.svg`
- Each candidate has a `source-license.txt` sidecar (URL + license string)
- Maintainer (the agent in this run) reviews candidates → picks best per variant
- Selected candidates moved to `baked/vendor_svgs/<vendor>_{light,dark}.svg`
- Symlinks created under `Packs/<pack>/Integrations/<int>/<int>_image_{light,dark}.svg`

LICENSES.md tracks per-source provenance for MIT-compatibility audit.

## Smoke matrix

1. ✓ agent-verified — all 197 packs render a logo in light theme, 0 console 404s (Playwright + console scan)
2. ✓ agent-verified — same in dark theme
3. ✓ agent-verified — theme toggle: light↔dark, logos transition cleanly (no broken images)
4. ✓ agent-verified — `?theme=light` and `?theme=dark` return different bytes for the same pack
5. ✓ agent-verified — no `_image.png` files remain in `cortex-content/baked/Packs/`
6. ✓ agent-verified — `vendor_map.yaml` has all 197 packs distributed across canonical vendors, no orphans
7. ✓ agent-verified — validator 16/16 → 17/17 with new `check_pack_theme_variants_complete()`
8. ✓ agent-verified — `LICENSES.md` covers every non-LLM-rendered SVG with a MIT-compatible source

## Risks + mitigations

| Risk | Mitigation |
|---|---|
| LLM-rendered SVG looks visually approximate | Tag `fidelity: approximate` in vendor_map; non-blocking for release; future iteration replaces |
| Theme switch brief broken-image flash | `loading="lazy"` + browser cache + 1-day Cache-Control (existing) → warm cache after first visit |
| Source license is non-MIT-compatible | Validator rejects on commit; falls through to LLM-render queue |
| Vendor classification is subjective | `vendor_map.yaml` is human-readable, committed; operator can override mid-review |
| Per-vendor sharing wrong for some packs | `pack_logo_override` field per pack supports per-pack override |

## Capability acceptance

The operator visits `/data-sources` in either theme; every one of 197 packs shows a recognizable vendor logo with brand-appropriate coloring for the active theme. Theme toggle transitions cleanly. No PNGs remain in the catalog. The vendor_map.yaml is committed and consumable by R2.
