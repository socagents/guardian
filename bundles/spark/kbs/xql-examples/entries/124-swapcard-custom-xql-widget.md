---
id: XQL-124-7f5b258f
title: '- Swapcard - Custom XQL Widget'
category: investigation
dataset: bh_swapcard_raw
tags:
- comp
- fields
- limit
- sort
- view
ecosystem: xsiam
---
# - Swapcard - Custom XQL Widget

**Dataset**: `bh_swapcard_raw`

```sql
dataset = bh_swapcard_raw  | comp count() as counter, avg(responseSize) as avgsize by remoteCountryCode | sort desc counter  | limit 20  //| fields - _*| view column order = populated
| view graph type = bubble subtype = standard xaxis = remoteCountryCode yaxis = counter series = avgsize bubblerad = avgsize default_limit = `false` seriescolor("counter","#01ec45")
```
