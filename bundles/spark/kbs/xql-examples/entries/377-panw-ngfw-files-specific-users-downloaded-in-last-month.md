---
id: XQL-377-7f18b865
title: PANW NGFW | Files Specific Users Downloaded in Last Month 
category: investigation
dataset: panw_ngfw_url_raw
tags:
  - config
  - filter
  - fields
  - comp
  - panw_ngfw_url_raw
  - source:dataset
  - operator-authored
---

# PANW NGFW | Files Specific Users Downloaded in Last Month 

**Dataset**: `panw_ngfw_url_raw`

```sql
config timeframe = 30d
| dataset = panw_ngfw_url_raw
| filter uri ~= "[\w\.\/]+\/\w+\.\w+$"
| fields source_ip , url_domain , uri ,dest_ip ,action ,users, source_user ,app ,app_category , dest_port , file_url , rule_matched , dest_location
| comp values(source_ip ) as source_ip_address, values(uri) as request_uri , values(app ) as application_name, values(app_category) as application_catgeory, count() as total_download,count_distinct(uri) as different_uri by users
| filter users contains $user
```

## When to use

Lists files that were downloaded by the user in the last month by searching the URL events and looking for a URL that ends with a file exstention. This indicates that this is a download file operation.

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
