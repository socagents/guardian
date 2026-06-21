---
id: XQL-020-8e5c8b3f
title: NUC Agent Update Script
category: investigation
dataset: endpoints
tags:
- alter
- fields
- filter
ecosystem: xsiam
---
# NUC Agent Update Script

**Dataset**: `endpoints`

```sql
dataset = endpoints
| filter group_names in ("NUCs") and last_upgrade_status = "COMPLETED_SUCCESSFULLY" and endpoint_status = ENUM.CONNECTED
| alter ct = current_time()
| alter diff_in_mins = timestamp_diff(ct, last_upgrade_status_time, "MINUTE")
| filter diff_in_mins < 59
| fields diff_in_mins, endpoint_status, endpoint_id, endpoint_name, group_names, agent_version, ip_address , mac_address, last_upgrade_status_time
```
