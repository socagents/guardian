---
id: XQL-246-cc4d1635
title: Mail read permissions added to Account
category: investigation
dataset: msft_azure_ad_audit
tags:
  - preset
  - filter
  - msft_azure_ad_audit
  - source:preset
  - operator-authored
---

# Mail read permissions added to Account

**Dataset**: `msft_azure_ad_audit`

```sql
preset = msft_azure_ad_audit // go over azure ad audit logs
| filter activityDisplayName IN ("Add app role assignment to service principal", "Add delegated permission grant", "Add application" ) and
         modifiedPropertyNewValue ~= "(Mail.Read|Mail.ReadWrite)" and 
         modifiedPropertyOldValue not contains "Mail.Read" // find cases where mail read was added as a permission to another account
```

## When to use

Displayes accounts that was granted Mail read permissions

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
