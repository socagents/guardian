---
id: XQL-272-4f106c26
title: Sender address and domain discrepancies
category: investigation
dataset: email_data
tags:
  - alter
  - filter
  - fields
  - dedup
  - email_data
  - source:dataset
  - operator-authored
---

# Sender address and domain discrepancies

**Dataset**: `email_data`

```sql
dataset = email_data
| alter sender_address = json_extract(to_json_string(sender), "$.address")
| alter sender_domain = to_string(regextract(sender_address , "@(?:[a-zA-Z0-9-]+\.)*([a-zA-Z0-9-]+)\.[a-zA-Z]{2,}"))
| alter from_address = json_extract(to_json_string(from) , "$.address")
| alter from_domain = to_string(regextract(from_address , "@(?:[a-zA-Z0-9-]+\.)*([a-zA-Z0-9-]+)\.[a-zA-Z]{2,}"))
| filter from_address != sender_address or from_domain != sender_domain
| fields from_address,from_domain, sender_address, sender_domain
| dedup from_address by asc _time
```

## When to use

Displays mismatches between 'from' address and sender address,  or ‘from’ domain and sender domain. This can indicate a potential spoofing.

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
