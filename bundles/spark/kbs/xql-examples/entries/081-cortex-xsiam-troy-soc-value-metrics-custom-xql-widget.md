---
id: XQL-081-9fb16aaa
title: Cortex XSIAM Troy SOC Value Metrics - Custom XQL Widget
category: investigation
dataset: xsiam_playbookmetrics_raw
tags:
- alter
- arrayexpand
- comp
- dedup
- fields
- filter
- join
- view
ecosystem: xsiam
---
# Cortex XSIAM Troy SOC Value Metrics - Custom XQL Widget

**Dataset**: `xsiam_playbookmetrics_raw`

```sql
dataset = xsiam_playbookmetrics_raw
| alter Tasks = Tasks->[]
| arrayexpand Tasks
// TODO apply a datamodel to these two objects instead (Tasks and Alert)
| alter
taskState = tasks->state,
taskType = tasks->type,
taskId = tasks->id,
taskName = tasks->name,
scriptID = tasks->scriptId,
incidentID = alert->parentXDRIncident,
alertID = alert->id,
alertName = alert->name,
alertType = alert->type,
playbookId = alert->playbookId
| filter taskType not in ("start", "title", "condition")
| filter playbookId != ""
// Since the job which posts this data runs every 15 min there may be duplicate data the more frequent it is run
| alter dedupkey = concat(incidentID,taskId)
| dedup dedupkey
// Filter for just automation
//| filter alerttype != "Unclassified"
| filter taskState = "Completed"
| filter tasktype = "regular"
//TODO make this a lookup table and join instead to make it scalable
| join type = inner (dataset = value_tags
| fields Category as value_category, ScriptID as value_scriptid, `Tag` as value_tag, TaskName as value_taskname, Time as value_time, PlaybookID as playbook_id
) as vt (scriptID contains vt.value_scriptid)
| fields value_category, value_scriptid, value_tag, value_taskname, value_time, _time, playbook_id
| filter ((value_time != null and value_time != """"""))
| filter ((value_scriptid != null and value_scriptid != """"""))
| alter soc_event_mintutes = to_integer(value_time)
| comp sum(soc_event_mintutes) as total_soc_minutes
| alter total_soc_hours = round(divide(total_soc_minutes,60))
| view graph type = single subtype = standard header = "Hours Saved by XSIAM" yaxis = total_soc_hours dataunit = "Hours" headcolor = "#f1f7f0" font = "Arial" headerfontsize = 6
```
