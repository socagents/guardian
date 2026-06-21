---
id: XQL-IR-227-kerberoasting-rc4-tgs-requests
title: Kerberoasting via RC4 TGS service-ticket requests (T1558.003)
category: threat-hunting
dataset: xdr_data
ecosystem: xsiam
tags: [filter, alter, comp, sort]
attack: [T1558.003]
---

# Kerberoasting via RC4 TGS service-ticket requests (T1558.003)

**Dataset**: `xdr_data`

Finds accounts requesting an unusually broad set of Kerberos service tickets (event 4769) with the weak RC4 encryption type (`0x17`), which attackers force to crack service-account hashes offline. Tune by excluding service accounts that legitimately fan out (e.g. SCCM) and raising `services_requested`.

```sql
dataset = xdr_data
| filter event_type = ENUM.STORY and action_evtlog_event_id = 4769
| alter ticket_enc = json_extract_scalar(action_evtlog_data_fields, "$.TicketEncryptionType"), requester = lowercase(action_username), spn = json_extract_scalar(action_evtlog_data_fields, "$.ServiceName")
| filter ticket_enc = "0x17"
| comp count() as tgs_requests, count_distinct(spn) as services_requested, values(spn) as service_spns by requester
| filter services_requested >= 3
| sort desc services_requested
```
