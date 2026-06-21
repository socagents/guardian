---
id: XQL-022-d6783fa2
title: 1000 eyes - uncleared alert
category: investigation
dataset: cisco_1000_raw
tags:
- alter
- comp
- filter
ecosystem: xsiam
---
# 1000 eyes - uncleared alert

**Dataset**: `cisco_1000_raw`

```sql
dataset = cisco_1000_raw
| filter alert_id != null
| comp min(_time) as _time ,count() as c , values(eventId)as event_ids , values(cleared_time) as cleared_time, values(devices_names) as devices_names, values(details) as details by alert_id, testId, signature, test_type, test_name , alert_type, triggered_time, itsiDrilldownURI, vendor_severity addrawdata = true
// | filter c = 1 and cleared_time = null
| alter vendor_severity = if(vendor_severity = "MINOR", "Low", if(vendor_severity = "CIRTICAL", "Critical", vendor_severity ))
| alter details = arraymerge(details )
| alter devices_names = arraymerge(devices_names)
```
