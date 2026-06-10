---
id: XQL-426-7d57f2f0
title: PANW NGFW | Top Denial of Service (DoS) Attacks Detected
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

# PANW NGFW | Top Denial of Service (DoS) Attacks Detected

**Dataset**: `panw_ngfw_threat_raw`

```sql
dataset = panw_ngfw_threat_raw
| filter threat_category = "dos"
| comp count() as dos_attack_count by threat_id, source_ip, dest_ip
| sort desc dos_attack_count
```

## When to use

Identifies the most common Denial of Service (DoS) attacks detected by the Next-Generation-Firewall (NGFW)

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
