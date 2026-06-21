---
id: XQL-IR-217-clear-windows-event-logs
title: Windows event logs cleared via wevtutil/Clear-EventLog or Event ID 1102 (T1070.001)
category: investigation
dataset: xdr_data
ecosystem: xsiam
tags: [filter, alter, fields, sort]
attack: [T1070.001]
---

# Windows event logs cleared via wevtutil/Clear-EventLog or Event ID 1102 (T1070.001)

**Dataset**: `xdr_data`

Scopes anti-forensic log clearing two ways: the process side (`wevtutil cl`, `Clear-EventLog`, `wmic ... cleareventlog`) and the audit side (Security log clear emits Event ID 1102, System log emits 104). Use during incident scoping to bound when an actor began covering tracks on a host.

```sql
dataset = xdr_data
| filter (event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
          and lowercase(action_process_image_command_line) ~= ".*(wevtutil\s+cl|clear-eventlog|cleareventlog).*")
      or (event_type = ENUM.EVENT_LOG and action_evtlog_event_id in (1102, 104))
| alter source = if(event_type = ENUM.EVENT_LOG, "eventlog_1102_104", "process_command"),
        detail = coalesce(action_process_image_command_line, action_evtlog_message)
| fields _time, agent_hostname, actor_effective_username, source, action_evtlog_event_id, detail
| sort desc _time
```
