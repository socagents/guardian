---
id: XQL-439-5db53ac5
title: Emails with Attachments
category: investigation
dataset: email_data
tags:
  - filter
  - fields
  - email_data
  - source:dataset
  - operator-authored
---

# Emails with Attachments

**Dataset**: `email_data`

```sql
dataset = email_data
| filter has_attachments = true
| fields attachments , has_attachments , sender , recipients , from , *
```

## When to use

Lists emails including attachments

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
