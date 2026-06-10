---
id: XQL-228-c8abd566
title: Process running with short name
category: investigation
dataset: xdr_process
tags:
  - preset
  - filter
  - fields
  - dedup
  - xdr_process
  - source:preset
  - operator-authored
---

# Process running with short name

**Dataset**: `xdr_process`

```sql
preset = xdr_process // Using the process execution preset
| filter len(action_process_image_name) < 6 and agent_os_type = ENUM.AGENT_OS_WINDOWS and action_process_image_name contains "." // Filtering for short process names that must contain a . on Windows
| fields action_process_image_name as process_name, action_process_image_command_line as process_cmd, action_process_image_sha256 as process_sha256, actor_process_image_name as parent_name, actor_process_command_line as parent_cmd // Selecting relevant fields
| dedup process_name, process_cmd, process_sha256, parent_name , parent_cmd by asc _time //Dedupping to only show the first time each process ran
```

## When to use

Displays cases where a process is running with a short name

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
