---
id: XQL-444-0970a834
title: Where the Emails by $sender Originated From
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

# Where the Emails by $sender Originated From

**Dataset**: `email_data`

```sql
dataset = email_data
| alter country = sender_ip_location -> country,sender_address = sender -> address
| filter sender_address contains $sender
| fields country , sender_address , sender_ip , sender_ip_location ,*
```

## When to use

Lists each country the given emails from the given sender ($sender) originated from

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
