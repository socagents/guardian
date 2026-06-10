---
id: XQL-502-c9fc8304
title: Removal Of AMSI Provider Registry Keys
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

# Removal Of AMSI Provider Registry Keys

**Dataset**: `xdr_data`

```sql
dataset = xdr_data
 | filter event_type = 4 and event_sub_type = 2
 | filter (action_registry_key_name ~= ".*{2781761E-28E0-4109-99FE-B9D127C57AFE}" OR action_registry_key_name ~= ".*{A7C452EF-8E9F-42EB-9F2B-245613CA0DC9}")
 | fields agent_hostname, event_type, event_sub_type, actor_process_image_path, actor_process_os_pid, actor_process_image_md5, actor_process_signature_vendor, actor_process_signature_status, actor_effective_username, action_registry_key_name
```

## When to use

Detects the deletion of AMSI provider registry key entries in HKLM\Software\Microsoft\AMSI.

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
