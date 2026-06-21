---
id: XQL-IR-222-timestomp-file-modification
title: Timestomping — file creation time predating modification time (T1070.006)
category: threat-hunting
dataset: xdr_data
ecosystem: xsiam
tags: [filter, alter, fields, sort]
attack: [T1070.006]
---

# Timestomping — file creation time predating modification time (T1070.006)

**Dataset**: `xdr_data`

Hunts files in executable directories whose creation timestamp is implausibly older than their modification timestamp, a hallmark of timestomping to blend a dropped payload into the OS. Tune the `gap_days` threshold and scope `action_file_path` to system directories to cut down on legitimate archive-extraction noise.

```sql
dataset = xdr_data
| filter event_type = ENUM.FILE and event_sub_type in (ENUM.FILE_WRITE, ENUM.FILE_CREATE_NEW)
| filter action_file_path ~= ".*\\(Windows|System32|Program Files)\\.*"
| filter lowercase(action_file_extension) in ("exe", "dll", "sys")
| alter gap_days = timestamp_diff(action_file_modification_time, action_file_creation_time, "DAY")
| filter gap_days > 180
| fields _time, agent_hostname, actor_process_image_name, action_file_path, action_file_creation_time, action_file_modification_time, gap_days
| sort desc gap_days
```
