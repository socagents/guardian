---
id: XQL-436-6c92f298
title: Verify Email Sent by $sender Read
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

# Verify Email Sent by $sender Read

**Dataset**: `email_data`

```sql
dataset = email_data
| alter country = sender_ip_location -> country,sender_address = sender -> address , is_read = o365_data -> is_read
| filter sender_address contains $sender
| fields  sender , is_read ,recipients ,*
```

## When to use

Checks whether the email that was recieved by $sender was opened by any of the recipients

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
