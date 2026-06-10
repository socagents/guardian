---
id: XQL-435-2d6bbd6f
title: Office 365 | Emails Associated with Alerts 
category: investigation
dataset: msft_graph_security_alerts_raw
tags:
  - filter
  - alter
  - join
  - msft_graph_security_alerts_raw
  - source:dataset
  - operator-authored
---

# Office 365 | Emails Associated with Alerts 

**Dataset**: `msft_graph_security_alerts_raw`

```sql
dataset = msft_graph_security_alerts_raw
| filter detectionSource = "microsoftDefenderForOffice365"
| alter analyzedMessageEvidence = arrayindex(arrayfilter(evidence ->[] , "@element" -> ["@odata.type"] = "#microsoft.graph.security.analyzedMessageEvidence"), 0)
| alter internetMessageId = analyzedMessageEvidence -> internetMessageId
| join (dataset = email_data ) as emails emails.internet_message_id contains internetMessageId
```

## When to use

Lists the mail events that triggered a Microsoft Defender for Office 365 alert.

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
