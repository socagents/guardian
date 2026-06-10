---
id: XQL-558-2e5c718c
title: Access To Crypto Currency Wallets By Uncommon Applications
category: investigation
dataset: xdr_data
tags:
  - filter
  - fields
  - xdr_data
  - source:dataset
  - operator-authored
  - Malware
---

# Access To Crypto Currency Wallets By Uncommon Applications

**Dataset**: `xdr_data`

```sql
dataset = xdr_data
| filter event_type = 3
| filter (action_file_path contains "\AppData\Roaming\Ethereum\keystore" OR  action_file_path contains "\AppData\Roaming\EthereumClassic\keystore" OR  action_file_path contains "\AppData\Roaming\monero\wallets") AND (action_file_path ~= ".*\\AppData\\Roaming\\Bitcoin\\wallet.dat" OR  action_file_path ~= ".*\\AppData\\Roaming\\BitcoinABC\\wallet.dat" OR  action_file_path ~= ".*\\AppData\\Roaming\\BitcoinSV\\wallet.dat" OR  action_file_path ~= ".*\\AppData\\Roaming\\DashCore\\wallet.dat" OR  action_file_path ~= ".*\\AppData\\Roaming\\DogeCoin\\wallet.dat" OR  action_file_path ~= ".*\\AppData\\Roaming\\Litecoin\\wallet.dat" OR  action_file_path ~= ".*\\AppData\\Roaming\\Ripple\\wallet.dat" OR  action_file_path ~= ".*\\AppData\\Roaming\\Zcash\\wallet.dat") and not (((actor_process_image_path IN ("System"))) OR ((actor_process_image_path ~= "C:\\Program Files (x86)\\.*" OR  actor_process_image_path ~= "C:\\Program Files\\.*" OR  actor_process_image_path ~= "C:\\Windows\\system32\\.*" OR  actor_process_image_path ~= "C:\\Windows\\SysWOW64\\.*"))) and not (((actor_process_image_path ~= "C:\\ProgramData\\Microsoft\\Windows Defender\\.*") AND (actor_process_image_path ~= ".*\\MpCopyAccelerator.exe" OR  actor_process_image_path ~= ".*\\MsMpEng.exe")))
| fields agent_hostname, event_type, event_sub_type, actor_process_image_path, actor_process_os_pid, actor_process_image_md5, actor_process_signature_vendor, actor_process_signature_status, actor_effective_username, action_file_path
```

## When to use

Detects file access requests to crypto currency files by uncommon processes.

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
