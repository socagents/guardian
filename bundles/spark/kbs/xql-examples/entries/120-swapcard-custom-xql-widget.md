---
id: XQL-120-7f5b258f
title: '- Swapcard - Custom XQL Widget'
category: investigation
tags:
- bin
- comp
- filter
- sort
- view
ecosystem: xsiam
---
# - Swapcard - Custom XQL Widget

```sql
preset = metrics_view
| filter (`_product` = """swapcard""" and `_vendor` = """bh""")
| bin _time span = 1h
| comp sum(total_event_count) by _time
| sort asc _time
| view graph type = line xaxis = _time yaxis = sum_1 default_limit = `false` seriescolor("sum_1","#01ec45") gridcolor = "#d9f2db" legend = `false` xaxistitle = "Time" yaxistitle = "Count"
```
