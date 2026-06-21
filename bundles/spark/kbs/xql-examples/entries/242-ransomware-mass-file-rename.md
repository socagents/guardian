---
id: XQL-IR-242-ransomware-mass-file-rename
title: Ransomware mass file rename to a single extension (T1486)
category: detection
dataset: xdr_data
ecosystem: xsiam
tags: [filter, alter, bin, comp, sort]
attack: [T1486]
---

# Ransomware mass file rename to a single extension (T1486)

**Dataset**: `xdr_data`

Detects the encryption burst: one process renaming many files to a uniform new extension within a short window. Binning by minute isolates the spike, and `count_distinct` on the target extension confirms convergence on a single ransom marker. Tune `rename_count` to your file-server churn and shrink the bin span for tighter bursts.

```sql
dataset = xdr_data
| filter event_type = ENUM.FILE and action_file_name != null and action_file_previous_file_name != null
| alter new_ext = lowercase(arrayindex(regextract(action_file_name, "\.([a-z0-9]+)$"), 0))
| alter old_ext = lowercase(arrayindex(regextract(action_file_previous_file_name, "\.([a-z0-9]+)$"), 0))
| filter new_ext != null and new_ext != old_ext
| alter t = _time
| bin t span = 1m
| comp count() as rename_count, count_distinct(new_ext) as distinct_new_ext, values(new_ext) as ransom_ext by agent_hostname, actor_process_image_name, t
| filter rename_count >= 50 and distinct_new_ext <= 2
| sort desc rename_count
```
