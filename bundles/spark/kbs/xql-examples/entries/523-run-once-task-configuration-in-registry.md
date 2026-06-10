---
id: XQL-523-ebb168e1
title: Run Once Task Configuration in Registry
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

# Run Once Task Configuration in Registry

**Dataset**: `xdr_data`

```sql
dataset = xdr_data
 | filter event_type = 4
 | filter (action_registry_key_name contains "\Microsoft\Active Setup\Installed Components") AND (action_registry_key_name ~= ".*\\StubPath") and not (((action_registry_value_name contains "C:\Program Files\Google\Chrome\Application" AND action_registry_value_name contains "\Installer\chrmstp.exe\" --configure-user-settings --verbose-logging --system-level")) OR ((action_registry_value_name contains "C:\Program Files (x86)\Microsoft\Edge\Application" OR action_registry_value_name contains "C:\Program Files\Microsoft\Edge\Application") AND (action_registry_value_name ~= ".*\\Installer\\setup.exe\\" --configure-user-settings --verbose-logging --system-level --msedge --channel=stable")))
 | fields agent_hostname, event_type, event_sub_type, actor_process_image_path, actor_process_os_pid, actor_process_image_md5, actor_process_signature_vendor, actor_process_signature_status, actor_effective_username, action_registry_key_name, action_registry_value_name
```

## When to use

Rule to detect the configuration of Run Once registry key.

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
