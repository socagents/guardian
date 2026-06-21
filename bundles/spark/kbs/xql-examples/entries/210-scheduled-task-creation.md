---
id: XQL-IR-210-scheduled-task-creation
title: Scheduled task creation via schtasks for persistence (T1053.005)
category: threat-hunting
dataset: xdr_data
ecosystem: xsiam
tags: [filter, alter, fields, sort]
attack: [T1053.005]
---

# Scheduled task creation via schtasks for persistence (T1053.005)

**Dataset**: `xdr_data`

Hunts persistence: `schtasks.exe /create` registering a task that runs a script host, encoded PowerShell, or a binary from a user-writable path. The task name and the action it runs are both pulled out for the analyst. Drop known deployment-tool task names into an allowlist filter.

```sql
dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| filter lowercase(action_process_image_name) = "schtasks.exe"
| alter cmd_lc = lowercase(action_process_image_command_line)
| filter cmd_lc contains "/create"
| filter cmd_lc contains "powershell" or cmd_lc contains "-enc" or cmd_lc contains "\temp\" or cmd_lc contains "\appdata\" or cmd_lc contains ".vbs" or cmd_lc contains "mshta"
| alter task_name = arrayindex(regextract(action_process_image_command_line, "(?i)/tn\s+\"?([^\"]+)\"?"), 1)
| fields _time, agent_hostname, actor_effective_username, causality_actor_process_image_name, task_name, action_process_image_command_line
| sort desc _time
```
