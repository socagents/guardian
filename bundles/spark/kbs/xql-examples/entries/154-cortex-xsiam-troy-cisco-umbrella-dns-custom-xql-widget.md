---
id: XQL-154-e9fc23f7
title: Cortex XSIAM Troy Cisco Umbrella DNS - Custom XQL Widget
category: investigation
dataset: cisco_umbrella_raw
tags:
- bin
- comp
- filter
- sort
- view
ecosystem: xsiam
---
# Cortex XSIAM Troy Cisco Umbrella DNS - Custom XQL Widget

**Dataset**: `cisco_umbrella_raw`

```sql
dataset = cisco_umbrella_raw
|filter action contains "blocked"
| bin _time span =1h
| sort asc  _time
| comp count(_collection_timestamp ) as counter by _time
| view graph type = line xaxis = _time yaxis = counter seriescolor("counter","#ec0101") legend = `false`
```
