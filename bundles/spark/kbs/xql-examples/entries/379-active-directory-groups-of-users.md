---
id: XQL-379-f4644c52
title: Active Directory Groups of Users
category: investigation
dataset: pan_dss_raw
tags:
  - filter
  - fields
  - arrayexpand
  - pan_dss_raw
  - source:dataset
  - operator-authored
---

# Active Directory Groups of Users

**Dataset**: `pan_dss_raw`

```sql
dataset = pan_dss_raw
| filter netbios_and_sam_account_name contains $user or upn contains $user or sam_account_name contains $user
| fields  display_name , security_groups , sam_account_name , upn ,netbios_and_sam_account_name , last_logon_timestamp , guid , dn,ou
| arrayexpand security_groups
```

## When to use

Lists all the Active Direcory groups a user is a member of

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
