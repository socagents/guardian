---
id: XQL-441-02fac293
title: Email Address for Given Display Name ($display_name)
category: investigation
dataset: email_data
tags:
  - arrayexpand
  - alter
  - filter
  - dedup
  - fields
  - email_data
  - source:dataset
  - operator-authored
---

# Email Address for Given Display Name ($display_name)

**Dataset**: `email_data`

```sql
dataset = email_data
| arrayexpand recipients
| alter recipient_address= recipients->address ,recipient_name = recipients -> name, sender_address = sender -> address ,sender_name = sender -> name
| filter recipient_name contains $display_name or sender_name contains $display_name
| dedup recipient_address, sender_address
| fields recipient_address,recipient_name,sender_address,sender_name,*
```

## When to use

Details the $email_address of a given $display_name

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
