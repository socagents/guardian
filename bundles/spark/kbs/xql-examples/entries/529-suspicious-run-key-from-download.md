---
id: XQL-529-b6485bec
title: Suspicious Run Key from Download
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

# Suspicious Run Key from Download

**Dataset**: `xdr_data`

```sql
dataset = xdr_data
 | filter event_type = 4
 | filter (actor_process_image_path contains "\Downloads" OR actor_process_image_path contains "\Temporary Internet Files\Content.Outlook" OR actor_process_image_path contains "\Local Settings\Temporary Internet Files") AND (action_registry_key_name contains "\SOFTWARE\Microsoft\Windows\CurrentVersion\Run")
 | fields agent_hostname, event_type, event_sub_type, actor_process_image_path, actor_process_os_pid, actor_process_image_md5, actor_process_signature_vendor, actor_process_signature_status, actor_effective_username, action_registry_key_name, action_registry_value_name
```

## When to use

Detects the suspicious RUN keys created by software located in Download or temporary Outlook/Internet Explorer directories.

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
