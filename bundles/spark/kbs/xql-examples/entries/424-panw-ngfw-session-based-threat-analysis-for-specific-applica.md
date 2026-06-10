---
id: XQL-424-881c8287
title: PANW NGFW | Session-Based Threat Analysis for Specific Applications
category: investigation
dataset: panw_ngfw_threat_raw
tags:
  - filter
  - comp
  - sort
  - panw_ngfw_threat_raw
  - source:dataset
  - operator-authored
---

# PANW NGFW | Session-Based Threat Analysis for Specific Applications

**Dataset**: `panw_ngfw_threat_raw`

```sql
dataset = panw_ngfw_threat_raw
| filter app in ($application)
| comp count() as threat_count by session_id, app
| sort desc threat_count
```

## When to use

Analyzes Next-Generation-Firewall (NGFW) threat logs based on specific applications and correlates threats to their sessions

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
