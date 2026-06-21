---
id: XQL-IR-243-inhibit-recovery-vssadmin-delete
title: Inhibit recovery via shadow copy deletion (T1490)
category: detection
dataset: xdr_data
ecosystem: xsiam
tags: [filter, alter, comp, sort]
attack: [T1490]
---

# Inhibit recovery via shadow copy deletion (T1490)

**Dataset**: `xdr_data`

Catches the recovery-sabotage step that precedes ransomware detonation: vssadmin/wmic/wbadmin deleting Volume Shadow Copies or bcdedit disabling recovery. The command-line regex matches the canonical deletion phrasings. This is high-fidelity - any single hit warrants triage, so no volume threshold is applied.

```sql
dataset = xdr_data
| filter event_type = ENUM.PROCESS and action_process_image_command_line != null
| alter cmd = lowercase(action_process_image_command_line)
| filter cmd contains "delete shadows" or cmd contains "delete catalog" or cmd contains "shadowcopy delete" or cmd contains "recoveryenabled no" or cmd contains "deletecatalog"
| alter recovery_tool = arrayindex(regextract(cmd, "(vssadmin|wmic|wbadmin|bcdedit)"), 0)
| comp count() as exec_count, values(cmd) as command_lines, values(actor_effective_username) as users by agent_hostname, recovery_tool, actor_process_image_name
| sort desc exec_count
```
