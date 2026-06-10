---
id: XQL-438-140799a7
title: Incoming Emails where Reply To is Different from Sender
category: investigation
dataset: email_data
tags:
  - alter
  - filter
  - arrayexpand
  - fields
  - email_data
  - source:dataset
  - operator-authored
---

# Incoming Emails where Reply To is Different from Sender

**Dataset**: `email_data`

```sql
dataset = email_data
| alter sender_address = sender -> address
| filter reply_to != null
| arrayexpand reply_to
| filter reply_to -> address != sender_address
| fields reply_to , sender , *
```

## When to use

Lists any incoming emails that replying to them would actually go to different email address

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
