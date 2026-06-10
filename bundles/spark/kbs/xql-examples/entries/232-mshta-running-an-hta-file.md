---
id: XQL-232-0d5d0565
title: Mshta running an HTA file
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

# Mshta running an HTA file

**Dataset**: `xdr_process`

```sql
preset = xdr_process  // Using XDR process execution preset
| filter action_process_image_name  = "mshta.exe"  and action_process_image_command_line contains ".hta" // Filtering by process name is mshta.exe and an hta file is in the command line
| fields action_process_image_path as process_path, action_process_image_command_line as process_cmd, actor_process_image_name as parent_process, actor_process_command_line as parent_cmd // Selecting relevant fields
| dedup process_path, process_cmd, parent_process, parent_cmd by asc _time // Dedupping to only show the first time
```

## When to use

Displays cases where mshta.exe ran an hta file

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
