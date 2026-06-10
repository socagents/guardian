---
id: XQL-195-a8967016
title: Windows Failed Logins
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

# Windows Failed Logins

**Dataset**: `xdr_data`

```sql
dataset = xdr_data // Using the xdr dataset
 | filter event_type = ENUM.EVENT_LOG and action_evtlog_event_id = 4625 // Filtering by windows event log and id 4625
 | alter User_Name =arrayindex(regextract(action_evtlog_message, "Account For Which Logon Failed:\r\n.*\r\n.*Account Name:.*?(\w.*)\r\n"),0), Logon_Type = arrayindex(regextract(action_evtlog_message, "Logon Type:.*?(\d+)\r\n"),0), Failure_Reason = arrayindex(regextract(action_evtlog_message,"Failure Reason:.*?(\w.*)\r\n"),0), Domain = arrayindex(regextract(action_evtlog_message, "Account For Which Logon Failed:\r\n.*\r\n.*.*\r\n.*Account Domain:.*?(\w.*?)\r\n"),0), Source_IP = arrayindex(regextract(action_evtlog_message, "Source Network Address:.*?(\d+\.\d+\.\d+\.\d+)\r\n"),0), Caller_Process_Name = arrayindex(regextract(action_evtlog_message, "Caller Process Name:.*?(\w.*)\r\n"),0), Host_Name = arrayindex(regextract(action_evtlog_message, "Workstation Name:.*?(\w.*)\r\n"),0) // Using regextract to get just a part of the full event log message into an array, then using arrayindex to take the first item in the array
 | fields User_Name, Host_Name, Domain, Logon_Type, Failure_Reason, Source_IP, Caller_Process_Name // Select all the fields to show them
```

## When to use

Display parsed failed logins to Windows hosts, including the username, hostname, domain, source, process and login type

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
