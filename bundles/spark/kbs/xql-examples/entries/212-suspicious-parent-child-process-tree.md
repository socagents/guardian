---
id: XQL-IR-212-suspicious-parent-child-process-tree
title: Suspicious parent-child process tree from a single root (T1059)
category: investigation
dataset: xdr_data
ecosystem: xsiam
tags: [filter, alter, comp, sort]
attack: [T1059, T1204.002]
---

# Suspicious parent-child process tree from a single root (T1059)

**Dataset**: `xdr_data`

Scopes an execution chain during an investigation: pivot from a known-bad causality root (the originating process) and roll up every distinct child image and command line it spawned on a host. Set `bad_root` to the process name from your alert, then read the breadth of children to size the blast radius.

```sql
dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| alter root = lowercase(causality_actor_process_image_name)
| alter child = lowercase(action_process_image_name)
| filter root = "winword.exe"
| comp count_distinct(child) as distinct_children, count(action_process_image_command_line) as total_spawns, values(child) as child_images by agent_hostname, root
| sort desc distinct_children
```
