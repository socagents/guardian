---
id: XQL-206-f7793146
title: All successful logins by a user
category: investigation
dataset: xdr_data
tags:
  - filter
  - alter
  - fields
  - xdr_data
  - source:dataset
  - operator-authored
---

# All successful logins by a user

**Dataset**: `xdr_data`

```sql
dataset = xdr_data // Using the xdr dataset
 | filter event_type = ENUM.EVENT_LOG and action_evtlog_event_id = 4624 // Filtering by windows event log and id 4624
 | alter Logon_Type = arrayindex(regextract(action_evtlog_message, "Logon Type:.*?(\d+)\r\n"),0), User_Name = arrayindex(regextract(action_evtlog_message,"New Logon:\r\n.*\r\n.*?Account Name:.*?(\w.*?)\r\n"),0), Domain = arrayindex(regextract(action_evtlog_message, "New Logon:\r\n.*\r\n.*\r\n.Account Domain:.*?(\w.*)\r\n"),0), Source_IP = arrayindex(regextract(action_evtlog_message, "Source Network Address:.*?(\d+\.\d+\.\d+\.\d+)\r\n"),0), Process_Name = arrayindex(regextract(action_evtlog_message, "Process Name:.*?(\w.*)\r\n"),0), Host_Name = arrayindex(regextract(action_evtlog_message, "Workstation Name:.*?(\w.*)\r\n"),0) // Using regextract to get just a part of the full event log message into an array, then using arrayindex to take the first item in the array and then making it a string
| filter lowercase(User_Name) contains lowercase($username) // using a parameter to allow a user to insert a value before execution
| fields User_Name, Host_Name, Domain, Logon_Type, Source_IP, Process_Name, action_evtlog_message as Raw_Message // Selecting the relevant fields
```

## When to use

Display all login events connected to a specific user

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
