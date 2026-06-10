---
id: XQL-443-3daecd68
title: Inbound Emails Received from External Mailboxes
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

# Inbound Emails Received from External Mailboxes

**Dataset**: `email_data`

```sql
dataset = email_data
| arrayexpand recipients
| alter recipient_address= recipients->address , sender_address = sender -> address
| alter sender_domain = arrayindex(regextract(sender_address,".*\@(.*)"),0), recipient_domain = arrayindex(regextract(recipient_address,".*\@(.*)"),0 )
| filter sender_domain != $company_domain and recipient_domain contains $company_domain
| fields _time , sender_domain , recipient_domain , sender , recipients ,return_path  , *
```

## When to use

Lists emails that were recieved from external mailboxes to an email address associated with the organization

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
