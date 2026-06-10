# R2 — Data Sources Vendor Grouping + Card Redesign (v0.11.0)

**Status**: In-progress, autonomous build. Builds on R1 (v0.10.0) which shipped `vendor_map.yaml`.

## Goal

Replace the dense per-pack grid on `/data-sources` (197 cards) with a vendor-grouped layout (~110 outer cards), redesigned card shape (icon-left, title+badges-right), inline expand-to-show-inner-packs interaction, category badges derived from pack metadata. Remove `agentix` noise from supportedModules pills.

## Non-goals (deferred to R3)

- Per-data-source YAML migration
- CRUD operations on data sources (POST/PUT/DELETE)
- Operator-uploaded custom data sources

## Data layer changes

### Catalog row enrichment (server-side at serve time)

`GET /api/v1/data-sources/catalog` (the rolled-up endpoint at `bundles/spark/mcp/src/api/data_sources.py:catalog_data_sources`) gains 4 enrichment fields per row, joined from `vendor_map.yaml` (R1) + per-pack `pack_metadata.json`:

```python
row.update({
    "vendor_key": "microsoft",
    "vendor_display_name": "Microsoft",
    "vendor_primary_color": "#0078D4",
    "categories": ["Analytics & SIEM", "Cloud Security"],  # from pack_metadata.json
})
```

Enrichment uses a process-cached lookup table built on first call (vendor_map.yaml + scan of all 197 pack_metadata.json files). Cost: ~30ms one-time per process; subsequent calls O(1) per row.

### Why not at bake time

The bake script (`scripts/refresh_cortex_baked_catalog.py`) is maintainer-only. Enriching at serve time means changes to `vendor_map.yaml` reflect immediately on the next request without a rebake.

## UI layer

### `VendorCard` (replaces `BrowsePackCard` in Browse view)

```
┌─────────────────────────────────────────────────────────────┐
│  ┌──────────┐  Microsoft                              ▼     │
│  │          │  26 data sources                              │
│  │ [logo]   │  [SIEM] [Cloud] [Network] [Email]             │
│  │          │                                                │
│  └──────────┘                                                │
└─────────────────────────────────────────────────────────────┘
```

- Icon: 96×96, left-aligned
- Title: vendor display_name
- Subtitle: "{N} data sources"
- Category badges: from grouped pack categories (mapped via `categories.ts`)
- Expand chevron on right
- Click anywhere on card → toggles expand state

### `PackRow` (inside expanded VendorCard)

```
  • cisco_secure_endpoint_raw          [Install]  →
    AMP / Cisco Secure Endpoint
    EDR · 16 fields
```

- Per-pack row inside the expanded vendor card
- Click row body → opens DetailDrawer
- Install button → existing handleInstall path

## Category-to-badge mapping

`mcp/agent/app/data-sources/categories.ts`:

```ts
export const CATEGORY_LABELS: Record<string, string> = {
  "Analytics & SIEM": "SIEM",
  "Network Security": "Network",
  "Endpoint": "EDR",
  "Cloud Security": "Cloud",
  "Cloud Services": "Cloud",
  "Cloud Service Provider": "Cloud Provider",
  "Identity and Access Management": "IAM",
  "Data Enrichment & Threat Intelligence": "Threat Intel",
  "Email": "Email",
  "Vulnerability Management": "Vuln",
  "IT Services": "IT",
  "CI/CD": "DevOps",
};
```

Outer vendor card aggregates categories across its inner packs, dedups, maps via this table, shows up to 4 badges.

## Agentix filter

A helper `filterAgentix(supportedModules: string[])` strips `"agentix"` everywhere supportedModules renders. All 197 packs include agentix; it's noise, not information.

## Smoke matrix

1. Browse view renders ~110 vendor cards (not 197 pack cards).
2. Icon-left layout verified visually in both themes via Playwright screenshot.
3. Expand interaction works on Microsoft (26 packs) and Cisco (9 packs).
4. Category badges show on outer cards.
5. No "agentix" string appears in any pill.
6. Pre-deploy gate green.
7. Auto-deploy lands on phantom-vm; visual smoke in both themes.

## Capability acceptance

Operator opens `/data-sources`, sees vendor-grouped cards, can read category labels at a glance, clicks any vendor to see and install individual data sources from within the expanded view. No agentix clutter.

## Files

```
docs/superpowers/specs/2026-05-23-data-sources-vendor-grouping-r2-design.md   NEW (this file)
bundles/spark/mcp/src/api/data_sources.py                                     MODIFIED (enrichment in catalog_data_sources)
mcp/agent/app/data-sources/categories.ts                                      NEW (category-to-badge mapping)
mcp/agent/app/data-sources/page.tsx                                           MODIFIED (VendorCard, PackRow, filterAgentix)
CHANGELOG.md, mcp/agent/lib/release-notes.ts                                  MODIFIED (entries)
```
