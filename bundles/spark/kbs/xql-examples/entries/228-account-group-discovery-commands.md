---
id: XQL-IR-228-account-group-discovery-commands
title: Account and group discovery command execution (T1087)
category: threat-hunting
dataset: xdr_data
ecosystem: xsiam
tags: [filter, alter, comp, sort]
attack: [T1087]
---

# Account and group discovery command execution (T1087)

**Dataset**: `xdr_data`

Surfaces built-in reconnaissance commands (`net user`, `net group`, `whoami /all`, `dsquery`, `Get-ADUser`) used to enumerate accounts and privileged groups after a foothold. Tune by allow-listing admin jump hosts and clustering on hosts that run several distinct recon commands in one window.

```sql
dataset = xdr_data
| filter event_type = ENUM.PROCESS
| alter cmd = lowercase(action_process_image_command_line), host = agent_hostname, actor = actor_effective_username
| filter cmd contains "net user" or cmd contains "net group" or cmd contains "net localgroup" or cmd contains "whoami /all" or cmd contains "dsquery" or cmd contains "get-aduser" or cmd contains "get-adgroupmember"
| comp count() as recon_events, count_distinct(cmd) as distinct_commands, values(cmd) as commands by host, actor
| filter distinct_commands >= 2
| sort desc distinct_commands
```
