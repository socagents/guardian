---
id: XQL-320-1d2fa544
title: AD Users with Domain Admin Access
category: investigation
dataset: ad_users
tags:
  - preset
  - filter
  - comp
  - ad_users
  - source:preset
  - operator-authored
---

# AD Users with Domain Admin Access

**Dataset**: `ad_users`

```sql
preset = ad_users
| filter netbios_domain in($domain)
|filter member_of contains "Domain Admins"
| comp count(full_user_name) as admins, values(full_user_name) as user_name
```

## When to use

Counts Active Directory users with domain admin privileges to help identify potential security risks by highlighting accounts with elevated permissions

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
