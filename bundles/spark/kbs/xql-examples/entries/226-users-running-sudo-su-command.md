---
id: XQL-226-7e618522
title: Users running Sudo Su command
category: investigation
dataset: xdr_data
tags:
  - filter
  - fields
  - xdr_data
  - source:dataset
  - operator-authored
---

# Users running Sudo Su command

**Dataset**: `xdr_data`

```sql
dataset = xdr_data // Using the xdr dataset 
| filter action_process_image_command_line ~= "\s+su\b" and action_process_image_name = "sudo" // Filtering for executions of sudo command with su in the command line
| fields actor_effective_username as source_username, action_process_username as target_username, action_process_image_command_line as command_line // Showing the users
```

## When to use

Display cases where users switch to another user on non-windows OSs

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
