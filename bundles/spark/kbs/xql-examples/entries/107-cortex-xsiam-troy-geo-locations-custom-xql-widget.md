---
id: XQL-107-1fef4d0f
title: Cortex XSIAM Troy Geo Locations - Custom XQL Widget
category: investigation
tags:
- comp
- filter
- iploc
- union
- view
ecosystem: xsiam
---
# Cortex XSIAM Troy Geo Locations - Custom XQL Widget

```sql
preset = network_story
| iploc action_remote_ip loc_country
| filter loc_country != null
| union (preset = network_story| iploc action_local_ip loc_country | filter loc_country != null)
| comp count(event_id) as counter by loc_country
| view graph type = map xaxis = loc_country yaxis = counter default_limit = `false` seriestitle("counter","Volume")
```
