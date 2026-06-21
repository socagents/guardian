---
id: XQL-150-0170f0b5
title: Troy Playbook Automation - Custom XQL Widget
category: investigation
dataset: xsiam_playbookmetrics_raw
tags:
- alter
- comp
- dedup
- view
ecosystem: xsiam
---
# Troy Playbook Automation - Custom XQL Widget

**Dataset**: `xsiam_playbookmetrics_raw`

```sql
dataset = xsiam_playbookmetrics_raw
| alter playbookId = alert->playbookId
| alter alertId = alert->id
| dedup alertId
| comp count(playbookId)
| view graph type = single subtype = standard header = "Playbook Runs" yaxis = count_1
```
