---
id: XQL-IR-203-encoded-obfuscated-powershell
title: Encoded or obfuscated PowerShell command line (T1059.001)
category: threat-hunting
dataset: xdr_data
ecosystem: xsiam
tags: [filter, alter, comp, sort]
attack: [T1059.001]
---

# Encoded or obfuscated PowerShell command line (T1059.001)

**Dataset**: `xdr_data`

Catches PowerShell invoked with `-EncodedCommand`, hidden windows, or download-cradle keywords -- classic obfuscation. The `comp` rollup ranks the noisiest hosts so you can triage spray vs. targeted use. Trim the keyword list if a legitimate management tool trips it.

```sql
dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| filter lowercase(action_process_image_name) in ("powershell.exe", "pwsh.exe")
| alter cmd_lc = lowercase(action_process_image_command_line)
| filter cmd_lc contains "-enc" or cmd_lc contains "-encodedcommand" or cmd_lc contains "frombase64string" or cmd_lc contains "-w hidden" or cmd_lc contains "downloadstring" or cmd_lc contains "iex("
| comp count(action_process_image_command_line) as exec_count, values(actor_effective_username) as users by agent_hostname
| sort desc exec_count
```
