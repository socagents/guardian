---
id: XQL-388-a345bab7
title: Emails Sent / Received from a Specific Domain in Last 3 Months
category: investigation
dataset: email_data
tags:
  - config
  - filter
  - email_data
  - source:dataset
  - operator-authored
---

# Emails Sent / Received from a Specific Domain in Last 3 Months

**Dataset**: `email_data`

```sql
config timeframe = 3mo | dataset = email_data
| filter to_string(from) contains $domain or to_string(from_normalized) contains $domain or to_string(sender) contains $domain or to_string(sender_normalized) contains $domain
```

## When to use

After reviewing the emails from Office365 and Gmail, lists the emails sent/received from a given domain in the last 3 months, and includes the applicable fields

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
