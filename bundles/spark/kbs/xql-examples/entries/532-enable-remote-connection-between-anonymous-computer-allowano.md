---
id: XQL-532-1bc5bcf9
title: Enable Remote Connection Between Anonymous Computer - AllowAnonymousCallback
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

# Enable Remote Connection Between Anonymous Computer - AllowAnonymousCallback

**Dataset**: `xdr_data`

```sql
dataset = xdr_data
 | filter event_type = 4
 | filter (action_registry_key_name contains "\Microsoft\WBEM\CIMOM\AllowAnonymousCallback") AND (action_registry_value_name IN ("DWORD (0x00000001)"))
 | fields agent_hostname, event_type, event_sub_type, actor_process_image_path, actor_process_os_pid, actor_process_image_md5, actor_process_signature_vendor, actor_process_signature_status, actor_effective_username, action_registry_key_name, action_registry_value_name
```

## When to use

Detects enabling of the AllowAnonymousCallback registry value, which allows a remote connection between computers that do not have a trust relationship.

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
