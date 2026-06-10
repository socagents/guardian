---
id: XQL-412-6041016c
title: PANW NGFW | Top 10 Threat-Generating Source IPs
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

# PANW NGFW | Top 10 Threat-Generating Source IPs

**Dataset**: `panw_ngfw_threat_raw`

```sql
dataset = panw_ngfw_threat_raw
| comp count() as threat_count by source_ip
| sort desc threat_count
| limit 10
```

## When to use

Reveals the top ten Next-Generation-Firewall (NGFW) source IP addresses that generated the most threat logs, helping to identify malicious or compromised hosts in the network

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
