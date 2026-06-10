---
id: XQL-230-468df36d
title: Unsigned Process creating dump file
category: investigation
dataset: xdr_file
tags:
  - preset
  - filter
  - fields
  - xdr_file
  - source:preset
  - operator-authored
---

# Unsigned Process creating dump file

**Dataset**: `xdr_file`

```sql
preset = xdr_file // Using the XDR file preset
| filter action_file_name ~= ".*?\.dmp|.*\.dump" and actor_process_signature_status != ENUM.SIGNED // Filtering for unsigned processes creating a dump file
| fields action_file_name as file_name , actor_process_image_name as process_name, actor_process_command_line as process_cmd, actor_process_image_sha256 as process_sha256 // Selecting the relevant fields
```

## When to use

Displays all dump files created by processes that are not validly signed

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
