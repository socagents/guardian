---
id: XQL-IR-204-lolbin-mshta-rundll32-regsvr32
title: mshta / rundll32 / regsvr32 executing remote or script payloads (T1218)
category: threat-hunting
dataset: xdr_data
ecosystem: xsiam
tags: [filter, alter, comp, sort]
attack: [T1218.005, T1218.010, T1218.011]
---

# mshta / rundll32 / regsvr32 executing remote or script payloads (T1218)

**Dataset**: `xdr_data`

Hunts signed-binary proxy execution: the three classic LOLBins pulling a URL, invoking `javascript:`/`vbscript:`, or loading a DLL with `/s /u` from a non-standard path. Group by LOLBin to see which one dominates. Add an allowlist `filter` for known admin DLLs to cut noise.

```sql
dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| alter lolbin = lowercase(action_process_image_name)
| filter lolbin in ("mshta.exe", "rundll32.exe", "regsvr32.exe")
| alter cmd_lc = lowercase(action_process_image_command_line)
| filter cmd_lc contains "http" or cmd_lc contains "javascript:" or cmd_lc contains "vbscript:" or cmd_lc contains "scrobj" or cmd_lc contains "/i:" or cmd_lc contains ".hta"
| comp count(action_process_image_command_line) as hits, values(agent_hostname) as hosts by lolbin
| sort desc hits
```
