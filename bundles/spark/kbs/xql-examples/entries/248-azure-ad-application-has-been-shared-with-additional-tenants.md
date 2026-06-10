---
id: XQL-248-e687d2f5
title: Azure AD application has been shared with additional tenants
category: investigation
dataset: msft_azure_ad_audit
tags:
  - preset
  - filter
  - msft_azure_ad_audit
  - source:preset
  - operator-authored
---

# Azure AD application has been shared with additional tenants

**Dataset**: `msft_azure_ad_audit`

```sql
preset = msft_azure_ad_audit  // go over azure ad audit logs
| filter activityDisplayName = "Update application"
  AND operationType="Update"
  and result="success"
  and modifiedDisplayName = "AvailableToOtherTenants"  // find cases where someone grants permission to access an app from another azuread tenant
```

## When to use

Displayes changes in available tenants that are granted to access the specific application

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
