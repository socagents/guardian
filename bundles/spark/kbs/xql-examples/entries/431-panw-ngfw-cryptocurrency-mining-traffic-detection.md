---
id: XQL-431-8bc4997a
title: PANW NGFW | Cryptocurrency Mining Traffic Detection
category: investigation
dataset: panw_ngfw_traffic_raw
tags:
  - filter
  - fields
  - panw_ngfw_traffic_raw
  - source:dataset
  - operator-authored
---

# PANW NGFW | Cryptocurrency Mining Traffic Detection

**Dataset**: `panw_ngfw_traffic_raw`

```sql
dataset = panw_ngfw_traffic_raw
|filter app in ("bitcoin", "coinhave", "coinblind", "coinimp", "coinnebula", "crypto-loot", "deepminer", "jsecoin", "litecoin", "mineralt", "webmine", "cryptonoter", "coinhive")
| fields app, to_zone, dest_device_host ,dest_ip, dest_port, log_source_name, action, rule_matched, session_id, from_zone, source_ip, source_port, source_user_info_name, *
```

## When to use

Detects Next-Generation-Firewall (NGFW) traffic associated with cryptocurrency mining applications, such as bitcoin and other miners

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
