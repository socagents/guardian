---
id: XQL-238-37a2ae71
title: Binary file dropped to Public user folder
category: investigation
dataset: xdr_file
tags:
  - preset
  - filter
  - fields
  - dedup
  - xdr_file
  - source:preset
  - operator-authored
---

# Binary file dropped to Public user folder

**Dataset**: `xdr_file`

```sql
preset = xdr_file // Using the XDR file preset
| filter lowercase(action_file_path) ~= "c:\\users\\public\\.*?.(exe|dll|sys|scr|msi)" and event_sub_type = ENUM.FILE_WRITE and action_file_sha256 != null //Filtering for binary files created under c:\users\public with a sha256 value
| fields action_file_path as file_path, action_file_sha256 as file_sha256, actor_process_image_path as process_path, actor_process_command_line as process_cmd,  causality_actor_process_image_path as cgo_path, causality_actor_process_command_line as cgo_cmd // Selecting the relevant fields
| dedup file_path, file_sha256, process_path, process_cmd, cgo_path, cgo_cmd by asc _time // Dedupping values to only show the first time a file was written
```

## When to use

Displays cases where a binary file is dropped to c:\users\public

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
