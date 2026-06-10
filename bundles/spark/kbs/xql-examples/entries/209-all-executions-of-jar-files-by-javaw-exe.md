---
id: XQL-209-f52fd6f1
title: All executions of JAR files by javaw.exe
category: investigation
dataset: xdr_data
tags:
  - filter
  - fields
  - xdr_data
  - source:dataset
  - operator-authored
---

# All executions of JAR files by javaw.exe

**Dataset**: `xdr_data`

```sql
dataset = xdr_data // Using the xdr dataset 
 | filter action_process_image_name = "javaw.exe" and action_process_image_command_line contains ".jar" // Filtering by process name is javaw.exe and command line contains .jar
 | fields action_process_image_path as Process_Path, action_process_image_command_line as Process_CMD, actor_process_image_path as Parent_Path, actor_process_command_line as Parent_CMD // Selecting all the relevant fields
```

## When to use

Display all cases where javaw.exe was used to run a jar file

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
