---
id: XQL-446-0c80c2d1
title: Top Email Recipients in the Organization
category: investigation
dataset: email_data
tags:
  - alter
  - arrayexpand
  - email_data
  - source:dataset
  - operator-authored
---

# Top Email Recipients in the Organization

**Dataset**: `email_data`

```sql
dataset = email_data
| alter sender_address = sender -> address
| alter recipients_address = arraymap(recipients , json_extract_scalar("@element","$.address"))
| arrayexpand recipients_address
| top recipients_address
```

## When to use

LIsts the top email recipients in the organizaiton

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
