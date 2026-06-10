---
id: XQL-561-9ce86a40
title: Microsoft Teams Sensitive File Access By Uncommon Applications
category: investigation
dataset: xdr_data
tags:
  - filter
  - fields
  - xdr_data
  - source:dataset
  - operator-authored
  - Process
  - Malware
---

# Microsoft Teams Sensitive File Access By Uncommon Applications

**Dataset**: `xdr_data`

```sql
dataset = xdr_data
| filter event_type = 3
| filter (action_file_path contains "\Microsoft\Teams\Cookies" OR  action_file_path contains "\Microsoft\Teams\Local Storage\leveldb") and not (((actor_process_image_path ~= ".*\\Microsoft\\Teams\\current\\Teams.exe")))
| fields agent_hostname, event_type, event_sub_type, actor_process_image_path, actor_process_os_pid, actor_process_image_md5, actor_process_signature_vendor, actor_process_signature_status, actor_effective_username, action_file_path
```

## When to use

Detects file access attempts to sensitive Microsoft teams files (leveldb, cookies) by an uncommon process.

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
