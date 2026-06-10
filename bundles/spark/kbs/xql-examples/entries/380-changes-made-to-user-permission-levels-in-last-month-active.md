---
id: XQL-380-2de316ae
title: Changes Made to User Permission Levels in Last Month (Active Directory domain)
category: investigation
dataset: xdr_data
tags:
  - config
  - filter
  - alter
  - xdr_data
  - source:dataset
  - operator-authored
---

# Changes Made to User Permission Levels in Last Month (Active Directory domain)

**Dataset**: `xdr_data`

```sql
config timeframe = 30d | dataset = xdr_data
| filter event_type = EVENT_LOG
| filter action_evtlog_event_id = 4728
| alter editor_sid = action_evtlog_data_fields -> SubjectUserSid
| alter editor_username = action_evtlog_data_fields -> SubjectUserName
| alter editor_domain = action_evtlog_data_fields -> SubjectDomainName
| alter editor_logonid = action_evtlog_data_fields -> SubjectLogonId
| alter target_group = action_evtlog_data_fields -> TargetUserName
| alter target_domain = action_evtlog_data_fields -> TargetDomainName
| alter target_member = action_evtlog_data_fields -> MemberName
| filter target_member contains $username or editor_username contains $username
```

## When to use

Lists the user's permission level changes in Active Directory in the last month using event ID 4728. Note: When Active Directory objects, such as a user, group, computer, is added to a security global group, event ID 4728 gets logged. Changes in the user's security group will affect the user's permission levels.

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
