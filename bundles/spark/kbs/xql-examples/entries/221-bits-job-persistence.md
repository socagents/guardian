---
id: XQL-IR-221-bits-job-persistence
title: BITS job created for download/persistence via bitsadmin or Start-BitsTransfer (T1197)
category: threat-hunting
dataset: xdr_data
ecosystem: xsiam
tags: [filter, alter, fields, sort]
attack: [T1197]
---

# BITS job created for download/persistence via bitsadmin or Start-BitsTransfer (T1197)

**Dataset**: `xdr_data`

Hunts use of the Background Intelligent Transfer Service to fetch payloads or stage persistence: `bitsadmin /create|/addfile|/setnotifycmdline` or PowerShell `Start-BitsTransfer`. The `/setnotifycmdline` branch is the persistence tell — a command fired on job completion. Tune by allow-listing software-distribution hosts in the URL regex.

```sql
dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| alter cmd = lowercase(action_process_image_command_line)
| filter lowercase(action_process_image_name) = "bitsadmin.exe"
      or (lowercase(action_process_image_name) in ("powershell.exe", "pwsh.exe") and cmd contains "start-bitstransfer")
| alter is_persistence = if(cmd contains "setnotifycmdline", "true", "false"),
        fetched_url = arrayindex(regextract(cmd, "https?://[^\s\"]+"), 0)
| fields _time, agent_hostname, actor_effective_username, action_process_image_name, is_persistence, fetched_url, action_process_image_command_line
| sort desc _time
```
