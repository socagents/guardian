---
id: XQL-IR-211-service-creation-persistence
title: Windows service creation for persistence or lateral movement (T1543.003)
category: threat-hunting
dataset: xdr_data
ecosystem: xsiam
tags: [filter, alter, comp, sort]
attack: [T1543.003]
---

# Windows service creation for persistence or lateral movement (T1543.003)

**Dataset**: `xdr_data`

Detects `sc.exe create` / `sc config` defining a new service whose binPath points at cmd, PowerShell, or a payload in a user-writable directory -- the pattern PsExec-style lateral movement and persistence leave behind. The host rollup highlights mass service deployment. Tune binPath fragments to your environment.

```sql
dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| filter lowercase(action_process_image_name) = "sc.exe"
| alter cmd_lc = lowercase(action_process_image_command_line)
| filter cmd_lc contains "create" or cmd_lc contains "config"
| filter cmd_lc contains "binpath" and (cmd_lc contains "cmd" or cmd_lc contains "powershell" or cmd_lc contains "\temp\" or cmd_lc contains "\programdata\" or cmd_lc contains ".bat")
| comp count(action_process_image_command_line) as service_cmds, values(actor_effective_username) as users by agent_hostname
| sort desc service_cmds
```
