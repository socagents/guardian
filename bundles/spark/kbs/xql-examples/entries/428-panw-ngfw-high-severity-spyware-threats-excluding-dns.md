---
id: XQL-428-7f2a1608
title: PANW NGFW | High-Severity Spyware Threats Excluding DNS
category: investigation
dataset: panw_ngfw_threat_raw
tags:
  - filter
  - fields
  - panw_ngfw_threat_raw
  - source:dataset
  - operator-authored
---

# PANW NGFW | High-Severity Spyware Threats Excluding DNS

**Dataset**: `panw_ngfw_threat_raw`

```sql
dataset = panw_ngfw_threat_raw
|filter severity != "Informational" and severity != "Low" and severity != "Medium" and severity != null
|filter app not contains "dns"
|filter sub_type = "spyware"
| fields source_ip , source_port , dest_ip , dest_port , action, app, app_category , threat_category , threat_name , direction_of_attack , from_zone , to_zone ,*
```

## When to use

Lists high-severity spyware threats detected in the network and filters out DNS-related traffic

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
