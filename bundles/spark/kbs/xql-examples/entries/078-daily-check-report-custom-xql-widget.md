---
id: XQL-078-e5ae180e
title: Daily Check Report - Custom XQL Widget
category: investigation
dataset: endpoints
tags:
- fields
- filter
ecosystem: xsiam
---
# Daily Check Report - Custom XQL Widget

**Dataset**: `endpoints`

```sql
dataset = endpoints
| filter operational_status != ENUM.PROTECTED or endpoint_status = ENUM.DISCONNECTED
| fields operational_status_description, endpoint_name, endpoint_status, operational_status, group_names, operating_system, agent_version, mac_address, os_version, ip_address, ipv6_address, user, last_seen, content_version, assigned_prevention_policy, assigned_extensions_policy
```
