---
id: XQL-125-7f5b258f
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
dataset = bh_swapcard_raw | fields serverName , responseCode  | comp count() as c by servername, responseCode  | sort desc c | limit 100   //filter  responseCode = 0
| view graph type = bubble subtype = grouppacked show_callouts = `true` show_callouts_names = `true` xaxis = responseCode yaxis = c series = servername default_limit = `false` headcolor = "#dedede" gridcolor = "#d9e4f2"
```
