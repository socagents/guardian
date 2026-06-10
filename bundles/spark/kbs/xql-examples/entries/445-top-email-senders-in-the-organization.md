---
id: XQL-445-27347d80
title: Top Email Senders in the Organization
category: investigation
dataset: email_data
tags:
  - alter
  - arrayexpand
  - email_data
  - source:dataset
  - operator-authored
---

# Top Email Senders in the Organization

**Dataset**: `email_data`

```sql
dataset = email_data
| alter sender_address = sender -> address
| alter recipients_address = arraymap(recipients , json_extract_scalar("@element","$.address"))
| arrayexpand recipients_address
| top sender_address
```

## When to use

Lists the top emails senders in the organizaiton

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
