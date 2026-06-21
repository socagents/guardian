---
id: XQL-007-94cde9af
title: IoT Security - New Raspberry Device Found
category: investigation
dataset: panw_iot_security_devices_raw
tags:
- alter
- dedup
- filter
ecosystem: xsiam
---
# IoT Security - New Raspberry Device Found

**Dataset**: `panw_iot_security_devices_raw`

```sql
dataset = panw_iot_security_devices_raw
| filter profile contains "Raspberry Pi Device"
| alter duration_time = timestamp_diff(_insert_time,first_seen_date,"MINUTE")
| filter duration_time <= 30 and duration_time  >= 0
//| dedup mac_address
```
