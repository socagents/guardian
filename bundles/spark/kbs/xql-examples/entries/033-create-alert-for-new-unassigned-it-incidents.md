---
id: XQL-033-7a41da60
title: Create alert for new/unassigned IT incidents
category: general
dataset: incidents
tags:
- filter
ecosystem: xsiam
---
# Create alert for new/unassigned IT incidents

**Dataset**: `incidents`

```sql
dataset = incidents
| filter incident_domain = "DOMAIN_IT"
| filter status = ENUM.NEW
```
