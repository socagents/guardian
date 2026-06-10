---
id: XQL-528-8d8309b9
title: Atbroker Registry Change
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

# Atbroker Registry Change

**Dataset**: `xdr_data`

```sql
dataset = xdr_data
 | filter event_type = 4
 | filter (action_registry_key_name contains "Software\Microsoft\Windows NT\CurrentVersion\Accessibility\ATs" OR action_registry_key_name contains "Software\Microsoft\Windows NT\CurrentVersion\Accessibility\Configuration") and not (((actor_process_image_path IN ("C:\Windows\system32\atbroker.exe")) AND (action_registry_key_name contains "\Microsoft\Windows NT\CurrentVersion\Accessibility\Configuration") AND (action_registry_value_name IN ("(Empty)"))) OR ((actor_process_image_path ~= "C:\\Windows\\Installer\\MSI.*") AND (action_registry_key_name contains "Software\Microsoft\Windows NT\CurrentVersion\Accessibility\ATs")))
 | fields agent_hostname, event_type, event_sub_type, actor_process_image_path, actor_process_os_pid, actor_process_image_md5, actor_process_signature_vendor, actor_process_signature_status, actor_effective_username, action_registry_key_name, action_registry_value_name
```

## When to use

Detects creation/modification of Assistive Technology applications and persistence with usage of 'at'.

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
