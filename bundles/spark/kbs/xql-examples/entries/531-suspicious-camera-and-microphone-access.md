---
id: XQL-531-5f95fea6
title: Suspicious Camera and Microphone Access
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

# Suspicious Camera and Microphone Access

**Dataset**: `xdr_data`

```sql
dataset = xdr_data
 | filter event_type = 4
 | filter (((action_registry_key_name contains "\Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore" AND action_registry_key_name contains "\NonPackaged")) AND ((action_registry_key_name contains "microphone" OR action_registry_key_name contains "webcam")) AND ((action_registry_key_name contains ":#Windows#Temp#" OR action_registry_key_name contains ":#$Recycle.bin#" OR action_registry_key_name contains ":#Temp#" OR action_registry_key_name contains ":#Users#Public#" OR action_registry_key_name contains ":#Users#Default#" OR action_registry_key_name contains ":#Users#Desktop#")))
 | fields agent_hostname, event_type, event_sub_type, actor_process_image_path, actor_process_os_pid, actor_process_image_md5, actor_process_signature_vendor, actor_process_signature_status, actor_effective_username, action_registry_key_name, action_registry_value_name
```

## When to use

Detects Processes accessing the camera and microphone from suspicious folder.

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
