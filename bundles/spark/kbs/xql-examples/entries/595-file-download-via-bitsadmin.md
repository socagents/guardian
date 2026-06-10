---
id: XQL-595-314042f1
title: File Download Via Bitsadmin
category: investigation
dataset: xdr_data
tags:
  - filter
  - alter
  - fields
  - xdr_data
  - source:dataset
  - operator-authored
  - Process
  - Network
---

# File Download Via Bitsadmin

**Dataset**: `xdr_data`

```sql
dataset = xdr_data
| filter event_type = 1 and event_sub_type = 1
| filter (action_process_image_path ~= ".*\\bitsadmin.exe") AND (json_extract_scalar(action_process_file_info, "$.original_name") IN ("bitsadmin.exe")) and ((action_process_image_command_line contains " /transfer ") or (((action_process_image_command_line contains " /create " OR  action_process_image_command_line contains " /addfile ")) AND ((action_process_image_command_line contains "http"))))
| alter original_name = json_extract_scalar(action_process_file_info, "$.original_name")
| fields agent_hostname, event_type, event_sub_type, actor_process_image_path, actor_process_os_pid, actor_process_image_md5, actor_process_signature_vendor, actor_process_signature_status, actor_effective_username, action_process_cwd, action_process_image_sha256, action_process_image_md5, action_process_signature_product, action_process_image_auth_sha1, action_process_image_command_line, action_process_signature_vendor, action_process_integrity_level, action_process_username, action_process_image_path, actor_process_image_command_line, original_name
```

## When to use

Detects usage of bitsadmin downloading a file.

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
