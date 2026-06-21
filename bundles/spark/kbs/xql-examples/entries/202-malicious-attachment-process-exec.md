---
id: XQL-IR-202-malicious-attachment-process-exec
title: Executable launched from mail attachment temp path (T1204.002)
category: threat-hunting
dataset: xdr_data
ecosystem: xsiam
tags: [filter, alter, fields, sort]
attack: [T1204.002]
---

# Executable launched from mail attachment temp path (T1204.002)

**Dataset**: `xdr_data`

Surfaces attachment detonation: a process whose image path sits in a mail-client attachment cache or the user temp tree, executed shortly after delivery. Adjust the path fragments to match your mail client's attachment-staging directories.

```sql
dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| alter image_path_lc = lowercase(actor_process_image_path)
| filter image_path_lc contains "\temp\" or image_path_lc contains "content.outlook" or image_path_lc contains "\inetcache\"
| filter image_path_lc ~= ".*\.(?:exe|scr|js|jse|vbs|hta)$"
| fields _time, agent_hostname, actor_effective_username, causality_actor_process_image_name, actor_process_image_path, actor_process_command_line
| sort desc _time
```
