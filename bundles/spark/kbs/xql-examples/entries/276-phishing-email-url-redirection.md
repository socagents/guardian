---
id: XQL-276-b4c58603
title: Phishing email URL redirection
category: investigation
dataset: email_data
tags:
  - arrayexpand
  - alter
  - filter
  - fields
  - email_data
  - source:dataset
  - operator-authored
---

# Phishing email URL redirection

**Dataset**: `email_data`

```sql
dataset = email_data
| arrayexpand urls
| alter from_address = json_extract(to_json_string(from) , "$.address")
| filter urls ~= "s?://(?:www\.)?t\.(?:[\w\-\.]+/+)+(r|redirect)/?"
| fields from_address, urls
```

## When to use

Attackers use URL redirection to manipulate users into visiting a malicious website or to evade detection. This query displays emails associated with a campaign that has used open redirector URLs.

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
