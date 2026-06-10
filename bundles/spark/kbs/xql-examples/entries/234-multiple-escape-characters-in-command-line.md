---
id: XQL-234-6ecb7356
title: Multiple escape characters in command line
category: investigation
dataset: xdr_process
tags:
  - preset
  - filter
  - alter
  - fields
  - xdr_process
  - source:preset
  - operator-authored
---

# Multiple escape characters in command line

**Dataset**: `xdr_process`

```sql
preset = xdr_process // Using the XDR process execution preset
| filter (action_process_image_command_line contains "`" or action_process_image_command_line contains "^" or action_process_image_command_line contains "+") and agent_os_type = ENUM.AGENT_OS_WINDOWS // Filtering for cases where the command line contains an escape char
| alter only_esc_caret = replex(action_process_image_command_line, "[^\^]",""), only_esc_backtick = replex(action_process_image_command_line, "[^\`]",""), only_esc_plus = replex(action_process_image_command_line, "[^\+]","") // Replacing every char in the string except ^ and ` and +, so is the string was for example abc^a^b^c it will be ^^^ after this command
| alter count_of_esc_caret = len(only_esc_caret), count_of_esc_backtick = len(only_esc_backtick), count_of_esc_plus = len(only_esc_plus) // Counting the legnth of the string we have left
| filter count_of_esc_caret > 3 or count_of_esc_backtick > 3  or count_of_esc_plus > 3// Filtering for more than 3 esc chars
| fields action_process_image_name as process_name, action_process_image_command_line as process_cmd, count_of_esc_caret, count_of_esc_backtick, count_of_esc_plus // Selecting the relevant fields
```

## When to use

Displays cases where commands are being executed with more than 3 escape characters

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
