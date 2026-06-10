---
id: XQL-423-90ce4be4
title: PANW NGFW | Analysis of Threat Categories in Specific Zones
category: investigation
dataset: panw_ngfw_threat_raw
tags:
  - comp
  - sort
  - panw_ngfw_threat_raw
  - source:dataset
  - operator-authored
---

# PANW NGFW | Analysis of Threat Categories in Specific Zones

**Dataset**: `panw_ngfw_threat_raw`

```sql
dataset = panw_ngfw_threat_raw
| comp count() as threat_count by from_zone, to_zone, threat_category
| sort desc threat_count
```

## When to use

Categorizes Next-Generation-Firewall (NGFW) threats based on the source and destination zones

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
