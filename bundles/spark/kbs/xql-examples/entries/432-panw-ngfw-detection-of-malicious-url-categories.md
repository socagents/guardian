---
id: XQL-432-b3daf6ff
title: PANW NGFW | Detection of Malicious URL Categories
category: investigation
dataset: panw_ngfw_url_raw
tags:
  - filter
  - fields
  - panw_ngfw_url_raw
  - source:dataset
  - operator-authored
---

# PANW NGFW | Detection of Malicious URL Categories

**Dataset**: `panw_ngfw_url_raw`

```sql
dataset = panw_ngfw_url_raw
|filter url_category ~= ".*malware.*|.*ransomware.*|.*adware.*|.*command-and-control.*|.*hijack.*|spyware|.*virus.*|c2" or url_category_list ~= ".*malware.*|.*ransomware.*|.*adware.*|.*command-and-control.*|.*hijack.*|spyware|.*virus.*"
| fields source_ip , source_port , dest_ip , dest_port , action, app, app_category , from_zone , to_zone, user_agent ,*
```

## When to use

Identifies URL categories related to malicious content, such as malware, ransomware, and spyware in the Next-Generation-Firewall (NGFW) events

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
