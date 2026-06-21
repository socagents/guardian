---
id: XQL-041-1f7ce6e8
title: Palo Alto Networks Threat Vault v2 Alerts (automatically generated)
category: alert-mapping
dataset: palo_alto_networks_threat_vault_v2_generic_alert_raw
tags:
- alter
- filter
ecosystem: xsiam
---
# Palo Alto Networks Threat Vault v2 Alerts (automatically generated)

**Dataset**: `palo_alto_networks_threat_vault_v2_generic_alert_raw`

```sql
dataset = palo_alto_networks_threat_vault_v2_generic_alert_raw
| filter _alert_data != null
| alter alert_severity = json_extract_scalar(_alert_data, "$.severity")
| alter alert_category = json_extract_scalar(_alert_data, "$.alert_category")
| alter alert_name = json_extract_scalar(_alert_data, "$.alert_name")
| alter alert_description = json_extract_scalar(_alert_data, "$.alert_description")
```
