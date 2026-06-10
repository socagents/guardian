---
id: XQL-247-c6ad0a1a
title: Azure AD service account created or modified
category: investigation
dataset: msft_azure_ad_audit
tags:
  - preset
  - filter
  - msft_azure_ad_audit
  - source:preset
  - operator-authored
---

# Azure AD service account created or modified

**Dataset**: `msft_azure_ad_audit`

```sql
preset = msft_azure_ad_audit  // go over azure ad audit logs
| filter activityDisplayName IN ("Add service principal credentials", "Add service principal") 
  AND result = "success" // find cases where somone adds SPNs to an account
```

## When to use

Monitor service account creation and changes in service account credentials

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
