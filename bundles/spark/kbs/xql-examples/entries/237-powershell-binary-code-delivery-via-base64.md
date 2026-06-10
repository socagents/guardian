---
id: XQL-237-b561efe6
title: Powershell binary code delivery via base64
category: investigation
dataset: xdr_event_log
tags:
  - preset
  - filter
  - fields
  - xdr_event_log
  - source:preset
  - operator-authored
---

# Powershell binary code delivery via base64

**Dataset**: `xdr_event_log`

```sql
preset = xdr_event_log // Using the XDR eventlog preset
| filter lowercase(action_evtlog_description) contains "scriptblock" and lowercase(action_evtlog_message) ~= ".*io.memorystream.*frombase64.*" // Filtering for cases where the scriptblock of powershell contains possible decompressions or manipulation of base64 strings that represent binary data to deliver payload
| fields  agent_hostname as hostname, action_evtlog_message as script, actor_process_image_path as process_path, actor_process_command_line as process_cmd, causality_actor_process_image_path as cgo_path, causality_actor_process_command_line as cgo_cmd // Selecting the relevant fields
```

## When to use

Displays cases where the scriptblock created for powershell commands shows evidence of binary code delivery via base64

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
