---
id: XQL-IR-205-wscript-cscript-script-exec
title: wscript / cscript running scripts from user-writable paths (T1059.005)
category: threat-hunting
dataset: xdr_data
ecosystem: xsiam
tags: [filter, alter, fields, dedup, sort]
attack: [T1059.005]
---

# wscript / cscript running scripts from user-writable paths (T1059.005)

**Dataset**: `xdr_data`

Finds the Windows Script Host executing `.vbs`/`.js`/`.wsf` payloads dropped under Temp, Downloads, or ProgramData -- a common second-stage from phishing. `dedup` keeps one row per host+script so a looping scheduled script does not flood results.

```sql
dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| filter lowercase(action_process_image_name) in ("wscript.exe", "cscript.exe")
| alter cmd_lc = lowercase(action_process_image_command_line)
| filter cmd_lc ~= ".*\.(?:vbs|js|jse|wsf|vbe)(?:\s|\"|$).*"
| filter cmd_lc contains "\temp\" or cmd_lc contains "\downloads\" or cmd_lc contains "\programdata\" or cmd_lc contains "\appdata\"
| fields _time, agent_hostname, actor_effective_username, causality_actor_process_image_name, action_process_image_command_line
| dedup agent_hostname, action_process_image_command_line by asc _time
| sort desc _time
```
