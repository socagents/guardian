---
id: XQL-308-65072ec9
title: Earliest Playbook Trigger Events with Notifications
category: investigation
dataset: management_auditing
tags:
  - alter
  - filter
  - comp
  - management_auditing
  - source:dataset
  - operator-authored
---

# Earliest Playbook Trigger Events with Notifications

**Dataset**: `management_auditing`

```sql
dataset = management_auditing
| alter xql_category = "XSIAM Management Audit Alert"
| alter notify_engineering = true
| alter skip_execution = true
| filter management_auditing_type in("PLAYBOOK_TRIGGERS")
| comp earliest(timestamp) as timestamp, count(timestamp) as count by description, subtype, email, user_name, xql_category, notify_engineering, skip_execution
```

## When to use

Lists the earliest occurrences of playbook trigger events and details how many had notifications for engineering enabled and execution skipped

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
