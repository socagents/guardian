---
id: XQL-190-f73ddcbe
title: Rare Executions of PSEXEC
category: investigation
dataset: xdr_data
tags:
  - filter
  - alter
  - fields
  - comp
  - sort
  - xdr_data
  - source:dataset
  - operator-authored
---

# Rare Executions of PSEXEC

**Dataset**: `xdr_data`

```sql
dataset = xdr_data // Using the xdr dataset
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START and lowercase(action_process_image_name) contains "psexec" // Filtering by process execution and acting process contains psexec. Note the lower case logic applied to the field
| alter Process_Command_Line = replex(lowercase(action_process_image_command_line), "\s+\\\\.*?\s+", " \\\\HOST "), Process_Name = lowercase(replace(action_process_image_name, "64","")) // Running an alter command to make sure the functions later ignore differences in hosts and in bit version, thus focusing on the command
| alter Process_Command_Line = replace(Process_Command_Line, "psexec64","psexec") // Running an alter command to make sure the functions later ignore differences in hosts and in bit version, thus focusing on the command
| fields Process_Command_Line, Process_Name, event_id // Selecting the process command line, name and event id
| comp count(event_id) as Counter by Process_Name, Process_Command_Line // Counting by how many times each process/cmd pairs were seen 
| filter Counter <= 10 // Filtering for pairs seen less than 10 times
| sort desc Counter // Sorting by occurrences in a descending order
```

## When to use

Display executions of PSEXEC with a command line seen fewer than 10 times

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
