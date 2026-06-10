---
id: XQL-447-ef7d0460
title: Emails with SPF/DKIM Verification Failure
category: investigation
dataset: email_data
tags:
  - filter
  - fields
  - email_data
  - source:dataset
  - operator-authored
---

# Emails with SPF/DKIM Verification Failure

**Dataset**: `email_data`

```sql
dataset = email_data
| filter to_string(authentication_results) contains "*"
| fields _time , sender , recipients , authentication_results, dkim_signature , received_spf , internet_message_headers , *
```

## When to use

Lists the emails that failed their DKIM/SPF verification

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
