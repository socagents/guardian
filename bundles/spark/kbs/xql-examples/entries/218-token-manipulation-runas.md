---
id: XQL-IR-218-token-manipulation-runas
title: Token manipulation / alternate-credential runas execution (T1134)
category: threat-hunting
dataset: xdr_data
ecosystem: xsiam
tags: [filter, alter, fields, sort]
attack: [T1134, T1134.002]
---

# Token manipulation / alternate-credential runas execution (T1134)

**Dataset**: `xdr_data`

Hunts processes launched under different credentials via `runas /user:` or PowerShell `Start-Process -Credential`, a common token/identity manipulation step. Tune by comparing `actor_effective_username` against `action_process_username` to surface only true identity switches and exclude approved admin jump accounts.

```sql
dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| alter cmd = lowercase(action_process_image_command_line)
| filter (lowercase(action_process_image_name) = "runas.exe" and cmd contains "/user:")
      or (cmd contains "start-process" and cmd contains "-credential")
| alter target_user = arrayindex(regextract(cmd, "/user:(\S+)"), 0),
        ran_as = action_process_username
| filter action_process_username != actor_effective_username or target_user != null
| fields _time, agent_hostname, actor_effective_username, ran_as, target_user, action_process_image_command_line
| sort desc _time
```
