---
id: XQL-421-6847f3f0
title: PANW NGFW | Top 10 Threats by Vendor Severity and Action
category: investigation
dataset: panw_ngfw_threat_raw
tags:
  - comp
  - sort
  - limit
  - panw_ngfw_threat_raw
  - source:dataset
  - operator-authored
---

# PANW NGFW | Top 10 Threats by Vendor Severity and Action

**Dataset**: `panw_ngfw_threat_raw`

```sql
dataset = panw_ngfw_threat_raw
| comp count() as threat_count by vendor_severity, action
| sort desc threat_count
| limit 10
```

## When to use

Categorizes the top Next-Generation-Firewall (NGFW) ten threats based on their severity and the actions taken by the firewall

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
