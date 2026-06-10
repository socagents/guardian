---
id: XQL-429-b4e38b67
title: PANW NGFW |  Hacking Tool Traffic Detection
category: investigation
dataset: panw_ngfw_threat_raw
tags:
  - filter
  - fields
  - panw_ngfw_threat_raw
  - source:dataset
  - operator-authored
---

# PANW NGFW |  Hacking Tool Traffic Detection

**Dataset**: `panw_ngfw_threat_raw`

```sql
dataset = panw_ngfw_threat_raw
|filter threat_category contains  "hacktool"
| fields source_ip , source_port , dest_ip , dest_port , action, app, app_category , threat_category , threat_name , direction_of_attack , from_zone , to_zone ,*
```

## When to use

Identifies Next-Generation-Firewall (NGFW) traffic associated with hacking tools in the network, helping analysts focus on potentially harmful activities

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
