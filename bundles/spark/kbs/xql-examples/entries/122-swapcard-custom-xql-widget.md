---
id: XQL-122-7f5b258f
title: '- Swapcard - Custom XQL Widget'
category: investigation
dataset: bh_swapcard_raw
tags:
- comp
- filter
- sort
- view
ecosystem: xsiam
---
# - Swapcard - Custom XQL Widget

**Dataset**: `bh_swapcard_raw`

```sql
dataset = bh_swapcard_raw | filter to_string(responseCode) ~= "\b[013456789]\d*\b" and responseCode != 0
| comp count() as counter by responseCode
| sort desc counter
| view graph type = pie subtype = full show_callouts = `true` show_callouts_names = `true` xaxis = responseCode yaxis = counter
```
