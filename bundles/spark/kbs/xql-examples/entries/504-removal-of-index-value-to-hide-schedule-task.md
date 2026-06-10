---
id: XQL-504-80aa9a99
title: Removal Of Index Value to Hide Schedule Task
category: investigation
dataset: xdr_data
tags:
  - filter
  - fields
  - xdr_data
  - source:dataset
  - operator-authored
  - Registry
  - Misconfiguration
---

# Removal Of Index Value to Hide Schedule Task

**Dataset**: `xdr_data`

```sql
dataset = xdr_data
 | filter event_type = 4 and event_sub_type = 2
 | filter (action_registry_key_name contains "\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Schedule\TaskCache\Tree" AND action_registry_key_name contains "Index")
 | fields agent_hostname, event_type, event_sub_type, actor_process_image_path, actor_process_os_pid, actor_process_image_md5, actor_process_signature_vendor, actor_process_signature_status, actor_effective_username, action_registry_key_name
```

## When to use

Detects when the index value of a scheduled task is removed or deleted from the registry.

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
