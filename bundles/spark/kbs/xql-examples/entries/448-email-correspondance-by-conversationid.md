---
id: XQL-448-f2c46016
title: Email Correspondance by $conversationid
category: investigation
dataset: email_data
tags:
  - filter
  - fields
  - email_data
  - source:dataset
  - operator-authored
---

# Email Correspondance by $conversationid

**Dataset**: `email_data`

```sql
dataset = email_data
| filter conversation_id contains $conversationid
| fields conversation_id , conversation_index , sender , recipients , internet_message_headers , o365_data , *
```

## When to use

Lists the entire email correspondance by the email conversation ID ($conversationid)

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
