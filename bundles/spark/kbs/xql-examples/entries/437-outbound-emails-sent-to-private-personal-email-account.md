---
id: XQL-437-92817a1e
title: Outbound Emails Sent to Private/Personal Email Account
category: investigation
dataset: email_data
tags:
  - alter
  - arrayexpand
  - filter
  - fields
  - email_data
  - source:dataset
  - operator-authored
---

# Outbound Emails Sent to Private/Personal Email Account

**Dataset**: `email_data`

```sql
dataset = email_data
| alter sender_address = sender -> address
| alter recipients_address = arraymap(recipients , json_extract_scalar("@element","$.address"))
| arrayexpand recipients_address
| filter recipients_address ~= ".*gmail|yahoo|outlook|microsoft.*"
| fields sender , sender_address , recipients , recipients_address , attachments
```

## When to use

Lists the people who have forwarded emails to their personal email account, which can indicate that somone is trying to leak sensitive data

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
