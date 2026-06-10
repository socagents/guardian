---
id: XQL-274-cca1a095
title: “From” domain and DKIM domain discrepancies
category: investigation
dataset: email_data
tags:
  - alter
  - filter
  - fields
  - email_data
  - source:dataset
  - operator-authored
---

# “From” domain and DKIM domain discrepancies

**Dataset**: `email_data`

```sql
dataset = email_data
| alter return_path_domain = to_string(regextract(return_path , "@(?:[a-zA-Z0-9-]+\.)*([a-zA-Z0-9-]+)\.[a-zA-Z]{2,}"))
| alter from_address = json_extract(to_json_string(from) , "$.address")
| alter from_domain = to_string(regextract(from_address , "@(?:[a-zA-Z0-9-]+\.)*([a-zA-Z0-9-]+)\.[a-zA-Z]{2,}"))
| filter return_path_domain != null and from_domain != null and from_domain != return_path_domain
| fields return_path_domain ,return_path , from_domain , from_address
```

## When to use

Displays mismatches between DKIM detected domain and “From” address domain. These should align since DKIM verifies the domain specified in the “From” address.
If they don’t match, it can indicate a potential spoofing.

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
