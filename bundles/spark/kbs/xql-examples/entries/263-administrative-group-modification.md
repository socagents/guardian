---
id: XQL-263-21e87f62
title: Administrative group modification
category: investigation
dataset: msft_azure_ad_audit_raw
tags:
  - filter
  - msft_azure_ad_audit_raw
  - source:dataset
  - operator-authored
---

# Administrative group modification

**Dataset**: `msft_azure_ad_audit_raw`

```sql
// Cloud provider - Azure
// Cloud component - Authorization\Group Management
config case_sensitive = false | dataset = msft_azure_ad_audit_raw 
| filter activityDisplayName contains "Add member to group" and targetResources in ("admin*") // Search for users added to administrative group
```

## When to use

Displays users added to the administrative group.

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
