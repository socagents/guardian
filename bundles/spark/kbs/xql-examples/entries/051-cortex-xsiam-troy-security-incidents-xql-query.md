---
id: XQL-051-a75720b7
title: Cortex XSIAM Troy Security Incidents - XQL Query
category: investigation
dataset: panw_ngfw_threat_raw
tags:
- comp
- fields
- filter
- limit
- sort
ecosystem: xsiam
---
# Cortex XSIAM Troy Security Incidents - XQL Query

**Dataset**: `panw_ngfw_threat_raw`

```sql
dataset = panw_ngfw_threat_raw
| filter app contains "dns" and threat_category contains "dns-malware" or threat_category contains "dns-phishing"
| filter threat_id != 93031
| fields threat_category, threat_name, url*, sub_type
| comp count(threat_name) as hits, values(threat_category) as dns_type by threat_name
| sort desc hits
| limit 10
```
