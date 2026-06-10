---
id: XQL-434-ef025ed7
title: Email Domains Communicated with via Email
category: investigation
dataset: email_data
tags:
  - arrayexpand
  - alter
  - dedup
  - comp
  - email_data
  - source:dataset
  - operator-authored
---

# Email Domains Communicated with via Email

**Dataset**: `email_data`

```sql
dataset = email_data
| arrayexpand recipients
| alter recipient_address= recipients->address , sender_address = sender -> address
| dedup recipient_address, sender_address
| alter sender_domain = arrayindex(regextract(sender_address,".*\@(.*)"),0), recipient_domain = arrayindex(regextract(recipient_address,".*\@(.*)"),0 )
| comp values(sender_domain ) as sent_from, values(recipient_domain) as recieved_from
```

## When to use

Lists all the email domains that have been commuincated with over email

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
