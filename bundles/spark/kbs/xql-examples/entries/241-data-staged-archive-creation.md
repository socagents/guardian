---
id: XQL-IR-241-data-staged-archive-creation
title: Data staged via archive utility execution (T1560.001)
category: threat-hunting
dataset: xdr_data
ecosystem: xsiam
tags: [filter, alter, comp, sort]
attack: [T1560.001]
---

# Data staged via archive utility execution (T1560.001)

**Dataset**: `xdr_data`

Hunts for command-line invocations of archive tools (7z, rar, tar, zip, makecab) with compression/password flags - the collection step before exfiltration. Aggregating distinct command lines per host highlights scripted bulk staging. Tune the regex to add bespoke packers, or pivot on `action_process_image_name` for living-off-the-land binaries.

```sql
dataset = xdr_data
| filter event_type = ENUM.PROCESS and action_process_image_command_line != null
| alter cmd = lowercase(action_process_image_command_line)
| alter archiver = arrayindex(regextract(cmd, "(7z|rar|winrar|7za|tar|makecab|zip)"), 0)
| filter archiver != null
| filter cmd contains "-p" or cmd contains "-hp" or cmd contains "a " or cmd contains "-czf"
| comp count() as exec_count, count_distinct(cmd) as distinct_cmds, values(actor_effective_username) as users by agent_hostname, archiver
| filter distinct_cmds >= 3
| sort desc distinct_cmds
```
