---
id: XQL-157-e9fc23f7
title: Cortex XSIAM Troy Cisco Umbrella DNS - Custom XQL Widget
category: investigation
dataset: cisco_umbrella_raw
tags:
- comp
- filter
- limit
- sort
- view
ecosystem: xsiam
---
# Cortex XSIAM Troy Cisco Umbrella DNS - Custom XQL Widget

**Dataset**: `cisco_umbrella_raw`

```sql
dataset = cisco_umbrella_raw
|filter action contains "blocked"
| comp count(catagories) as counter by catagories
|sort desc counter
|limit 5
| view graph type = pie xaxis = catagories yaxis = counter seriestitle("counter","Blocked DNS")
```
