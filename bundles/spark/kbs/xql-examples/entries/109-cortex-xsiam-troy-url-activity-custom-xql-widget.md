---
id: XQL-109-4c54581e
title: Cortex XSIAM Troy URL Activity - Custom XQL Widget
category: investigation
dataset: panw_ngfw_
tags:
- comp
- filter
- limit
- sort
- view
ecosystem: xsiam
---
# Cortex XSIAM Troy URL Activity - Custom XQL Widget

**Dataset**: `panw_ngfw_`

```sql
dataset = panw_ngfw_*
| filter risk_of_app != "Informational"
| comp count(_id) as counter by url_category
| filter url_category != "catch-all"
| filter url_category != "any"
| filter url_category != "private-ip-addresses"
| filter url_category != "panw*"
| sort  desc counter
| limit 20
| view graph type = wordcloud xaxis = url_category yaxis = counter word_color = "#5ae9d2"
```
