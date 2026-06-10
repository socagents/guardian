---
id: XQL-277-1e0e1ab8
title: Appspot subdomain abuse
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

# Appspot subdomain abuse

**Dataset**: `email_data`

```sql
dataset = email_data
| arrayexpand urls
| arrayexpand decoded_urls
| arrayexpand recipients
| alter full_domain = regextract(to_string(urls), "^(?:https?://)?([^/?#]+)")
| alter from_address = json_extract(to_json_string(from) , "$.address")
| alter recipient_address = json_extract(to_json_string(recipients) , "$.address")
| filter full_domain != null and full_domain ~= "\b[\w-]+-dot-[\w.-]+\.appspot\.com\b" and (urls contains recipient_address or decoded_urls contains recipient_address)
| fields from_address,urls
```

## When to use

Display potential phishing campaigns associated with Appspot abuse. These emails frequently contain phishing links that utilize the recipients' own email address as a unique identifier in the URI.

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
