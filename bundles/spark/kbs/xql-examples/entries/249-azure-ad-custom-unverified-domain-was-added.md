---
id: XQL-249-a16557f3
title: Azure AD custom unverified domain was added
category: investigation
dataset: msft_azure_ad_audit
tags:
  - preset
  - filter
  - msft_azure_ad_audit
  - source:preset
  - operator-authored
---

# Azure AD custom unverified domain was added

**Dataset**: `msft_azure_ad_audit`

```sql
preset = msft_azure_ad_audit // go over azure ad audit logs
| filter activityDisplayName = "Add unverified domain" AND result = "success"  // find cases where someone added a custom domain to the azuread env
```

## When to use

Displays unverified domains added to Azure AD

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
