---
id: XQL-152-0170f0b5
title: Troy Playbook Automation - Custom XQL Widget
category: investigation
dataset: xsiam_playbookmetrics_raw
tags:
- alter
- comp
- dedup
- filter
- join
- view
ecosystem: xsiam
---
# Troy Playbook Automation - Custom XQL Widget

**Dataset**: `xsiam_playbookmetrics_raw`

```sql
dataset = xsiam_playbookmetrics_raw
| alter
incidentID = alert->parentXDRIncident,
alertID = alert->id,
alertName = alert->name,
alertType = alert->type,
playbookId = alert->playbookId
| dedup alertID
| filter playbookId != ""
| join (dataset = playbook_mapping) as playbook_mapping playbook_mapping.PlaybookID = playbookId
| comp count(PlaybookName ) as PlaybookCount by PlaybookName
| view graph type = pie xaxis = PlaybookName yaxis = PlaybookCount
```
