---
id: XQL-449-316ec1fa
title: BCC Emails Sent by Sender ($sender) and Recipients
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

# BCC Emails Sent by Sender ($sender) and Recipients

**Dataset**: `email_data`

```sql
dataset = email_data
| alter country = sender_ip_location -> country,sender_address = sender -> address
| filter sender_address contains $sender
| filter bcc_recipients  != null
| fields bcc_recipients , sender ,sender_address ,*
```

## When to use

Lists the emails that were sent as BCC (Blind Carbon Copy) to additional recipients without the primary recipient being made aware. This query includes the sender and BCC recipients.

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
